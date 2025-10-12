# © 2014 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import cli
import simics, simicsutils.host
from . import traffic_dump

class_name = 'ieee_802_15_4_probe'

linktype_doc = """
<arg>linktype</arg> is a link-layer header type code. The typical values are:

1 - Ethernet\n
191 - IEEE 802.15.4, with address fields padded, as is done by Linux
drivers\n
195 - IEEE 802.15.4, exactly as it appears in the spec. FCS is expected
to be present.\n
215 - IEEE 802.15.4, exactly as it appears in the spec, but with the
PHY-level data for non-ASK PHYs (default)\n
230 - IEEE 802.15.4, exactly as it appears in the spec, and with no
FCS at the end of the frame

The default value is 1.
"""

#
# ------------------------ info -----------------------
#

def get_info(obj):
    return [("Connection", [("endpoint", obj.ep),
                            ("device", obj.device)])]

cli.new_info_command(class_name, get_info)

#
# ------------------------ status -----------------------
#

def get_status(obj):
    return [("Probe",
              [("Dynamic Info", "N/A")
              ])]

cli.new_status_command(class_name, get_status)

#
# ------------------------ insert-ieee-802-15-4-probe -----------------------
#

def insert_ieee_802_15_4_probe(device, name):
    if name == None:
        name = device.name + "_probe"

    probe = simics.SIM_create_object('ieee_802_15_4_probe', name,
                                     [["ep", device.ep],
                                      ["device", device],
                                      ["queue", device.queue]])
    device.ep = probe
    if probe.ep:
        probe.ep.device = probe

    return probe

cli.new_command('insert-ieee-802-15-4-probe', insert_ieee_802_15_4_probe,
            args=[cli.arg(cli.obj_t('receiver', 'ieee_802_15_4_receiver'), 'device'),
                  cli.arg(cli.str_t, 'name', '?', None)],
            type = ["Probes"],
            short='insert IEEE 802.15.4 probe',
            doc="""
            Insert IEEE 802.15.4 probe to listen to traffic on the given
            <arg>device</arg>, an ieee_802_15_4_receiver.

            The probe may be given a <arg>name</arg>.""")

#
# ------------------------ traffic dump -----------------------
#
cli.new_command('pcap-dump', traffic_dump.pcap_dump_cmd,
            [cli.arg(cli.filename_t(), 'file'),
             cli.arg(cli.int_t, 'linktype', '?', 215),
             cli.arg(cli.flag_t, '-ns'),],
             cls=class_name,
             type = ["Networking"],
             short='dump network traffic to a file',
             doc="""
                 Dump network traffic to a <arg>file</arg>, in libpcap format.
The optional <tt>-ns</tt> flag sets the timestamp resolution of the file in
nano-seconds. The default timestamp resolution is in micro-seconds."""
            + linktype_doc)

cli.new_command('pcap-dump-stop', traffic_dump.capture_stop_cmd,
            [],
            cls=class_name,
            type = ["Networking"],
            short="stop the current dump",
            doc="""Stop the current dump.""")

if not simicsutils.host.is_windows():
    cli.new_command("tcpdump", traffic_dump.tcpdump_cmd,
                [cli.arg(cli.str_t, "flags", "?", "-n -v"),
                 cli.arg(cli.int_t, 'linktype', '?', 215)],
                 cls=class_name,
                 type = ["Networking"],
                 short="run the tcpdump program",
                 doc="""
                     Runs the <b>tcpdump</b> program in a separate console,
                     with network traffic captured from the simulated
                     Ethernet network. The <arg>flags</arg> are passed on
                     unmodified to <b>tcpdump</b>.
                     """ + linktype_doc)
    cli.new_command('tcpdump-stop', traffic_dump.capture_stop_cmd,
                [],
                cls=class_name,
                type = ["Networking"],
                short="stop the current tcpdump capture",
                doc="""Stop the current tcpdump capture.""")

cli.new_command("wireshark", traffic_dump.ethereal_cmd,
            [cli.arg(cli.str_t, "flags", "?", "-S -l"),
             cli.arg(cli.int_t, 'linktype', '?', 215)],
             cls=class_name,
             type = ["Networking"],
             short="run the wireshark/ethereal program",
             alias=["ethereal"],
             doc="""
                   Runs the <b>wireshark</b> or <b>ethereal</b> program in
                   a separate console, with network traffic captured from
                   the simulated Ethernet network. The <arg>flags</arg> are
                   passed on unmodified to program. The path to the
                   wireshark binaries can be specified in the
                   prefs->wireshark_path setting.
                   """ + linktype_doc)

cli.new_command('wireshark-stop', traffic_dump.capture_stop_cmd,
                [],
                cls = class_name,
                type = ["Networking"],
                short = "stop the current wireshark capture",
                alias = ['ethereal-stop'],
                doc = """Stop the current wireshark capture.""")
