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


from cli import (
    arg,
    int_t,
    new_command,
    new_info_command,
    new_status_command,
    )
from simics import *
import nic_common

def get_info(obj):
    return ([("IP configuration",
              [("IP address", obj.ip),
               ("Netmask", obj.netmask),
               ("Target", obj.dst_ip),
               ("Gateway", obj.gateway)]),
             ("Traffic parameters",
              [("Rate", "%d pps" % obj.pps),
               ("Size", "%d bytes" % obj.packet_size)])] +
            nic_common.get_nic_info(obj))

def get_status(obj):
    left = obj.count
    if left is None:
        left = "unlimited"
    return ([ (None,
               [ ("Enabled", "yes" if obj.enabled else "no"),
                 ("Packets left to send", left),
                 ("Packets sent", obj.total_tx_packets),
                 ("Packets received", obj.total_rx_packets),
                 ("CRC errors", obj.crc_errors)])] +
            nic_common.get_nic_status(obj))

new_info_command("etg", get_info)
new_status_command("etg", get_status)

def start(obj, count):
    if count:
        obj.count = count
    if not obj.enabled:
        print("Starting", obj.name)
        obj.enabled = 1

new_command("start", start,
            [arg(int_t, "count", "?")],
            type = ["Networking"],
            short = "start generating traffic",
            cls = "etg",
            doc = """
Start the traffic generator. Limit amount of packets with <arg>count</arg>.
""")

def stop(obj):
    if obj.enabled:
        print("Stopping", obj.name)
        obj.enabled = 0

new_command("stop", stop,
            [],
            type = ["Networking"],
            short = "stop generating traffic",
            cls = "etg",
            doc = """
Stop the traffic generator.
""")

def packet_rate(obj, pps):
    if pps is None:
        print("Packet rate is %d packets/second" % obj.pps)
    else:
        obj.pps = pps

new_command("packet-rate", packet_rate,
            [arg(int_t, "rate", "?")],
            type = ["Networking"],
            short = "set or display the packets per second rate",
            cls = "etg",
            doc = """
Set the <arg>rate</arg>, in packets per second, at which packets are sent by
the traffic generator.

If no rate is given, the current rate is displayed.
""")

def packet_size(obj, size):
    if size is None:
        print("Packet size is %d bytes" % obj.packet_size)
    else:
        obj.packet_size = size

new_command("packet-size", packet_size,
            [arg(int_t, "size", "?")],
            type = ["Networking"],
            short = "set or display the packet size",
            cls = "etg",
            doc = """
Set the <arg>size</arg> of the packets that are sent by the traffic generator.

If no size is given, the current size is displayed.
""")

def bandwidth_limit(obj, limit):
    if limit is None:
        print(f"Bandwidth limit is {obj.bandwidth_limit}")
    else:
        if limit <= 0:
            raise cli.CliError("Limit has to be a positive number and not zero")
        obj.bandwidth_limit = limit

new_command("set-bandwidth-limit", bandwidth_limit,
            [arg(int_t, "bandwidth_limit", "?")],
            type = ["Networking"],
            short = "set or display the bandwidth limit in bits per second",
            cls = "etg",
            doc = """
Set the <arg>bandwidth_limit</arg> of the packets that are sent by the traffic
generator. This is an optional setting as the default is 1Gbit/s.

If no limit is given, the current limit is displayed.
""")
