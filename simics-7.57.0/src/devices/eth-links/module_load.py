# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import cli, math, simics, struct, os, signal, threading
import subprocess
import errno
import ipaddress
import simicsutils.host
from simmod.real_network.simics_start import register_ethernet_commands
from simmod.service_node.simics_start import (
    register_connect_real_network_napt_cmd,)

#
# info, status for link objects
#
def objport(op):
    try:
        obj, port = op
    except (TypeError, ValueError):
        obj, port = (op, None)
    return obj, port

def link_info_status(cls):
    def info(obj):
        return [(None,
                 [('Component', obj.component)]),
                (None,
                 [('Goal latency', cli.format_seconds(obj.goal_latency)),
                  ('Effective latency',
                   cli.format_seconds(obj.effective_latency))])]
    def status(obj):
        def fmt(op):
            # an endpoint's device cannot be nil while connected to a link
            assert op is not None
            obj, port = objport(op)
            cellname = getattr(simics.VT_object_cell(obj),
                               'name', 'no cell')
            if port == None:
                return (obj.name, cellname)
            else:
                return ('%s:%s' % (obj.name, port), cellname)
        return [(None,
                 [('Effective latency',
                   cli.format_seconds(obj.effective_latency))]),
                (None,
                 [('Connected devices',
                   sorted([fmt(ep.device) for ep in obj.endpoints]))])]
    cli.new_info_command(cls, info)
    cli.new_status_command(cls, status)

def ep_info_status(cls, snoop, vlan):
    def info(obj):
        def fmt(op):
            obj, port = objport(op)
            if port == None:
                return obj.name if obj else '<none>'
            else:
                return '%s:%s' % (obj.name, port)
        disp = [('Link', '%s (%s)' % (obj.link.name, obj.link.classname))]
        if snoop:
            disp.append(('Clock', obj.clock.name))
        else:
            disp.append(('Connected device', fmt(obj.device)))
        if vlan:
            vlan_id = "None" if obj.vlan_id is None else str(obj.vlan_id)
            disp.extend([('VLAN Identifier', '%s' % vlan_id),
                         ('VLAN trunk', 'Yes' if obj.vlan_trunk else 'No')])
        return [(None, disp)]
    cli.new_info_command(cls, info)
    cli.new_status_command(cls, lambda obj: [])

for t in ['hub', 'cable', 'switch']:
    link_info_status('eth-%s-link' % t)
    ep_info_status('eth-%s-link-endpoint' % t,
                   snoop = False, vlan = 'switch' in t)
for t in ['eth', 'eth-switch']:
    ep_info_status('%s-link-snoop-endpoint' % t,
                   snoop = True, vlan = 'switch' in t)


#
# Ethernet link components
#

from component_utils import get_component
from pyobj import SimpleAttribute
import link_components


def create_hub_endpoint(link, dev):
    return link_components.create_generic_endpoint('eth-hub-link-endpoint',
                                                   link, dev)

class ethernet_hub(
    link_components.create_simple(link_class = 'eth-hub-link',
                                  endpoint_class = 'eth-hub-link-endpoint',
                                  connector_type = 'ethernet-link',
                                  class_desc =
                                  'an Ethernet hub component',
                                  basename = 'ethernet_hub',
                                  help_categories = ['Networking'])):
    """Ethernet hub: this component represents a simple broadcasting Ethernet
    link allowing any number of devices to connect."""

    def get_free_connector_cmd(self):
        c = self.get_unconnected_connector_object('device')
        if not c:
            raise cli.CliError('Internal error: no connectors found')
        return c.name

def create_vlan_switch_endpoint(link, dev, vlan_id, vlan_trunk):
    ep_obj = link_components.create_generic_endpoint('eth-switch-link-endpoint',
                                                     link, dev)
    ep_obj.vlan_id = vlan_id
    ep_obj.vlan_trunk = vlan_trunk
    return ep_obj

# <add id="ets_comp"><insert-upto text="self.eth_tmpl)"/></add>
class ethernet_switch(link_components.link_component):
    """Ethernet switch: this component represents a switched Ethernet network,
    allowing any number of devices to connect and optimizing the packet routing
    according to what is learned about the MAC addresses talking on the link."""

    _class_desc = 'an Ethernet switch component'
    _help_categories = ['Networking']

    class basename(link_components.link_component.basename):
        val = 'ethernet_switch'

    def create_unconnected_endpoint(self, cnt):
        return create_vlan_switch_endpoint(self.get_slot('link'), None,
                                           None, True)

    def register_connector_templates(self):
        self.eth_tmpl = self.add_link_connector_template(
            name = 'ethernet-link-connector',
            type = 'ethernet-link',
            growing = True,
            create_unconnected_endpoint = self.create_unconnected_endpoint)

    def add_objects(self):
        self.add_pre_obj_with_name('link', 'eth-switch-link',
                                   self.get_link_object_name(),
                                   goal_latency = self.goal_latency.val,
                                   global_id = self.global_id.val)
        self.add_link_connector('device', self.eth_tmpl)

    def get_free_connector_cmd(self):
        c = self.get_unconnected_connector_object('device')
        if not c:
            raise cli.CliError('Internal error: no connectors found')
        return c.name


def create_cable_endpoint(link, dev):
    return link_components.create_generic_endpoint('eth-cable-link-endpoint',
                                                   link, dev)

# <add id="etc_comp"><insert-upto text="self.eth_tmpl)"/></add>
class ethernet_cable(link_components.link_component):
    """Ethernet cable: this component represents a two-points Ethernet cable,
    allowing two devices to connect to each other."""

    _class_desc = 'an Ethernet cable component'
    _help_categories = ['Networking']

    class basename(link_components.link_component.basename):
        val = 'ethernet_cable'

    class connector_count(SimpleAttribute(0, 'i')):
        """Total number of occupied connectors"""

    def allow_new_connector(self):
        if self.connector_count.val == 2:
            # all connectors are occupied
            return False
        elif self.connector_count.val == 1:
            # there is already one free connector
            self.connector_count.val += 1
            return False
        else:
            self.connector_count.val += 1
            return True

    def allow_destroy_connector(self):
        if self.connector_count.val == 2:
            # two connectors occupied, so let one become free
            self.connector_count.val -= 1
            return False
        else:
            # one connector was occupied, one free, so destroy one
            self.connector_count.val -= 1
            return True

    def create_unconnected_endpoint(self, cnt):
        return create_cable_endpoint(self.get_slot('link'), None)

    def register_connector_templates(self):
        self.eth_tmpl = self.add_link_connector_template(
            name = 'single-ethernet-link-connector',
            type = 'ethernet-link',
            growing = True,
            create_unconnected_endpoint = self.create_unconnected_endpoint,
            allow_new_cnt = self.allow_new_connector,
            allow_destroy_cnt = self.allow_destroy_connector)

    def add_objects(self):
        self.add_pre_obj_with_name('link', 'eth-cable-link',
                                   self.get_link_object_name(),
                                   goal_latency = self.goal_latency.val,
                                   global_id = self.global_id.val)
        self.add_link_connector('device', self.eth_tmpl)

    def get_free_connector_cmd(self):
        c = self.get_unconnected_connector_object('device')
        if not c:
            raise cli.CliError('The ethernet cable %s has no free connectors'
                               % self.obj.name)
        return c.name


class ethernet_vlan_switch(link_components.link_component):
    """Ethernet VLAN switch: this component represents a switched Ethernet
    network with VLAN support. Any number of devices is allowed to connect to
    various ports of the switch. Each port can be configured with its own VLAN
    information, in order to create sub-networks in the switch."""

    _class_desc = 'an Ethernet VLAN switch component'
    _help_categories = ['Networking']

    class basename(link_components.link_component.basename):
        val = 'ethernet_vlan_switch'

    def create_unconnected_endpoint(self, cnt):
        # use connector name to gather vlan info. Not the cutest way of doing
        # it, but the easiest right now
        cnt_s = cnt.component_slot.split("_")
        if len(cnt_s) == 2:
            # trunk with no native VLAN ID (e.g. "trunk_dev0")
            vlan_id = None
            trunk = True
        else:
            vlan_id = int(cnt_s[1])
            trunk = (len(cnt_s) != 3)
        return create_vlan_switch_endpoint(self.get_slot('link'), None,
                                           vlan_id, trunk)

    def register_connector_templates(self):
        self.eth_tmpl = self.add_link_connector_template(
            name = 'ethernet-link-connector',
            type = 'ethernet-link',
            growing = True,
            create_unconnected_endpoint = self.create_unconnected_endpoint)

    def add_objects(self):
        self.add_pre_obj_with_name('link', 'eth-switch-link',
                                   self.get_link_object_name(),
                                   goal_latency = self.goal_latency.val,
                                   global_id = self.global_id.val)
        self.add_link_connector('trunk_dev', self.eth_tmpl)

    def get_slot_template(self, vlan_id):
        return ("vlan_%d" % vlan_id) + "_dev%d"

    def get_trunk_slot_template(self, vlan_id):
        if vlan_id is None:
            return "trunk_dev%d"
        else:
            return ("vlan_%d_trunk" % vlan_id) + "_dev%d"

    def add_vlan_connector_cmd(self, vlan_id):
        slot_name = self.get_slot_template(vlan_id)
        slot_name_trunk = self.get_trunk_slot_template(vlan_id)
        if self.get_unconnected_connector_object(slot_name):
            raise cli.CliError("VLAN %d is already defined" % vlan_id)
        self.add_link_connector(slot_name, self.eth_tmpl)
        self.add_link_connector(slot_name_trunk, self.eth_tmpl)

    def do_get_free_connector(self, slot_name, vlan_id):
        c = self.get_unconnected_connector_object(slot_name)
        if not c:
            raise cli.CliError('VLAN id %d has not been created' % vlan_id)
        return c.name

    def get_free_connector_cmd(self, vlan_id):
        return self.do_get_free_connector(
            self.get_slot_template(vlan_id), vlan_id)

    def get_free_trunk_connector_cmd(self, vlan_id):
        return self.do_get_free_connector(
            self.get_trunk_slot_template(vlan_id), vlan_id)

cli.new_command('add-vlan',
                lambda x, y : get_component(x).add_vlan_connector_cmd(y),
                [cli.arg(cli.uint16_t, 'vlan_id')],
                cls = 'ethernet_vlan_switch',
                type = ["Networking"],
                short = 'add a VLAN definition and corresponding connectors',
                doc = """
Add a VLAN definition with <arg>vlan_id</arg> and corresponding connectors.
""")


get_free_connector_doc = """
This command returns the name of a connector which is not
connected to anything."""

for cls in ('ethernet_cable', 'ethernet_switch', 'ethernet_hub'):
    cli.new_command('get-free-connector',
                    lambda x : get_component(x).get_free_connector_cmd(),
                    [],
                    cls = cls,
                    type = ["Networking", "Links"],
                    short = 'return the name of an unused connector',
                    doc = get_free_connector_doc)

cli.new_command('get-free-connector',
                lambda x, y : get_component(x).get_free_connector_cmd(y),
                [cli.arg(cli.uint16_t, 'vlan_id')],
                cls = 'ethernet_vlan_switch',
                type = ["Networking", "Links"],
                short = 'return the name of an unused access connector',
                doc = """
Returns the name of an access connector on a specific VLAN, <arg>vlan_id</arg>
that is not connected to anything.""")

cli.new_command('get-free-trunk-connector',
                lambda x, y : get_component(x).get_free_trunk_connector_cmd(y),
                [cli.arg(cli.uint16_t, 'vlan_id', '?')],
                cls = 'ethernet_vlan_switch',
                type = ["Networking", "Links"],
                short = 'return the name of an unused trunk connector',
                doc = """
Returns the name of a trunk connector that is not connected to anything. The
new trunk connector can have a native VLAN id if <arg>vlan_id</arg> is
provided. In this case, untagged packets passing through this port will all be
assumed to belong to its native VLAN. An ordinary trunk port is created if
<arg>vlan_id</arg> is not specified, in which case untagged packets will not
be tagged to any VLAN and will be dropped to all but other ordinary trunk
ports.""")

from real_ethernet_network import new_ethernet_link_cmps

def set_goal_latency(link, latency):
    link.goal_latency = latency

for cls in new_ethernet_link_cmps:
    cli.new_command('set-goal-latency', set_goal_latency,
                    [cli.arg(cli.float_t, 'latency')],
                    cls = cls,
                    type = ["Networking", "Links"],
                    short = "set the link's goal latency in seconds",
                    see_also = ["set-min-latency"],
                    doc = """
Set the desired communication <arg>latency</arg> of this link in seconds.""")

#
# Packet capture commands
#

# return all new ethernet link components found
def all_new_ethernet_links():
    return [o for o in simics.SIM_object_iterator(None)
            if o.classname in new_ethernet_link_cmps and o.instantiated]

# return the first path of binary found in $PATH
def fullpath(binary):
    binary_paths = [x for x in
                    [os.path.join(y, binary)
                     for y in os.environ['PATH'].split(':')]
                    if os.path.exists(x)]
    return binary_paths[0] if binary_paths else None

def kill_process(pid):
    if simicsutils.host.is_windows():
        import win32api, win32con
        try:
            h = win32api.OpenProcess(win32con.PROCESS_TERMINATE, 0, pid)
            if h != None:
                win32api.TerminateProcess(h, 1)
                win32api.CloseHandle(h)
        except win32api.error:
            # The process probably no longer exists - no complaints.
            pass
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            # The process probably no longer exists - no complaints.
            pass

class Pcap:
    def __init__(self, fileobj, ns_resolution = False):
        self.__file = fileobj
        self.lock = threading.Lock()
        self.ns_resolution = ns_resolution
        self.__write_header(ns_resolution)
    def __write_header(self, ns_resolution):
        if ns_resolution:
            magic = 0xa1b23c4d
        else:
            magic = 0xa1b2c3d4
        major = 2
        minor = 4
        thiszone = 0
        sigfigs = 0
        snaplen = 2048
        linktype = 1
        self.__file.write(struct.pack('IHHIIII', magic, major, minor, thiszone,
                                      sigfigs, snaplen, linktype))
    def write_frame(self, clock, frame):
        with self.lock:
            fsec, isec = math.modf(simics.SIM_time(clock))
            self.__file.write(struct.pack('IIII', int(isec),
                                          int(1e9*fsec) if self.ns_resolution \
                                          else int(1e6*fsec), len(frame),
                                          len(frame)))
            self.__file.write(frame)
    def close(self):
        with self.lock:
            self.__file.close()

ongoing_pcap_dumps = {}

def is_eth_probe(obj):
    return obj.classname == 'eth-probe'

# stop capture for link
def stop_capture(link_or_probe):
    try:
        ep, pcap, pid = ongoing_pcap_dumps[link_or_probe]
    except KeyError:
        # No pcap dump in progress for this link
        return
    del ongoing_pcap_dumps[link_or_probe]
    print("Stopping capture on %s" % link_or_probe)

    # find out if pcap and pid are still used for other links
    destroy_pcap = True
    kill_pid = True
    for k in ongoing_pcap_dumps:
        o_ep, o_pcap, o_pid = ongoing_pcap_dumps[k]
        if o_pcap == pcap:
            destroy_pcap = False
        if o_pid == pid:
            kill_pid = False

    if pid and kill_pid:
        kill_process(pid)
    if ep:
        simics.SIM_delete_object(ep)
    else:
        link_or_probe.iface.ethernet_probe.detach()

    # close all capture files
    if destroy_pcap:
        try:
            pcap.close()
        except OSError:
            # if this was a pipe, it was probably already broken
            pass

# register an exit callback to stop all on-going captures
def stop_capture_callback(ignore1 = None, ignore2 = None):
    for l in list(ongoing_pcap_dumps.keys()):
        stop_capture(l)

simics.SIM_hap_add_callback("Core_At_Exit", stop_capture_callback, None)

def start_capture(pcap, link_or_probe, pid = None):
    print("Starting capture on %s" % link_or_probe)
    def write_frame(clock, frame):
        try:
            pcap.write_frame(clock, frame)
        except OSError as e:
            print(f"Failed writing frame: {e.strerror} (error code {e.errno})")
            # If the write fails, just close the capture to avoid further
            # errors. stop_capture needs to run in Global Context.
            simics.SIM_run_alone(lambda d: stop_capture(link_or_probe), None)
    if not is_eth_probe(link_or_probe):
        def callback(user_data, clock, frame, crc_status):
            write_frame(clock, frame)
        ep = link_or_probe.link.iface.ethernet_snoop.attach(None, callback,
                                                            None)
    else:
        def callback(clock, to_side, probe, frame, crc_status):
            write_frame(clock, frame)
        link_or_probe.iface.ethernet_probe.attach_snooper(
            callback, link_or_probe.probe_ports[0].partner.queue)
        ep = None
    ongoing_pcap_dumps[link_or_probe] = (ep, pcap, pid)

def pcap_dump_start(links_or_probes, filename, ns_resolution):
    for l in links_or_probes:
        stop_capture(l)
    try:
        pcap = Pcap(open(filename, 'wb', 0), ns_resolution)
    except Exception as ex:
        raise cli.CliError("Failed starting pcap: %s" % ex)
    for l in links_or_probes:
        start_capture(pcap, l, None)

def check_obj_instantiated(obj):
    if hasattr(obj.iface, 'component') and not obj.instantiated:
        raise cli.CliError("object '%s' is not instantiated" % obj)

def pcap_dump_cmd(obj, filename, ns_resolution):
    check_obj_instantiated(obj)
    pcap_dump_start([obj], filename, ns_resolution)

def zero_or_one_set(args):
    return len([a for a in args if a]) <= 1

def global_pcap_dump_cmd(link, probe, filename, ns_resolution):
    if not zero_or_one_set([link, probe]):
        raise cli.CliError("Capture should be enabled either a link"
                           " or a probe")
    if link and link.classname in new_ethernet_link_cmps:
        check_obj_instantiated(link)
        pcap_dump_start([link], filename, ns_resolution)
    elif probe:
        pcap_dump_start([probe], filename, ns_resolution)
    else:
        new_links = all_new_ethernet_links()
        if new_links:
            pcap_dump_start(new_links, filename, ns_resolution)
        else:
            raise cli.CliError("No Ethernet links can be found for the capture")

def capture_stop_cmd(obj):
    stop_capture(obj)

def global_capture_stop_cmd(link, probe):
    if not zero_or_one_set([link, probe]):
        raise cli.CliError('Specify a link or a probe to stop capture for')
    if link:
        stop_capture(link)
    elif probe:
        stop_capture(probe)
    else:
        stop_capture_callback()

def external_capture(links_or_probes, read_fd, write_fd, dup_read, execl_args):
    pid = os.fork()
    if pid == 0:
        os.close(write_fd)
        os.setsid()
        if dup_read:
            os.dup2(read_fd, 0)
            os.close(read_fd)
        os.execl(*execl_args)
        os._exit(1)
    os.close(read_fd)
    pcap = Pcap(os.fdopen(write_fd, 'wb', 0))
    for l in links_or_probes:
        start_capture(pcap, l, pid)

def tcpdump_start(links_or_probes, flags):
    for l in links_or_probes:
        stop_capture(l)
    xterm_path = fullpath("xterm")
    if not xterm_path:
        raise cli.CliError("No 'xterm' binary found in PATH")
    tcpdump_path = fullpath("tcpdump")
    if not tcpdump_path:
        raise cli.CliError("No 'tcpdump' binary found in PATH.")
    (read_fd, write_fd) = os.pipe()
    os.set_inheritable(read_fd, True)
    external_capture(links_or_probes, read_fd, write_fd, False,
                     [xterm_path, "xterm", "-title", "tcpdump", "-e",
                      "/bin/bash",
                      "-c", tcpdump_path + " -r - %s <&%d" % (flags, read_fd)])

def tcpdump_cmd(obj, flags):
    check_obj_instantiated(obj)
    tcpdump_start([obj], flags)

def global_tcpdump_cmd(link, probe, flags):
    if not zero_or_one_set([link, probe]):
        raise cli.CliError("Capture should be enabled on either a link"
                           " or a probe")
    if link and link.classname in new_ethernet_link_cmps:
        check_obj_instantiated(link)
        tcpdump_start([link], flags)
    elif probe:
        tcpdump_start([probe], flags)
    else:
        new_links = all_new_ethernet_links()
        if new_links:
            tcpdump_start(new_links, flags)
        else:
            raise cli.CliError("No Ethernet links can be found for the capture")

# like subprocess.Popen, but returns None if the program wasn't found
def try_start_program(args, **kwords):
    try:
        return subprocess.Popen(args, **kwords)
    except OSError as e:
        # Python translates windows errors from CreateProcess to Posix
        # error codes in e.errno.
        if e.errno == errno.ENOENT:
            return None
        else:
            raise cli.CliError('%s: %s' % (e.__class__.__name__, str(e)))

def ethereal_start(links, flags):
    for l in links:
        stop_capture(l)

    def preexec():
        if 'setsid' in dir(os):
            os.setsid()

    win = simicsutils.host.is_windows()
    for prog in ["wireshark", "ethereal"]:
        if win:
            # We don't have a good stdout/stderr when running in GUI mode
            # on Windows; use a null file to keep subprocess from crashing
            # (bug 18837).
            out = subprocess.DEVNULL
            err = subprocess.STDOUT
        else:
            out = err = None
        if cli.conf.prefs.wireshark_path:
            prog = os.path.join(cli.conf.prefs.wireshark_path, prog)

        args = ['-k', '-i', '-']
        if prog == "wireshark":
            win_title = ', '.join(l.name for l in links)
            args += ['-o', 'gui.window_title:%s' % win_title]

        p = try_start_program([prog] + args + flags.split(), bufsize=0,
                              stdin=subprocess.PIPE, stdout=out, stderr=err,
                              close_fds=not win,
                              preexec_fn=preexec if not win else None)
        if p:
            break

    if not p:
        raise cli.CliError("Neither 'wireshark' nor 'ethereal' could be"
                           " started. Set the prefs->wireshark_path to"
                           " specify the directory where the wireshark"
                           " binaries are install or include that directory"
                           " in the PATH environment variable.")
    pcap = Pcap(p.stdin)
    for l in links:
        start_capture(pcap, l, p.pid)

def ethereal_cmd(obj, flags):
    check_obj_instantiated(obj)
    ethereal_start([obj], flags)

def global_ethereal_cmd(link, probe, flags):
    if not zero_or_one_set([link, probe]):
        raise cli.CliError("Capture should be enabled on either a link"
                           " or a probe")
    if link and link.classname in new_ethernet_link_cmps:
        check_obj_instantiated(link)
        ethereal_start([link], flags)
    elif probe:
        ethereal_start([probe], flags)
    else:
        new_links = all_new_ethernet_links()
        if new_links:
            ethereal_start(all_new_ethernet_links(), flags)
        else:
            raise cli.CliError("No Ethernet links can be found for the capture")

def register_pcap_class_commands(cls):
    cli.new_command('pcap-dump', pcap_dump_cmd,
                    [cli.arg(cli.filename_t(), 'file'),
                     cli.arg(cli.flag_t, '-ns'),],
                    cls = cls,
                    type = ["Networking"],
                    short = 'dump Ethernet traffic to a pcap file',
                    doc = """
Dump all network traffic on the Ethernet link to the file <arg>file</arg> in
pcap format. The optional <tt>-ns</tt> flag sets the timestamp resolution of
the file in nano-seconds. The default timestamp resolution is in
micro-seconds.""")

    cli.new_command('pcap-dump-stop', capture_stop_cmd,
                    [],
                    cls = cls,
                    type = ["Networking"],
                    short = "stop the current dump",
                    doc = """Stop dumping network traffic to the file.""")

    if not simicsutils.host.is_windows():
        cli.new_command("tcpdump", tcpdump_cmd,
                        [cli.arg(cli.str_t, "flags", "?", "-n -v")],
                        cls = cls,
                        type  = ["Networking"],
                        short = "run the tcpdump program",
                        doc = """
Runs the <tt>tcpdump</tt> program in a separate console, with network traffic
captured from the simulated Ethernet network. The <arg>flags</arg> are passed
unmodified to <tt>tcpdump</tt>.""")
        cli.new_command('tcpdump-stop', capture_stop_cmd,
                        [],
                        cls = cls,
                        type = ["Networking"],
                        short = "stop the current tcpdump capture",
                        doc_with = '<%s>.tcpdump' % cls)

    cli.new_command("wireshark", ethereal_cmd,
                    [cli.arg(cli.str_t, "flags", "?", "-S -l")],
                    cls = cls,
                    type  = ["Networking"],
                    short = "run the wireshark/ethereal program",
                    alias = ["ethereal"],
                    doc = """
Runs the <tt>wireshark</tt> or <tt>ethereal</tt> program in a separate
console, with network traffic captured from the simulated Ethernet network.
The <arg>flags</arg> are passed unmodified to program. The path to the
wireshark binary can be specified in the prefs->wireshark_path setting.""")

    cli.new_command('wireshark-stop', capture_stop_cmd,
                    [],
                    cls = cls,
                    type = ["Networking"],
                    short = "stop the current wireshark capture",
                    alias = ['ethereal-stop'],
                    doc_with = '<%s>.wireshark' % cls)

for cls in new_ethernet_link_cmps:
    register_pcap_class_commands(cls)

from real_ethernet_network import new_ethernet_link_cmps, ethlink_t

cli.new_command('pcap-dump', global_pcap_dump_cmd,
                [cli.arg(ethlink_t, 'link', '?'),
                 cli.arg(cli.obj_t('ethernet probe', 'eth-probe'),
                         'probe', '?'),
                 cli.arg(cli.filename_t(), 'filename'),
                 cli.arg(cli.flag_t, "-ns"),],
                type = ["Networking"],
                alias = ['pcapdump'],
                short = 'dump Ethernet traffic to file',
                doc = """
Dump all Ethernet network traffic on the given <arg>link</arg> or
<arg>probe</arg> to the given <arg>filename</arg> in pcap format.
The optional <tt>-ns</tt> flag sets the timestamp resolution of the file in
nano-seconds. The default timestamp resolution is in micro-seconds.""")

cli.new_command('pcap-dump-stop', global_capture_stop_cmd,
                [cli.arg(ethlink_t, 'link', '?'),
                 cli.arg(cli.obj_t('Ethernet probe', 'eth-probe'),
                         'probe', '?')],
                type = ["Networking"],
                short = "stop the current dump",
                alias = ['pcapdump-stop'],
                doc = """
Stop dumping network traffic on the given <arg>link</arg> or <arg>probe</arg>
to file.""")

cli.new_command("wireshark", global_ethereal_cmd,
                [cli.arg(ethlink_t, 'link', '?'),
                 cli.arg(cli.obj_t('Ethernet probe', 'eth-probe'),
                         'probe', '?'),
                 cli.arg(cli.str_t, "flags", "?", "-S -l")],
                type  = ["Networking"],
                short = "run the wireshark/ethereal program",
                alias = ['ethereal'],
                doc = """
Runs the <tt>wireshark</tt> or <tt>ethereal</tt> program in a separate
console, with network traffic captured from the simulated Ethernet network.
The <arg>flags</arg> are passed on unmodified to program. The path to the
wireshark binary can be specified in the prefs->wireshark_path setting.

The <arg>link</arg> or <arg>probe</arg> to capture for.""")

cli.new_command('wireshark-stop', global_capture_stop_cmd,
                [cli.arg(ethlink_t, 'link', '?'),
                 cli.arg(cli.obj_t('Ethernet probe', 'eth-probe'),
                         'probe', '?')],
                type = ["Networking"],
                short = "stop the current wireshark capture",
                alias = ['ethereal-stop'],
                doc = """
The <arg>link</arg> or <arg>probe</arg> to stop capture for.""")

if not simicsutils.host.is_windows():
    cli.new_command("tcpdump", global_tcpdump_cmd,
                    [cli.arg(ethlink_t, 'link', '?'),
                     cli.arg(cli.obj_t('Ethernet probe', 'eth-probe'),
                             'probe', '?'),
                     cli.arg(cli.str_t, "flags", "?", "-n -v")],
                    type  = ["Networking"],
                    short = "run the tcpdump program",
                    doc = """
Runs the <tt>tcpdump</tt> program in a separate console, with network traffic
captured from the simulated Ethernet network. The <arg>flags</arg> are passed
unmodified to <tt>tcpdump</tt>.

The <arg>link</arg> or <arg>probe</arg> to stop capture for.""")

    cli.new_command('tcpdump-stop', global_capture_stop_cmd,
                    [cli.arg(ethlink_t, 'link', '?'),
                     cli.arg(cli.obj_t('Ethernet probe', 'eth-probe'),
                             'probe', '?')],
                    type = ["Networking"],
                    short = "stop the current tcpdump capture",
                    doc = """
The <arg>link</arg> or <arg>probe</arg> to stop capture for.""")

class eth_link_details:
    def __init__(self, link):
        self.src_mac_dict = None
        self.snoop = None
        self.link = link
        self.src_mac_dict = dict()

    def process_ethernet_frame(self, user_data, clock, frame, crc_status):
        src_mac = ':'.join(f"{i:02x}" for i in frame[6:12])
        dst_mac = ':'.join(f"{i:02x}" for i in frame[:6])
        iptype  =  ''.join(f"{i:02x}" for i in frame[12:14])
        ip = ""
        if iptype == '0800':
            ip = ipaddress.IPv4Address(frame[26:30])

        if iptype == '86dd':
            ip = ipaddress.IPv6Address(frame[22:38])

        if not src_mac in self.src_mac_dict:
            self.src_mac_dict[src_mac] = dict()
            self.src_mac_dict[src_mac][(dst_mac, ip)] = 1
        else:
            try:
                if (dst_mac, ip) in self.src_mac_dict[src_mac]:
                    self.src_mac_dict[src_mac][(dst_mac, ip)] += 1
                else:
                    self.src_mac_dict[src_mac][(dst_mac, ip)] = 1
            except KeyError:
                s = dict()
                s[src_mac] = dict()
                s[src_mac][(dst_mac, ip)] = 1
                self.src_mac_dict.update(s)
                return

    def start_snoop(self):
        self.snoop = self.link.link.iface.ethernet_snoop.attach(
            None, self.process_ethernet_frame, None)

    def stop_snoop(self):
        simics.SIM_delete_object(self.snoop)

    def result(self):
        print(f"Link {self.link.name}:")
        if self.src_mac_dict:
            for src, data in self.src_mac_dict.items():
                for to,ip in data.keys():
                    print(f"{src} ({ip}) sent {data[(to,ip)]} packets to {to}")
        else:
            print("No packet registered")
        print("")

ed_dict = dict()

def link_stop_monitor_cmd(link):
    if not ed_dict:
        raise cli.CliError(f"Ethernet link {link.name} is not being monitored")
    ed_dict[link.name].stop_snoop()
    ed_dict.pop(link.name)

def link_start_monitor_cmd(link):
    if not link:
        raise cli.CliError("No Ethernet link is provided")
    if link.name in ed_dict:
        raise cli.CliError(f"Ethernet link {link.name} is already monitored")
    ed_dict[link.name] = eth_link_details(link)
    ed_dict[link.name].start_snoop()

def link_view_monitored_cmd(link):
    if not ed_dict:
        raise cli.CliError("No Ethernet links monitored")
    for links in ed_dict.values():
        links.result()
    print("")

for cls in ('ethernet_cable', 'ethernet_switch', 'ethernet_hub'):
    cli.new_command("start-link-monitor", link_start_monitor_cmd,
                    cls = cls,
                    type = 'network commands',
                    short ="start background monitoring of an Ethernet link",
                    doc = """
                    Monitoring the Ethernet link and capture packets
                    sent from source MAC address and IP(s) to destination
                    MAC address""")

    cli.new_command("view-link-monitor", link_view_monitored_cmd,
                    cls = cls,
                    type = 'network commands',
                    short ="view status of the monitored Ethernet link",
                    doc = """
                    View the captured data of the monitored Ethernet link.""")

    cli.new_command("stop-link-monitor", link_stop_monitor_cmd,
                    cls = cls,
                    type = 'network commands',
                    short ="stop Ethernet link monitoring",
                    doc = """
                    Stop and remove monitoring of Ethernet link.""")

for classname in new_ethernet_link_cmps:
    # It is not possible to connect the VLAN switch to the real network. There
    # is no support for sending and receiving VLAN tagged packets. A possible
    # improvement would be to allow one of the VLANs to be connected, but then
    # VLAN specific connect-real-network- command is needed.
    if not 'vlan' in classname:
        register_ethernet_commands(classname)
        see_also = ['<%s>.connect-real-network-host' % classname,
                    '<%s>.connect-real-network-bridge' % classname]
    else:
        see_also = []
    register_connect_real_network_napt_cmd(
        classname, see_also)
