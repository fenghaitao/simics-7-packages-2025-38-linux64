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

# Instances of this class is used for the object assigned to
# os_awareness.object_data, to get variables required to re-use existing
# python code from os_awareness.

import cli
from simmod.os_awareness import commands
from simmod.os_awareness import common
from simmod.os_awareness import interfaces
from simmod.os_awareness import node_logging
from simmod.os_awareness import framework

class OsaFrameworkObjectData:
    """This class implements required methods and variables that are needed
    to add existing OSA commands which requires certain python methods.
    Since 'os_awareness' is implemented in C, the variable 'object_data'
    is None, so 'object_data' is set to an instance of this class, which
    has the methods and variables required by the commands."""

    # This member is required when adding or running certain commands, and is
    # required because this class is not a Simics class.
    classname = 'os_awareness'

    def __init__(self, obj):
        self.obj = obj
        self.tracker_callbacks = {}
        self.next_callback_id = 1
        self.enable_req_id = None
        self.log_disable_cid = None
        self.node_log_creation = node_logging.NodeLoggingCreation(self.obj)
        self.node_log_destruction = node_logging.NodeLoggingDestruction(
            self.obj)
        self.node_log_prop_change = node_logging.NodeLoggingPropChange(self.obj)
        self.breakpoints = {}
        self.disable_notification_id = None
        self.sb_breakpoints = {}

    def child_base_name(self):
        return 'tracker'

    def osa_admin(self):
        return self.obj

    def get_parents(self):
        return (self.obj, self.obj, self.obj)

    def register_child(self, child_cmp):
        self.obj.current_tracker = child_cmp
        tracker = child_cmp.iface.osa_tracker_component.get_tracker()
        mapper = child_cmp.iface.osa_tracker_component.get_mapper()
        if tracker:
            self.obj.top_trackers.append(tracker)
        if mapper:
            self.obj.top_mappers.append(mapper)
        for (cb, data) in list(self.tracker_callbacks.values()):
            cb(data)
        self.tracker_callbacks.clear()

    def unregister_child(self, child_cmp):
        tracker = child_cmp.iface.osa_tracker_component.get_tracker()
        mapper = child_cmp.iface.osa_tracker_component.get_mapper()
        if tracker:
            self.obj.top_trackers.remove(tracker)
        if mapper:
            self.obj.top_mappers.remove(mapper)
        self.obj.current_tracker = None

    def check_args(self):
        if self.obj.requests:
            clients = (client for [_, client] in self.obj.requests)
            raise framework.FrameworkException(
                "Can't insert tracker; %s is currently used by %s"
                %  (self.obj.name, ", ".join(clients)))

        if self.obj.current_tracker is not None:
            raise framework.FrameworkException(
                '%s already has a tracker' % (self.obj.name,))

def get_info_cmd(obj):
    tracker_obj = obj.current_tracker
    if tracker_obj:
        tracker_name = tracker_obj.name
        tracker_class = tracker_obj.classname
    else:
        tracker_name = None
        tracker_class = None
    return [("Software",
             [("Tracker", tracker_name),
              ("Tracker class", tracker_class),
              ("CPUs", [x.name for x in common.get_all_processors(obj)])])]

def add_info_cmd():
    cli.new_info_command('os_awareness', get_info_cmd)

def get_status_cmd(obj):
    requests = obj.requests
    tracker_status = ("Software",
                      [("Tracker", "active" if requests else "inactive"),])
    r = [("%d" % r[0], "%s" % r[1]) for r in sorted(requests)]
    tracker_listeners = ("Listeners", r)
    nt_query = obj.iface.osa_node_tree_query
    root_ids = nt_query.get_root_nodes()
    root_ids_with_mapper = []
    for root_id in root_ids:
        mapper = nt_query.get_mapper(root_id)
        root_ids_with_mapper.append((root_id, mapper))
    node_tree = ("Node tree", [("Root node(s)", root_ids_with_mapper)])
    return [tracker_status] + [tracker_listeners] + [node_tree]

def add_status_cmd():
    cli.new_status_command('os_awareness', get_status_cmd)

def add_cmds(unsupported_feature):
    add_info_cmd()
    add_status_cmd()
    commands.node_inspection_cmds.add()
    commands.node_logging_cmds.add_unsupported(unsupported_feature)
    commands.breakpoint_cmds.add_unsupported(unsupported_feature)
    commands.parameter_cmds.add()
    commands.tracker_cmds.add(OsaFrameworkObjectData, 'os_awareness')

def add_interfaces():
    interfaces.osa_component.register()
    interfaces.osa_parameters.register()
    interfaces.nodepath.register_osa_node_path_interface('os_awareness')

def set_object_data(obj):
    obj.object_data = OsaFrameworkObjectData(obj)
