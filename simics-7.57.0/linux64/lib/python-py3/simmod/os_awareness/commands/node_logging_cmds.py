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
from simmod.os_awareness import node_logging

def cancel_logging_on_disable(osa_obj, admin):
    obj_data = osa_obj.object_data
    for node_logging_objs in (obj_data.node_log_creation,
                              obj_data.node_log_destruction,
                              obj_data.node_log_prop_change):
        if node_logging_objs.is_active():
            node_logging_objs.uninstall()

    node_logging.cancel_disable_cb_if_node_logging_inactive(osa_obj)

def install_log_disable_cb(osa_obj):
    obj_data = osa_obj.object_data
    if obj_data.log_disable_cid is not None:
        # Disable notification already active
        return

    obj_data.log_disable_cid = common.get_node_tree_notification(
        osa_obj).notify_disable(cancel_logging_on_disable, osa_obj)

def log_node_update_common(node_logger, disable, no_props):
    common.requires_osa_enabled(node_logger.osa_obj)
    if disable:
        node_logger.disable()
        return

    node_logger.set_root_id()
    node_logger.set_logging_of_props(not no_props)
    if node_logger.is_active():
        raise cli.CliError("Node %s log already active"
                           % node_logger.get_log_type())

    install_log_disable_cb(node_logger.osa_obj)
    node_logger.install_cb()

def log_node_creation(osa_obj, disable, no_props):
    log_node_update_common(osa_obj.object_data.node_log_creation, disable,
                           no_props)

def add_log_node_creation(feature):
    cli.new_unsupported_command(
        'log-node-creation', feature, log_node_creation,
        args = [cli.arg(cli.flag_t, '-disable'),
                cli.arg(cli.flag_t, '-no-properties')],
        cls = 'os_awareness',
        short = 'Log all new nodes that are created',
        doc = node_logging.NodeLoggingCreation.get_doc())

def log_node_destruction(osa_obj, disable, no_props):
    log_node_update_common(osa_obj.object_data.node_log_destruction, disable,
                           no_props)

def add_log_node_destruction(feature):
    cli.new_unsupported_command(
        'log-node-destruction', feature, log_node_destruction,
        args = [cli.arg(cli.flag_t, '-disable'),
                cli.arg(cli.flag_t, '-no-properties')],
        cls = 'os_awareness',
        short = 'Log all nodes that are destroyed',
        doc = node_logging.NodeLoggingDestruction.get_doc())

def log_node_prop_changes(osa_obj, disable):
    log_node_update_common(osa_obj.object_data.node_log_prop_change, disable,
                           None)

def add_log_node_property_changes(feature):
    cli.new_unsupported_command(
        'log-node-property-changes', feature, log_node_prop_changes,
        args = [cli.arg(cli.flag_t, '-disable')],
        cls = 'os_awareness',
        short = 'Log all node property changes',
        doc = node_logging.NodeLoggingPropChange.get_doc())

def add_unsupported(feature):
    add_log_node_creation(feature)
    add_log_node_destruction(feature)
    add_log_node_property_changes(feature)
