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
# 

import stest
import pyobj
import dev_util

# Create test system - use from X import star in order to make
# all local variables in the module appear in the top-level 
# namespace in this test file
from rgb_led_i2c_test_common import *

# Increase log level on the object under test
rgb_led.log_level = 4

# Cache the slave interface on the rgb
rgb_i2c_in = rgb_led.port.i2c_in.iface.i2c_slave_v2


def write_and_test(value):
    rgb_i2c_in.write(value)
    # Expect the device to indicate the same byte (this is a special test facility)
    stest.expect_equal(rgb_led.written_value, value)
    # Check that the device also called back with an ack, following the I2C V2 protocol 
    stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])


def test_set_color(red, green, blue, led_code):
    # Set the address of this LED 
    i2c_addr = 0x22
    rgb_led.address = i2c_addr

    # Start operation     
    rgb_i2c_in.start(i2c_addr << 1)
    stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])

    # Write in a color value:
    #  c, 1, 0, 0
    write_and_test(ord('c'))
    write_and_test(red)    
    write_and_test(green)    
    write_and_test(blue)    

    rgb_i2c_in.stop()
    stest.expect_equal(panel_led.current_color, led_code)

def test_set_color_with_postfix(red,green,blue,led_code):
    # Number of extra bytes
    extra_bytes = 3
    
    # Set the address of this LED 
    i2c_addr = 0x22
    rgb_led.address = i2c_addr 

    # Start operation     
    rgb_i2c_in.start(i2c_addr << 1)
    stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])

    # Write in a color value:
    #  c, 1, 0, 0
    write_and_test(ord('c'))
    write_and_test(red)    
    write_and_test(green)    
    write_and_test(blue)    

    # write a bunch of extra bytes 
    # unless it goes to 4 bytes, nothing should happen
    for i in range(extra_bytes):
        write_and_test(i)
        
    # expect the device to just ignore the extra bytes
    rgb_i2c_in.stop()
    stest.expect_equal(panel_led.current_color, led_code)
    
def test_set_color_with_stop_and_postfix(red,green,blue,led_code):
    # Number of extra bytes
    extra_bytes = 8
    
    # Set the address of this LED 
    i2c_addr = 0x22
    rgb_led.address = i2c_addr

    # Start operation     
    rgb_i2c_in.start(i2c_addr << 1)
    stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])

    # Write in a color value:
    #  c, 1, 0, 0
    write_and_test(ord('c'))
    write_and_test(red)    
    write_and_test(green)    
    write_and_test(blue)    
    
    # issue stop
    rgb_i2c_in.stop()
    stest.expect_equal(panel_led.current_color, led_code)

    # write a bunch of extra bytes
    # - Check that the device warns about it 
    for i in range(extra_bytes):
        stest.expect_log(rgb_i2c_in.write, [i], None, 'spec-viol')
        
    # expect the device to just ignore the extra bytes
    stest.expect_equal(panel_led.current_color, led_code)


def test_write_read(red, green, blue):
    # Set the address of this LED 
    i2c_addr = 0x22
    rgb_led.address = i2c_addr 

    # Start operation - write in a color
    rgb_i2c_in.start(i2c_addr << 1 ) 
    stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])
    write_and_test(ord('c'))
    write_and_test(red)    
    write_and_test(green)    
    write_and_test(blue)    
    rgb_i2c_in.stop()

    # Read operation - read back values
    rgb_i2c_in.start((i2c_addr << 1) + 1) 
    stest.expect_equal(link.object_data.reqs[-1], ['ack', 0])
    rgb_i2c_in.read()
    stest.expect_equal(link.object_data.reqs[-1], ['read_response', 99])
    rgb_i2c_in.read()
    stest.expect_equal(link.object_data.reqs[-1], ['read_response', red])
    rgb_i2c_in.read()
    stest.expect_equal(link.object_data.reqs[-1], ['read_response', green])
    rgb_i2c_in.read()
    stest.expect_equal(link.object_data.reqs[-1], ['read_response', blue])
    rgb_i2c_in.stop()

# test color coding
#
# red, green, blue --> color code
#   0 = black
#   1 = blue
#   2 = red
#   3 = red + blue = magenta
#   4 = green
#   5 = blue + green = cyan
#   6 = red + green = yellow
#   7 = white
#
# 
test_set_color(255, 0, 0, 2)
test_set_color(1, 0, 0, 2)
test_set_color(1, 0, 1, 3)   # 
test_set_color(0, 127, 0, 4)
test_set_color(0,100,0,4)
test_set_color(0,0,0,0)
test_set_color(1, 2, 0, 6)
test_set_color(255,255,255,7)
test_set_color(0,100,100,5)
test_set_color(0,0,1,1)

# test inputs with a few extra bytes
test_set_color_with_postfix(255,0,0,2)
test_set_color_with_postfix(0,255,0,4)
test_set_color_with_postfix(0,0,255,1)

# test inputs with a stop and extra bytes
test_set_color_with_stop_and_postfix(255,0,0,2)

# test read-write
test_write_read(255,127,0)
test_write_read(0,255,254)




print("All tests passed.")
