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


import ieee_802_15_4_probe_common

[probes, devs, links] = ieee_802_15_4_probe_common.create_ieee_802_15_4_probe()

simics.SIM_run_command('log-level 1')
simics.SIM_run_command('%s.set-rssi %s 5' % (devs[0].name, devs[1].name))

simics.SIM_run_command('%s.tcpdump' % probes[0].name)

for i in range(5):
    devs[0].ep.iface.ieee_802_15_4_link.transmit("\nFrame %d" % i, 0, 0, 0)

simics.SIM_run_command('%s.tcpdump-stop' % probes[0].name)

for i in range(5, 10):
    devs[0].ep.iface.ieee_802_15_4_link.transmit("\nFrame %d" % i, 0, 0, 0)
