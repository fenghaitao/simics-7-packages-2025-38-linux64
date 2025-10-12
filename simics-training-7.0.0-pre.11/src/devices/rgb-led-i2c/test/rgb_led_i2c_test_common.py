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


import pyobj
import dev_util
import conf
from simics import *

# Set up an LED
#
# Fake receiver for uint64_state 
# Receives any value for processing
#
class dummy_led(pyobj.ConfObject):
    '''Dummy representing the LED in a System Panel'''
    def _initialize(self):
        self.current_color.val = None 

    class uint64_state(pyobj.Interface):
        def finalize(self):
            pass
        def set(self,level):
            print("dummy_led got LED value %d" % (level))
            self._up.current_color.val = level

    class current_color(pyobj.SimpleAttribute(0,type='i')):
        """Current color code of the lED."""
        pass
#
# Fake I2C link
#
class fake_link(pyobj.ConfObject):
    '''Fake I2C link v2 class'''
    def _initialize(self):
        self.reqs = []

    class i2c_master_v2(pyobj.Interface):
        def finalize(self):
            pass

        def acknowledge(self, ack):
            self._up.reqs.append(['ack', ack])

        def read_response(self, value):
            self._up.reqs.append(['read_response', value])

rgb_led = pre_conf_object('rgb_led', 'rgb_led_i2c')
rgb_led.address = 0x20
i2c_link = pre_conf_object('dummy_i2c_link', 'fake_link')
rgb_led.i2c_link = i2c_link
panel_led = pre_conf_object('dummy_panel_led', 'dummy_led')
rgb_led.panel_led_out = panel_led

SIM_add_configuration([rgb_led, i2c_link, panel_led], None)

## Reassign the variables from the pre-conf to actual conf objects 
rgb_led    = conf.rgb_led
link       = conf.dummy_i2c_link
panel_led  = conf.dummy_panel_led 
###
