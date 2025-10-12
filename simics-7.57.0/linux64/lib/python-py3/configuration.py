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


__all__ = ["OBJECT", "OBJ"]

from cli import doc

next_cpu_number = 0
def get_next_cpu_number():
    global next_cpu_number
    tmp = next_cpu_number
    next_cpu_number += 1
    return tmp

def replace_hyphens(name):
    name = name.replace("-", "_")
    return name

def canonical_attr_name(name):
    name = replace_hyphens(name)

    if not name[:1].isalpha():
        raise Exception(f"Illegal attribute name: '{name}'")

    for n in range(len(name)):
        # Allow $ for components
        if not name[n] in "_$" and not name[n].isalnum():
            raise Exception(f"Illegal attribute name: '{name}'")

    return name

def OBJECT(name, objclass, **attrs):
    name = replace_hyphens(name)
    a = []
    for k in list(attrs.keys()):
        a.append([canonical_attr_name(k), attrs[k]])
    return [name, objclass] + a

def set_attribute(config, objname, attrname, new_value):
    objname = replace_hyphens(objname)
    attrname = canonical_attr_name(attrname)
    for obj in config:
        if obj[0] == objname:
            for attr in obj[2:]:
                if attr[0] == attrname:
                    attr[1] = new_value
                    return
            obj.append([attrname, new_value])
            return
    raise Exception("Object '%s' not found" % objname)

class OBJ(
        metaclass=doc(
            'class for referring to another object, existing or not',
            synopsis = 'OBJ(name)',
            see_also = '<fun>SIM_set_configuration</fun>',
            doc_id = 'simulator python configuration api')):
    '''<fun>OBJ</fun> is only used together with the
    <fun>SIM_set_configuration</fun> API function. <fun>OBJ</fun> is
    used when a configuration attribute needs to refer to another
    object. The other object can either be present in an existing
    configuration, or it can be an object that will be created as a
    result of the same call to <fun>SIM_set_configuration</fun>. See
    <fun>SIM_set_configuration</fun> for an example.'''

    def __init__(self, name):
        self.__conf_object_attribute__ = name
    def __repr__(self):
        return "OBJ('%s')" % self.__conf_object_attribute__
