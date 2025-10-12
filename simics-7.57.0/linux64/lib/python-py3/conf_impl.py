# © 2010 Intel Corporation
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
import conf

class namespace:
    pass

classes = namespace()

def canonicalize_name(name):
    return name.replace("-", "_")

def add_object_to_conf(obj):
    '''Add 'obj' to the 'conf' namespace unless it is a hierarchical name.'''
    if '.' in obj.name:
        return
    setattr(conf, obj.name, obj)

def del_object_from_conf(obj):
    '''Delete 'obj' to the 'conf' namespace unless it is a hierarchical name.'''
    if '.' in obj.name:
        return
    delattr(conf, obj.name)

def new_object(dummy, obj):
    add_object_to_conf(obj)

def del_object(dummy, obj):
    try:
        del_object_from_conf(obj)
    except AttributeError as msg:
        print("Failed removing %s from conf namespace: %s" % (obj.name, msg))

def rename_object(dummy, obj, old_name):
    if hasattr(conf, old_name):
        delattr(conf, old_name)
    add_object_to_conf(obj)

def new_class(arg, obj, name):
    setattr(classes, canonicalize_name(name), simics.SIM_get_class(name))

def del_class(arg, obj, name):
    delattr(classes, canonicalize_name(name))

# put it in a try to get documentation working
try:
    simics.SIM_hap_add_callback("Core_Conf_Object_Create", new_object, None)
    simics.SIM_hap_add_callback("Core_Conf_Object_Pre_Delete", del_object, None)
    simics.SIM_hap_add_callback("Core_Conf_Object_Rename", rename_object, None)
    simics.SIM_hap_add_callback("Core_Conf_Class_Register", new_class, None)
    simics.SIM_hap_add_callback("Core_Conf_Class_Unregister", del_class, None)
except NameError:
    pass

# Fill the namespace with existing objects and classes
# SIM_object_iterator not yet available here, since it is defined in Python
for obj in simics.CORE_object_iterator(None):
    new_object(None, obj)

for cls in simics.SIM_get_all_classes():
    new_class(None, None, cls)
