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

import dev_util
import simics
import stest

# Create the python device.
py_dev = simics.SIM_create_object('empty_device_confclass',
                                  'empty_dev_confclass')

# Add register definition for the device's register.
register = dev_util.Register_LE(py_dev.bank.regs, 0, size = 1)

# Test the register.
a = register.read()
register.write(a + 1)
b = register.read()
stest.expect_equal(b, a + 1)

# Also test the 'r1' attribute which backs the register.
stest.expect_equal(py_dev.r1, b)
c = b + 1
py_dev.r1 = c
stest.expect_equal(py_dev.r1, c)
stest.expect_equal(register.read(), c)
