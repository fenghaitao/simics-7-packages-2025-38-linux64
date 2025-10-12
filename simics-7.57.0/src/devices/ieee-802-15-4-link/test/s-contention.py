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

# set-rssi
simics.SIM_run_command('%s.set-rssi %s %d' % (devs[0].name, devs[1].name, 50))
stest.expect_equal(len(devs[0].ep.rssi_table), len(devs) - 1)

# transmit
for contention_ratio in range(0, 100 + 1, 10):
    simics.SIM_run_command('%s.set-contention-ratio %d' % (devs[0].name,
                                                           contention_ratio))

    total_frame = 50
    sent_frame_count = 0

    for i in range(total_frame):
        status = devs[0].ep.iface.ieee_802_15_4_link.transmit(b"abcd", 0, 0, 0)
        if status == 0:
            sent_frame_count += 1

    if contention_ratio == 0:
        stest.expect_equal(sent_frame_count, total_frame,
                           "All packets should have been sent out.")
    elif contention_ratio == 100:
        stest.expect_equal(sent_frame_count, 0,
                           "No packet should have been sent out.")
    else:
        stest.expect_true(0 < sent_frame_count < total_frame,
                           "Only parts of the frame should have been sent out")
