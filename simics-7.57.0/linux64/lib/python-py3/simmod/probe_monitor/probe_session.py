# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Takes a dict (from json) with probe information which has been generated
# and wrap this as a class where the probe-data can be accesses as if they
# are probe-objects. Also creates 'class-probes' for probes which share the
# same simics-class.

import collections
import re

from dataclasses import dataclass
from typing import (Optional, Any)

# Note, this is just to get hold of probes.probe_type_classes
# We need this functionality to be available outside of Simics too
import probes
import table

exec_mode_re = re.compile(
    "cls[.]cpu[.]exec_mode[.](hypersim|jit|vmp|interpreter)_percent")

def drop_prefix(k):
    if ":" in k:
        return k.split(':')[1]
    return k

def format_probe_value(probe, cell_value):
    float_decimals = None
    # TODO: pass this instead of createing a new for each point
    prop_obj = table.cell_props.CellProps(probe.table_properties())
    cell = table.cell.data_to_cell(cell_value, float_decimals, prop_obj)
    val_str = "\n".join([cell.line(i) for i in range(cell.num_lines())])
    return val_str

def dict_to_probe(probe_dict):
    return Probe(**probe_dict)


# Representation of a probe, converted from the json format or generated
# as class-probes from other object-probes of the same Simics class.
@dataclass(slots=True)
class Probe:
    # Required, used by normal and class-probes
    kind : str
    mode : str
    type : str
    owner : str
    display_name : str
    raw_sample_history : [Any]
    final_value : [Any]

    # Optional
    classname : Optional[str] = ""
    module:  Optional[str] = ""
    categories:  Optional[Any] = None
    float_decimals : Optional[int] = None
    percent : Optional[bool] = False
    final_value_cell : Optional[Any] = None
    final_value_fmt : Optional[str] = None
    metric: Optional[str] = None
    binary: Optional[str] = None
    time_fmt: Optional[bool] = False
    desc: Optional[str] = ""
    definition: Optional[str] = ""
    width: Optional[int] = None
    unit: Optional[str] = ""

    # Derivatives
    cls_probe: Optional[bool] = False
    module_probe: Optional[bool] = False

    plot_formatter: Optional[Any] = None

    def __post_init__(self):
        # New-lines can be used in the display-name to make the column less
        # wide. It looks bad in graphs though so replace them with spaces.
        self.display_name = self.display_name.replace('\n', ' ')

    @property
    def sample_history(self):
        if not self.plot_formatter:
            self.plot_formatter = probes.CellFormatter(
                max_lines=10,
                ignore_column_widths=True)

        cls = probes.probe_type_classes.get_value_class(self.type)
        return [cls.table_cell_value(v, self.plot_formatter)
                for v in self.raw_sample_history]

    @property
    def global_probe(self):
        return self.owner in ["sim", "host"]

    # Create the corresponding table-properties to format the
    # value according to the probe's properties.
    def table_properties(self):
        l = [(table.Column_Key_Int_Radix, 10)]
        if self.percent:
            l.append((table.Column_Key_Float_Percent, True))
        if self.float_decimals:
            l.append((table.Column_Key_Float_Decimals, self.float_decimals))
        if self.metric != None:
            l.append((table.Column_Key_Metric_Prefix, self.metric))
        if self.binary != None:
            l.append((table.Column_Key_Binary_Prefix, self.binary))
        if self.time_fmt:
            l.append((table.Column_Key_Time_Format, self.time_fmt))
        return l

# FakeProbe used when there is no probe, returning "n/a" for any
# member accessed
class FakeProbe:
    def __getattr__(self, a):
        return "n/a"

class SimicsSession:
    __slots__ = ('json', 'probes', 'all_probe_kinds', 'distinct_probe_names',
                 'no_prefix_probe_names')
    def __init__(self, json):
        self.json = json

        # Create a dict of the probes in json format represented as
        # Probe objects
        probes_dict = self.json.get("target", {}).get("probes", {})
        self.probes = {
            key : dict_to_probe(value)
            for (key, value) in probes_dict.items()
        }
        self._generate_module_probes()
        self._generate_class_probes()

        # All probe-name used
        kinds = {p.kind for p in self.probes.values()}
        self.all_probe_kinds = kinds

        # All probes used with object prefix and mode suffix
        names = set(self.probes.keys())
        self.distinct_probe_names = names

        # All probes, but with removed object prefix
        names = {drop_prefix(n) for n in names}
        self.no_prefix_probe_names = names

    def _generate_module_probes(self):
        # Module-probes are derived probes, when a probe is actually
        # global in the module it is implemented in. This is uncommon
        # but used for JIT, for example. This is identified by having
        # the "module-global" probe-category.
        #
        # Each CPU will have the same probe, but it does not make
        # sense to sum these into classes, since they are all the same
        # value. Instead we create mod.<probe-kind> probe which just
        # takes the first value from any of the probe-sets included.

        # Find each module-global probe and assign them to the
        # module they are included in.
        mp = {}                  # "module": [Probe*]
        for k, v in self.probes.items():
            if v.cls_probe:     # Ignore derived class-probes
                continue
            if not v.categories or "module-global" not in v.categories:
                continue
            mp.setdefault(v.module, [])
            mp[v.module].append(v)

        # Iterate over each module and create the module-probe
        for module, module_probes in mp.items():
            probe_kinds = set(p.kind for p in module_probes)
            for pk in probe_kinds:
                m = [p for p in module_probes if p.kind == pk]

                # Add the new module probe, the module becomes the owner
                owner = f"[{module}]"
                kind=f"module.{m[0].kind}"
                p = f"{owner}:{kind}"
                self.probes[p] = Probe(
                    kind=kind,
                    mode=m[0].mode,
                    type=m[0].type,
                    owner=owner,
                    display_name=m[0].display_name,
                    raw_sample_history=m[0].sample_history,
                    final_value=m[0].final_value,
                    final_value_cell=m[0].final_value_cell,
                    final_value_fmt=m[0].final_value_fmt,
                    module_probe=True
                )


    @staticmethod
    def _get_aggregate_function_for_probe(probe_name, ptype):
        type_class = probes.probe_type_classes
        if ptype != "fraction":
            if not type_class.supports_aggregate_function(ptype, "sum"):
                return None
            return type_class.get_aggregate_function(ptype, "sum")

        # Check fractions. How class probe's data should be
        # constructed, depends on what the fractions represents. There
        # is currently no hint in properties for this.

        # Uses common denominator, do a simple sum of the fractions
        if probe_name in ["cls.cpu.schedule_percent",
                          "cls.cpu.load_sim_percent"]:
            return type_class.get_aggregate_function(ptype, "sum")

        mo = exec_mode_re.match(probe_name)
        if mo:
            return type_class.get_aggregate_function(ptype,
                                                     "weighted-arith-mean")

        if probe_name in ["cls.cpu.mips"]:
            return  type_class.get_aggregate_function(ptype,
                                                      "weighted-arith-mean")

        # Unspecified fraction, do not sum it
        return None

    def _generate_class_probes(self):
        cls_history = {}
        for k, v in self.probes.items():
            if v.global_probe:
                continue       # Nothing to aggregate on global probes

            if v.module_probe:  # Ignore already derived module-probes
                continue

            # Don't produce class probes for data which is module global
            if v.categories and (
                    "module-global" in v.categories):
                continue

            (obj, probe_name) = k.split(":")
            cls = v.classname
            cls_probe = f"<{cls}>:cls.{probe_name}"
            cls_history.setdefault(cls_probe, [])
            cls_history[cls_probe].append(v)

        for k, v in cls_history.items():
            type_set = {co.type for co in v}
            if len(type_set) != 1:
                # different types
                continue
            type = type_set.pop()
            (cls, cls_probe_kind) = k.split(':')
            aggregate_fun = self._get_aggregate_function_for_probe(
                cls_probe_kind, type)
            if not aggregate_fun:
                continue        # Not supported to aggregate

            sample_history = []
            for l in zip(*[co.raw_sample_history for co in v]):
                row = aggregate_fun(l)
                sample_history.append(row)

            # Get hold of class for this probe-type
            probe_cls = probes.probe_type_classes.get_value_class(type)

            final_value = aggregate_fun([co.final_value for co in v])
            final_value_cell = probe_cls.table_cell_value(final_value)
            final_value_fmt = format_probe_value(v[0], final_value_cell)

            # Add the new class probe
            self.probes[k] = Probe(
                kind=f"cls.{v[0].kind}",
                mode=v[0].mode,
                type=type,
                owner=cls,
                display_name=v[0].display_name,
                raw_sample_history=sample_history,
                final_value=final_value,
                final_value_cell=final_value_cell,
                final_value_fmt=final_value_fmt,
                cls_probe=True
            )


    def get_object_probes(self, probe_name):
        y_probes = []
        for k, v in self.probes.items():
            if v.global_probe:  # Skip global classes
                continue
            (obj, pn) = k.split(":")
            if pn == probe_name:
                y_probes.append(k)
        return y_probes

    def get_object_probes_from_wildcard(self, obj_name, probe_kind):
        y_probes = []
        for k, v in self.probes.items():
            try:
                (obj, pk) = k.split(":")
            except Exception as msg:
                print("probe-name:", k)
                raise Exception(msg)
            if pk == probe_kind:
                if obj_name == "*" or obj_name == obj:
                    y_probes.append(k)

        return y_probes

    def get_wildcard_objects(self, probe_kind):
        objs = set()
        for k, v in self.probes.items():
            (obj, pk) = k.split(":")
            if pk == probe_kind:
                objs.add(obj)
        return objs

    def summary_data(self):
        '''Returns an ordered dict, with key and values as strings.
        The summary data is collected from various sections in the JSON
        file.'''
        def final_value(probe_name):
            p = self.probes.get(probe_name, FakeProbe())
            return p.final_value_fmt

        target = self.json.get("target", {})
        host = self.json.get("host", {})
        num_cores = str(host.get("CPU cores", "n/a"))
        host_freqs = ",".join(
            str(int(n)) for n in host.get("CPU max freqs", {}))
        host_cores_and_freqs = f" [{num_cores} cores @ {host_freqs} MHz]"
        host_os = host.get("OS", "n/a")
        hyp = host.get("hypervisor", "no")
        os_and_hypervisor = host_os + (
            f" Hypervisor:{hyp}" if hyp != "no" else "")
        return collections.OrderedDict({
            "Workload": target.get("workload", "n/a"),
            "Date": self.json.get("date", "n/a"),
            "Target": target.get("CPU summary", "n/a"),
            "Wallclock Time": final_value("sim:sim.time.wallclock-session"),
            "Virtual Time": final_value("sim:sim.time.virtual-session"),
            "Slowdown": final_value("sim:sim.slowdown"),
            "MIPS": final_value("sim:sim.mips"),
            "Target load%": final_value("sim:sim.load_percent"),
            "Host HW": host.get("CPU brand", "n/a") + (host_cores_and_freqs),
            "Host SW": os_and_hypervisor,
            "Simics CPU load%": final_value("sim:sim.process.cpu_percent"),
            "Threading mode": self.json.get("simics", {}).get(
                "Threading mode", "n/a")
        })

    def host_data(self):
        return self.json["host"]

    def simics_data(self):
        return self.json["simics"]

    def target_data(self):
        d = self.json["target"]
        d.pop("probes")
        return d

    def probes_data(self):
        return self.probes

    # Returns the full name of the probe, including the obj:kind-[mode]
    def global_probe_names(self, type_exclude=None):
        return sorted(
            {k for (k,v) in self.probes.items()
             if (v.global_probe
                 and (not type_exclude
                      or (v.type not in type_exclude)))
             })

    # Return the probe names *without* the actual object:
    # kind-[mode]
    def class_probe_names(self, type_exclude=None):
        return sorted(
            {v.kind for (k,v) in self.probes.items()
             if (v.cls_probe
                 and (not type_exclude
                      or (v.type not in type_exclude)))
             })

    # Return the probe names *without* the actual object:
    # kind-[mode]
    def module_probe_names(self, type_exclude=None):
        return sorted(
            {v.kind for (k,v) in self.probes.items()
             if (v.module_probe
                 and (not type_exclude
                      or (v.type not in type_exclude)))
             })

    # Return the probe names *without* the actual object:
    # kind-[mode]
    def object_probe_names(self, type_exclude=None):
        return sorted(
            {v.kind for (k,v) in self.probes.items()
             if (not (v.global_probe or v.cls_probe or v.module_probe)
                 and (not type_exclude
                      or (v.type not in type_exclude)))
             })

    def flamegraph_data(self):
        if not "flamegraph" in self.json:
            return None
        return self.json["flamegraph"]

    # Returns True if any of the probes are not present
    def probes_missing(self, probe_names):
        return not set(probe_names).issubset(self.no_prefix_probe_names)
