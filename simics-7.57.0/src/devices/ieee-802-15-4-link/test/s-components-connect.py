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
import stest
import common
import cli

simics.SIM_run_command("log-level 1")
cli.global_cmds.set_min_latency(count=1, unit="ms")

[devs, ] = common.create_test_bench_by_components()

simics.SIM_run_command('%s.set-rssi %s 5' % (devs[0].name, devs[1].name))

for dev in devs:
    stest.expect_equal(dev.received_frames_count, 0)

# Send message from Node 0 to Node 1
devs[0].ep.iface.ieee_802_15_4_link.transmit(b"abcd", 0, 0, 0)
simics.SIM_run_command("run-seconds 1")
stest.expect_equal(devs[1].received_frames_count, 1,
                   "Node 1 should be reachable to Node 0.")

# Send message from Node 1 to Node 0
devs[1].ep.iface.ieee_802_15_4_link.transmit(b"abcd", 0, 0, 0)
simics.SIM_run_command("run-seconds 1")
stest.expect_equal(devs[0].received_frames_count, 0,
                   "Node 0 should be unreachable to Node 1.")
