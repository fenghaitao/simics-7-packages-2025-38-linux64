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
import pyobj

modes = {simics.Sim_CPU_Mode_User: "User mode",
         simics.Sim_CPU_Mode_Supervisor: "Supervisor mode",
         simics.Sim_CPU_Mode_Hypervisor: "Hypervisor mode"}

class MapperTransaction:
    """Handles transactions (begin/end calls) for mappers"""
    def __init__(self, nt_admin, cpu):
        self.cpu = cpu
        self.nt_admin = nt_admin

    def __enter__(self):
        self.tx_id = self.nt_admin.begin(self.cpu)

    def __exit__(self, exc_type, exc_value, traceback):
        self.nt_admin.end(self.tx_id)


class cpumode_software_mapper(pyobj.ConfObject):
    """A mapper for the CPU mode software tracker. It creates a node-tree
    with three levels: root->mode->CPU and activates the CPU leaf node
    in the mode branch whenever the CPU enters that mode."""
    _class_desc = "mapper for the CPU mode tracker"

    class tracker(pyobj.SimpleAttribute(None, 'o', simics.Sim_Attr_Required)):
        """Tracker to create a node-tree representation for"""

    class parent(pyobj.SimpleAttribute(None, 'o', simics.Sim_Attr_Required)):
        """parent object to use, should implement osa_tracker_state_query,
        osa_tracker_state_notification and osa_node_tree_admin interfaces.
        This is usually the osa_admin object."""

    class root_id(pyobj.SimpleAttribute(None, 'i|n')):
        """Root node id"""

    class base_nodes(pyobj.SimpleAttribute(dict, 'D')):
        """Base nodes for all modes"""

    class cpu_and_mode_to_node(pyobj.SimpleAttribute(list, '[[oii]*]')):
        """Mapping from entitys plus mode to a node ID in the node tree on the
        following format: [cpu, mode, node ID]."""

    class entity_to_cpu(pyobj.SimpleAttribute(list, '[[io]*]')):
        """Mapping from entity to cpu on the format [entity ID, cpu]."""

    class enabled(pyobj.SimpleAttribute(False, 'b', simics.Sim_Attr_Pseudo)):
        """Is the mapper enabled"""

    class osa_mapper_admin(pyobj.Interface):
        def tracker_updated(self, initiator, changesets):
            changeset = changesets.get(self._top.tracker.val)
            if not changeset:
                simics.SIM_log_error(self._top.obj, 0,
                                    "No changeset for current tracker")
                return
            self._top.tracker_update(initiator, changeset)

    def tracker_update(self, initiator, changeset):
        added = changeset["added"]
        modified = changeset["modified"]
        removed = changeset["removed"]

        with self.tx(initiator):
            for (entity_id, props) in added.items():
                self.__add_node(entity_id, props)

            for (entity_id, mod_props) in modified.items():
                self.__update_node(entity_id, mod_props)

            for entity_id in removed:
                self.__remove(entity_id)

    def __cpu_from_entity(self, searched_entity_id):
        for (entity_id, cpu) in self.entity_to_cpu.val:
            if entity_id == searched_entity_id:
                return cpu
        return None

    def __cpu_and_mode_is_added(self, search_cpu, search_mode):
        for (node_cpu, node_mode, _) in self.cpu_and_mode_to_node.val:
            if search_cpu == node_cpu and search_mode == node_mode:
                return True
        return False

    def __add_node(self, entity_id, props):
        cpu = props.get("cpu")
        cpu_mode = props.get("mode")
        if cpu is None or cpu_mode is None:
            simics.SIM_log_error(self.obj, 0, "Invalid property update: %s"
                                 % (props,))
            return

        for (mode, base_node) in self.base_nodes.val.items():
            if not self.__cpu_and_mode_is_added(cpu, mode):
                node_name = "%s" % (cpu.name,)
                self.cpu_and_mode_to_node.val.append(
                    [cpu, mode,
                     self.nt_admin.add(base_node, {"name": node_name,
                                                   "cpu_mode": mode})])

        self.entity_to_cpu.val.append([entity_id, cpu])
        self.__activate(cpu, cpu_mode)

    def __update_node(self, entity_id, mod_props):
        mode_prop = mod_props.get("mode")
        if not mode_prop:
            simics.SIM_log_error(self.obj, 0,
                                 "Unknown property modified %s" % (mod_props,))
            return
        cpu = self.__cpu_from_entity(entity_id)
        (old_mode, new_mode) = mode_prop
        if new_mode is None:
            self.__deactivate(cpu, old_mode)
        else:
            self.__activate(cpu, new_mode)

    def __activate(self, cpu, cpu_mode):
        for (node_cpu, node_cpu_mode, node_id) in self.cpu_and_mode_to_node.val:
            if (node_cpu == cpu) and (node_cpu_mode == cpu_mode):
                self.nt_admin.activate(node_id, cpu)
                return

    def __deactivate(self, cpu, cpu_mode):
        for (node_cpu, node_cpu_mode, node_id) in self.cpu_and_mode_to_node.val:
            if node_cpu == cpu and node_cpu_mode == cpu_mode:
                self.nt_admin.deactivate(node_id, cpu)
                return

    # Do not remove any nodes from the node tree except on disable or
    # clear_state.
    def __remove(self, entity_id):
        cpu = self.__cpu_from_entity(entity_id)
        self.entity_to_cpu.val.remove([entity_id, cpu])

    class osa_mapper_control(pyobj.Interface):
        def enable(self):
            return self._top.enable()

        def disable(self):
            self._top.disable()

        def clear_state(self):
            self._top.clear_state()

    class osa_mapper_query(pyobj.Interface):
        pass

    def __add_base_nodes(self):
        # Should be called from within a transaction
        self.root_id.val = self.nt_admin.create(
            self.obj, {"name": "CPU modes"})

        for mode in modes:
            self.base_nodes.val[mode] = self.nt_admin.add(
                self.root_id.val, {"name": modes[mode], "cpu_mode": mode})

    def enable(self):
        simics.SIM_log_info(2, self.obj, 0, "Enabling mapper")
        self.enabled.val = True

        if not self.base_nodes.val:
            self.state_notify.subscribe_tracker(self.obj, self.tracker.val)
            with self.tx(None):
                self.__add_base_nodes()

                added = self.state_query.get_entities(self.tracker.val)
                if added:
                    for (entity_id, props) in added.items():
                        self.__add_node(entity_id, props)

        return True

    def disable(self):
        simics.SIM_log_info(2, self.obj, 0, "Disabling mapper")
        self.__do_clear_state()
        self.enabled.val = False

    def clear_state(self):
        simics.SIM_log_info(2, self.obj, 0, "Clearing mapper state")
        self.__do_clear_state()

    def __do_clear_state(self):
        self.cpu_and_mode_to_node.val = []
        self.entity_to_cpu.val = []

        self.root_id.val = None
        self.base_nodes.val = {}

    def _initialize(self):
        super()._initialize()

    def _finalize(self):
        super()._finalize()
        parent = self.parent.val
        self.nt_admin = parent.iface.osa_node_tree_admin
        self.state_notify = parent.iface.osa_tracker_state_notification
        self.state_query = parent.iface.osa_tracker_state_query

    def tx(self, cpu):
        return MapperTransaction(self.nt_admin, cpu)


class TrackerTransaction:
    """Handles transactions (begin/end calls) for trackers"""
    def __init__(self, state_admin, obj, cpu):
        self.cpu = cpu
        self.obj = obj
        self.state_admin = state_admin

    def __enter__(self):
        self.tx_id = self.state_admin.begin(self.obj, self.cpu)

    def __exit__(self, exc_type, exc_value, traceback):
        self.state_admin.end(self.tx_id)


class cpumode_software_tracker(pyobj.ConfObject):
    """Track mode changes on CPUs"""
    _class_desc = "tracker for CPU mode changes"

    class cpus(pyobj.SimpleAttribute(list, '[[oi]*]')):
        """The CPUs to track and their current mode"""

    class parent(pyobj.SimpleAttribute(None, 'o', simics.Sim_Attr_Required)):
        """The parent object to use, must provide osa_machine_state interfaces
        and osa_tracker_state_admin interface. This is usually the osa_admin
        object."""

    class enabled(pyobj.SimpleAttribute(False, 'b', simics.Sim_Attr_Pseudo)):
        """Is the tracker enabled"""

    class cpu_to_entity_id(pyobj.SimpleAttribute(list, '[[oi]*]')):
        """Maps a given cpu to a unique entity id"""

    class osa_tracker_control(pyobj.Interface):
        """The Control interface used by the admin to control this tracker"""
        def enable(self):
            return self._top.enable()

        def disable(self):
            self._top.disable()

        def clear_state(self):
            self._top.clear_state()

        def add_processor(self, cpu):
            return self._top.add_processor(cpu)

        def remove_processor(self, cpu):
            return self._top.remove_processor(cpu)


    def enable(self):
        simics.SIM_log_info(2, self.obj, 0, "Enabling tracker")
        self.enabled.val = True
        # If enable is called after state has been restored from a
        # checkpoint we need to install callbacks. Otherwise
        # processors will be added after enable and callbacks will be
        # installed then.
        for (cpu, _) in self.cpus.val:
            self.__install_callbacks_on_processor(cpu)

        return True

    def __do_clear_state(self):
        self.remove_all_processors()

    def disable(self):
        simics.SIM_log_info(2, self.obj, 0, "Disabling tracker")
        self.__do_clear_state()
        self.enabled.val = False

    def clear_state(self):
        simics.SIM_log_info(3, self.obj, 0, "Clearing tracker state")
        self.__do_clear_state()

    def __cpu_mode_change(self, cbdata, updated_cpu, old_mode, new_mode):
        for cpu_and_mode in self.cpus.val:
            (cpu, _) = cpu_and_mode
            if cpu == updated_cpu:
                cpu_and_mode[1] = new_mode
                break

        with self.tx(cpu):
            self.state_admin.update(self.__get_entity_id(updated_cpu),
                                    {"mode": new_mode})

    def __install_callbacks_on_processor(self, cpu):
        self.cancel_ids[cpu] = self.machine_notify.notify_mode_change(
            self.obj, cpu, self.__cpu_mode_change, None)

    def add_processor(self, cpu):
        simics.SIM_log_info(3, self.obj, 0, "Adding processor '%s'"
                            % cpu.name)
        self.__install_callbacks_on_processor(cpu)
        cpu_mode = self.machine_query.cpu_mode(self.obj, cpu)
        self.cpus.val.append([cpu, cpu_mode])
        with self.tx(cpu):
            self.state_admin.add(self.__get_entity_id(cpu),
                                 {"cpu": cpu, "mode": cpu_mode})
        return True

    def remove_all_processors(self):
        for (cpu, _) in self.cpus.val:
            self.__clear_state_for_processor(cpu)
        self.cpus.val = []

    def remove_processor(self, cpu):
        simics.SIM_log_info(3, self.obj, 0, "Removing processor '%s'"
                            % cpu.name)
        for old_cpu_and_mode in self.cpus.val:
            if old_cpu_and_mode[0] == cpu:
                self.cpus.val.remove(old_cpu_and_mode)
                break
        self.__clear_state_for_processor(cpu)
        return True

    def __get_entity_id(self, wanted_cpu):
        for (cpu, entity_id) in self.cpu_to_entity_id.val:
            if (wanted_cpu == cpu):
                return entity_id

        new_entity_id = len(self.cpu_to_entity_id.val)
        self.cpu_to_entity_id.val.append([wanted_cpu, new_entity_id])
        return new_entity_id

    def __clear_state_for_processor(self, cpu):
        if cpu not in self.cancel_ids:
            return

        entity_id = self.__get_entity_id(cpu)
        with self.tx(cpu):
            # The mapper does not keep the active node in its state, so if the
            # entity is active mark it as inactive first.
            self.state_admin.update(entity_id, {"mode": None})
            self.state_admin.remove(entity_id)

        cancel_id = self.cancel_ids.pop(cpu)
        self.machine_notify.cancel(self.obj, cancel_id)

    def _initialize(self):
        super()._initialize()
        self.cancel_ids = {}

    def _finalize(self):
        super()._finalize()

        parent = self.parent.val
        self.machine_query = parent.iface.osa_machine_query
        self.machine_notify = parent.iface.osa_machine_notification
        self.state_admin = parent.iface.osa_tracker_state_admin

    def tx(self, cpu):
        return TrackerTransaction(self.state_admin, self.obj, cpu)
