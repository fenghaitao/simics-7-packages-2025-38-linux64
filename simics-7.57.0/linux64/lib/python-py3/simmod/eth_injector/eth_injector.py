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


import simics
import pyobj
import pcapfile

class eth_injector(pyobj.ConfObject):
    """Pseudo Ethernet device for packet injection based on pcap file
    input."""
    _class_desc = "pseudo eth device for packet injection"
    def _initialize(self):
        super()._initialize()
        self.packets = []
        self.connection = None
        self.ethernet_common_iface = None

    def _pre_delete(self):
        self.obj.connection = None
        super()._pre_delete()

    class pcapfile(pyobj.Attribute):
        "Pcap file to inject packets from."
        attrtype = "s|n"

        def _initialize(self):
            self.filename = None

        def setter(self, filename):
            if filename == None:
                return
            elif filename == self.filename:
                return

            try:
                self._up.packets = pcapfile.parse_pcap(filename)
            except pcapfile.PcapFileException as e:
                simics.SIM_attribute_error(str(e))
                return simics.Sim_Set_Illegal_Value
            simics.SIM_log_info(2, self._up.obj, 0, ("Read %d packets from %s."
                                              % (len(self._up.packets),
                                                 filename)))
            self.filename = filename

        def getter(self):
            return self.filename

    def stop_inject_packet(self):
        if self.obj.queue:
            simics.SIM_event_cancel_time(self.obj.queue,
                                  inject_packet_event,
                                  self.obj,
                                  lambda x, y: 1,
                                  None)

    class sent(pyobj.SimpleAttribute(0, type = 'i')):
        """Number of sent packets."""
        attrtype = "i"

    class auto_restart(pyobj.SimpleAttribute(False, type = 'b')):
        """True if injection will be automatically restarted when pcap is
        depleted."""
        attrtype = "b"

    class start(pyobj.Attribute):
        """Controls starting and stopping of pcap packet
        playback. When set to non zero, the packet playback will start
        from the beginning."""
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = "i"

        def _initialize(self):
            self.val = 0

        def getter(self):
            return self.val

        def setter(self, val):
            self.val = val
            self._up.stop_inject_packet()
            if val and len(self._up.packets):
                self._up.inject_packet()

    class connection(pyobj.Attribute):
        """The Ethernet link endpoint or Ethernet device that this
        injector is connected to."""
        attrtype = "o|n"

        def getter(self):
            return self._up.connection

        def setter(self, connection):
            o = self._up
            if connection == None:
                o.stop_inject_packet()
                o.connection = None
                o.ethernet_common_interface = None
                return

            try:
                o.ethernet_common_interface = connection.iface.ethernet_common
                o.connection = connection
            except simics.SimExc_Lookup:
                simics.SIM_attribute_error("%s does not implement ethernet_common"
                                    " interface" % connection.name)
                return simics.Sim_Set_Interface_Not_Found

    class append_crc(pyobj.SimpleAttribute(False, type = 'b')):
        """Assume that the CRC field of the Ethernet frame read from the pcap
        file is missing and append four zero bytes at the end of the frame
        before sending it. The simulation will handle the packet as if the
        CRC was correct"""
        pass

    class rate_multiplier(pyobj.SimpleAttribute(1.0, type = 'f')):
        """Modifies the rate/frequency that packets are injected by the
        float value defined. A value of 2.0 injects packets twice as fast,
        and a value of 0.5 injects packets at half the speed, relative to
        the timestamps in the source pcap file"""
        attrtype="f"

    class ethernet_common(pyobj.Interface):
        # No action for incoming frames
        def frame(self, frame, crc_status):
            pass

    def get_packet(self, i):
        if i < len(self.packets):
            return self.packets[i]
        return None

    def inject_packet(self):
        i = self.sent.val % len(self.packets)
        pkt = self.get_packet(i)
        pkt_time = pkt.get_time()
        if self.append_crc.val:
            simics.SIM_log_info(3, self.obj, 0,
                         "Appending crc to packet %d" % i)
            pkt.append_crc()

        crc_match = (simics.Eth_Frame_CRC_Match
                     if self.append_crc.val or pkt.correct_crc()
                     else simics.Eth_Frame_CRC_Mismatch)

        simics.SIM_log_info(2, self.obj, 0,
                     ("Sending packet %d with %scorrect crc."
                      % (i, ["in", ""][crc_match == simics.Eth_Frame_CRC_Match])))
        self.ethernet_common_interface.frame(pkt.data, crc_match)
        self.sent.val += 1

        next_pkt = self.get_packet(i + 1)
        if next_pkt == None:
            simics.SIM_hap_occurred_always(pcap_ended_hap, self.obj, 0, [
                    self.pcapfile.filename, self.sent.val,
                    len(self.packets), int(self.auto_restart.val)])
            if not self.auto_restart.val:
                simics.SIM_log_info(2, self.obj, 0, "No more packets to send.")
                return
            simics.SIM_log_info(2, self.obj, 0, "Auto-restarting package sending.")
            i = 0
            pkt_time = self.get_packet(i).get_time()
            next_pkt = self.get_packet(i + 1)

        next_pkt_time = next_pkt.get_time()
        pkt_time_diff = (next_pkt_time - pkt_time) / self.obj.rate_multiplier
        simics.SIM_log_info(4, self.obj, 0, "Posting sending of packet %d in %s." % (
            i + 1, pkt_time_diff))
        simics.SIM_event_post_time(self.obj.queue, inject_packet_event, self.obj,
                            pkt_time_diff, None)

    def _status(self):
        if self.packets:
            progress = '%d/%d' % (self.sent.val % len(self.packets),
                                  len(self.packets))
            in_progress = (self.obj.queue and
                           simics.SIM_event_find_next_cycle(
                               self.obj.queue, inject_packet_event,
                               self.obj, None, None) >= 0)
            if not in_progress:
                progress += ' (stopped)'
        else:
            progress = '-'
        return [(None,
                 [("Connection", self.connection and self.connection.name),
                  ("Pcap file", self.pcapfile.filename),
                  ("Append CRC", self.append_crc.val),
                  ("Progress", progress),
                  ("Total", self.sent.val),
                  ("Auto Restart", self.obj.auto_restart),
                  ("Rate Multiplier", self.obj.rate_multiplier)])]


def pcap_event_inject(obj, data):
    obj.object_data.inject_packet()

def pcap_event_describe(obj, data):
    return "inject frame %d" % (obj.sent % len(obj.object_data.packets))

inject_packet_event = simics.SIM_register_event("pcap inject", "eth_injector", 0,
                                         pcap_event_inject, None, None, None,
                                         pcap_event_describe)

pcap_ended_hap = simics.SIM_hap_add_type(
    "Eth_Injector_Pcap_Eof", "siii",
    "pcap_file num_injected pcap_num_pkgs auto_restart", None,
    "Triggered by the <class>eth_injector</class> object when all"
    " contents of the pcap file has been sent. The callback function will"
    " have the pcap file name, next packet index, total number of packets"
    " in the pcap file, and auto-restart as arguments.", 0)

import cli
def start_command():
    def command(obj, filename, no_crc, auto_restart, rate_multiplier):
        if obj.connection == None:
            raise cli.CliError("Nothing is connected to the link connector")
        obj.rate_multiplier = rate_multiplier
        if filename:
            obj.pcapfile = filename
            obj.append_crc = bool(no_crc)
            obj.sent = 0
            obj.auto_restart = auto_restart
        if obj.pcapfile:
            if obj.start == 0:
                simics.SIM_log_info(3, obj, 0, "Clear sent because was stopped.")
                obj.sent = 0
            obj.start = 1
        else:
            raise cli.CliError("Pcap file not specified")

    cli.new_command("start", command,
                [cli.arg(cli.filename_t(exist = True), "file", '?', None),
                 cli.arg(cli.flag_t, name = "-no-crc"),
                 cli.arg(cli.bool_t(), "auto-restart", "?", False),
                 cli.arg(cli.float_t, "rate-multiplier", "?", 1.0)],
                cls = "eth_injector",
                short = "start pcap playback",
                doc = """Start injecting packets from the pcap file
                      <arg>file</arg>. If packets in the pcap file has no
                      Ethernet CRC included use the <tt>-no-crc</tt> flag.
                      This will append a dummy CRC to the frame and the
                      simulation handle the packet as if the CRC is correct.
                      If the <tt>-no-crc</tt> was not given, the frame will
                      be injected without modification.

                      The rate of injection can also be modified with the
                      <arg>rate-multiplier</arg> argument.

                      If <arg>auto-restart</arg> is set to true, the injection
                      will be restarted when all packets in the pcap file
                      has been sent.

                      This command will start a new session as well as terminate
                      the running session, if exists. Without arguments, the
                      values of a previous session will be used, if there was
                      any. Otherwise, the new values will be used.""")

def stop_command():
    def command(obj):
        obj.start = 0

    cli.new_command("stop", command, [],
                cls = "eth_injector",
                short = "stop pcap playback",
                doc = """Stop injecting packets and terminate the current
                      playback session.""")

start_command()
stop_command()
