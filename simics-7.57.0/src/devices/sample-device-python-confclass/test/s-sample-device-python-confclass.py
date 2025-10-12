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

import simics
import stest

# Create the sample python device.
py_dev = simics.SIM_create_object('sample_device_python_confclass',
                                  'sample_dev_python_confclass')

# Create a memory with the sample device mapped at 0.
space = simics.SIM_create_object('memory-space', 'phys_mem',
                                 [['map',[[0, py_dev, 0, 0, 8],]]])

# Test the temperature attribute so that it can be set and read correctly.
def test_temperature_attr():
    for temp in (0, -22, 17, 35):
        py_dev.attr.temperature = temp
        stest.expect_equal(py_dev.attr.temperature, temp,
                           "Error writing/reading temperature attribute")

# Test the memory mapped registers for writing and reading temperature.
def test_temperature_mapped():
    for temp in (0, 1, 21, 122):
        # Address 0 reads temperature, address 1 writes temperature.
        space.memory[1] = temp
        stest.expect_equal(space.memory[0], temp,
                           "Error writing/reading temperature through memory")
        # Also test that the attribute has changed.
        stest.expect_equal(py_dev.attr.temperature, temp,
                           "Error reading temperature attribute")

test_temperature_attr()
test_temperature_mapped()

print("All tests passed.")
