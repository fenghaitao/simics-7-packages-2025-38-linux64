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

# Unit test setup for the p_control class
#
# Setup:
#    Call in with mouse updates from the top
#    Check that it finds and calls the right devices
#    Need two stub devices that fake being controls
#    Posted at 

import stest
import pyobj
import dev_util
import conf
import simics

## Stubs

## Stub the display
class stub_display(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()  

    class width(pyobj.SimpleAttribute(512, type='i')):
        """Fake width of display."""

    class height(pyobj.SimpleAttribute(384, type='i')):
        """Fake height of display."""

    class p_display_draw(pyobj.Interface):
        """Fake necessary calls in the display unit."""
        def get_width(self):
            return self._up.width.val

        def get_height(self):
            return self._up.height.val

        def color_rect(self, x, y, w, h, argb):
            pass

        def draw_image_alpha(self, x, y, w, h, pxs):
            pass

        def draw_png_image(self, x, y, id):
            pass

        def get_png_image_width(self, id):
            return 100

        def get_png_image_height(self, id):
            return 150

## Stub the button
#
# In a way designed to facilitate testing:
# - Test sets next hit/no-hit reply
# - Test reads called function
class stub_button(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()  

    class next_hit(pyobj.SimpleAttribute(False, type='b')):
        """Next hit call will return this."""

    class last_call(pyobj.SimpleAttribute("none", type='s')):
        """Name of last called function."""

    class p_control_button(pyobj.Interface):
        """Fake necessary calls in the button."""
        def hit(self,_px,_py):
            if(self._up.next_hit.val):
                simics.SIM_log_info(2, self._up.obj, 0, "Stub button report hit" )              
                return True
            simics.SIM_log_info(2, self._up.obj, 0, "Stub button report miss" )
            return False

        def initial_state(self):
            self._up.last_call.val = "initial_state"
            simics.SIM_log_info(2, self._up.obj, 0, "Stub button: initial_state" )

        def start_press(self):
            simics.SIM_log_info(2, self._up.obj, 0, "Stub button: start_press" )
            self._up.last_call.val = "start_press"

        def end_press(self):
            simics.SIM_log_info(2, self._up.obj, 0, "Stub button: end_press" )
            self._up.last_call.val = "end_press"

        def cancel_press(self):
            simics.SIM_log_info(2, self._up.obj, 0, "Stub button: cancel_press" )
            self._up.last_call.val = "cancel_press"

        def down_in(self):
            simics.SIM_log_info(2, self._up.obj, 0, "Stub button: down_in" )
            self._up.last_call.val = "down_in"

        def down_outside(self):
            simics.SIM_log_info(2, self._up.obj, 0, "Stub button: down_outside" )
            self._up.last_call.val = "down_outside"

## Create objects
def create_p_control():
    ## A clock
    clock = simics.pre_conf_object('clock',
                                   'clock', 
                                   freq_mhz=1000)

    ## Stub display
    stub_d = simics.pre_conf_object('stub_display',
                                    'stub_display',
                                    width=768,
                                    height=512)

    ## Stub buttons
    stub_b_A = simics.pre_conf_object('stub_button_A',
                                    'stub_button')

    stub_b_B = simics.pre_conf_object('stub_button_B',
                                    'stub_button')

    stub_b_C = simics.pre_conf_object('stub_button_C',
                                    'stub_button')

    ## Control device
    dev = simics.pre_conf_object(
        'control',
        'p_control',
        display = stub_d,
        queue = clock,
        controls= [stub_b_A, stub_b_B, stub_b_C])

    ## Actually create objects
    preobjs = [dev, clock, stub_d, stub_b_A, stub_b_B, stub_b_C]
    simics.SIM_add_configuration(preobjs, None)

    ## Convert list to object pointers
    objs=[simics.SIM_get_object(p.name) for p in preobjs]

    return objs
