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


import dev_util
import conf
import stest
import p_button_common

# Raise the log level to make the test logs more useful for debug
cli.global_cmds.log_level(level=3)

# Create an instance of the device to test
[dev, stub_i_o, stub_receiver] = p_button_common.create_p_button()

# Cache the control button interface to make test code shorter
dev_pbh = dev.port.control.iface.p_control_button

# Write your tests here

## Test from the perspective of the controller 

#-------------------------------------------------------
# Check if we detect hits right
#   Button is at:  x=100, y=50
#                  w=70,  h=35
#   As set up in the common code 
def test_hit(x, y, b):
    h=dev_pbh.hit(x, y)
    stest.expect_equal(h, b,
                       f"hit({x},{y}) expected {b} got f{h}")

# WAY off
test_hit(0, 0, False)
test_hit(10000, 10000, False)
# JUST inside
test_hit(p_button_common.bx, p_button_common.by, True)
test_hit(p_button_common.bx + p_button_common.bw - 1, p_button_common.by, True)
test_hit(p_button_common.bx, p_button_common.by + p_button_common.bh - 1, True)
# JUST outside
test_hit(p_button_common.bx + p_button_common.bw, p_button_common.by, False)
test_hit(p_button_common.bx + p_button_common.bw, 
         p_button_common.by + p_button_common.bh, False)
test_hit(p_button_common.bx - 1, p_button_common.by - 1, False)

#---------------------------------------------------------
# Check the state machine
#
stest.expect_equal(stub_i_o.current_state, 0,
                   "Expected image object state to be zero on its own")

# Go to initial state
stub_i_o.current_state = 100
dev_pbh.initial_state()
stest.expect_equal(stub_i_o.current_state, 0,
                   "Expected initial image state to drive to zero")

#
# Start a press, and end inside the button
#
dev_pbh.start_press()
stest.expect_equal(stub_i_o.current_state, 1,
                   "Expected active state to be shown")

# And end successfully
rc = stub_receiver.signal.raise_count
lc = stub_receiver.signal.lower_count
stest.expect_equal(rc, 0, "Expected initial raise count to be zero")
stest.expect_equal(lc, 0, "Expected initial lower count to be zero")
dev_pbh.end_press()
stest.expect_equal(stub_i_o.current_state, 0, "Expected idle state")

rc2 = stub_receiver.signal.raise_count
lc2 = stub_receiver.signal.lower_count
stest.expect_equal(rc2 - rc, 1, f"Expected one additional raise")
stest.expect_equal(lc2 - lc, 1, f"Expected one additional lower")

#
# Start a press, move out, move in, move out, and then release
#
rc = rc2
lc = lc2

dev_pbh.start_press()
stest.expect_equal(stub_i_o.current_state, 1,
                   "Expected active state to be shown")

dev_pbh.down_in()
stest.expect_equal(stub_i_o.current_state, 1,
                   "Expected active state to be shown")

dev_pbh.down_outside()
stest.expect_equal(stub_i_o.current_state, 0,
                   "Expected idle state to be shown")

dev_pbh.down_in()
stest.expect_equal(stub_i_o.current_state, 1,
                   "Expected active state to be shown")

dev_pbh.down_outside()
stest.expect_equal(stub_i_o.current_state, 0,
                   "Expected idle state to be shown")

dev_pbh.cancel_press()
stest.expect_equal(stub_i_o.current_state, 0,
                   "Expected idle state to be shown")

rc2 = stub_receiver.signal.raise_count
lc2 = stub_receiver.signal.lower_count
stest.expect_equal(rc2 - rc, 0, "Expected no raise")
stest.expect_equal(lc2 - lc, 0, "Expected no lower")

#
# Start a press, move out, move in, and then release
#
rc = rc2
lc = lc2

dev_pbh.start_press()
stest.expect_equal(stub_i_o.current_state, 1,
                   "Expected active state to be shown")

dev_pbh.down_in()
stest.expect_equal(stub_i_o.current_state, 1,
                   "Expected active state to be shown")

dev_pbh.down_outside()
stest.expect_equal(stub_i_o.current_state, 0,
                   "Expected idle state to be shown")

dev_pbh.down_in()
stest.expect_equal(stub_i_o.current_state, 1,
                   "Expected active state to be shown")

dev_pbh.end_press()
stest.expect_equal(stub_i_o.current_state, 0,
                   "Expected idle state to be shown")

rc2 = stub_receiver.signal.raise_count
lc2 = stub_receiver.signal.lower_count
stest.expect_equal(rc2 - rc, 1, "Expected one additional raise")
stest.expect_equal(lc2 - lc, 1, "Expected one additional lower")

#
# Testing incorrect sequences, just to make sure the
# device does not crash in case they happen.  It is
# not expected that the button will do anything to 
# check the sequences. 
# 
rc = rc2
lc = lc2

dev_pbh.end_press()
stest.expect_equal(stub_i_o.current_state, 0,
                   "Expected idle state to be shown")
rc2 = stub_receiver.signal.raise_count
lc2 = stub_receiver.signal.lower_count

# And yes, each end_press produces a signal! 
# The logic of the button is designed to be simple. 
# In a way, it is just a messenger between different
# part of the system. 
stest.expect_equal(rc2 - rc, 1, "Expected one additional raise")
stest.expect_equal(lc2 - lc, 1, "Expected one additional lower")
