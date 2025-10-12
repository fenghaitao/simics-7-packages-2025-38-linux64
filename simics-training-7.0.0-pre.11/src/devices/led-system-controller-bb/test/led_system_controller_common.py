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


# Unit test for the LED system controller
# Common code that sets up the required environment:
#
#   Controller
#   i2c Bus
#   ...
#

import pyobj
import conf
from simics import *

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

    class i2c_slave_v2(pyobj.Interface):
        def finalize(self):
            pass

        def start(self,address):
            pass


## Create objects
i2c_addr = 100
controller = pre_conf_object('controller', 'led_system_controller_bb')
controller.i2c_address  = i2c_addr
i2c_link = pre_conf_object('dummy_i2c_link', 'fake_link')
controller.i2c_link = i2c_link

## Fake software setup of I2C addresses 
controller.regs_display_width         = 8
controller.regs_display_height        = 8
controller.regs_display_i2c_base      = 16
controller.regs_toggle_i2c_address    = [90,91,0,0 ,0,0,0,0 ,0,0,0,0 ,0,0,0,0]
controller.regs_button_a_i2c_address  = 92
controller.regs_button_b_i2c_address  = 93

## A clock
clock = pre_conf_object(
    'clock',
    'clock',
    freq_mhz=1000)
controller.queue = clock

## Memory
ram_size_in_bytes = 1024 * 1024
card_mem = pre_conf_object('local_memory', 'memory-space')
ram_image = pre_conf_object('ram_image', 'image')
ram_image.size = ram_size_in_bytes
ram = pre_conf_object('ram', 'ram')
ram.image = ram_image
card_mem.map = [ [0x0000, ram, 0, 0, ram_size_in_bytes] ]
controller.local_memory = card_mem

SIM_add_configuration([clock, controller, i2c_link, card_mem, ram_image, ram], None)

## Reassign the variables from the pre-conf to actual conf objects 
controller    = conf.controller
link          = conf.dummy_i2c_link

