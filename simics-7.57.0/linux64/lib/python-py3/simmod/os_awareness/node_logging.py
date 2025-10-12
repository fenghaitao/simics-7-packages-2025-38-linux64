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


import cli
import simics
from simmod.os_awareness import common

def node_logging_is_active(osa_obj):
    obj_data = osa_obj.object_data
    for node_logging_obj in (obj_data.node_log_creation,
                             obj_data.node_log_destruction,
                             obj_data.node_log_prop_change):
        if node_logging_obj.is_active():
            return True
    return False

def cancel_disable_cb_if_node_logging_inactive(osa_obj):
    obj_data = osa_obj.object_data
    if obj_data.log_disable_cid is None:
        return

    if node_logging_is_active(osa_obj):
        return

    common.get_node_tree_notification(osa_obj).cancel_notify(
        obj_data.log_disable_cid)
    obj_data.log_disable_cid = None

class NodeLogging:
    def __init__(self, osa_obj):
        self.osa_obj = osa_obj
        self.obj_data = osa_obj.object_data
        self.cid = None
        self.log_props = None
        self.root_id = None

    def set_logging_of_props(self, log_props):
        self.log_props = log_props

    def set_root_id(self):
        roots = common.roots(self.osa_obj)
        if not roots:
            raise cli.CliError("No root nodes")
        self.root_id = roots[0]

    @classmethod
    def get_log_type(cls):
        return None

    def uninstall(self):
        common.get_node_tree_notification(
            self.osa_obj).cancel_notify(self.cid)
        self.cid = None

    def disable(self):
        if not self.is_active():
            raise cli.CliError("Node %s log not active" % self.get_log_type())
        self.uninstall()
        cancel_disable_cb_if_node_logging_inactive(self.osa_obj)

    def is_active(self):
        return self.cid is not None

    def cb(self, data, admin, cpu, node_id):
        nt_query = admin.iface.osa_node_tree_query
        props = nt_query.get_node(node_id)
        name = props.pop("name", "unknown")
        msg = "Node %d (%s) %s" % (node_id, name, self.get_log_type())
        if self.log_props:
            msg += ": %s" % (", ".join("%s: %s" % (key, props[key])
                                       for key in sorted(props)),)
        simics.SIM_log_info(1, admin, 0, msg)

    @classmethod
    def get_event_type(cls):
        return None

    @classmethod
    def doc_about(cls):
        return ("Logs all new nodes that are %s the node tree."
                % cls.get_event_type())

    @classmethod
    def doc_disable(cls):
        return ("To disable node %s logging use this command with the"
                " <tt>-disable</tt> flag." % cls.get_log_type())

    @classmethod
    def doc_no_prop(cls):
        return ("The command will display the node properties unless the"
                " <tt>-no-properties</tt> flag is given.")

    @classmethod
    def doc_extra(cls):
        return cls.doc_no_prop()

    @classmethod
    def get_doc(cls):
        return "%s\n\n%s\n\n%s" % (cls.doc_about(), cls.doc_disable(),
                                   cls.doc_extra())

class NodeLoggingCreation(NodeLogging):
    def install_cb(self):
        assert self.root_id is not None
        self.cid = common.get_node_tree_notification(
            self.osa_obj).notify_create(self.root_id, True, self.cb, self)

    @classmethod
    def get_log_type(cls):
        return "creation"

    @classmethod
    def get_event_type(cls):
        return "created in"

class NodeLoggingDestruction(NodeLogging):
    def install_cb(self):
        assert self.root_id is not None
        self.cid = common.get_node_tree_notification(
            self.osa_obj).notify_destroy(self.root_id, True, self.cb, self)

    @classmethod
    def get_log_type(cls):
        return "destruction"

    @classmethod
    def get_event_type(cls):
        return "destroyed from"

class NodeLoggingPropChange(NodeLogging):
    def install_cb(self):
        assert self.root_id is not None
        self.cid = common.get_node_tree_notification(
            self.osa_obj).notify_property_change(
                self.root_id, None, True, self.cb, None)

    @classmethod
    def get_log_type(cls):
        return "property change"

    @classmethod
    def doc_extra(cls):
        return ""

    @classmethod
    def doc_about(cls):
        return ("Logs all nodes that get properties changed in the node tree."
                " The logs will show the properties that changed as well as"
                " the node ID and name (prior to change) of the node.")

    def set_logging_of_props(self, log_props):
        # Not used for property change
        pass

    def cb(self, data, admin, cpu, node_id, key, old_val, new_val):
        nt_query = admin.iface.osa_node_tree_query
        if key == "name":
            name = old_val
        else:
            props = nt_query.get_node(node_id)
            name = props.get("name", "unknown")
        msg = ("Node %d (%s) changed properties for '%s': '%s' -> '%s'"
               % (node_id, name, key, old_val, new_val))
        simics.SIM_log_info(1, admin, 0, msg)
