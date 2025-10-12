# © 2023 Intel Corporation
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
import cli

# Create many objects and set the register
ms = SIM_create_object('memory-space', 'ms', [])
dut = SIM_create_object('SampleDevice', 'dut', [])

ms.map = [
    [0x1000, dut.bank.b, 0, 0, 0x1000]
]

# wiggle the register
regs = dev_util.bank_regs(dut.bank.b)
stest.expect_equal(regs.REG1.read(), 0x0)  # always 42
dut.bank.b.log_level = 3
regs.REG1.write(0xff)
stest.expect_equal(regs.REG1.read(), 0xff)  # always 42
dut.bank.b.log_level = 1

