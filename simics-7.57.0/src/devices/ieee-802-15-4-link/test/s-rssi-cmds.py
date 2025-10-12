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


import simics
import dev_util
import stest
import common

simics.SIM_run_command("log-level 1")

[devs, eps, link] = common.create_test_bench(dev_num=10)

for (set_rssi, rm_rssi) in (("set-rssi", "rm-rssi"), ("sr", "rr")):
    # set-rssi
    for i in range(1, len(devs)):
        simics.SIM_run_command('%s.%s %s 5'
                               % (devs[0].name, set_rssi, devs[i].name))
    stest.expect_equal(len(devs[0].ep.rssi_table), len(devs) - 1)

    # rm-rssi
    simics.SIM_run_command('%s.%s %s' % (devs[0].name, rm_rssi, devs[1].name))
    stest.expect_equal(len(devs[0].ep.rssi_table), len(devs) - 2)

    # rm-rssi -all
    simics.SIM_run_command('%s.%s -all' % (devs[0].name, rm_rssi))
    stest.expect_equal(len(devs[0].ep.rssi_table), 0)

# set-rssi
for i in range(1, len(devs)):
    simics.SIM_run_command('%s.set-rssi %s 5' % (devs[0].name, devs[i].name))
stest.expect_equal(len(devs[0].ep.rssi_table), len(devs) - 1)

# rm-rssi node_name -all
simics.SIM_run_command('%s.rm-rssi %s -all' % (devs[0].name, devs[1].name))
stest.expect_equal(len(devs[0].ep.rssi_table), 0)
