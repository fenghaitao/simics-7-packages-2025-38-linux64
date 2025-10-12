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
import re

class CmpUtilException(Exception):
    pass

_re_slot_name = re.compile(r'[a-zA-Z_][a-zA-Z_0-9]*\Z')
_re_slot_name_indices = re.compile(r'[a-zA-Z_][a-zA-Z_0-9]*(\[[0-9]+\])*\Z')
def is_valid_slot_name(name):
    return _re_slot_name.match(name)

def is_valid_slot_name_with_indices(name):
    return _re_slot_name_indices.match(name)

def is_valid_slot_value(val):
    return (   isinstance(val, (simics.conf_object_t, simics.pre_conf_object))
            or val is None
            or (isinstance(val, list) and all(is_valid_slot_value(e)
                                              for e in val)))

# Get value in slot. Slot name can be indexed, i.e. foo[0][1] will get
# slot foo with index [0][1].
# cmp: component object
# slot: slot name, can be indexed slot name
def cmp_get_indexed_slot(cmp, slot):
    if cmp.iface.component.has_slot(slot):
        return cmp.iface.component.get_slot_value(slot)
    raise CmpUtilException('found no slot named %s' % slot)

def flatten_slot_dictionary(d, only_conf_obj = False):
    # flatten v and return [(key, value)]
    def flatten(k, v):
        if isinstance(v, list):
            ret = []
            for idx in range(len(v)):
                ret += flatten(k + "[%d]" % idx, v[idx])
            return ret
        if only_conf_obj and not isinstance(v, simics.conf_object_t):
            return []
        return [(k, v)]
    ret = {}
    for (k, v) in d.items():
        for (key, val) in flatten(k, v):
            ret[key] = val
    return ret


def cmp_get_up_connectors(cmp):
    return [o for o in cmp.iface.component.get_slot_objects()
            if (isinstance(o, simics.conf_object_t)
                and hasattr(o.iface, 'connector')
                and (o.iface.connector.direction()
                     == simics.Sim_Connector_Direction_Up))]

def cmp_support_top_level(cmp):
    if cmp_get_up_connectors(cmp):
        raise CmpUtilException('Component has up connectors.')
    if not cmp.cpu_list:
        raise CmpUtilException('Component not aware of any processors.')

# Create a new object name by taking obj.name and adding the suffix.
# Deal with slots and indexed slots intelligently. Examples (with
# suffix "_suff"):
#
#   foo -> foo_suff
#   bar.foo -> bar.foo_suff
#   bar.foo[17] -> bar.foo_suff[17]
#
# If the name is already taken or otherwise doesn't work, raise a
# CmpUtilException with a suitable message.
def derived_object_name(obj, suffix):
    (s1, sep, s) = obj.name.rpartition(".")
    (s2, sep2, s3) = s.partition("[")
    s2 += suffix
    name = s1 + sep + s2 + sep2 + s3
    if simics.VT_get_object_by_name(name):
        raise CmpUtilException('An object named "%s" already exists' % name)
    return name
