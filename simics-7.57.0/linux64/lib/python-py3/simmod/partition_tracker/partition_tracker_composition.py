# © 2015 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from simmod.os_awareness import framework
from simmod.os_awareness import common
from simmod.os_awareness.commands import tracker_cmds
from simmod.os_awareness.interfaces import nodepath
import pyobj
import cli
import simics

__all__ = ["partition_tracker_comp"]

def get_guest_params(guest_comp, guest_comp_type):
    params_iface = simics.SIM_c_get_interface(guest_comp, "osa_parameters")
    if not params_iface:
        return [False, "%s missing osa_parameters interface" % guest_comp.name]
    [ok, res] = params_iface.get_parameters(True)
    if not ok or not isinstance(res, list) or len(res) != 2:
        return [False, "Bad parameters for %s: %s" % (guest_comp, res)]
    if guest_comp_type != res[0]:
        return [False, "Parameters class for %s does not match actual class"
                % guest_comp.name]
    return [True, res[1]]

def get_guest_comp_type(guest_comp):
    guest_comp_type = None
    if guest_comp is not None:
        if not guest_comp.classname.endswith("_comp"):
            return [False, "Bad class name for '%s', should have suffix '_comp'"
                    % guest_comp]
        guest_comp_type = guest_comp.classname[:-5]
    return [True, guest_comp_type]


class partition_tracker_comp(framework.tracker_composition):
    """A Partition Tracker that can be used to assign only certain processors
    to other trackers."""
    _class_desc = 'partition tracker'
    basename = 'partition_tracker'

    class guests(pyobj.SimpleAttribute(list, '[[iso|n[o*]]*]')):
        """Maps from partitions to guest trackers.
        Format is [id, name, guest composition, [cpus]]"""

    def _get_guest_id(self):
        guest_id = 1
        for guest in self.guests.val:
            if guest[0] >= guest_id:
                guest_id = guest[0] + 1
        return guest_id

    def _tracker_has_state(self):
        return self.get_tracker().root_added

    def _mapper_has_state(self):
        return self.get_mapper().root_id is not None

    def _update_tracker_partitions(self, val):
        # If an update occurs while the tracker or mapper has state
        # but the framework has not been enabled, then clear the state
        # as the system has been modified by the user.
        if ((not self.framework_is_enabled())
            and (self._tracker_has_state() or self._mapper_has_state())):
            self.osa_admin.val.iface.osa_control_v2.clear_state()

        self.obj.tracker_obj.partitions = val

    def _insert_tracker_partition(self, val):
        partitions = self.obj.tracker_obj.partitions.copy()
        partitions.append(val)
        self._update_tracker_partitions(partitions)

    class osa_parameters(pyobj.Interface):
        def get_parameters(self, include_children):
            part_params = []
            for (guest_id, guest_name, guest_comp,
                 guest_cpus) in self._top.guests.val:
                guest_comp_type = None
                guest_params = None
                if guest_comp is not None and include_children:
                    [ok, ret] = get_guest_comp_type(guest_comp)
                    if not ok:
                        return [ok, ret]
                    guest_comp_type = ret
                    [ok, res] = get_guest_params(guest_comp, guest_comp_type)
                    if not ok:
                        return [ok, res]
                    guest_params = res

                cpus_str = [o.name for o in guest_cpus]
                part_params.append([guest_comp_type, guest_id, guest_name,
                                    cpus_str, guest_params])
            params = {"partitions": part_params,
                      "tracker_name": self._top.obj.tracker_obj.tracker_name,
                      "tracker_version": self._top.obj.build_id}
            return [True, [self._top.basename, params]]

        def _get_objects_to_delete(self):
            objs = []
            for (_, _, guest_comp, _) in self._top.guests.val:
                if guest_comp is None:
                    continue
                comp_iface = simics.SIM_c_get_interface(
                    guest_comp, "osa_tracker_component")
                if comp_iface:
                    mapper = comp_iface.get_mapper()
                    if mapper:
                        objs.append(mapper)
                    tracker = comp_iface.get_tracker()
                    if tracker:
                        objs.append(tracker)
                objs.append(guest_comp)
            return objs

        def _clear_partitions(self):
            self._top.guests.val = []
            self._top._update_tracker_partitions([])
            self._top.obj.mapper_obj.mappers = []

        def _guest_comp_exists(self, guest_comp_type):
            if not guest_comp_type:
                # No tracker composition for partition
                return True

            guest_class = guest_comp_type + "_comp"
            try:
                simics.SIM_get_class(guest_class)
            except simics.SimExc_General:
                return False
            return True

        def _params_are_valid(self, partitions):
            if not isinstance(partitions, list):
                return [False, "partitions must be a list"]
            for guest in partitions:
                if not isinstance(guest, list) or len(guest) != 5:
                    return [False, "Invalid partitions in parameters"]
                (guest_comp_type, _, _, cpus_str, guest_params) = guest
                if not self._guest_comp_exists(guest_comp_type):
                    return [False, "Can not find composition for '%s'"
                            % guest_comp_type]
                if guest_params is not None:
                    if guest_comp_type is None:
                        return [False,
                                "Empty composition, but parameters set"]
                    guest_comp = guest_comp_type + "_comp"
                    try:
                        simics.SIM_get_class_interface(guest_comp,
                                                       "osa_parameters")
                    except simics.SimExc_Lookup:
                        return [False, "'%s' composition lacks osa_parameters"
                                " interface" % guest_comp]

                (ok, err_msg) = self._top._cpus_are_ok(cpus_str)
                if not ok:
                    return [False, err_msg]
            return [True, None]

        def _insert_empty_partition(self, partition, cpus_str, part_id):
            cpus = self._top._get_cpus_from_strings(cpus_str)
            self._top.guests.val.append([part_id, partition, None, cpus])
            self._top._insert_tracker_partition([part_id, None, partition,
                                                 cpus])

        def _check_parameters(self, parameters):
            [tracker, params] = parameters
            if not self.is_kind_supported(tracker):
                return [False,
                        'partition tracker cannot handle parameters of type %s'
                        % (tracker,)]

            partitions = params.get("partitions")
            if partitions is None:
                return [False, "No 'partitions' field in parameters"]

            if not isinstance(params.get("tracker_name"), str):
                return [False,
                        "Missing or bad 'tracker_name' field in parameters"]

            [ok, err_msg] = self._params_are_valid(partitions)
            if not ok:
                return [False, err_msg]
            return [True, None]

        def remove_old_objects(self, admin, tx_id):
            old_objs = self._get_objects_to_delete()
            self._clear_partitions()
            if tx_id is not None:
                # Can not have an active transaction in tracker state when
                # deleting objects, as the objects will be referred to then.
                admin.iface.osa_tracker_state_admin.end(tx_id)
            simics.SIM_delete_objects(old_objs)

        def set_parameters(self, parameters):
            [tracker, params] = parameters
            (ok, error_msg) = self._check_parameters(parameters)
            if not ok:
                return [False, error_msg]
            admin = self._top.osa_admin.val
            tx_id = None
            if self._top.framework_is_enabled():
                nt_id = admin.iface.osa_node_tree_admin.begin(None)
                tx_id = admin.iface.osa_tracker_state_admin.begin(
                    self._top.get_tracker(), None)
            self.remove_old_objects(admin, tx_id)
            if self._top.framework_is_enabled():
                tx_id = admin.iface.osa_tracker_state_admin.begin(
                    self._top.get_tracker(), None)
            part_tracker = self._top.get_tracker()
            part_tracker.tracker_name = params.get("tracker_name")
            partitions = params.get("partitions")
            added_objects = []
            for guest in partitions:
                (guest_comp_type, guest_id, guest_name, cpus_str,
                 guest_params) = guest
                base_name = self._top._str_base_name(guest_name)
                if guest_comp_type:
                    guest_obj = framework.insert_tracker(
                        self._top.obj, base_name, guest_comp_type + "_comp",
                        None, (cli.str_t, guest_name, "partition"), cpus_str,
                        guest_id)
                    added_objects.append(guest_obj)
                    # Must set guest objects and cpus before adding parameters,
                    # Linux tracker for example needs some cpus before setting
                    # parameters.
                    if guest_params is not None:
                        # Should already have been checked that
                        # interface exists in class.
                        params_iface = guest_obj.iface.osa_parameters
                        params = [guest_comp_type, guest_params]
                        (ok, err) = params_iface.set_parameters(params)
                        if not ok:
                            self.remove_old_objects(admin, tx_id)
                            if self._top.framework_is_enabled():
                                admin.iface.osa_tracker_state_admin.end(tx_id)
                                admin.iface.osa_node_tree_admin.end(nt_id)
                            return [False, "Could not set parameters for '%s':"
                                    " %s'" % (guest_name, err)]
                else:
                    self._insert_empty_partition(guest_name, cpus_str, guest_id)
            if self._top.framework_is_enabled():
                admin.iface.osa_tracker_state_admin.end(tx_id)
                admin.iface.osa_node_tree_admin.end(nt_id)
            return [True, None]

        def is_kind_supported(self, kind):
            return kind == self._top.basename

    def add_objects(self):
        tracker = simics.SIM_create_object(
            'partition_tracker', f'{self.obj.name}.tracker_obj',
            [['parent', self.tracker_domain.val]])
        simics.SIM_create_object(
            'partition_mapper', f'{self.obj.name}.mapper_obj',
            [['parent', self.mapper_domain.val], ['tracker', tracker]])

    def _info(self):
        tracker_info = [
            [guest[1], [["id", guest[0]], ["cpus", guest[3]]]]
             for guest in self.guests.val]
        tracker_mapper = [[None, [["Tracker", self.obj.tracker_obj],
                                  ["Mapper", self.obj.mapper_obj]]]]

        return tracker_mapper + tracker_info

    def _status(self):
        return [[None, [["Enabled", self.framework_is_enabled()]]]]

    def framework_is_enabled(self):
        return len(self.osa_admin.val.requests) > 0

    def get_tracker(self):
        return self.obj.tracker_obj

    def get_mapper(self):
        return self.obj.mapper_obj

    def get_parents(self):
        return (self.osa_admin.val, self.obj.tracker_obj, self.obj.mapper_obj)

    def _cpus_are_ok(self, cpus_str):
        for cpu_str in cpus_str:
            try:
                cpu = simics.SIM_get_object(cpu_str)
            except simics.SimExc_General:
                return [False, "Object '%s' not found" % cpu_str]
            if not simics.SIM_c_get_interface(cpu, "cycle"):
                return [False,
                        "Object '%s' is not a processor object" % cpu_str]
        return [True, None]

    def _is_empty_node(self, guest_id):
        for guest in self.guests.val:
            if guest[0] == guest_id:
                return guest[2] is None
        raise framework.FrameworkException("Unknown guest")

    def _partition_name_from_id(self, guest_id):
        for guest in self.guests.val:
            if guest[0] == guest_id:
                return guest[1]
        return "unknown"

    def _check_node_args(self, node, cpus_str):
        if not self.framework_is_enabled():
            raise framework.FrameworkException(
                "Can not get node when OSA framework is disabled")
        if cpus_str is not None:
            raise framework.FrameworkException(
                "Can not set cpus when attaching tracker to an existing node")
        guest_id = self._get_mapper_id_from_node_spec_str(node)
        if guest_id is None:
            raise framework.FrameworkException(
                "Could not locate guest for node")
        if not self._is_empty_node(guest_id):
            raise framework.FrameworkException("Partition %s is not empty"
                               % self._partition_name_from_id(guest_id))

    def check_partition_args(self, partition, cpus_str):
        if partition == "":
            raise framework.FrameworkException(
                "Partition name can not be empty")

        if not cpus_str:
            raise framework.FrameworkException(
                "Must set processors when creating a new partition")
        (ok, err_msg) = self._cpus_are_ok(cpus_str)
        if not ok:
            raise framework.FrameworkException(err_msg)
        cpus = self._get_cpus_from_strings(cpus_str)
        for (guest_id, guest_name, _, guest_cpus) in self.guests.val:
            for guest_cpu in guest_cpus:
                if guest_cpu in cpus:
                    raise framework.FrameworkException(
                        "Processor '%s' is already used by guest with"
                        " id=%d ('%s')" % (guest_cpu.name,
                                           guest_id, guest_name))
        if len(set(cpus)) != len(cpus):
            raise framework.FrameworkException(
                "Multiple entries of same processor in cpus")

    def check_args(self, partition_or_node, cpus_str):
        if partition_or_node[0] is nodepath.node_spec_t:
            self._check_node_args(partition_or_node[1], cpus_str)
            return
        self.check_partition_args(partition_or_node[1], cpus_str)

    def _get_child_tracker_and_mapper(self, child_cmp):
        if child_cmp:
            child_tracker = child_cmp.iface.osa_tracker_component.get_tracker()
            child_mapper = child_cmp.iface.osa_tracker_component.get_mapper()
        else:
            child_mapper = None
            child_tracker = None
        return (child_tracker, child_mapper)

    def _get_cpus_from_strings(self, cpus_str):
        if cpus_str is None:
            return []
        return list(map(simics.SIM_get_object, cpus_str))

    # part_id will be set when insert_tracker is called from set_parameters
    def register_child(self, child, partition_or_node, cpus_str, part_id=None):
        if partition_or_node[0] == nodepath.node_spec_t:
            self._register_child_node(child, partition_or_node[1], cpus_str)
            return
        self.register_child_partition(child, partition_or_node[1], cpus_str,
                                      part_id)

    def _register_child_node(self, child, node_spec, cpus_str):
        cpus = self._get_cpus_from_strings(cpus_str)
        try:
            node = nodepath.parse_node_spec(node_spec)
        except nodepath.NodePathError as e:
            raise cli.CliError(str(e))

        self._insert_node(child, node, cpus)

    def register_child_partition(self, child, partition, cpus_str, part_id):
        cpus = self._get_cpus_from_strings(cpus_str)
        if part_id is None:
            part_id = self._get_guest_id()
        (tracker, mapper) = self._get_child_tracker_and_mapper(child)
        try:
            if tracker and mapper:
                self.obj.mapper_obj.mappers.append([tracker, mapper])
            self._insert_tracker_partition([part_id, tracker, partition, cpus])
        except (simics.SimExc_IllegalValue, simics.SimExc_Type,
                simics.SimExc_InterfaceNotFound) as ex:
            raise framework.FrameworkException(str(ex))
        # Guests attribute in composition should be set after partitions
        # attribute in tracker in case the latter can not be set.
        self.guests.val.append([part_id, partition, child, cpus])

    def _first_available_name(self, base_name):
        name = base_name
        i = 1
        while hasattr(self.obj, name) and getattr(self.obj, name):
            name = base_name + "_" + str(i)
            i += 1
        return name

    def _str_base_name(self, partition):
        return self._first_available_name('guest_%s' % (partition,))

    def _node_base_name(self, node_spec):
        try:
            node = nodepath.parse_node_spec(node_spec)
        except nodepath.NodePathError as e:
            raise cli.CliError(str(e))

        guest_name = "unknown"
        guest_id = self._get_mapper_id_from_node_id(self._get_node_id(node))
        for guest in self.guests.val:
            if guest_id == guest[0]:
                guest_name = guest[1]
                break
        return self._first_available_name("guest_" + guest_name)

    def child_base_name(self, partition_or_node, cpus):
        if partition_or_node[0] == cli.str_t:
            return self._str_base_name(partition_or_node[1])
        return self._node_base_name(partition_or_node[1])

    def _get_mapper_id_from_node_spec_str(self, node_spec):
        try:
            node = nodepath.parse_node_spec(node_spec)
        except nodepath.NodePathError as e:
            raise cli.CliError(str(e))

        return self._get_mapper_id_from_node_id(self._get_node_id(node))

    def _get_node_id(self, node):
        admin = self.osa_admin.val
        root_id = self.get_mapper().root_id
        all_nodes = nodepath.get_all_matching_nodes(admin, root_id, node)
        if not all_nodes:
            return None
        return all_nodes[0]

    def _get_mapper_id_from_node_id(self, node_id):
        for partition in self.get_mapper().partitions:
            partition_node_id = partition[4]
            if partition_node_id == node_id:
                return partition[0]
        return None

    def _insert_node(self, child, node, cpus):
        node_id = self._get_node_id(node)
        if node_id is None:
            return
        # Mapper and tracker ID are the same.
        guest_id = self._get_mapper_id_from_node_id(node_id)
        if not guest_id:
            return
        (tracker, mapper) = self._get_child_tracker_and_mapper(child)
        for guest in self.guests.val:
            if guest[0] == guest_id:
                guest[2] = child
                if not cpus:
                    cpus = guest[3]

                self.obj.mapper_obj.mappers.append([tracker, mapper])
                tracker_partitions = list(self.obj.tracker_obj.partitions)
                for tpart in tracker_partitions:
                    if tpart[0] == guest_id:
                        tpart[1] = tracker
                        tpart[3] = cpus
                self._update_tracker_partitions(tracker_partitions)
                return

    def _remove_partition_with_id(self, guest_id):
        guest_index = None
        for (i, guest) in enumerate(self.guests.val):
            if (guest[0] == guest_id):
                guest_index = i
                break

        if guest_index is None:
            raise cli.CliError("Guest with id %d not found in composition"
                               % guest_id)
        guests = list(self.guests.val)
        removed_guest = guests.pop(guest_index)
        self.guests.val = guests
        tracker = self.get_tracker()
        partition_index = None
        for (i, partition) in enumerate(tracker.partitions):
            if (partition[0] == guest_id):
                partition_index = i
                break

        if partition_index is None:
            raise cli.CliError("Partition with id %d not found in tracker '%s'"
                               % (guest_id, tracker.name))
        partitions = list(tracker.partitions)
        partitions.pop(partition_index)
        self._update_tracker_partitions(partitions)

        guest_comp = removed_guest[2]
        if guest_comp:
            mapper = self.get_mapper()
            mappers = list(mapper.mappers)
            guest_tracker = guest_comp.iface.osa_tracker_component.get_tracker()
            for guest_tracker_and_mapper in mappers:
                if guest_tracker_and_mapper[0] == guest_tracker:
                    mappers.remove(guest_tracker_and_mapper)
                    break
            mapper.mappers = mappers
            simics.SIM_delete_object(guest_comp)

    def remove_partition_by_node(self, node_spec):
        if not self.framework_is_enabled():
            raise cli.CliError("No nodes exist when the framework is disabled")
        guest_id = self._get_mapper_id_from_node_spec_str(node_spec)
        if guest_id is None:
            raise cli.CliError("Could not find a partition node for '%s'"
                               % node_spec)
        self._remove_partition_with_id(guest_id)

    def _get_guest_ids_from_name(self, name):
        ids = []
        for guest in self.guests.val:
            if guest[1] == name:
                ids.append(guest[0])
        return ids

    def remove_partition_by_name(self, partition):
        ids = self._get_guest_ids_from_name(partition)
        if not ids:
            raise cli.CliError("Could not find a partition named '%s'"
                               % partition)
        if len(ids) != 1:
            raise cli.CliError("Found %d partitions named '%s'" % (len(ids),
                                                                   partition))
        self._remove_partition_with_id(ids[0])

    def _part_id_exists(self, part_id):
        for guest in self.guests.val:
            if guest[0] == part_id:
                return True
        return False

    def remove_partition_by_id(self, part_id):
        if not self._part_id_exists(part_id):
            raise cli.CliError("No partition with id %d" % part_id)
        self._remove_partition_with_id(part_id)

    @classmethod
    def insert_cmd_extra_doc(cls):
        return """The <arg>partition</arg> argument is used to specify the
        partition name. This is required if the partition is not inserted on an
        empty node. In that case the <arg>node</arg> argument is used to insert
        a tracker on an existing node for an empty partition. The
        <arg>node</arg> should be given as a node path pattern or a node
        number.

        The <arg>cpus</arg> argument is a list of processors to be
        assigned to the added partition. This argument is required if
        the <arg>partition</arg> argument is used and should only be
        used in that case, when then <arg>node</arg> argument is used
        that partition should already have processors assigned to it.
        """

def insert_empty_partition_cmd(comp, partition, cpus_str):
    part_cmp = comp.object_data
    try:
        part_cmp.check_partition_args(partition, cpus_str)
        part_cmp.register_child_partition(None, partition, cpus_str, None)
    except framework.FrameworkException as ex:
        raise cli.CliError(str(ex))

tracker_cmds.add_insert_tracker_cmd(
    partition_tracker_comp,
    [cli.arg((cli.str_t, nodepath.node_spec_t),
             ("partition", "node")),
     cli.arg(cli.list_t, "cpus", "?")])

cli.new_command("insert-empty-partition", insert_empty_partition_cmd,
                ([cli.arg(cli.str_t, "partition"),
                  cli.arg(cli.list_t, "cpus")]),
                cls = partition_tracker_comp.__name__,
                short = ("insert a partition that is not associated with any"
                         " tracker"),
                doc = """
Add a new partition that is not associated with any tracker.

<arg>partition</arg> specifies the name of the partition and <arg>cpus</arg>
specifies the processors that are assigned to the partition.

Run the <cmd class="partition_tracker_comp">insert-tracker</cmd> with the
<arg>node</arg> argument to insert a tracker on the empty partition.""")

def remove_partition_cmd(comp, partition_or_node):
    part_cmp = comp.object_data
    if partition_or_node[0] == nodepath.node_spec_t:
        part_cmp.remove_partition_by_node(partition_or_node[1])
        return
    elif partition_or_node[0] == cli.str_t:
        part_cmp.remove_partition_by_name(partition_or_node[1])
        return
    part_cmp.remove_partition_by_id(partition_or_node[1])

cli.new_command("remove-partition", remove_partition_cmd,
                ([cli.arg((cli.str_t, nodepath.node_spec_t, cli.int_t),
                          ("partition", "node", "id"))]),
                cls = partition_tracker_comp.__name__,
                short = "remove a partition",
                doc = """
Remove a partition by selecting either a <arg>partition</arg> name,
a <arg>node</arg> specification or a partition <arg>id</arg>.""")
