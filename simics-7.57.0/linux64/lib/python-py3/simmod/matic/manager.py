# © 2012 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import re
import random
import collections
import threading
import simics
import cli
from . import jobs
from . import buffer
from . import channel
from . import handle
from . import exceptions as ex
import sys
from simicsutils.internal import ensure_text

class AgentManager:
    """Agent Manager class"""
    v1_magic_rsv_min = 0x1b90f02e00000000
    v1_magic_rsv_max = 0x1b90f02e10d513ff
    v1_magic_nfo_min = 0x1b90f02e10d51400
    v1_magic_nfo_max = 0x1b90f02e10d514ff
    v1_magic_new_min = 0x1b90f02e10d51500
    v1_magic_new_max = 0x1b90f02effffffff
    v1_magic_new_mod = 0xef2aeb00

    def __init__(self, obj):
        self.obj = obj
        self.basename = {}
        self.ids = {}
        self.chan = collections.deque()  # channels in the order they connect
        self.chips = {}
        self.pipe = None
        self.debug = False
        self.enabled = None
        self.mg_part = []
        self.new_chn = {}
        self.waitlist = {}
        self.handle_count = 0
        self.lock = threading.Lock()
        self.job_hap_t = simics.SIM_hap_add_type(
            "Internal_Matic_Run_Until", "", "", "Job ID for an Agent Handle",
            "Matic Job Completion Hap", 0)

    def __del__(self):
        self.disable()
        simics.SIM_hap_remove_type(self.job_hap_t)

    def _new_v1_magic(self, cpu):
        with self.lock:
            cpus = len(simics.SIM_get_all_processors())
            cpun = simics.SIM_get_processor_number(cpu)
            mod = self.v1_magic_new_mod // cpus
            for p in range(len(self.mg_part), cpus):
                self.mg_part.append((p + 1) * 7919)
            while True:
                self.mg_part[cpun] += 29789
                base = self.v1_magic_new_min + cpun * mod
                magic = base + (self.mg_part[cpun] % mod)
                if magic not in self.ids:
                    return magic

    def _is_v1_magic(self, magic):
        if self.v1_magic_nfo_min <= magic <= self.v1_magic_new_max:
            return True
        return False

    def _find_machine(self, name):
        for chip in self.chips:
            if name in chip:
                return self.chips[chip][0]
        return None

    def _find_channel(self, name, chlist):
        for chn in chlist:
            if chn.id == name:
                return chn
        return None

    def _find_agent(self, name, chlist):
        for chn in chlist:
            if re.search(name, chn.name):
                return chn
        return None

    def _try_find(self, connect_to, channels=[]):
        chlist = channels if channels else self.chan
        if not chlist:
            return None
        if not connect_to:
            return chlist[0]
        chn = None
        if not chn:
            chn = self._find_channel(connect_to, chlist)
        if not chn:
            chn = self._find_agent(connect_to, chlist)
        if not chn:
            chn = self._find_machine(connect_to)
        return chn

    def _retry_connect(self, channels=[]):
        connlist = []
        with self.lock:
            for (hndl, connect) in list(self.waitlist.items()):
                chn = self._try_find(connect.to, channels)
                if chn:
                    del self.waitlist[hndl]
                    connlist.append((hndl, connect, chn))
        for (hndl, connect, chn) in connlist:
            chn.connect(hndl, connect)

    def open_pipe(self):
        cl = simics.SIM_get_class("magic_pipe")
        inst = list(simics.SIM_object_iterator_for_class(cl))
        if not inst:
            try:
                self.pipe = simics.SIM_create_object(
                    "magic_pipe", "magic_pipe", [])
            except simics.SimExc_General as e:
                raise ex.ManagerException(
                    "Could not start the required magic pipe: %s" % str(e))
        elif len(inst) == 1:
            self.pipe = inst[0]
        else:
            raise ex.ManagerException("Found more than one magic pipe")
        simics.SIM_log_info(3, self.obj, 0, "Connected to %s" % self.pipe.name)
        self.su = self.pipe.iface.magic_pipe_setup
        self.rd = self.pipe.iface.magic_pipe_reader
        self.wr = self.pipe.iface.magic_pipe_writer
        # Reserve the legacy magic number handshake range
        self.su.register_pipe_range(
            self.obj, self.v1_magic_rsv_min, self.v1_magic_rsv_max, None, None)
        self.su.register_pipe_range(
            self.obj, self.v1_magic_nfo_min, self.v1_magic_nfo_max,
            self.new_agent_read, self.new_agent_write)
        self.su.register_pipe_range(
            self.obj, self.v1_magic_new_min, self.v1_magic_new_max, None, None)
        self.su.register_reserved_pipe(
            self.obj, 0, self.lost_agent_read, self.lost_agent_write)

    def close_pipe(self):
        magic_list = [0,
                      self.v1_magic_rsv_min,
                      self.v1_magic_nfo_min,
                      self.v1_magic_new_min]
        for magic in magic_list:
            self.su.unregister_pipe(self.obj, magic)
        self.su = None
        self.rd = None
        self.wr = None
        self.pipe = None

    def enable(self):
        if not self.pipe:
            self.open_pipe()
        self.enabled = True

    def disable(self):
        self.enabled = False
        handles = []
        with self.lock:
            for chn in self.chan:
                handles += chn.get_handles()
        for hndl in handles:
            hndl.disconnect()
        if self.pipe:
            self.close_pipe()

    def get_info(self):
        rows = [("Matic Enabled", str(self.enabled))]
        if self.pipe:
            rows += [("Connected through", self.pipe.name)]
        return [(None, rows)]

    def get_status(self):
        rows = []
        if self.pipe:
            rows += [("Matic Haps", str(self.pipe.haps))]
        with self.lock:
            channels = list(self.chan)
            hndl_index = self.handle_count
            waiting = [(jq.name, cn.to) for (jq, cn) in list(self.waitlist.items())]
        hndl_count = sum([len(chn.get_handles()) for chn in channels])
        rows += [("Simics Agents", str(len(channels)))]
        rows += [(chn.id, chn.short_description()) for chn in channels]
        rows += [("Next Agent Index", "%d"  % hndl_index)]
        rows += [("Agent Handles", "%d"  % hndl_count)]
        rows += [(job_name, "Waiting to connect (%s)" % connect_to)
                 for (job_name, connect_to) in waiting]
        return [(None, rows)]

    def get_agent_list(self):
        with self.lock:
            return list(self.chan)

    # Serialize the array of dictionaries into an array of strings
    def get_agent_infos(self):
        with self.lock:
            infolist = [chn.get_info() for chn in self.chan]
        if not infolist:
            return [""]
        val = []
        for nfo in infolist:
            val.append("\n".join("%s=%s" % (k, v) for (k,v) in list(nfo.items())))
        return val

    # Split the array of strings into an array of dictionaries
    def _split_agent_info_string(self, agstr):
        nfo = {}
        for item in agstr.split('\n'):
            (k, v) = item.split('=', 1)
            nfo[ensure_text(k)] = v
        return nfo

    def set_agent_infos(self, val):
        if not simics.SIM_is_restoring_state(self.obj):
            return simics.Sim_Set_Not_Writable
        if not self.pipe:
            self.open_pipe()
        for agstr in val:
            if not agstr:
                continue
            nfo = self._split_agent_info_string(agstr)
            cpu = nfo.get('last_cpu', None)
            if cpu:
                cpu = simics.SIM_get_object(cpu)
            try:
                self._add_new_channel(self.pipe, cpu, nfo)
            except ex.ChannelException:
                return simics.Sim_Set_Illegal_Value
        return simics.Sim_Set_Ok

    def get_pipe(self):
        return self.pipe

    def new_handle_name(self):
        with self.lock:
            name = "matic%d" % self.handle_count
            self.handle_count += 1
        return name

    def connect_to_agent(self, hndl, connect):
        with self.lock:
            chn = self._try_find(connect.to)
            if chn:
                chn.connect(hndl, None)
                return True
            self.waitlist[hndl] = connect
            return False

    def stop_waiting_for_agent(self, hndl):
        with self.lock:
            self.waitlist.remove(hndl)

    def make_channel_id(self, name, magic):
        ndx = self.basename.get(name, 0)
        self.basename[name] = ndx + 1
        return ndx

    def _add_new_channel(self, pipe, cpu, nfo):
        chn = channel.MaticChannel(self, self.pipe, cpu, nfo, self.debug)
        with self.lock:
            # Store the agents by the order they appear in
            self.chan.append(chn)
            # Store the unique channel id by their magic number
            self.ids[chn.magic] = chn
            # Store the channel by the cpu they initially connected on
            chip = nfo['cpu']
            if chip in self.chips:
                self.chips[chip].append(chn)
            else:
                self.chips[chip] = [chn]
        return chn

    def discard_channel(self, chn):
        with self.lock:
            # Remove all knowledge of the channel from the manager
            nfo = chn.get_info()
            self.chips[nfo['cpu']].remove(chn)
            del self.ids[chn.magic]
            self.chan.remove(chn)

    def new_agent_read(self, cpu, bufh, magic):
        if not self._is_v1_magic(magic):
            return  # Only v1 is currently supported
        simics.SIM_log_info(4, self.obj, 0, "new_agent_read(%s, %s, %s)"
                            % (cpu.name, hex(bufh), hex(magic)))
        # Read and parse the greeting message
        buf = buffer.MaticBuffer(self.pipe, bufh)
        nfo = buf.parse_info()
        # Compile agent information and assign a magic
        nfo['cpu'] = cpu.name
        if self._is_v1_magic(magic):
            nfo['magic'] = hex(self._new_v1_magic(cpu))
        # Create a new channel for the agent
        try:
            chn = self._add_new_channel(self.pipe, cpu, nfo)
        except ex.ChannelException as e:
            simics.SIM_log_error(self.obj, 0, str(e))
            return
        with self.lock:
            self.new_chn[bufh] = (chn, buf)
        simics.SIM_log_info(2, self.obj, 0,
                            "Simics Agent %s connected (%s on %s)" % (
                                chn.id, nfo['magic'], nfo['cpu']))
        self._retry_connect([chn])
        chn.run_embedded_command()

    def new_agent_write(self, cpu, bufh, magic):
        simics.SIM_log_info(4, self.obj, 0, "new_agent_write(%s, %s, %s)"
                            % (cpu.name, hex(bufh), hex(magic)))
        # Pass the new channel magic back to the agent
        with self.lock:
            (chn, buf) = self.new_chn.pop(bufh)
        chn.first_request(cpu, buf)

    def lost_agent_read(self, cpu, bufh, magic):
        # Ignore the buffer data. It is not meant for us.
        simics.SIM_log_info(4, self.obj, 0, "lost_agent_read(%s, %s, %s)"
                            % (cpu.name, hex(bufh), hex(magic)))

    def lost_agent_write(self, cpu, bufh, magic):
        simics.SIM_log_info(4, self.obj, 0, "lost_agent_write(%s, %s, %s)"
                            % (cpu.name, hex(bufh), hex(magic)))
        try:
            buf = buffer.MaticBuffer(self.pipe, bufh)
        except ex.BufferException as e:
            simics.SIM_log_error(self.obj, 0, str(e))
            return
        simics.SIM_log_info(3, self.obj, 0, "Unrecognized magic (0x%016x) in: %s"
                            % (magic, buf))
        buf._reset_data()
        buf.reset_magic()
        buf.new_request(0, 0)
        buf._write_commit()
