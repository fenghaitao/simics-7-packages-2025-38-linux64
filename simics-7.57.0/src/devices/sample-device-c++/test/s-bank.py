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
import dev_util

def test_bank(class_name):
    dut = SIM_create_object(class_name, "dut", [])
    SIM_run_command('set-table-border-style borderless')
    cli.run_command('output-radix 16')

    result = cli.quiet_run_command('print-device-regs bank = "dut.bank.b[0]"')[1]
    stest.expect_true('   0x0  r[0]   0x4   0x2a' in result)
    stest.expect_true('  0x10  r[1]   0x4   0x2a' in result)

    result = cli.quiet_run_command('print-device-reg-info register = "dut.bank.b[0].r[1]"')[1]
    stest.expect_true('f1 @ [31:16]  :  0000000000000000  "a default field"' in result)
    stest.expect_true('f0 @ [15:0]  :  0000000000101010  "a sample field"' in result)

    result = cli.quiet_run_command('print-device-regs bank = "dut.bank.b[1]"')[1]
    stest.expect_true('   0x0  r[0]   0x4   0x2a' in result)
    stest.expect_true('  0x10  r[1]   0x4   0x2a' in result)

    result = cli.quiet_run_command('print-device-reg-info register = "dut.bank.b[1].r[1]"')[1]
    stest.expect_true('f1 @ [31:16]  :  0000000000000000  "a default field"' in result)
    stest.expect_true('f0 @ [15:0]  :  0000000000101010  "a sample field"' in result)

    regs = dev_util.bank_regs(dut.bank.b[0])
    # Register has initial value 42
    stest.expect_equal(regs.r[1].read(), 42)

    cli.run_command("dut.log-level 3 -r")
    stest.expect_log(regs.r[1].write, (0xdeadbeef, ), log_type="info", regex="Write to SampleField")
    stest.expect_equal(regs.r[1].field.f1.read(), 0xdead)
    stest.expect_equal(regs.r[1].field.f0.read(), 0xbeef)
    stest.expect_log(regs.r[1].read, tuple(), log_type="info", regex="Read from SampleRegister")
    stest.expect_equal(regs.r[1].read(), 0xdeadbeef)

    # Unmapped read
    t = transaction_t()
    t.size = 0x8
    stest.expect_log(SIM_issue_transaction, (dut.bank.b[0], t, 0x0),
                     log_type="spec-viol",
                     regex="Read 8 bytes at offset 0 outside registers or misaligned")

    SIM_delete_object(dut)

test_bank("sample_device_cxx_bank_by_code")
test_bank("sample_device_cxx_bank_by_data")
