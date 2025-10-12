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
import p_toggle_common

# Raise the log level to make the test logs more useful for debug
cli.global_cmds.log_level(level=3)

# Create an instance of the device to test
[dev, stub_i_o, stub_receiver] = p_toggle_common.create_p_toggle()

# Cache the control button interface to make test code shorter
dev_pbh = dev.port.control.iface.p_control_button

#-------------------------------------------------------
# Check if we detect hits right
#   As set up in the common code 
def test_hit(x, y, b):
    h=dev_pbh.hit(x, y)
    stest.expect_equal(h, b,
                       f"hit({x},{y}) expected {b} got f{h}")

# WAY off
test_hit(0, 0, False)
test_hit(10000, 10000, False)
# JUST inside
test_hit(p_toggle_common.bx, p_toggle_common.by, True)
test_hit(p_toggle_common.bx + p_toggle_common.bw - 1, p_toggle_common.by, True)
test_hit(p_toggle_common.bx, p_toggle_common.by + p_toggle_common.bh - 1, True)
# JUST outside
test_hit(p_toggle_common.bx + p_toggle_common.bw, p_toggle_common.by, False)
test_hit(p_toggle_common.bx + p_toggle_common.bw,
         p_toggle_common.by + p_toggle_common.bh, False)
test_hit(p_toggle_common.bx - 1, p_toggle_common.by - 1, False)

#---------------------------------------------------------
# Check that setting the state attribute causes the
# correct image to be displayed
#
stest.expect_equal(stub_i_o.current_state, 0,
                   "Expected image object state to be zero on its own")

# State OFF, check image drive correctly
stub_i_o.current_state = 100
dev.toggle_state = False
dev_pbh.initial_state()
stest.expect_equal(stub_i_o.current_state, 0,
                   "Expected initial image state to drive to zero")
stest.expect_equal(stub_receiver.current_state, 0,
                   "Expected initial state to drive zero")                   

# State ON, check image drive correctly
stub_i_o.current_state = 100
dev.toggle_state = True
dev_pbh.initial_state()
stest.expect_equal(stub_i_o.current_state, 2,
                   "Expected initial image state to drive to two for toggle on")
stest.expect_equal(stub_receiver.current_state, 1,
                   "Expected initial state to drive one for toggle on")                   

#---------------------------------------------------------
# Check the button control inputs
#
dev.toggle_state = False
dev_pbh.initial_state()
dev_pbh.start_press()
stest.expect_equal(stub_i_o.current_state, 1, "Expected 'change' image")

# Click completed inside the toggle, expect a change
dev_pbh.end_press()
stest.expect_equal(dev.toggle_state, True, "Expected toggle to be on")
stest.expect_equal(stub_i_o.current_state, 2, "Expected 'on' image")
stest.expect_equal(stub_receiver.current_state, 1, "Expected state to change to 1")

# Click in button, pull out, go back, pull out, release
dev_pbh.start_press()
stest.expect_equal(stub_i_o.current_state, 1, "Expected 'change' image")

dev_pbh.down_in()
stest.expect_equal(stub_i_o.current_state, 1, "Expected 'change' image")

dev_pbh.down_outside()
stest.expect_equal(stub_i_o.current_state, 2, "Expected 'on' image")

dev_pbh.down_in()
stest.expect_equal(stub_i_o.current_state, 1, "Expected 'change' image")

dev_pbh.down_outside()
stest.expect_equal(stub_i_o.current_state, 2, "Expected 'on' image")

dev_pbh.cancel_press()
stest.expect_equal(dev.toggle_state, True, "Expected toggle to be on")
stest.expect_equal(stub_i_o.current_state, 2, "Expected 'on' image")
