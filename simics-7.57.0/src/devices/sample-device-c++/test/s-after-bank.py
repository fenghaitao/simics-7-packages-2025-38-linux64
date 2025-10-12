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
import dev_util

clk = SIM_create_object("clock", "clk", [["freq_mhz", 10]])
dut0 = SIM_create_object("sample_device_cxx_after_bank", "dut0",
                         [["queue", clk]])
dut1 = SIM_create_object("sample_device_cxx_after_bank", "dut1",
                         [["queue", clk]])

b0 = dev_util.bank_regs(conf.dut0.bank.b[0])
stest.expect_equal(b0.r[1].read(), 0x2a)

stest.expect_log(cli.run_command, ["run 10000000"], obj=conf.dut0.bank.b[0],
                 log_type="info",
                 regex=r"Call to write at reg level of reg b\[0\].r\[1\] with"
                 " value 0xdeadbeef")
stest.expect_equal(b0.r[1].read(), 0xdeadbeef)

stest.expect_log(cli.run_command, ["run 10000000"], obj=conf.dut0.bank.b[0],
                 log_type="info",
                 regex=r"Call to clear at field level of field b\[0\].r\[1\].f0")
stest.expect_equal(b0.r[1].field.f0.read(), 0)
