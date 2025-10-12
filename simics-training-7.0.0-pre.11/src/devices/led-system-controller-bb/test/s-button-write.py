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
# Test writes from a button to the master
# 
import stest
import info_status
import dev_util
import pyobj

# Create test system - use from X import star in order to make
# all local variables in the module appear in the top-level 
# namespace in this test file
from led_system_controller_common import *

cslave = controller.port.i2c_in.iface.i2c_slave_v2

# utility function 
def write_value(value):
    cslave.write(value)
    # Check that the device also called back with an ack, following the I2C V2 protocol 
    stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])

##
## Start operation - test bad input
##
print("Testing input for button, but with wrong address")
stest.expect_equal(controller.bank.regs.button_a_status,0)
stest.expect_equal(controller.bank.regs.button_b_status,0)
     
cslave.start(i2c_addr << 1)
stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])
write_value(98)
write_value(95)
cslave.stop()
stest.expect_equal(controller.bank.regs.button_a_status,0)
stest.expect_equal(controller.bank.regs.button_b_status,0)

##
## Start operation - test bad input
##
print("Testing input that is not a button message")
stest.expect_equal(controller.bank.regs.button_a_status,0)
stest.expect_equal(controller.bank.regs.button_b_status,0)
     
cslave.start(i2c_addr << 1)
stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])
write_value(99)
write_value(92)
cslave.stop()
stest.expect_equal(controller.bank.regs.button_a_status,0)
stest.expect_equal(controller.bank.regs.button_b_status,0)

##
## Start operation - test too long input
##
print("Testing very long input")
stest.expect_equal(controller.bank.regs.button_a_status,0)
stest.expect_equal(controller.bank.regs.button_b_status,0)
     
cslave.start(i2c_addr << 1)
stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])
write_value(1)
write_value(2)
write_value(3)
write_value(4)
write_value(5)
write_value(6)
write_value(7)
write_value(8)
write_value(9)
write_value(10)
write_value(11)
write_value(12)
write_value(13)
write_value(14)
write_value(15)
write_value(16)
write_value(17)
write_value(18)
cslave.stop()
stest.expect_equal(controller.bank.regs.button_a_status,0)
stest.expect_equal(controller.bank.regs.button_b_status,0)
stest.expect_equal(controller.bank.i2cregs.i2c_data_buffer[0],17)


##
## Start operation - test Button A
##
print("Testing button A input")
stest.expect_equal(controller.bank.regs.button_a_status,0)
     
cslave.start(i2c_addr << 1)
stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])
write_value(98)
write_value(92)
cslave.stop()
stest.expect_equal(controller.bank.regs.button_a_status,1)

##
## Start operation - test Button B
##
print("Testing button B input")
stest.expect_equal(controller.bank.regs.button_b_status,0)
     
cslave.start(i2c_addr << 1)
stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])
write_value(98)
write_value(93)
cslave.stop()
stest.expect_equal(controller.bank.regs.button_b_status,1)

