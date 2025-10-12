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
import dev_util
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

# Global test objects 
mem = dev_util.Memory()

# Extend this function if your device requires any additional attributes to be
# set. It is often sensible to make additional arguments to this function
# optional, and let the function create mock objects if needed.
def create_p_display(name="display"):
    '''Create a new m_display object'''
    clock = simics.pre_conf_object('clock', 'clock', freq_mhz=1000)
    display = simics.pre_conf_object(
        name,
        'p_display', 
        queue=clock,
        height=500,
        width=1000)
    ## Objects
    preobjs = [display, clock]
    simics.SIM_add_configuration(preobjs, None)

    ## Convert preobjs to objs
    objs=[simics.SIM_get_object(p.name) for p in preobjs]

    return objs
