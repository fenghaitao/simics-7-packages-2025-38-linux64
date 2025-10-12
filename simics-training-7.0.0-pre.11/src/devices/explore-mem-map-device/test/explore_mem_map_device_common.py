# © 2020 Intel Corporation
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

# Extend this function if your device requires any additional attributes to be
# set. It is often sensible to make additional arguments to this function
# optional, and let the function create mock objects if needed.
def create_explore_mem_map_device(name=None):
    '''Create a new explore_mem_map_device object'''
    explore_mem_map_device = simics.pre_conf_object(name, 'explore-mem-map-device')
    simics.SIM_add_configuration([explore_mem_map_device], None)
    return simics.SIM_get_object(explore_mem_map_device.name)
