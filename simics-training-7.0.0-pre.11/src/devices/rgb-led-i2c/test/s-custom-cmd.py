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


import stest
import info_status
import pyobj
import dev_util

# Create test system - use from X import star in order to make
# all local variables in the module appear in the top-level 
# namespace in this test file
from rgb_led_i2c_test_common import *

cmd  = "set-color"

# Poke a Blue pixel and check results
args     = " red = 0 green = 0 blue = 0xff"
led_code = 1 
try:
    SIM_run_command(rgb_led.name + '.' + cmd + args)
except SimExc_General as e:
    stest.fail(cmd + ' command failed: ' + str(e))
stest.expect_equal(panel_led.current_color, led_code)


# Bad arguments to check failure on purpose
args     = " red = ab green = garbage blue = bad"
try:
    SIM_run_command(rgb_led.name + '.' + cmd + args)
    stest.fail(cmd + args + " did not fail, which it should")
except SimExc_General as e:
    print("Bad command did not execute: " + str(e))

# Bad arguments to check failure on purpose
args     = " red = 0x00 green = 0xff "
try:
    SIM_run_command(rgb_led.name + '.' + cmd + args)
    stest.fail(cmd + args + " did not fail, which it should")
except SimExc_General as e:
    print("Missing blue argument did not execute" + str(e))



# Poke a White pixel and check results
args     = " red = 0xff green = 0xff blue = 0xff"
led_code = 7 
try:
    SIM_run_command(rgb_led.name + '.' + cmd + args)
except SimExc_General as e:
    stest.fail(cmd + ' command failed: ' + str(e))
stest.expect_equal(panel_led.current_color, led_code)


