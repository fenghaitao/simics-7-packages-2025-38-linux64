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

import simics
import pyobj
import dev_util

# Some constants
bx=200
by=200
bw=50
bh=100

# Stub the image_object
class stub_image_object(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()  

    class current_state(pyobj.SimpleAttribute(0, type='i')):
        """Current state driven to the image."""

    class uint64_state(pyobj.Interface):
        def set(self,level):
            simics.SIM_log_info(2, self._up.obj, 0, "Stub image object got state {level}" )
            self._up.current_state.val = level

    class p_image_properties(pyobj.Interface):
        def get_x(self):
            return bx
        
        def get_y(self):
            return by

        def get_width(self):
            return bw
        
        def get_height(self):
            return bh

## Stub the state receiver
class stub_state_receiver(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()  

    class current_state(pyobj.SimpleAttribute(0, type='i')):
        """Current state driven to the image."""

    class uint64_state(pyobj.Interface):
        def set(self,level):
            simics.SIM_log_info(2, self._up.obj, 0, f"Stub receiver object got state {level}" )
            self._up.current_state.val = level


# Create a test setup
# - Button
# - Fake image display object
# - Fake signal receiver 
# 
def create_p_toggle(name="toggle_under_test"):
    '''Create a test setup'''
    ## Toggle
    p_toggle = simics.pre_conf_object(name, 'p_toggle')
    
    ## Stub output_image
    stub_o_i = simics.pre_conf_object("stub_o_i", 'stub_image_object')
    p_toggle.attr.output_image = stub_o_i

    ## Stub state receiver
    stub_s = simics.pre_conf_object("stub_state", 'stub_state_receiver')
    p_toggle.attr.output = stub_s

    ## Create objects 
    preobjs = [p_toggle, stub_o_i, stub_s]
    simics.SIM_add_configuration(preobjs, None)

    ## Convert preobjs to objs
    objs=[simics.SIM_get_object(p.name) for p in preobjs]

    ## Return actual objects
    return objs
