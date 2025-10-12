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
# Unit test the button device 
#
# - Push the button from the script
# - Check that it can be read as an I2C slave
# - Check that the state can be cleared over I2C
#
# DOES NOT TEST the master behavior of the button (yet)
# 

import stest
import pyobj
import dev_util

# Create test system - use from X import star in order to make
# all local variables in the module appear in the top-level 
# namespace in this test file
from button_i2c_test_common import *


button.log_level = 4

##
## test that we can change the state over the button input, 
## and read the state of the button over I2C
##
i2c_addr = 0x22
button.address = i2c_addr

##-------
## Test 1
##
## Push the button and check that we read state right
button.ports.button_in.signal.signal_raise()

## Start read of a 1 signal  
button.port.i2c_in.iface.i2c_slave_v2.start(i2c_addr << 1)
stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])

button.port.i2c_in.iface.i2c_slave_v2.read()
stest.expect_equal(link.object_data.reqs[-1], ['read_response', 1])

button.port.i2c_in.iface.i2c_slave_v2.stop()

##------ 
## Test clearing the button pressed state with an i2c write
##
# Send a zero to the device 
button.port.i2c_in.iface.i2c_slave_v2.start( (i2c_addr << 1) + 0)
stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])
button.port.i2c_in.iface.i2c_slave_v2.write(0)

# check ack of write
stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])
# Check updated state in device
stest.expect_equal( (button.i2cregs_button_pressed), 0 )
# end transaction
button.port.i2c_in.iface.i2c_slave_v2.stop()

## Check that we read back a zero
button.port.i2c_in.iface.i2c_slave_v2.start((i2c_addr << 1) + 1)
stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])
button.port.i2c_in.iface.i2c_slave_v2.read()
stest.expect_equal(link.object_data.reqs[-1], ['read_response', 0])
button.port.i2c_in.iface.i2c_slave_v2.stop()



##-------
## Test bus busy detect
##
# chekc bus busy detect - by looking at the bit in the i2c register

# Not busy
stest.expect_equal( (button.i2cregs_i2c_slave_state & 0x02), 0 )
button.port.i2c_in.iface.i2c_slave_v2.start( (i2c_addr << 1) + 2)  # targeting another address
# busy
stest.expect_equal( (button.i2cregs_i2c_slave_state & 0x02), 2 )
button.port.i2c_in.iface.i2c_slave_v2.stop()
# not busy  
stest.expect_equal( (button.i2cregs_i2c_slave_state & 0x02), 0 )
                    





##-------
## Test 2
##
## Push the button and check that we read state right
button.ports.button_in.signal.signal_raise()
button.ports.button_in.signal.signal_lower()


print("All tests passed.")
