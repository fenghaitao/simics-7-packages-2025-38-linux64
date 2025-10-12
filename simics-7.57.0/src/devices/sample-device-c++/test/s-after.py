# © 2024 Intel Corporation
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
import cli
import os.path
import shutil

clk = SIM_create_object("clock", "clk", [["freq_mhz", 10]])
dut = SIM_create_object("sample_device_cxx_after", "dut", [["queue", clk]])

# Check the event queue
result = cli.quiet_run_command("peq clk")
stest.expect_equal(result[0][1],
                    [[10000000, 'dut', 'after_event'],
                     [20000000, 'dut', 'after_event']])

stest.expect_log(cli.run_command, ["run 10000000"], obj=conf.sim,
                 log_type="info",
                 regex=r"twoStrsArgumentGlobalFunction\(abc, def\)")

result = cli.quiet_run_command("peq clk")
stest.expect_equal(result[0][1],
                   [[10000000, 'dut', 'after_event']])

# Test cancel_after
dut.cancel_after = True

result = cli.quiet_run_command("peq clk")
stest.expect_equal(result[0], [])
