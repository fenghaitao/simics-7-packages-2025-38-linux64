# © 2022 Intel Corporation
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
# Test the p-control unit using stubbed buttons
# 

import dev_util
import simics
import stest
import p_control_common

# Raise the log level to make the test logs more useful for debug
cli.global_cmds.log_level(level=3)

# Create test objects
[dev, clock, stub_d, stub_b_A, stub_b_B, stub_b_C] =  p_control_common.create_p_control()


## Helpers
def create_mouse_button_down():
    return simics.abs_pointer_state_t(buttons=simics.Abs_Pointer_Button_Left,
                                      x=0x8000, y=0x8000, z=100)

def create_mouse_button_up():
    return simics.abs_pointer_state_t(buttons=0, x=0x8000, y=0x8000, z=100)


## Check detection of button clicks

# Nothing is hit
stub_b_A.next_hit = False
stub_b_B.next_hit = False
stub_b_C.next_hit = False

bdown = create_mouse_button_down()
bup = create_mouse_button_up()

dev.port.pointer.iface.abs_pointer.set_state(bdown)

stest.expect_equal(stub_b_A.last_call, "none")
stest.expect_equal(stub_b_B.last_call, "none")
stest.expect_equal(stub_b_C.last_call, "none")

# Release the mouse button 
dev.port.pointer.iface.abs_pointer.set_state(bup)
stest.expect_equal(stub_b_A.last_call, "none")
stest.expect_equal(stub_b_B.last_call, "none")
stest.expect_equal(stub_b_C.last_call, "none")

#
# New click, hitting C - and move in and out, 
#                        and end inside
#
stub_b_A.next_hit = False
stub_b_B.next_hit = False
stub_b_C.next_hit = True

dev.port.pointer.iface.abs_pointer.set_state(bdown)

stest.expect_equal(stub_b_A.last_call, "none")
stest.expect_equal(stub_b_B.last_call, "none")
stest.expect_equal(stub_b_C.last_call, "start_press")

# keep mouse pressed in button
dev.port.pointer.iface.abs_pointer.set_state(bdown)
stest.expect_equal(stub_b_A.last_call, "none")
stest.expect_equal(stub_b_B.last_call, "none")
stest.expect_equal(stub_b_C.last_call, "down_in")

# and move out 
stub_b_C.next_hit = False
dev.port.pointer.iface.abs_pointer.set_state(bdown)
stest.expect_equal(stub_b_C.last_call, "down_outside")

# and move in 
stub_b_C.next_hit = True
dev.port.pointer.iface.abs_pointer.set_state(bdown)
stest.expect_equal(stub_b_C.last_call, "down_in")

# and release
stub_b_C.next_hit = True
dev.port.pointer.iface.abs_pointer.set_state(bup)
stest.expect_equal(stub_b_C.last_call, "end_press")

#
# New click, hitting B - and move out, 
#                        and end outside
#
stub_b_B.next_hit = True
stub_b_C.next_hit = False 
dev.port.pointer.iface.abs_pointer.set_state(bdown)
stest.expect_equal(stub_b_B.last_call, "start_press")
stest.expect_equal(stub_b_C.last_call, "end_press")  # no change

stub_b_B.next_hit = False
dev.port.pointer.iface.abs_pointer.set_state(bdown)
stest.expect_equal(stub_b_B.last_call, "down_outside")

stub_b_B.next_hit = False
dev.port.pointer.iface.abs_pointer.set_state(bup)
stest.expect_equal(stub_b_B.last_call, "cancel_press")
