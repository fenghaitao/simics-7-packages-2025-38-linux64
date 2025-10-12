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

def get_root_id(osa_obj):
    tracker_comp = osa_obj.current_tracker
    if not tracker_comp:
        return None
    mapper = tracker_comp.iface.osa_tracker_component.get_mapper()
    if not mapper:
        # If the component only contains a tracker, that could have
        # created the node tree.
        mapper = tracker_comp.iface.osa_tracker_component.get_tracker()
        if not mapper:
            return None
    query = osa_obj.iface.osa_node_tree_query
    for root_id in query.get_root_nodes():
        if query.get_mapper(root_id) == mapper:
            return root_id

def get_admin(osa_obj):
    return osa_obj

def get_root_node(osa_obj):
    root_id = get_root_id(osa_obj)
    valid = root_id is not None
    val = root_id if valid else 0
    return simics.maybe_node_id_t(valid=valid, id=val)

def notify_tracker(osa_obj, cb, data):
    cancel_id = osa_obj.object_data.next_callback_id
    osa_obj.object_data.next_callback_id += 1
    osa_obj.object_data.tracker_callbacks[cancel_id] = (cb, data)
    return cancel_id

def cancel_notify(osa_obj, cancel_id):
    if cancel_id in osa_obj.object_data.tracker_callbacks:
        del osa_obj.object_data.tracker_callbacks[cancel_id]

def has_tracker(osa_obj):
    return osa_obj.current_tracker is not None

def get_processors(osa_obj):
    if osa_obj.processors:
        return osa_obj.processors

    parent = simics.SIM_object_parent(osa_obj)
    if not parent:
        return []

    cpu_list = getattr(parent, 'cpu_list', None)
    if cpu_list:
        return cpu_list

    return [o for o in simics.SIM_object_iterator(parent)
            if hasattr(o.iface, 'processor_info')]

def register():
    simics.SIM_register_interface(
        'os_awareness', 'osa_component',
        simics.osa_component_interface_t(
            get_admin = get_admin,
            get_root_node = get_root_node,
            notify_tracker = notify_tracker,
            cancel_notify = cancel_notify,
            has_tracker = has_tracker,
            get_processors = get_processors))
