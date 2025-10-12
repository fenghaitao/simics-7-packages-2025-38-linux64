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


import cli
import simics

def roots(obj):
    """Return a list with the root of obj, or an empty list if no root is found.
    """
    root = obj.iface.osa_component.get_root_node()
    return [root.id] if root.valid else []

def get_node_tree_query(obj):
    return obj.iface.osa_node_tree_query

def get_node_tree_notification(obj):
    return obj.iface.osa_node_tree_notification

def get_all_processors(obj):
    nt_query = get_node_tree_query(obj)
    return nt_query.get_all_processors()

def get_osa_admin(obj):
    return obj.iface.osa_component.get_admin()

def requires_osa_enabled(obj):
    if not obj.requests:
        raise cli.CliError("No tracker is enabled")

def requires_osa_disabled(obj):
    if obj.requests:
        raise cli.CliError(
            "Operation not supported with the OSA framework enabled.")

def get_top_obj(obj):
    parent = simics.SIM_object_parent(obj)
    if parent:
        return get_top_obj(parent)
    return obj

class CCError(Exception):
    def __init__(self, msg):
        super(CCError, self).__init__(msg)
