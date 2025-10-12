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


import dev_util
import conf
import stest

import sys
sys.path.append("../../ieee-802-15-4-link/test/")
import common

[devs, eps, link] = common.create_test_bench()

tx_fifo_reg = dev_util.Register_LE(devs[0].bank.regs, 0x0, size = 1)
tx_cmd_reg = dev_util.Register_LE(devs[0].bank.regs, 0x4)
SIM_set_log_level(devs[0], 4)
SIM_set_log_level(devs[1], 4)
SIM_set_log_level(link[0], 4)
SIM_set_log_level(eps[0], 4)
SIM_set_log_level(eps[1], 4)

simics.SIM_run_command('%s.set-rssi %s 5' % (devs[0].name, devs[1].name))
stest.expect_equal(devs[0].sent_frames_count, 0)
stest.expect_equal(devs[0].contention_count, 0)
stest.expect_equal(devs[1].received_frames_count, 0)
stest.expect_equal(devs[1].lost_frames_count, 0)

# test sent_frames_count and received_frames_count
tx_fifo_reg.write(0x5a)
tx_cmd_reg.write(1)
simics.SIM_continue(5)
stest.expect_equal(devs[0].sent_frames_count, 1)
stest.expect_equal(devs[0].contention_count, 0)
stest.expect_equal(devs[1].received_frames_count, 1)
stest.expect_equal(devs[1].lost_frames_count, 0)

# test contention_count
simics.SIM_run_command('%s.set-contention-ratio 100' % devs[0].name)
tx_fifo_reg.write(0x5a)
tx_cmd_reg.write(1)
simics.SIM_continue(5)
stest.expect_equal(devs[0].sent_frames_count, 1)
stest.expect_equal(devs[0].contention_count, 1)
stest.expect_equal(devs[1].received_frames_count, 1)
stest.expect_equal(devs[1].lost_frames_count, 0)

# test lost_frames_count
simics.SIM_run_command('%s.set-contention-ratio 0' % devs[0].name)
simics.SIM_run_command('%s.set-rssi-always-drop 10' % devs[1].name)
tx_fifo_reg.write(0x5a)
tx_cmd_reg.write(1)
simics.SIM_continue(5)
stest.expect_equal(devs[0].sent_frames_count, 2)
stest.expect_equal(devs[0].contention_count, 1)
stest.expect_equal(devs[1].received_frames_count, 1)
stest.expect_equal(devs[1].lost_frames_count, 1)
