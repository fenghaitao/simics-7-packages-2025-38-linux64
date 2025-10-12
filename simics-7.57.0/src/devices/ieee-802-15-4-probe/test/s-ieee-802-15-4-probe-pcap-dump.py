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


import stest
import ieee_802_15_4_probe_common
import os

file_name = 'pcap_dump'
[probes, devs, links] = ieee_802_15_4_probe_common.create_ieee_802_15_4_probe()

simics.SIM_run_command('log-level 1')
simics.SIM_run_command('%s.set-rssi %s 5' % (devs[0].name, devs[1].name))

if os.path.exists(file_name):
    os.remove(file_name)

simics.SIM_run_command('%s.pcap-dump %s' % (probes[0].name, file_name))

for i in range(5):
    devs[0].ep.iface.ieee_802_15_4_link.transmit(b"\nFrame %d" % i, 0, 0, 0)

simics.SIM_run_command('%s.pcap-dump-stop' % probes[0].name)

for i in range(5, 10):
    devs[0].ep.iface.ieee_802_15_4_link.transmit(b"\nFrame %d" % i, 0, 0, 0)

dump_file = open(file_name, "rb")
line_count = len(dump_file.readlines())
dump_file.close()
stest.expect_equal(line_count, 6,
                   "There should be exactly 6 lines in the dump file")
