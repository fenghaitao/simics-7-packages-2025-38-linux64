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

# This file contains code common for pyobj.py and confclass.py.

__all__ = [
    'handle_attr_get_errors',
    'handle_attr_set_errors'
]

import simics

class _SimpleMessageException(Exception):
    pass

def handle_attr_get_errors(desc, gfun, py_obj):
    try:
        r = gfun(py_obj)
    except Exception as msg:
        simics.CORE_attribute_error(
            False, '%s.getter() raised an exception:\n  %s' % (desc, msg))
        return None
    try:
        # see if 'r' can be converted to attr_value_t
        simics.SIM_call_python_function('id', [r])
    except Exception as msg:
        simics.CORE_attribute_error(
            False, ('cannot convert return value %r from'
                    ' %s.getter to attr_value_t:\n  %s') % (
                r, desc, msg))
        return None
    return r

def handle_attr_set_errors(desc, sfun, py_obj, val):
    try:
        ret = sfun(py_obj, val)
    except _SimpleMessageException as msg:
        simics.CORE_attribute_error(False, str(msg))
        return simics.Sim_Set_Illegal_Value
    except Exception as msg:
        simics.CORE_attribute_error(
            False, '%s.setter raised an exception:\n  %s' % (desc, msg))
        return simics.Sim_Set_Illegal_Value
    if ret is None:
        return simics.Sim_Set_Ok
    try:
        i = int(ret)
    except Exception:
        simics.CORE_attribute_error(
            False, ('return value %r from %s.setter cannot be '
                    ' converted to set_error_t') % (ret, desc))
        return simics.Sim_Set_Illegal_Value
    if i < 0 or i >= simics.Sim_Set_Error_Types:
        simics.CORE_attribute_error(
            False, 'return value %r from %s.setter is out of range' % (
                ret, desc))
        return simics.Sim_Set_Illegal_Value
    return i
