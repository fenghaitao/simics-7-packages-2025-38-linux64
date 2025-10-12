# © 2018 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

#
# Unit test the RGB LED device
#
# - Pass in traffic over I2C
# - Check that output matches expectations
# - Setting the toggle state from the interface towards the panel
# 
import stest
import pyobj
import dev_util

# Create test system - use from X import star in order to make
# all local variables in the module appear in the top-level 
# namespace in this test file
from toggle_i2c_test_common import *

toggle.log_level = 4

##
## test that we can change the state over the toggle input, 
## and read the state of the toggle over I2C
##
i2c_addr = 0x22
toggle.address = i2c_addr
toggle_i2c_in = toggle.port.i2c_in.iface.i2c_slave_v2

##-------
## Test 1
##
## Set toggle state to 0  
toggle.ports.toggle_in.uint64_state.set(0)

## Start read 
toggle_i2c_in.start(i2c_addr << 1)
stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])
toggle_i2c_in.read()
stest.expect_equal(link.object_data.reqs[-1], ['read_response', 0])

##-------
## Test 2
##
## Set toggle state to 1 
toggle.ports.toggle_in.uint64_state.set(1)

## Start read of a 1 signal  
toggle_i2c_in.start(i2c_addr << 1)
stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])

toggle_i2c_in.read()
stest.expect_equal(link.object_data.reqs[-1], ['read_response', 1])

# Test repeated read
toggle_i2c_in.read()
stest.expect_equal(link.object_data.reqs[-1], ['read_response', 1])

# And more repeated 
toggle_i2c_in.read()
stest.expect_equal(link.object_data.reqs[-1], ['read_response', 1])


print("All tests passed.")
