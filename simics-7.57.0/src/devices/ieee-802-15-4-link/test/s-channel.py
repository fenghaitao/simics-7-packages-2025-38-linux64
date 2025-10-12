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

[devs, eps, link] = common.create_test_bench()

simics.SIM_run_command('%s.set-rssi %s 5' % (devs[0].name, devs[1].name))

# set page and channel for Node 1
devs[1].channel_page = 1
devs[1].channel_num = 3

devs[1].received_frames_count = 0
# Send message from Node 0 to Node 1 by channel page 1 num 3 -- match
devs[0].ep.iface.ieee_802_15_4_link.transmit(b"abcd", 1, 3, 0)
simics.SIM_continue(5)
stest.expect_equal(devs[1].received_frames_count, 1,
                   "Node 1 should be reachable to Node 0.")

devs[1].received_frames_count = 0
# Send message from Node 0 to Node 1 by channel page 0 num 3 -- mismatch
devs[0].ep.iface.ieee_802_15_4_link.transmit(b"abcd", 0, 3, 0)
simics.SIM_continue(5)
stest.expect_equal(devs[1].received_frames_count, 0,
                   "Node 1 should not be reachable to Node 0.")

devs[1].received_frames_count = 0
# Send message from Node 0 to Node 1 by channel page 1 num 0 -- mismatch
devs[0].ep.iface.ieee_802_15_4_link.transmit(b"abcd", 1, 0, 0)
simics.SIM_continue(5)
stest.expect_equal(devs[1].received_frames_count, 0,
                   "Node 1 should not be reachable to Node 0.")
