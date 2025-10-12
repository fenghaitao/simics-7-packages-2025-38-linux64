# © 2010 Intel Corporation

import simics

# Extend this function if your device requires any additional attributes to be
# set. It is often sensible to make additional arguments to this function
# optional, and let the function create mock objects if needed.
def create_empty_device_python(name = None):
    '''Create a new empty_device_python object'''
    empty_device_python = simics.pre_conf_object(name, 'empty_device_python')
    simics.SIM_add_configuration([empty_device_python], None)
    return simics.SIM_get_object(empty_device_python.name)
