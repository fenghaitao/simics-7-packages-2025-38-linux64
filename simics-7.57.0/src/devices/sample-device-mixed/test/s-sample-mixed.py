# © 2012 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Tests for sample-device-mixed

import stest
import dev_util as du

# Create the sample device
mixed = SIM_create_object('sample_device_mixed', 'sample_mixed')

# Make the registers in bank regs accessible
r1 = du.Register((mixed, 'regs', 0))
r2 = du.Register((mixed, 'regs', 0x10))

# Test that written values to register r are read correctly
def test_r1():
    for val in (0, 1, 0x20, 0x1212):
        r1.write(val)
        stest.expect_equal(r1.read(), val + 4711, "Bad value read from r1")
def test_r2():
    for val in (0, 1, 0x20, 0x1212):
        r2.write(val)
        stest.expect_equal(r2.read(), val + 4712, "Bad value read from r2")

# Tests that written values to attribute int_attr are read correctly
def test_int_attr():
    for val in (0, 2, 0x10, 0x4711):
        mixed.attr.int_attr = val
        stest.expect_equal(mixed.attr.int_attr, val, "Bad value read from int_attr")


test_r1()
test_r2()
test_int_attr()

print("All tests passed.")
