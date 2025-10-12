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
rssi = 50
simics.SIM_run_command('%s.set-rssi %s %d' % (devs[0].name, devs[1].name, rssi))
stest.expect_equal(len(devs[0].ep.rssi_table), len(devs) - 1)

# transmit
for rssi_always_drop in range(0, 100 + 1, 10):
    for rssi_random_drop in range(0, 100 + 1, 10):
        for rssi_random_drop_ratio in range(0, 100 + 1, 10):
            simics.SIM_run_command('%s.set-rssi-always-drop %d'
                                   % (devs[1].name, rssi_always_drop))
            simics.SIM_run_command('%s.set-rssi-random-drop %d'
                                   % (devs[1].name, rssi_random_drop))
            simics.SIM_run_command('%s.set-rssi-random-drop-ratio %d'
                                   % (devs[1].name, rssi_random_drop_ratio))

            if rssi_always_drop >= rssi or rssi > rssi_random_drop:
                total_frame = 5
            else:
                total_frame = 50

            devs[1].lost_frames_count = 0
            devs[1].received_frames_count = 0
            for i in range(total_frame):
                devs[0].ep.iface.ieee_802_15_4_link.transmit(b"abcd", 0, 0, 0)
            simics.SIM_continue(5)

            if rssi_always_drop >= rssi:
                stest.expect_equal(devs[1].received_frames_count, 0,
                       "All packets should be dropped.")
            elif rssi > rssi_random_drop:
                stest.expect_equal(devs[1].received_frames_count, total_frame,
                       "All packets should have been received.")
            else:
                stest.expect_equal(devs[1].received_frames_count
                                   + devs[1].lost_frames_count,
                                   total_frame,
                                   "inconsistent frame numbers")

                lost_ratio = devs[1].lost_frames_count * 100 // total_frame

                if rssi_random_drop_ratio == 0:
                    stest.expect_equal(lost_ratio, 0,
                                       "All packets should have been received.")
                elif rssi_random_drop_ratio == 100:
                    stest.expect_equal(lost_ratio, 100,
                                       "All packets should have been dropped.")
                else:
                    stest.expect_true(lost_ratio not in [0, 100])
