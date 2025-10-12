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
import cli
import conf
from enum import IntEnum

class Breakpoint:
    def __init__(self, bm_id, delete, delete_data,
                 get_properties, get_properties_data,
                 set_enabled, set_enabled_data,
                 set_temporary, set_temporary_data,
                 set_ignore_count, set_ignore_count_data):
        self.get_properties = lambda: get_properties(get_properties_data,
                                                     bm_id)
        self.delete = lambda: delete(delete_data, bm_id)

        if set_enabled:
            self.set_enabled = lambda e: set_enabled(set_enabled_data,
                                                     bm_id, e)
        else:
            self.set_enabled = None

        if set_temporary:
            self.set_temporary = lambda o: set_temporary(set_temporary_data,
                                                         bm_id, o)
        else:
            self.set_temporary = None

        if set_ignore_count:
            self.set_ignore_count = lambda c: set_ignore_count(
                set_ignore_count_data, bm_id, c)
        else:
            self.set_ignore_count = None

        self.hit_count = 0
        self.ignore_count = 0
        self.enabled = True

        self.provider = None

next_bp_id = 1
breakpoints = {}  # bp_id -> breakpoint object

def register_breakpoint(mgr, *args):
    global next_bp_id
    bm_id = next_bp_id
    next_bp_id += 1
    breakpoints[bm_id] = Breakpoint(bm_id, *args)
    return bm_id

# bp_id -> (obj, notifier_handle_t)
bp_del_notifiers = {}

def rm_delete_notifier(bm_id):
    # Remove delete notifier if registered
    data = bp_del_notifiers.pop(bm_id, None)
    if data:
        (obj, handle) = data
        simics.SIM_delete_notifier(obj, handle)

def delete_notifier_cb(mgr, obj, bm_id):
    mgr.iface.bp_manager.delete_breakpoint(bm_id)

def delete_notifier_data(bm_id):
    return bp_del_notifiers.get(bm_id)

# Helper function for breakpoint deletion when corresponding
# objects are removed
def add_delete_notifier(bm_id, obj):
    handle = simics.SIM_add_notifier(obj, simics.Sim_Notify_Object_Delete,
                                     conf.bp, delete_notifier_cb, bm_id)
    bp_del_notifiers[bm_id] = (obj, handle)

# bp_manager interface
def list_breakpoints(mgr):
    return sorted(bm_id for (bm_id, bp) in list(breakpoints.items()))

# bp_manager interface
def get_properties(mgr, bm_id):
    props = breakpoints[bm_id].get_properties()
    if 'hit count' not in props:
        props['hit count'] = {'hits': breakpoints[bm_id].hit_count}
    if 'ignore count' not in props:
        props['ignore count'] = breakpoints[bm_id].ignore_count
    if 'enabled' not in props:
        props['enabled'] = breakpoints[bm_id].enabled
    return props

# bp_manager interface
def set_enabled(mgr, bm_id, enabled):
    if breakpoints[bm_id].set_enabled:
        breakpoints[bm_id].set_enabled(enabled)
    elif 'enabled' not in breakpoints[bm_id].get_properties():
        breakpoints[bm_id].enabled = enabled
    else:
        return False
    return True

# bp_manager interface
def set_temporary(mgr, bm_id, temporary):
    if not breakpoints[bm_id].set_temporary:
        return False
    breakpoints[bm_id].set_temporary(temporary)
    return True

# bp_manager interface
def set_ignore_count(mgr, bm_id, ignore_count):
    if breakpoints[bm_id].set_ignore_count:
        breakpoints[bm_id].set_ignore_count(ignore_count)
    elif 'ignore count' not in breakpoints[bm_id].get_properties():
        breakpoints[bm_id].ignore_count = ignore_count
    else:
        return False
    return True

def is_enabled(bm_id):
    assert bm_id in breakpoints
    assert not breakpoints[bm_id].set_enabled
    return breakpoints[bm_id].enabled

def is_ignored(bm_id):
    assert bm_id in breakpoints
    assert not breakpoints[bm_id].set_ignore_count
    return breakpoints[bm_id].ignore_count > 0

class BreakEnum(IntEnum):
    # Type implements its own ignore/enabling
    NA = -1
    # Ignored or disabled breakpoint
    Ignored = 0
    # Break did happen
    Break = 1

def bp_do_break(bm_id, cb):
    # Do nothing if breakpoint handles enabling and ignore count itself
    bp = breakpoints[bm_id]
    if not bp.set_ignore_count and not bp.set_enabled:
        if bp.enabled and bp.ignore_count == 0:
            cb()
            return BreakEnum.Break
        else:
            return BreakEnum.Ignored
    else:
        return BreakEnum.NA

# Helper function for breakpoint_type interface
def bp_triggered(bm_id):
    assert bm_id in breakpoints
    breakpoints[bm_id].hit_count += 1
    if (not breakpoints[bm_id].set_ignore_count
        and (not breakpoints[bm_id].set_enabled
             and breakpoints[bm_id].enabled)):
        breakpoints[bm_id].ignore_count = max(breakpoints[bm_id].ignore_count
                                              - 1, 0)

# Helper function for breakpoint_type interface
def bp_set_provider(bm_id, provider):
    assert bm_id in breakpoints
    breakpoints[bm_id].provider = provider

# bp_manager interface
def bp_get_provider(mgr, bm_id):
    assert bm_id in breakpoints
    return breakpoints[bm_id].provider

from . import bp_type

# bp_manager interface
def delete(mgr, bm_id):
    rm_delete_notifier(bm_id)
    if not bp_type.bp_abort(bm_id):
        breakpoints.pop(bm_id).delete()
        bp_type.bp_mapping_cleanup(bm_id)

def deleted(mgr, bm_id):
    if bm_id in breakpoints:
        rm_delete_notifier(bm_id)
        bp_type.bp_deleted(bm_id)
        del breakpoints[bm_id]

# bp_manager interface
def list_breakpoint_types(mgr):
    return [[c, simics.VT_get_class_description(simics.SIM_object_class(c))]
            for c in bp_type.get_provider_list()]
