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


import conf
from simics import *
from configuration import OBJECT
from . import common
from . import probes
from . import probe_type_classes
from . import sketch

from .probe_cache import cached_probe_read

def new_instances(new, old):
    return set(new).difference(old)


# Abstract base classes
# A non-persistent factor can be removed once it has created an object
class BaseProbeFactory:
    __slots__ = ('name', 'created', 'persistent')
    def __init__(self, name, persistent=True):
        self.name = name
        self.created = 0
        self.persistent = persistent

    def create_sketch(self, cls, name, attrs):
        new = sketch.new(cls, name, attrs)
        if new:
            self.created += 1
        return new

    def is_persistent(self):
        return self.persistent

val = "s|i|o|n|b|[s*]"
key_value_attr_type = (
    "[[i"                       # Key
    f"{val}|"                   # Ordinary value
    f"[[i{val}]*]|"             # Global/cell sums, kv-list - deprecated
    f"[[[i{val}]*]*]"           # Aggregates list of kv-lists
    "]*]")

class base_probe_confclass:
    # Add the "cprops" attribute which passes the
    # probe properties list
    cls = confclass()
    cls.attr.cprops(key_value_attr_type, default = [],
                    doc = "Probe properties")

# Factory classes for creating probes

# doc
class IfaceProbeFactory(BaseProbeFactory):
    __slots__ = ('ifaces', 'cls', 'seen_objs')
    def __init__(self, name, ifaces, cls):
        super().__init__(name)
        self.ifaces = ifaces    # List of ifaces, all must match
        self.cls = cls
        self.seen_objs = set()

    def create(self):
        objs = list(SIM_object_iterator_for_interface(self.ifaces))
        new_objs = []
        for obj in new_instances(objs, self.seen_objs):
            new_objs += self.create_sketch(
                self.cls, obj.name + f".probes.{self.name}",
                [["owner", obj]])
        self.seen_objs = objs
        return new_objs

class TimeScheduledProbeFactory(BaseProbeFactory):
    __slots__ = ('iface', 'cls', 'seen_objs')
    def __init__(self):
        super().__init__("cpu.time.schedule")
        self.iface = "execute"
        self.cls = "probe_execute_load"
        self.seen_objs = set()

    def create(self):
        objs = set(SIM_object_iterator_for_interface([self.iface]))
        new_objs = []
        for obj in new_instances(objs, self.seen_objs):
            if hasattr(obj, "do_not_schedule") and obj.do_not_schedule:
                continue
            new_objs += self.create_sketch(
                self.cls, obj.name + f".probes.{self.name}",
                [["owner", obj]])
        self.seen_objs = objs
        return new_objs

# Creates a probe class which handles multiple cell io-access probes
class CellIoAccessProbeFactory(BaseProbeFactory):
    __slots__ = ('seen_objs')
    def __init__(self):
        super().__init__("cell_io_access_probes")
        self.seen_objs = set()

    def create(self):
        objs = set(SIM_object_iterator_for_interface(["cell_inspection"]))
        new_objs = []
        for o in new_instances(objs, self.seen_objs):
            new_objs += self.create_sketch(
                "probe_cell_io_access",
                f"{o.name}.probes.{self.name}",
                [["cell_owner", o]])
        self.seen_objs = objs
        return new_objs

class CpuDisabledFactory(BaseProbeFactory):
    __slots__ = ('seen_objs')
    disabled_attributes = {
        "enabled_flag" : [False, "User-disable"],
        "reset_asserted" : [True, "Reset"],
        "externally_disabled" : [True, "External"],
        "thread_disabled" : [True, "Thread"],
        "microcode_disabled" : [True, "Microcode"],
        "debugger_disabled" : [True, "Debugger"],
        "non_architecturally_disabled" : [True, "NonArch"]
    }

    def __init__(self):
        super().__init__("cpu.disabled_reason")
        self.seen_objs = set()

    def has_disable_attr(self, obj):
        for attr in self.disabled_attributes:
            if not hasattr(obj, attr):
                return False
        return True

    def create(self):
        objs = set(SIM_object_iterator_for_interface(["processor_info"]))

        new_objs = []
        for obj in new_instances(objs, self.seen_objs):
            if not self.has_disable_attr(obj):
                continue

            new_objs += self.create_sketch(
                "probe_cpu_disabled_reason", obj.name + f".probes.{self.name}",
                [["owner", obj]])
        self.seen_objs = objs
        return new_objs

    class simics_class_disabled_probe:
        cls = confclass("probe_cpu_disabled_reason", pseudo = True,
                        short_doc = "internal class",
                        doc = "Probe class for disabled status.")
        cls.attr.owner("o", default = None, doc = "The cpu")

        def get_disable_str(self):
            status = []
            attrs = CpuDisabledFactory.disabled_attributes
            for attr in attrs:
                value = getattr(self.owner, attr)
                (active, disable_str) = attrs[attr]
                if value == active:
                    status.append(disable_str)

            if hasattr(self.owner.iface, "x86_reg_access"):
                cpu = self.owner
                act_state = cpu.iface.x86_reg_access.get_activity_state()
                if act_state != X86_Activity_Normal:
                    act_str = {
                        X86_Activity_Normal: None,
                        X86_Activity_Hlt: "HLT",
                        X86_Activity_Shutdown: "Shutdown",
                        X86_Activity_Wait_For_SIPI: "Wait SIPI",
                        X86_Activity_Cx_State: "Cx",
                        X86_Activity_MWait: "MWait",
                        X86_Activity_Senter_Sleep_State: "SENTER sleep"
                    }[act_state]
                    status.append(act_str)
            return ",".join(status)

        @cls.iface.probe
        def value(self):
            return self.get_disable_str()

        @cls.iface.probe
        def properties(self):
            return common.listify(
                [(Probe_Key_Kind, "cpu.disabled_reason"),
                 (Probe_Key_Display_Name, "Disabled reason"),
                 (Probe_Key_Description,
                  "Reports the current reason why a processor is not"
                  " running instructions (as a string)"),
                 (Probe_Key_Type, "string"),
                 (Probe_Key_Categories, ["cpu", "disabled"]),
                 (Probe_Key_Width, 15),
                 (Probe_Key_Owner_Object, self.owner)])

class InterpreterProbeFactory(BaseProbeFactory):
    __slots__ = ('cls', 'seen_objs')
    def __init__(self):
        super().__init__("cpu.exec_mode.interpreter_steps")
        self.cls = "probe_interpreter_steps"
        self.seen_objs = set()

    def create(self):
        objs = set(SIM_object_iterator_for_interface(["step"]))
        new_objs = []
        for obj in new_instances(objs, self.seen_objs):
            new_objs += self.create_sketch(
                self.cls, obj.name + f".probes.{self.name}",
                [["owner", obj]])
        self.seen_objs = objs
        return new_objs

# TODO: Move this to the CPU itself
class TurboProbeFactory(BaseProbeFactory):
    __slots__ = ('seen_objs')
    def __init__(self):
        super().__init__("turbo_stat")
        self.seen_objs = set()

    def create(self):
        new_objs = []
        objs = set(SIM_object_iterator_for_interface(["processor_info"]))

        for obj in new_instances(objs, self.seen_objs):
            if hasattr(obj, "turbo_stat"):
                new_objs += self.create_sketch(
                    "probe_turbo_stat", obj.name + f".probes.{self.name}",
                    [["owner", obj]])
        self.seen_objs = objs
        return new_objs

import vmp_common

class VmpProbeFactory(BaseProbeFactory):
    __slots__ = ('simics_cls', 'vm_space_name', 'vm_space_index',
                 'vm_prefix', 'seen_objs')

    def __init__(self, name, simics_cls, vm_space_name, vm_space_index,
                 vm_prefix):
        super().__init__(name)
        self.simics_cls = simics_cls
        self.vm_space_name = vm_space_name
        self.vm_space_index = vm_space_index
        self.vm_prefix = vm_prefix
        self.seen_objs = set()

    def create(self):
        new_objs = []
        objs = set(SIM_object_iterator_for_interface(["processor_info"]))

        for obj in new_instances(objs, self.seen_objs):
            if hasattr(obj, "vm_monitor_statistics"):
                new_objs += self.create_sketch(
                    self.simics_cls,
                    obj.name + f".probes.{self.name}",
                    [["owner", obj],
                     ["vm_space_name", self.vm_space_name],
                     ["vm_space_index", self.vm_space_index],
                     ["vm_prefix", self.vm_prefix]])
        self.seen_objs = objs
        return new_objs

    class VmpNameTranslate:
        __slots__ = ('translate_dict', 'probe_idx_to_name')

        def get_name(self, probe_idx):
            # Use a cached name if it exists
            if probe_idx in self.probe_idx_to_name:
                return self.probe_idx_to_name[probe_idx]

            # Create a new suitable name for the
            vm_idx = self.translate_dict[probe_idx]
            name = self.names[vm_idx]
            assert name.startswith(self.vm_prefix)
            name =  name[len(self.vm_prefix):].lower()
            name = name.replace(" ", "_")
            name = name.replace("-", "_")
            name = name.replace("__", "_")
            name = name.replace("__", "_")
            name = name.replace("#", "num_")
            self.probe_idx_to_name[probe_idx] = name
            return name

        @cached_probe_read
        def cached_vmp_stats(self):
            if not self.owner.init_vm_monitor:
                return None
            # Return entire big attribute, now as a list, shared by cache
            return list(self.owner.vm_monitor_statistics)

        def get_value(self, probe_idx):
            stats = self.cached_vmp_stats()
            if stats == None:   # vmp not active
                return 0

            vm_idx = self.translate_dict[probe_idx]
            try:
                return stats[self.vm_space_index][vm_idx]
            except IndexError:
                return 0

        def setup_translation_dict_from_probe_index_to_vm_index(self):
            self.translate_dict = {}
            self.probe_idx_to_name = {} # Populated later in get_name()
            n = 0
            for i in sorted(self.names.keys()):
                self.translate_dict[n] = i
                n += 1

    class simics_class_vmp_probe_group(VmpNameTranslate):
        __slots__ = ('owner', 'vm_space_name', 'vm_space_index',
                     'vm_prefix', 'names', 'vmp_space', 'obj')
        cls = confclass("probe_vmp_probe_group", pseudo = True,
                        short_doc = "internal class",
                        doc = "Probe class for vmp statistics.")
        cls.attr.owner("o", default = None, doc = "The cpu")
        cls.attr.vm_space_name("s", default = None,
                               doc = "The vm probe space name to use")
        cls.attr.vm_space_index("i", default = None,
                                doc = "The vm probe space index to use")
        cls.attr.vm_prefix("s", default = None,
                           doc = "Probe prefix")

        @cls.finalize
        def finalize_instance(self):
            vm_dict = getattr(vmp_common.VmpEventNames, self.vm_space_name)
            self.names = vm_dict.copy()

            self.setup_translation_dict_from_probe_index_to_vm_index()
            self.vmp_space = f"{self.vm_space_name[1:]}"

        @cls.iface.probe_index
        def num_indices(self):
            return len(self.names)

        @cls.iface.probe_index
        def value(self, probe_idx):
            return self.get_value(probe_idx)

        @cls.iface.probe_index
        def properties(self, probe_idx):
            name = f"cpu.vmp.{self.vmp_space}." + self.get_name(probe_idx)
            return common.listify(
                [(Probe_Key_Kind, name),
                 (Probe_Key_Display_Name, name[4:]),
                 (Probe_Key_Description, ""),
                 (Probe_Key_Type, "int"),
                 (Probe_Key_Categories, ["vmp", "internals"]),
                 (Probe_Key_Width, 10),
                 (Probe_Key_Owner_Object, self.owner)])


    class simics_class_vmp_probe_group_total:
        __slots__ = ('owner', 'vm_space_name', 'vm_space_index',
                     'vm_prefix', 'names', 'vmp_space', 'obj')

        cls = confclass("probe_vmp_probe_group_total", pseudo = True,
                        short_doc = "internal class",
                        doc = "Probe class for vmp total statistics.")
        cls.attr.owner("o", default = None, doc = "The cpu")
        cls.attr.vm_space_name("s", default = None,
                               doc = "The vm probe space to use")
        cls.attr.vm_space_index("i", default = None,
                                doc = "The vm probe space to use")
        cls.attr.vm_prefix("s", default = None,
                           doc = "Probe prefix")

        @cls.finalize
        def finalize_instance(self):
            self.vmp_space = f"{self.vm_space_name[1:]}"

        @cls.iface.probe
        def value(self):
            if not self.owner.init_vm_monitor:
                return 0
            return sum(self.owner.vm_monitor_statistics[self.vm_space_index])

        @cls.iface.probe
        def properties(self):
            name = f"cpu.vmp.{self.vmp_space}.total"
            return common.listify(
                [(Probe_Key_Kind, name),
                 (Probe_Key_Display_Name, name[4:]),
                 (Probe_Key_Description,
                  f"Total number of {self.vmp_space}"),
                 (Probe_Key_Type, "int"),
                 (Probe_Key_Categories, ["vmp", "performance"]),
                 (Probe_Key_Width, 10),
                 (Probe_Key_Owner_Object, self.owner)])

    class simics_class_vmp_probe_group_histogram(VmpNameTranslate):
        __slots__ = ('owner', 'vm_space_name', 'vm_space_index',
                     'vm_prefix', 'names', 'vmp_space', 'obj')
        cls = confclass("probe_vmp_probe_group_histogram", pseudo = True,
                        short_doc = "internal class",
                        doc = "Probe class for vmp histogram statistics.")
        cls.attr.owner("o", default = None, doc = "The cpu")
        cls.attr.vm_space_name("s", default = None,
                               doc = "The vm probe space to use")
        cls.attr.vm_space_index("i", default = None,
                                doc = "The vm probe space to use")
        cls.attr.vm_prefix("s", default = None,
                           doc = "Probe prefix")

        @cls.finalize
        def finalize_instance(self):
            vm_dict = getattr(vmp_common.VmpEventNames, self.vm_space_name)
            self.names = vm_dict.copy()
            self.setup_translation_dict_from_probe_index_to_vm_index()
            self.vmp_space = f"{self.vm_space_name[1:]}"

        @cls.iface.probe
        def value(self):
            return [
                [self.get_name(i), self.get_value(i)]
                for i in range(len(self.names))]

        @cls.iface.probe
        def properties(self):
            name = f"cpu.vmp.{self.vmp_space}.histogram"
            return common.listify(
                [(Probe_Key_Kind, name),
                 (Probe_Key_Display_Name, name[4:]),
                 (Probe_Key_Description,
                  f"Histogram of {self.vmp_space}"),
                 (Probe_Key_Type, "histogram"),
                 (Probe_Key_Categories, ["vmp", "performance"]),
                 (Probe_Key_Width, 40),
                 (Probe_Key_Owner_Object, self.owner),
                 (Probe_Key_Aggregates, [
                     [
                         (Probe_Key_Kind,
                          f"cell.vmp.{self.vmp_space}.histogram"),
                         (Probe_Key_Aggregate_Scope, "cell"),
                         (Probe_Key_Aggregate_Function, "sum"),
                         (Probe_Key_Description,
                          f"Cell histogram of {self.vmp_space}.")
                     ],
                     [
                         (Probe_Key_Kind, f"sim.vmp.{self.vmp_space}.histogram"),
                         (Probe_Key_Aggregate_Scope, "global"),
                         (Probe_Key_Owner_Object, conf.sim),
                         (Probe_Key_Aggregate_Function, "sum"),
                         (Probe_Key_Description,
                          f"Total histogram of {self.vmp_space}")
                     ]
                 ])])


# doc
class AttributeProbeFactory(BaseProbeFactory):
    __slots__ = ('class_name', 'attr_name', 'probe_kind',
                 'keys', 'seen_objs', 'valid_attrs')

    def __init__(self, class_name, attr_name, probe_kind, keys = []):
        super().__init__(class_name)
        self.class_name = class_name
        self.attr_name = attr_name
        self.probe_kind = probe_kind
        self.keys = keys
        self.seen_objs = set()
        self.valid_attrs = probe_type_classes.attr_type_to_probe_type

    def get_attr_type(self, cls, attribute):
        for info in cls.attributes:
            if info[0] == attribute:
                return info[-1]
        return None

    def create(self):
        new_objs = []
        objs = set(SIM_object_iterator_for_class(self.class_name))
        for obj in new_instances(objs, self.seen_objs):
            if hasattr(obj, self.attr_name):
                t = self.get_attr_type(SIM_object_class(obj), self.attr_name)
                if t in self.valid_attrs:
                    new_objs += self.create_sketch(
                        "probe_attribute", f"{obj.name}.probes.{self.probe_kind}",
                        [["owner", obj], ["attr_name", self.attr_name],
                         ["probe_type", self.valid_attrs[t]],
                         ["cprops", common.listify(self.keys)]])
                else:
                    SIM_log_info(
                        1, conf.probes, 0,
                        f"Cannot create probe '{obj.name}:{self.probe_kind}'"
                        f" unsupported attribute type: {t}")
        self.seen_objs = objs
        return new_objs

    class simics_class(base_probe_confclass):
        cls = confclass("probe_attribute", pseudo = True,
                        parent = base_probe_confclass.cls,
                        short_doc = "internal class",
                        doc = "Probe class for attribute encapsulation.")

        cls.attr.owner("o", default = None, doc = "The attribute object")
        cls.attr.probe_type("s", default = None, doc = "The probe type")
        cls.attr.attr_name("s", default = None, doc = "The attribute name")

        @cls.iface.probe
        def value(self):
            return getattr(self.owner, self.attr_name)

        @cls.iface.probe
        def properties(self):
            default =  [(Probe_Key_Type, self.probe_type),
                        (Probe_Key_Categories, ["attribute"]),
                        (Probe_Key_Width, 12),
                        (Probe_Key_Definition,
                         f"attr({self.owner.classname}.{self.attr_name})"),
                        (Probe_Key_Owner_Object, self.owner)]
            return common.merge_keys(default, self.cprops)

# doc
class AggregateProbeFactory(BaseProbeFactory):
    __slots__ = ('aggregate_name', 'probe_kind', 'function',
                 'object_names', 'keys')

    def __init__(self, aggregate_name, probe_kind, function,
                 object_names=[], # Only aggregate these objects (optional)
                 keys=[]):
        # A global aggregator factory be removed once it has created a probe
        super().__init__(aggregate_name, persistent=False)
        self.aggregate_name = aggregate_name
        self.probe_kind = probe_kind
        self.function = function
        self.object_names = object_names
        self.keys = keys
        self.created = False

    def create(self):
        assert self.created == 0 # We should only be called once

        # If owner is not explicitly set in the global aggregate
        # (and not to None) use conf.sim instead.
        default_object = conf.sim
        owners = [value for (key, value) in self.keys
                  if (key == Probe_Key_Owner_Object
                      and value != None)]
        o = owners[0] if owners else default_object
        new_objs = self.create_sketch(
            "probe_aggregator", f"{o.name}.probes.{self.aggregate_name}",
            [["aggregate_name", self.aggregate_name],
             ["probe_kind", self.probe_kind],
             ["function_string", self.function],
             ["object_names", self.object_names],
             ["cprops", common.listify(self.keys)]])
        return new_objs

class CellAggregateProbeFactory(BaseProbeFactory):
    __slots__ = ('aggregate_name', 'probe_kind', 'function',
                 'objects', 'keys', 'iface', 'seen_objs')
    def __init__(self, aggregate_name, probe_kind, function, keys=[]):
        super().__init__(aggregate_name)
        self.aggregate_name = aggregate_name
        self.probe_kind = probe_kind
        self.function = function
        self.keys = keys
        self.iface = "cell_inspection"
        self.seen_objs = set()

    def create(self):
        objs = set(SIM_object_iterator_for_interface([self.iface]))
        new_objs = []
        for o in new_instances(objs, self.seen_objs):
            new_objs += self.create_sketch(
                "probe_aggregator",
                f"{o.name}.probes.{self.aggregate_name}",
                [["aggregate_name", self.aggregate_name],
                 ["probe_kind", self.probe_kind],
                 ["function_string", self.function],
                 ["cell_owner", o],
                 ["cprops", common.listify(self.keys)]])
        self.seen_objs = objs
        return new_objs

# Helper classes returning which proxy-probe objects to aggregate over.
class CellCollector:
    __slots__ = ('probe_kind', 'cell_owner')
    def __init__(self, probe_kind, cell_owner):
        self.probe_kind = probe_kind
        self.cell_owner = cell_owner

    def proxy_probes_to_aggregate(self):
        return list(
            probes.get_cell_probes(self.cell_owner, self.probe_kind))

class GlobalCollector:
    __slots__ = ('probe_kind')
    def __init__(self, probe_kind):
        self.probe_kind = probe_kind

    def proxy_probes_to_aggregate(self):
        return list(probes.get_probes(self.probe_kind))

class ObjSetCollector:
    __slots__ = ('probe_kind', 'object_probes')
    def __init__(self, probe_kind, objects):
        self.probe_kind = probe_kind
        self.object_probes = [
            probes.get_probe_by_object(self.probe_kind, o)
            for o in objects]

    def proxy_probes_to_aggregate(self):
        return self.object_probes


# Generic Simics class for both global, cell or selected object aggregate
class simics_class:
    cls = confclass("probe_aggregator", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for aggregate of probes.")
    cls.attr.aggregate_name("s", default = None, doc = "The aggregate name")
    cls.attr.probe_kind("s", default = None, doc = "The probe-kind")
    cls.attr.function_string("s", default = None, doc = "The probe function")
    cls.attr.cell_owner("o|n", default = None, doc = "The cell owner")
    cls.attr.object_names("[s*]", default = [],
                          doc = "Restricted set of objects to aggregate")
    cls.attr.cprops(key_value_attr_type, default = [],
                    doc = "Probe properties")

    @cls.finalize
    def finalize_instance(self):
        self.users = 0
        self.subscribed = set()  # Child-probes already subscribed to
        self.aggregate_func = None
        self.aggregate_value_map_func = None
        self.objects = [SIM_get_object(o) for o in self.object_names]
        # Depending on configuration, use the correct selector class
        # returning the set of proxy-probes to aggregate.
        if self.objects:
            assert self.cell_owner == None
            self.collector = ObjSetCollector(self.probe_kind, self.objects)
            obj_str = ",".join([o.name for o in self.objects])
            self.def_str = f"{self.function_string}(OBJ({obj_str}):{self.probe_kind})"
            probes.register_dependencies(self.obj.name, self.objects)
        elif self.cell_owner:
            self.collector = CellCollector(self.probe_kind, self.cell_owner)
            self.def_str = f"{self.function_string}(CELL_OBJS({self.probe_kind}))"
        else:
            self.collector = GlobalCollector(self.probe_kind)
            self.def_str = f"{self.function_string}(ALL({self.probe_kind}))"

    @cls.iface.probe_subscribe
    def subscribe(self):
        probes_to_aggregate = self.collector.proxy_probes_to_aggregate()
        self.subscribe_to_new_probes(probes_to_aggregate)
        self.users += 1

    @cls.iface.probe_subscribe
    def unsubscribe(self):
        if self.users > 0:
            self.users -= 1
        if self.users == 0:
            # Some probes might have been deleted in the "subscribed" set.
            child_probes = probes.get_probes(self.probe_kind)
            deleted = self.subscribed.difference(child_probes)
            for p in self.subscribed - deleted: # Skip deleted probe proxies
                p.unsubscribe()
            self.subscribed = set()

    @cls.iface.probe_subscribe
    def num_subscribers(self):
        return self.users

    def subscribe_to_new_probes(self, probes_to_aggregate):
        for p in probes_to_aggregate:
            if p not in self.subscribed:
                self.subscribed.add(p)
                p.subscribe()

    @cached_probe_read
    def aggregate(self):
        probes_to_aggregate = self.collector.proxy_probes_to_aggregate()
        if not probes_to_aggregate:
            our_proxy = probes.get_probe_by_implementer(
                self.aggregate_name, self.obj)
            return our_proxy.type_class.neutral_value()

        if not self.aggregate_func:
            # Lazily get the correct aggregate function from name
            # Just pick the first probe to get what we are aggregating for type
            a_type = probes_to_aggregate[0].prop.type
            self.aggregate_func = probe_type_classes.get_aggregate_function(
                a_type, self.function_string)

            self.aggregate_value_map_func = (
                probe_type_classes.get_aggregate_value_map_function(
                    self.function_string))

        self.subscribe_to_new_probes(probes_to_aggregate)

        # Get the values to aggregate, can be scalar value list or
        # (object/class, value) pairs in a list
        values = self.aggregate_value_map_func(probes_to_aggregate)

        # Let the aggregator-function calculate the result
        result = self.aggregate_func(values)
        return result

    @cls.iface.probe
    def value(self):
        if self.users == 0:
            return None
        return self.aggregate()

    @cls.iface.probe
    def properties(self):
        # Properties will be reflected only for the probes
        # we have right now. Not 100% correct, TODO?
        pprobes = self.collector.proxy_probes_to_aggregate()
        cause_slowdown = any([c.prop.cause_slowdown for c in pprobes])
        default = [(Probe_Key_Kind, self.aggregate_name),
                   (Probe_Key_Definition, self.def_str),
                   (Probe_Key_Cause_Slowdown, cause_slowdown),
                   (Probe_Key_Type, "float"),
                   (Probe_Key_Owner_Object, self.cell_owner),
                   (Probe_Key_Width, 12)]
        return common.merge_keys(default, self.cprops)

# doc
class FractionProbeFactory(BaseProbeFactory):
    __slots__ = ('numerator', 'denominator', 'keys',
                 'seen_generation_id', 'factor', 'def_str')

    def __init__(self, name, numerator, denominator, keys = [],
                 factor = 1):
        super().__init__(name)
        self.numerator = numerator
        self.denominator = denominator
        self.keys = keys
        self.seen_generation_id = 0
        self.factor = factor
        if factor != 1:
            self.def_str = f"{self.numerator} * {self.factor} / {self.denominator}"
        else:
            self.def_str = f"{self.numerator} / {self.denominator}"

    def singleton(self, p):
        return probes.is_singleton(p.prop.owner_obj)

    def both_non_singleton(self, p1, p2):
        return (not self.singleton(p1)) and (not self.singleton(p2))

    def both_singleton(self, p1, p2):
        return self.singleton(p1) and self.singleton(p2)

    def non_singleton_object(self, p1, p2):
        if not self.singleton(p1):
            return p1.prop.owner_obj
        if not self.singleton(p2):
            return p2.prop.owner_obj
        assert 0

    def create(self):
        def update_categories(p1, p2, cat):
            cat1 = set(p1.prop.categories)
            cat2 = set(p2.prop.categories)
            return cat1.union(cat2).union(set(cat) if cat else set())

        pd = conf.probes.object_data
        gen_id = pd.get_generation_id()
        if gen_id == self.seen_generation_id:
            return []
        self.seen_generation_id = gen_id

        set1 = probes.get_probes(self.numerator)
        set2 = probes.get_probes(self.denominator)
        new_objs = []
        (keys, cat) = common.filter_out_key(self.keys, Probe_Key_Categories)
        for p1 in set1:
            for p2 in set2:
                if self.both_non_singleton(p1, p2):
                    if p1.prop.owner_obj != p2.prop.owner_obj:
                        continue
                    o = p1.prop.owner_obj
                    p = [(Probe_Key_Owner_Object, o)]
                elif self.both_singleton(p1, p2):
                    o = p1.prop.owner_obj
                    p = [(Probe_Key_Owner_Object, o)]
                else:
                    o = self.non_singleton_object(p1, p2)
                    p = [(Probe_Key_Owner_Object, o)]

                c = update_categories(p1, p2, cat)
                p.append((Probe_Key_Categories, list(c)))
                cause_slowdown = any([p1.prop.cause_slowdown,
                                      p2.prop.cause_slowdown])
                p.append((Probe_Key_Cause_Slowdown, cause_slowdown))
                p.append((Probe_Key_Definition, self.def_str))

                new_name = f"{o.name}.probes.{self.name}"

                new_objs += self.create_sketch(
                    "probe_fraction_probe",
                    new_name,
                    [["cname", self.name],
                     ["part", p1.id],
                     ["total", p2.id],
                     ["cprops", common.listify(p + keys)],
                     ["factor", self.factor]
                     ])
                if new_objs:
                    probes.register_dependencies(new_name, [p1.obj, p2.obj])
        return new_objs

    class simics_class(base_probe_confclass):
        cls = confclass("probe_fraction_probe", pseudo = True,
                        parent = base_probe_confclass.cls,
                        short_doc = "internal class",
                        doc = "Probe class for fraction of two probes.")
        cls.attr.part("i", default = None, doc = "The part probe")
        cls.attr.total("i", default = None, doc = "The total probe")
        cls.attr.cname("s", default = None, doc = "The probe name")
        cls.attr.factor("f|i", default = None, doc = "Multiply factor")

        @cls.finalize
        def finalize_instance(self):
            self.users = 0
            pd = conf.probes.object_data
            self.part_probe = pd.get_probe_by_id(self.part)
            self.total_probe = pd.get_probe_by_id(self.total)

        @cls.iface.probe_subscribe
        def subscribe(self):
            self.part_probe.subscribe()
            self.total_probe.subscribe()
            self.users += 1

        @cls.iface.probe_subscribe
        def unsubscribe(self):
            self.part_probe.unsubscribe()
            self.total_probe.unsubscribe()
            self.users -= 1

        @cls.iface.probe_subscribe
        def num_subscribers(self):
            return self.users

        @cls.iface.probe
        def value(self):
            pv = self.part_probe.value()
            tv = self.total_probe.value()
            try:
                nv = self.part_probe.type_class.value_as_fraction(pv)
                dv = self.total_probe.type_class.value_as_fraction(tv)
            except probe_type_classes.ProbeValueException:
                return None

            # Divide two fractions with eachother (with a factor)
            return [nv[0] * dv[1] * self.factor, nv[1] * dv[0]]

        @cls.iface.probe
        def properties(self):
            default = [(Probe_Key_Kind, self.cname),
                       (Probe_Key_Type, "fraction"),
                       (Probe_Key_Width, 12)]

            return common.merge_keys(default, self.cprops)

# doc
class PercentProbeFactory(FractionProbeFactory):
    __slots__ = ()
    def __init__(self, name, numerator, denominator, keys = []):
        default = [(Probe_Key_Definition,
                    f"percent({numerator} / {denominator})")]
        super().__init__(name, numerator, denominator,
                         common.merge_keys(
                             default,
                             [(Probe_Key_Float_Percent, True)] + keys))


class AliasProbeFactory(BaseProbeFactory):
    __slots__ = ('base', 'keys', 'seen_probes')
    def __init__(self, name, base, keys = []):
        super().__init__(name)
        self.base = base
        self.keys = keys
        self.seen_probes = 0

    def create(self):
        # Use current set of probes to find if we can
        # derive a new probe from them.
        base_probes = probes.get_probes(self.base)
        new_objs = []

        if len(base_probes) == self.seen_probes:
            return []
        self.seen_probes = len(base_probes)

        for c in base_probes:
            o = c.prop.owner_obj
            p = [(Probe_Key_Owner_Object, o)]
            p.append((Probe_Key_Cause_Slowdown, bool(c.prop.cause_slowdown)))

            new_name = f"{o.name}.probes.{self.name}"
            new_objs += self.create_sketch(
                "probe_alias_probe",
                new_name,
                [["alias_name", self.name],
                 ["base", c.id],
                 ["cprops", common.listify(p + self.keys)]
                ])
            if new_objs:
                probes.register_dependencies(new_name, [c.obj])
        return new_objs

    class simics_class(base_probe_confclass):
        cls = confclass("probe_alias_probe", pseudo = True,
                        parent = base_probe_confclass.cls,
                        short_doc = "internal class",
                        doc = "Probe class for an alias probe.")
        cls.attr.alias_name("s", default = None, doc = "The alias name")
        cls.attr.base("i", default = None, doc = "The probe id")

        @cls.finalize
        def finalize_instance(self):
            self.users = 0
            self.seen = set()

        @cls.iface.probe_subscribe
        def subscribe(self):
            pd = conf.probes.object_data
            pd.get_probe_by_id(self.base).subscribe()
            self.users += 1

        @cls.iface.probe_subscribe
        def unsubscribe(self):
            self.users -= 1
            pd = conf.probes.object_data
            pd.get_probe_by_id(self.base).unsubscribe()

        @cls.iface.probe_subscribe
        def num_subscribers(self):
            return self.users

        @cls.iface.probe
        def value(self):
            pd = conf.probes.object_data
            return pd.get_probe_by_id(self.base).value()

        @cls.iface.probe
        def properties(self):
            pd = conf.probes.object_data
            p = pd.get_probe_by_id(self.base)
            default = [(Probe_Key_Kind, self.alias_name),
                       (Probe_Key_Definition,
                        f"alias({p.prop.kind})")]
            return common.merge_keys(default, self.cprops)

class cpu_cycle_triggered_probe_class:
    cls = confclass("probe_cycle_triggered", pseudo = True,
                    parent = base_probe_confclass.cls,
                    short_doc = "internal class",
                    doc = "Probe class for cycle objects with extended clocks.")
    cls.attr.owner("o", default = None, doc = "The cpu")

    @cls.finalize
    def finalize_instance(self):
        self.child_clocks = []
        self.child_proxies = set()
        self.users = 0

        for obj in list(SIM_object_iterator(self.owner)) + [self.owner]:
            if hasattr(obj.iface, "cycle_event_instrumentation"):
                self.child_clocks.append(obj)

    @cls.iface.probe_subscribe
    def subscribe(self):
        for c in self.child_clocks:
            pp = probes.get_probe_by_object("clk.event.cycle.triggered", c)
            pp.subscribe()
            self.child_proxies.add(pp)

        if not self.child_proxies:
            SIM_log_info(1, conf.probes, 0,
                         f"{self.owner.name} has a clock interface, but not"
                         " the needed interfaces for the"
                         " cpu.event.cycle.triggered probe."
                         " No events will be shown.")
        self.users += 1

    @cls.iface.probe_subscribe
    def unsubscribe(self):
        self.users -= 1
        for pp in self.child_proxies:
            pp.unsubscribe()

    @cls.iface.probe_subscribe
    def num_subscribers(self):
        return self.users

    @cls.iface.probe
    def value(self):
        return sum([pp.value() for pp in self.child_proxies])

    @cls.iface.probe
    def properties(self):
        return common.listify([
            (Probe_Key_Kind, "cpu.event.cycle.triggered"),
            (Probe_Key_Display_Name, "Cycle Events"),
            (Probe_Key_Type, "int"),
            (Probe_Key_Width, 10),
            (Probe_Key_Categories, ["cycle", "event"]),
            (Probe_Key_Description, "Number of cycle events triggered"),
            (Probe_Key_Owner_Object, self.owner),
            (Probe_Key_Aggregates,
             [[(Probe_Key_Kind, "sim.event.cycle.triggered"),
               (Probe_Key_Description,
                "Total number of cycle events triggered."),
               (Probe_Key_Aggregate_Scope, "global"),
               (Probe_Key_Owner_Object, conf.sim),
               (Probe_Key_Aggregate_Function, "sum")],
              [(Probe_Key_Kind, "cell.event.cycle.triggered"),
               (Probe_Key_Description, ("Total number of cycle events triggered"
                                        " in a cell.")),
               (Probe_Key_Aggregate_Scope, "cell"),
               (Probe_Key_Aggregate_Function, "sum")]])])


class cpu_cycle_histogram_probe_class:
    cls = confclass("probe_cycle_histogram", pseudo = True,
                    parent = base_probe_confclass.cls,
                    short_doc = "internal class",
                    doc = "Probe class for cycle objects with extended clocks.")
    cls.attr.owner("o", doc = "The cpu")

    @cls.finalize
    def finalize_instance(self):
        self.child_clocks = []
        self.child_proxies = set()
        self.users = 0

        for obj in list(SIM_object_iterator(self.owner)) + [self.owner]:
            if hasattr(obj.iface, "cycle_event_instrumentation"):
                self.child_clocks.append(obj)

    @cls.iface.probe_subscribe
    def subscribe(self):
        for c in self.child_clocks:
            pp = probes.get_probe_by_object("clk.event.cycle.histogram", c)
            pp.subscribe()
            self.child_proxies.add(pp)

        if not self.child_proxies:
            SIM_log_info(1, conf.probes, 0,
                         f"{self.owner.name} has a clock interface, but not"
                         " the needed interfaces for the"
                         " cpu.event.cycle.histogram probe."
                         " No events will be shown.")
        self.users += 1

    @cls.iface.probe_subscribe
    def unsubscribe(self):
        self.users -= 1
        for pp in self.child_proxies:
            pp.unsubscribe()

    @cls.iface.probe_subscribe
    def num_subscribers(self):
        return self.users

    @cls.iface.probe
    def value(self):
        if not self.child_proxies:
            return [] # Nothing

        # Get hold of any type-class which supports histogram_sum
        tc = tuple(self.child_proxies)[0].type_class

        # Return the aggregated histogram_sum for all the cycle-event
        # queues underneath the 'cycle' object.
        return tc.histogram_sum([pp.value()
                                 for pp in self.child_proxies])

    @cls.iface.probe
    def properties(self):
        return common.listify([
            (Probe_Key_Kind, "cpu.event.cycle.histogram"),
            (Probe_Key_Display_Name, "Cycle Event Histogram"),
            (Probe_Key_Type, "histogram"),
            (Probe_Key_Width, 50),
            (Probe_Key_Categories, ["cycle", "event"]),
            (Probe_Key_Description,
             "Histogram of cycle events triggered on this processor. This is the"
             " same as the merged events triggered on the port objects"
             " vtime.cycles and vtime.ps beneath the processor. Each line"
             " shows the class of the object that has the event"
             " registered together with the name of the event class,"
             " then the frequency."),
            (Probe_Key_Owner_Object, self.owner),
            (Probe_Key_Aggregates,
             [[(Probe_Key_Kind, "sim.event.cycle.histogram"),
               (Probe_Key_Description,
                ("Histogram of cycle events triggered in the entire simulation."
                 " This is the aggregated value of all cpu.event.cycle.histogram"
                 " probes. Each line shows the class of the object that has the"
                 " event registered together with the name of the event class,"
                 " then the frequency.")),
               (Probe_Key_Aggregate_Scope, "global"),
               (Probe_Key_Owner_Object, conf.sim),
               (Probe_Key_Aggregate_Function, "sum")],
              [(Probe_Key_Kind, "cell.event.cycle.histogram"),
               (Probe_Key_Description,
                ("Histogram of cycle events triggered in the cell."
                 " This is the aggregated value of the cpu.event.cycle.histogram"
                 " probes in this cell. Each line shows the class of the object"
                 " that has the event registered together with the name of the"
                 " event class, then the frequency.")),
               (Probe_Key_Aggregate_Scope, "cell"),
               (Probe_Key_Aggregate_Function, "sum")]])])
