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

import sys

import conf
import simics

COMMON_DOC = """
The nodes that are evaluated are specified in either in the
<arg>node-pattern</arg> or in the <arg>node-id</arg>. The
<arg>node-pattern</arg> parameter should contain string with a <em>node path
pattern</em>. Node path patterns are described in the <cite>Analyzer User's
Guide</cite>. The <arg>node-id</arg> parameter should contain a node-id.

If <tt>-immediately</tt> is specified, and the node condition is true
when the command is issued, the command take action immediately,
otherwise, the next time the node condition evaluates to true.

If a <arg>cpu</arg> is specified, this command will ignore events on all other
processors."""

CONDITION = """ one or more OS Awareness nodes that
matches <arg>node-pattern</arg> or <arg>node-id</arg> becomes active
(<tt>-active</tt>) or inactive (<tt>-inactive</tt>).
"""

BREAK_DOC = "Stop the simulation when" + CONDITION + COMMON_DOC
RUN_UNTIL_DOC = "Run until" + CONDITION + COMMON_DOC
WAIT_FOR_DOC = ("Postpone execution of a script branch until"
                + CONDITION + COMMON_DOC)
TRACE_DOC = "Trace when" + CONDITION + COMMON_DOC

os_awareness_module = None

def get_os_awareness_module():
    global os_awareness_module
    if not os_awareness_module:
        import simmod
        simics.SIM_load_module('os-awareness')
        os_awareness_module = simmod.os_awareness
    return os_awareness_module

def osa_common():
    return get_os_awareness_module().common

def osa_nodepath():
    return get_os_awareness_module().interfaces.nodepath

class CmdError(Exception):
    def __init__(self, msg):
        self.msg = msg

class Breakpoint:
    def __init__(self, bp_id, osa_obj, node_arg, active, immediately,
                 cpu_obj, once, bp_cb):
        self.check_tracker_enabled(osa_obj)
        self.bp_id = bp_id
        self.osa_obj = osa_obj
        self.root_id = self.get_verified_root_id(osa_obj)
        self.cpu_objs = self.get_verified_cpus(osa_obj, cpu_obj)
        self.cpu_obj = cpu_obj
        self.active = active
        self.once = once
        self.immediately = immediately
        self.node_spec = self.get_node_spec(node_arg)
        self.matching = osa_nodepath().get_all_matching_nodes(
            self.osa_obj, self.root_id, self.node_spec)
        self.notifications = set()
        self.cancelled_notifications = set()
        self.bp_cb = bp_cb
        self.removed = False

    @staticmethod
    def check_tracker_enabled(osa_obj):
        if not osa_obj.requests:
            raise CmdError('This command requires that there is an enabled'
                           ' software tracker')

    @staticmethod
    def get_node_spec(value):
        try:
            node_spec = osa_nodepath().parse_node_spec(value)
        except osa_nodepath().NodePathError as e:
            raise CmdError(
                f'There was an error with the node pattern "{value}".'
                f' Error: "{str(e)}"')
        return node_spec

    @staticmethod
    def get_verified_root_id(osa_obj):
        roots = osa_common().roots(osa_obj)
        if len(roots) != 1:
            raise CmdError('Command requires one root node')
        return roots[0]

    @staticmethod
    def get_verified_cpus(osa_obj, cpu_obj):
        cpu_objs = osa_obj.iface.osa_node_tree_query.get_all_processors()
        if cpu_obj and cpu_obj not in cpu_objs:
            raise CmdError(
                f'The cpu ({cpu_obj.name}) does not belong to this machine'
                f' configuration ({osa_obj.name}).')
        return [cpu_obj] if cpu_obj else cpu_objs

    def is_active(self):
        nt_query = self.osa_obj.iface.osa_node_tree_query
        for cpu in self.cpu_objs:
            current_nodes = nt_query.get_current_nodes(self.root_id, cpu)
            for node_id in self.matching:
                if node_id in current_nodes:
                    return True
        return False

    def notify_iface(self):
        return self.osa_obj.iface.osa_node_tree_notification

    def register_notification(self, node_id, cancel_id):
        self.notifications.add((node_id, cancel_id))

    def unregister_notification(self, node_id, cancel_id):
        self.notifications.remove((node_id, cancel_id))

    def remove_move_cbs(self):
        move_notifications = [x for x in self.notifications if (
            x[0] is not None)]
        for (node_id, cancel_id) in move_notifications:
            self.unregister_notification(node_id, cancel_id)
            self.notify_iface().cancel_notify(cancel_id)

    def nodes_without_children(self):
        result = []
        nt_query = self.osa_obj.iface.osa_node_tree_query
        for node_id in self.matching:
            if node_id == self.root_id:
                return [self.root_id]
            curr_node_id = node_id
            while True:
                curr_node_id = nt_query.get_parent(curr_node_id)
                if curr_node_id in self.matching:
                    break
                if curr_node_id == self.root_id:
                    result.append(node_id)
                    break
        return result

    def move_common_cb(self, arg, osa_obj, trigger_cpu_obj, node_path):
        assert self.osa_obj == osa_obj
        if trigger_cpu_obj not in self.cpu_objs:
            return
        if simics.SIM_is_restoring_state(self.osa_obj):
            return
        if not [x for x in self.matching if x in node_path]:
            return
        self.bp_cb(self)

    def register_cpu_move_cb(self, node_id):
        if self.active:
            notify = self.notify_iface().notify_cpu_move_to
        else:
            notify = self.notify_iface().notify_cpu_move_from
        cancel_id = notify(node_id, self.move_common_cb, None)
        assert cancel_id != 0
        self.register_notification(node_id, cancel_id)

    def node_destroy_cb(self, arg, osa_obj, cpu, destroyed_node_id):
        destroyed = [(x[0], x[1]) for x in self.notifications if (
            x[0] == destroyed_node_id)]
        for (node_id, cancel_id) in destroyed:
            self.unregister_notification(node_id, cancel_id)
            self.notify_iface().cancel_notify(cancel_id)

            # Matching will only contain one of a node_id, but several
            # entries in notifications can contain that node_id.
            if node_id in self.matching:
                self.matching.remove(node_id)

    def register_node_destroy_cb(self, node_id):
        cancel_id = self.notify_iface().notify_destroy(
            node_id, False, self.node_destroy_cb, None)
        assert cancel_id != 0
        self.register_notification(node_id, cancel_id)

    def update_move_cbs(self):
        # Remove old move_{to,from} callbacks as the might not be valid after a
        # property has changed.
        self.remove_move_cbs()

        # Do not install cpu_move callbacks on children, parents callbacks will
        # be call when children changes too. Otherwise several callbacks can
        # be called when one node becomes active.
        # Install move_{to,from} callbacks on existing matches.
        for node_id in self.nodes_without_children():
            self.register_cpu_move_cb(node_id)
            self.register_node_destroy_cb(node_id)

    def updated_props_common(self):
        """Update matching nodes and reinstall callbacks."""
        self.matching = osa_nodepath().get_all_matching_nodes(
            self.osa_obj, self.root_id, self.node_spec)
        self.update_move_cbs()

    def node_create_cb(self, data, osa_obj, cpu, node_id):
        self.updated_props_common()

    def register_node_create_cbs(self):
        cancel_id = self.notify_iface().notify_create(
            self.root_id, True, self.node_create_cb, None)
        assert cancel_id != 0
        self.register_notification(None, cancel_id)

    def node_prop_change_cb(self, data, osa_obj, cpu, node_id, key, old, new):
        self.updated_props_common()

    def register_node_prop_change_cbs(self):
        cancel_id =  self.notify_iface().notify_property_change(
            self.root_id, None, True, self.node_prop_change_cb, None)
        if cancel_id == 0:
            raise CmdError('Could not add property change callbacks.')
        self.register_notification(None, cancel_id)

    def plant(self):
        self.update_move_cbs()
        self.register_node_create_cbs()
        self.register_node_prop_change_cbs()
        if self.immediately and self.active == self.is_active():
            simics.SIM_register_work(self.trigger_immediately, None)

    def unplant(self):
        for (node_id, cancel_id) in set(self.notifications):
            self.unregister_notification(node_id, cancel_id)
            self.notify_iface().cancel_notify(cancel_id)

    def condition_msg(self):
        node_condition = 'activation' if self.active else 'deactivation'
        cpu_cond = f" (only on CPU '{self.cpu_obj.name}')" if (
            self.cpu_obj) else ""
        return (f"{node_condition} of nodes that match '{self.node_spec}'"
                f"{cpu_cond} in '{self.osa_obj.name}'")

    def desc(self):
        return 'Break on ' + self.condition_msg()

    def break_msg(self):
        return self.desc()

    def wait_msg(self):
        return 'Wait for ' + self.desc()

    def trace_msg(self):
        node_condition = 'active' if self.active else 'inactive'
        return f"nodes matching '{self.node_spec}' became {node_condition}."

    def properties(self):
        props = {"temporary": self.once,
                 "planted": True,
                 "object": self.osa_obj.name,
                 "node path": str(self.node_spec),
                 "description": self.desc(),
                 "cpus": sorted([x.name for x in self.cpu_objs])
                 }
        return props

    def trigger_immediately(self, data):
        if not self.removed:
            self.bp_cb(self)

class OSABreakpoints:
    TYPE_DESC = "OS Awareness breakpoints"
    cls = simics.confclass("bp-manager.os_awareness", doc=TYPE_DESC,
                           short_doc=TYPE_DESC, pseudo=True)

    def __init__(self):
        self.bp_data = {}
        self.next_id = 1
        self.notifications = {}

    @cls.objects_finalized
    def objects_finalized(self):
        object_required = True
        recursive = False
        cli_args = [
            [["str_t", "uint_t"], ["node-pattern", "node-id"],
             '1', None, None, "", [None, None]],
            [["flag_t", "flag_t"], ["-active", "-inactive"],
              '1', None, None, "", [None, None]],
            ["flag_t", "-immediately", "?", None, None, "", None],
            [["obj_t", "cpu object", "processor_info"],
              "cpu", "?", None, None, "", None],
        ]
        name = ''
        trigger_desc = 'OS Awareness node changes'
        conf.bp.iface.breakpoint_type.register_type(
            name, self.obj,
            cli_args,
            None, 'osa_component', [
                'break on ' + trigger_desc, BREAK_DOC,
                'run until ' + trigger_desc, RUN_UNTIL_DOC,
                'wait for ' + trigger_desc, WAIT_FOR_DOC,
                'trace ' + trigger_desc, TRACE_DOC],
            object_required, False, recursive)

    def bm_id(self, bp_id):
        return conf.bp.iface.breakpoint_type.get_manager_id(self.obj, bp_id)

    def delete_bp(self, _, bm_id):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        self.remove_bp(bp_id)

    def get_props(self, _, bm_id):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        return self.bp_data[bp_id].properties()

    def create_bp(self, osa_obj, node_spec_arg, active_arg, immediately,
                   cpu_obj, once):
        assert node_spec_arg[2] in ['node-pattern', 'node-id']
        node_arg = node_spec_arg[1]
        active = active_arg[2] == '-active'
        bp_id = self.next_id
        self.next_id += 1
        try:
            bp = Breakpoint(
                bp_id, osa_obj, node_arg, active, immediately, cpu_obj,
                once, self.bp_cb)
            bp.plant()
            self.bp_data[bp_id] = bp
        except CmdError as e:
            print(e.msg, file=sys.stderr)
            return 0

        if not osa_obj in self.notifications:
            self.notifications[osa_obj] = bp.notify_iface().notify_disable(
                self.remove_bp_on_disable, None)
        return bp_id

    def remove_bp_on_disable(self, arg, osa_obj):
        to_remove = []
        for (bp_id, bp_data) in self.bp_data.items():
            if bp_data.osa_obj == osa_obj:
                to_remove.append(bp_id)
        for bp_id in to_remove:
            conf.bp.iface.breakpoint_registration.deleted(self.bm_id(bp_id))

    def bp_cb(self, bp):
        conf.bp.iface.breakpoint_type.trigger(
            self.obj, bp.bp_id, bp.osa_obj,
            bp.trace_msg())
        return 1

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bpm_iface = conf.bp.iface.breakpoint_registration
        return bpm_iface.register_breakpoint(
            self.delete_bp, None, self.get_props, None, None, None,
            None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, _, args):
        (osa_obj, node_spec_arg, active_arg, immediately, cpu_obj, once) = args
        return self.create_bp(
            osa_obj, node_spec_arg, active_arg, immediately, cpu_obj, once)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        osa_obj = bp.osa_obj
        assert osa_obj
        bp.unplant()
        del self.bp_data[bp_id]
        assert osa_obj in self.notifications
        num_bps = len([x for x in self.bp_data.values() if (
            x.osa_obj == osa_obj)])
        if num_bps == 0:
            bp.notify_iface().cancel_notify(self.notifications[osa_obj])
            del self.notifications[osa_obj]
        bp.removed = True

    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return bp.trace_msg()

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bp_id):
        return self.bp_data[bp_id].break_msg()

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        return self.bp_data[bp_id].wait_msg()

def register_osa_breakpoints(bpm_class):
    simics.SIM_register_port(bpm_class, "os_awareness",
                             OSABreakpoints.cls.classname,
                             OSABreakpoints.TYPE_DESC)
