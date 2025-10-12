# © 2015 Intel Corporation

import dev_util
import simics
import stest

# Create the python device.
py_dev = simics.SIM_create_object('empty_device_pyobj', 'empty_dev_pyobj')

# Add register definition for the device's register.
register = dev_util.Register_LE(py_dev.bank.regs, 0, size = 1)

# Test the value attribute so that it can be set and read correctly.
def test_value_attr():
    for val in (0, -22, 17, 35):
        py_dev.value = val
        stest.expect_equal(py_dev.value, val,
                           "Error writing/reading value attribute")

# Test the register for writing and reading value.
def test_value_mapped():
    for val in (0, 1, 21, 122):
        register.write(val)
        # Test that the attribute has changed.
        stest.expect_equal(py_dev.value, val,
                           "Error reading value attribute")
        stest.expect_equal(register.read(), val,
                           "Error writing value attribute")

test_value_attr()
test_value_mapped()
