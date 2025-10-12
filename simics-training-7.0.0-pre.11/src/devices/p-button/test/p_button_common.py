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
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

# Some constants
bx=100
by=100
bw=70
bh=35

# Fake the image_object
class stub_image_object(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()  

    class current_state(pyobj.SimpleAttribute(0,type='i')):
        """Current state driven to the image."""

    class uint64_state(pyobj.Interface):
        def set(self,level):
            simics.SIM_log_info(2, self._up.obj, 0, f"Stub image object got state {level}" )
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


class signal_receive(dev_util.iface("signal")):
    def __init__(self):
        self.raise_count = 0
        self.lower_count = 0
        self.raised = False
    def signal_raise(self, sim_obj):
        # .dev.obj needed since we go via devutils
        simics.SIM_log_info(2, self.dev.obj, 0, "Signal raised!" )
        self.raised = True
        self.raise_count += 1
    def signal_lower(self, sim_obj):
        simics.SIM_log_info(2, self.dev.obj, 0, "Signal lowered!" )
        self.raised = False
        self.lower_count += 1


# Create a test setup
# - Button
# - Fake image display object
# - Fake signal receiver 
# 
def create_p_button(name = "button_under_test"):
    '''Create a test setup'''
    ## Button
    p_button = simics.pre_conf_object(name, 'p_button')
    ## Stub output_image
    stub_o_i = simics.pre_conf_object("stub_o_i", 'stub_image_object')
    p_button.attr.output_image = stub_o_i

    ## Objects
    preobjs = [p_button, stub_o_i]
    simics.SIM_add_configuration(preobjs, None)

    ## Convert preobjs to objs
    objs=[simics.SIM_get_object(p.name) for p in preobjs]

    ## Directly create the stub, not via add_configuration     
    stub_receiver = dev_util.Dev([signal_receive])
    objs[0].output = stub_receiver.obj

    return (objs + [ stub_receiver ])
