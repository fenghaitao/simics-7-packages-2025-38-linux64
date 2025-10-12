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


# Set up the environment 
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

##
## Total environment 
##
toggle = pre_conf_object('toggle', 'toggle_i2c')
toggle.address = 0x20
i2c_link = pre_conf_object('dummy_i2c_link', 'fake_link')
toggle.i2c_link = i2c_link

SIM_add_configuration([toggle, i2c_link], None)

## Reassign the variables from the pre-conf to actual conf objects 
toggle    = conf.toggle
link      = conf.dummy_i2c_link
