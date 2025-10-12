# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import conf
import simics
import cli
import re
import ipaddress
import itertools
import binascii

break_doc = """
Set Simics to break simulation when <arg>src_mac</arg>, <arg>dst_mac</arg> or
<arg>eth_type</arg> is discovered in the network stream by the link.
"""
trace_doc = """
Enable tracing of appearances of the <arg>src_mac</arg>, <arg>dst_mac</arg> or
<arg>eth_type</arg> is discovered in the network stream by the link.
"""
run_until_doc = """
Run Simulation until specified src <arg>src_mac</arg>, <arg>dst_mac</arg> or
<arg>eth_type</arg> is discovered in the network stream by the link.
"""

wait_for_doc = """
Postspones execution of a script branch until specified <arg>src_mac</arg>,
<arg>dst_mac</arg> or <arg>eth_type</arg> is discovered in the network stream
by the link.
"""

class Breakpoint:
    __slots__ = ('link', 'link_id', 'src_mac', 'dst_mac', 'eth_type', 'once', 'msg')
    def __init__(self, link, link_id, src_mac, dst_mac, eth_type, once):
        self.link     = link
        self.link_id  = link_id
        self.src_mac  = src_mac
        self.dst_mac  = dst_mac
        self.eth_type = eth_type
        self.once     = once
        self.msg      = ""

    def format_break_string(self):
        src = ""
        dst = ""
        eth_type = ""
        if self.src_mac:
            src = f"src_mac = {self.src_mac}"
        if self.dst_mac:
            dst = f"dst_mac = {self.dst_mac}"
        if self.eth_type:
            eth_type = f"ether_type = {str(self.eth_type)}"

        return f"{src} {dst} {eth_type}"


class EthStrBreakpoints:
    TYPE_DESC = "target network packet breakpoints"
    cls = simics.confclass("bp-manager.eth_link",
                           doc=TYPE_DESC, pseudo=True)

    def __init__(self):
        self.bp_data = {}
        self.next_id = 1
        self.mac_pattern = re.compile("[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}")

    @cls.objects_finalized
    def objects_finalized(self):
        object_required = True
        name = 'network'
        trigger_desc = "Found src mac in network stream at the provided link"
        cli_args = [["str_t", "src_mac", '?', None, None, "", None],
                    ["str_t", "dst_mac", '?', None, None, "", None],
                    ["uint_t", "eth_type", '?', 0, None, "", None]]
        conf.bp.iface.breakpoint_type.register_type(
             name, self.obj,
            cli_args,
            None, 'network_breakpoint', [
                'break on ' + trigger_desc, break_doc,
                'trace ' + trigger_desc, trace_doc,
                'run_until', run_until_doc,
                'wait_for', wait_for_doc],
            object_required, False, False)

    def _delete_bp(self, _, bm_id):
        self.remove_bp(conf.bp.iface.breakpoint_type.get_break_id(bm_id))

    def _describe_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"Eth '{bp.link.name}' break on {bp.format_break_string()}"

    def _get_props(self, _, bm_id):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        bp = self.bp_data[bp_id]
        return {"temporary": bp.once,
                "planted": True,
                "object": bp.link.name,
                "description": self._describe_bp(bp_id)}

    def _create_bp(self, link, src_mac, dst_mac, eth_type, once, cb):
        bp_id = self.next_id
        self.next_id += 1
        s_mac = b""
        d_mac = b""
        if src_mac:
            s_mac = binascii.unhexlify(src_mac.replace(':', ''))
        if dst_mac:
            d_mac = binascii.unhexlify(dst_mac.replace(':', ''))

        link_id = link.iface.network_breakpoint.add(s_mac, d_mac, eth_type, cb, once, bp_id)
        if link_id > 0:
            self.bp_data[bp_id] = Breakpoint(link, link_id, src_mac, dst_mac, eth_type,  once)
            return bp_id
        self.next_id -= 1
        return 0

    def _parse_frame(self, frame):
        ip = ''
        src_mac = ':'.join(f"{i:02x}" for i in frame[6:12])
        dst_mac = ':'.join(f"{i:02x}" for i in frame[:6])
        eth_type = ''.join(f"{i:02x}" for i in frame[12:14])
        if eth_type == '0800':
            ip = ipaddress.IPv4Address(frame[26:30])
        if eth_type == '86dd':
            ip = ipaddress.IPv6Address(frame[22:38])

        return (src_mac, dst_mac, eth_type, ip)

    def _bp_cb(self, link, data, size, bp_id):
        (src, dst, etype, ip) = self._parse_frame(data)
        msg = f"src = {src}, dst = {dst}, ether_type = {etype}, ip = {ip}"
        conf.bp.iface.breakpoint_type.trigger(self.obj, bp_id, link,
                                              msg)
        return 1

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bpm_iface = conf.bp.iface.breakpoint_registration
        return bpm_iface.register_breakpoint(
            self._delete_bp, None, self._get_props, None, None, None,
            None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, _, args):
        (link, src_mac, dst_mac, eth_type, once) = args
        #Validate given params
        if src_mac and not self.mac_pattern.findall(src_mac):
            src_mac = None
        if dst_mac and not self.mac_pattern.findall(dst_mac):
            dst_mac = None

        if src_mac  or dst_mac or eth_type:
            return self._create_bp(link, src_mac, dst_mac, eth_type, once, self._bp_cb)

        return 0

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        if isinstance(bp.link, simics.conf_object_t):
            bp.link.iface.network_breakpoint.remove(bp.link_id)
        del self.bp_data[bp_id]

    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"matched {bp.format_break_string()}"

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"{bp.link.name} will break on {bp.format_break_string()}"

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"{bp.link.name} waiting on {bp.format_break_string()}"

def register_network_breakpoints(bpm_class):
    simics.SIM_register_port(bpm_class, "network",
                             EthStrBreakpoints.cls.classname,
                             EthStrBreakpoints.TYPE_DESC)
