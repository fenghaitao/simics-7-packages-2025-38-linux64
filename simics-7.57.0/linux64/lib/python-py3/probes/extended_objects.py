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
from configuration import *
from .common import listify

from .probe_type_classes import Int128Value
from .probe_cache import cached_probe_read

# Defines object probes for existing objects

class pseudo_namespace:
    cls = confclass("pseudo_namespace", pseudo = True,
                    short_doc = "pseudo namespace",
                    doc = """
The pseudo_namespace is similar to the namespace class but is of pseudo
class type. It does not have any structure itself, but it
can be used as a hierarchical parent to pseudo child objects""")

class execute_load:
    cls = confclass("probe_execute_load", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for execution time spent"
                    " simulating a processor.")
    cls.attr.owner("o", default = None, doc = "The cpu object.")

    @cls.finalize
    def finalize_instance(self):
        self.users = 0

    @cls.iface.probe_subscribe
    def subscribe(self):
        if self.users == 0:
            VT_enable_cpuload_stats()
        self.users += 1

    @cls.iface.probe_subscribe
    def unsubscribe(self):
        self.users -= 1
        if self.users == 0:
            VT_disable_cpuload_stats()

    @cls.iface.probe_subscribe
    def num_subscribers(self):
        return self.users

    @cls.iface.probe
    def value(self):
        if self.users:
            return float(VT_cpuload_ns(self.owner))/1e9
        return None             # Not enabled

    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "cpu.time.schedule"),
             (Probe_Key_Display_Name, "Sched"),
             (Probe_Key_Description,
              "Host time this processor has been scheduled."),
             (Probe_Key_Type, "float"),
             (Probe_Key_Unit, "hh:mm:ss.d"),
             (Probe_Key_Time_Format, True),
             (Probe_Key_Cause_Slowdown, True),
             (Probe_Key_Categories, ["performance"]),
             (Probe_Key_Owner_Object, self.owner),
             (Probe_Key_Aggregates, [
                 [
                     (Probe_Key_Kind, "sim.time.schedule"),
                     (Probe_Key_Aggregate_Scope, "global"),
                     (Probe_Key_Owner_Object, conf.sim),
                     (Probe_Key_Aggregate_Function, "sum"),
                     (Probe_Key_Description,
                      "Accumulated host time all processors have been"
                      " scheduled."),
                 ],
                 [
                     (Probe_Key_Kind, "cell.time.schedule"),
                     (Probe_Key_Aggregate_Scope, "cell"),
                     (Probe_Key_Aggregate_Function, "sum"),
                     (Probe_Key_Categories, ["cell", "performance"]),
                     (Probe_Key_Description,
                      "Accumulated host time the processors in a specific"
                      " cell has been scheduled."),
                 ],
                 [
                     (Probe_Key_Kind, "sim.time.schedule_object_histogram"),
                     (Probe_Key_Aggregate_Scope, "global"),
                     (Probe_Key_Owner_Object, conf.sim),
                     (Probe_Key_Display_Name, "Scheduled Object Histogram"),
                     (Probe_Key_Width, 60),
                     (Probe_Key_Time_Format, False),
                     (Probe_Key_Unit, "s"),
                     (Probe_Key_Aggregate_Function, "object-histogram"),
                     (Probe_Key_Type, "histogram"),
                     (Probe_Key_Description,
                      "Histogram of the processor objects that has been"
                      " scheduled the most"),
                 ],
                 [
                     (Probe_Key_Kind, "sim.time.schedule_class_histogram"),
                     (Probe_Key_Aggregate_Scope, "global"),
                     (Probe_Key_Owner_Object, conf.sim),
                     (Probe_Key_Display_Name, "Scheduled Class Histogram"),
                     (Probe_Key_Width, 50),
                     (Probe_Key_Time_Format, False),
                     (Probe_Key_Unit, "s"),
                     (Probe_Key_Aggregate_Function, "class-histogram"),
                     (Probe_Key_Type, "histogram"),
                     (Probe_Key_Description,
                      "Histogram of the processor classes that has been"
                      " scheduled the most."),
                 ],

             ])])

class steps:
    cls = confclass("probe_steps", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for processor steps.")
    cls.attr.owner("o", default = None, doc = "The step object.")


    @cls.finalize
    def finalize_instance(self):
        self.step_iface = SIM_get_interface(self.owner, "step")

    @cls.iface.probe
    def value(self):
        return self.step_iface.get_step_count()

    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "cpu.steps"),
             (Probe_Key_Display_Name, "Steps"),
             (Probe_Key_Type, "int"),
             (Probe_Key_Categories, ["cpu", "instructions", "steps"]),
             (Probe_Key_Width, 12),
             (Probe_Key_Owner_Object, self.owner),
             (Probe_Key_Description,
              "Number of steps (~instructions) consumed by this"
              " processor, including any halt steps"),
             (Probe_Key_Aggregates, [
                 [
                     (Probe_Key_Kind, "sim.steps"),
                     (Probe_Key_Aggregate_Scope, "global"),
                     (Probe_Key_Owner_Object, conf.sim),
                     (Probe_Key_Aggregate_Function, "sum"),
                     (Probe_Key_Description,
                      "Total number of steps (~instructions) executed on all"
                      " processor, including any halt steps")
                 ],
                 [
                     (Probe_Key_Kind, "cell.steps"),
                     (Probe_Key_Aggregate_Scope, "cell"),
                     (Probe_Key_Aggregate_Function, "sum"),
                     (Probe_Key_Categories, ["cell", "cpu",
                                             "instructions", "steps"]),
                     (Probe_Key_Description,
                      "Total number of steps (~instructions) executed on all"
                      " processor in a specific cell, including any halt steps")
                 ]
             ])])

class esteps:
    cls = confclass("probe_esteps", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for execute steps on a processor.")
    cls.attr.owner("o", default = None, doc = "The executed steps object.")

    @cls.finalize
    def finalize_instance(self):
        self.step_iface = SIM_get_interface(self.owner, "step")
        self.step_info_iface = SIM_c_get_interface(self.owner, "step_info")

    @cls.iface.probe
    def value(self):
        steps = self.step_iface.get_step_count()
        if self.step_info_iface:
            halt_steps = self.step_info_iface.get_halt_steps()
        else:
            halt_steps = 0
        return steps - halt_steps

    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "cpu.esteps"),
             (Probe_Key_Display_Name, "Esteps"),
             (Probe_Key_Description,
              "Number of executed steps (~instructions) on this"
              " processor, ignoring any halt steps"),
             (Probe_Key_Type, "int"),
             (Probe_Key_Categories, ["cpu", "instructions", "steps"]),
             (Probe_Key_Width, 12),
             (Probe_Key_Owner_Object, self.owner),
             (Probe_Key_Aggregates, [
                 [
                     (Probe_Key_Kind, "sim.esteps"),
                     (Probe_Key_Aggregate_Scope, "global"),
                     (Probe_Key_Owner_Object, conf.sim),
                     (Probe_Key_Aggregate_Function, "sum"),
                     (Probe_Key_Description,
                      "Total number of executed steps (~instructions) on all"
                      " processors, ignoring any halt steps"),
                 ],
                 [
                     (Probe_Key_Kind, "cell.esteps"),
                     (Probe_Key_Aggregate_Scope, "cell"),
                     (Probe_Key_Aggregate_Function, "sum"),
                     (Probe_Key_Categories, ["cell", "cpu", "instructions",
                                             "steps"]),
                     (Probe_Key_Description,
                      "Total number of executed steps (~instructions) on all"
                      " processors in a specific cell, ignoring any halt steps"),
                 ]])
              ])

class load_percent:
    cls = confclass("probe_load_percent", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for how much a processor is idling.")
    cls.attr.owner("o", default = None, doc = "The step object.")

    @cls.finalize
    def finalize_instance(self):
        # We also require the "processor_info_v2" interface, but not used for
        # the calculation
        self.step_iface = SIM_get_interface(self.owner, "step")
        self.cycle_iface = SIM_get_interface(self.owner, "cycle")
        # Optional interfaces
        self.step_info_iface = SIM_c_get_interface(self.owner, "step_info")
        self.ratio_iface = SIM_c_get_interface(self.owner, "step_cycle_ratio")
        if self.ratio_iface:
            self.start_ratio = self.ratio_iface.get_ratio()

    @cls.iface.probe
    def value(self):
        if not self.cycle_iface:  # No cycle interface in same obj
            return [0, 0]
        steps = self.step_iface.get_step_count()
        halt_steps = 0
        if self.step_info_iface:
            halt_steps = self.step_info_iface.get_halt_steps()

        esteps = steps - halt_steps
        cycles = self.cycle_iface.get_cycle_count()
        if not self.ratio_iface:
            return [esteps, cycles]

        # Compensate for latest step_ratio setting for this cpu
        ratio = self.ratio_iface.get_ratio()
        if (ratio.steps != self.start_ratio.steps
            or ratio.cycles != self.start_ratio.cycles):
            # step-rate has changed
            return [0, 0]

        nsteps = esteps // ratio.steps
        ncycles = cycles // ratio.cycles
        return [nsteps, ncycles]


    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "cpu.load_percent"),
             (Probe_Key_Display_Name, "Sim Load%"),
             (Probe_Key_Type, "fraction"),
             (Probe_Key_Float_Percent, True),
             (Probe_Key_Float_Decimals, 0),
             (Probe_Key_Width, 4),
             (Probe_Key_Categories, [
                 "cpu", "instructions", "load", "cycles", "steps"]),
             (Probe_Key_Owner_Object, self.owner),
             (Probe_Key_Description,
              "Calculated load of a processor, that is, instruction per"
              " cycles, shown as percent: esteps / cycles."
              " 0% is reported if the processor is entirely idle and 100%"
              " when the processor executes instructions for all cycles."
              " The value is also adjusted with the current step-rate of a"
              " processor, if this exists."
              " Note that if the step-rate is dynamically changed"
              " during execution, the result will be incorrect and"
              " 0 / 0 is returned."),
             (Probe_Key_Aggregates, [
                 [
                     (Probe_Key_Kind, "sim.load_percent"),
                     (Probe_Key_Aggregate_Scope, "global"),
                     (Probe_Key_Owner_Object, conf.sim),
                     (Probe_Key_Aggregate_Function, "weighted-arith-mean"),
                     (Probe_Key_Description,
                      "Sum of all cpu.load_percent probes in the system,"
                      " that is: total_executed_instruction / total_cycles."),
                 ],
                 [
                     (Probe_Key_Kind, "cell.load_percent"),
                     (Probe_Key_Aggregate_Scope, "cell"),
                     (Probe_Key_Aggregate_Function, "weighted-arith-mean"),
                     (Probe_Key_Description,
                      "Sum of all cpu.load_percent probes in the cell,"
                      " that is: cell_total_executed_instruction /"
                      " cell_total_cycles."),
                 ],
             ])])

class cycles:
    cls = confclass("probe_cycles", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for elapsed cycles on a processor.")
    cls.attr.owner("o", default = None, doc = "The owner object.")

    @cls.finalize
    def finalize_instance(self):
        self.cycle_iface = SIM_get_interface(self.owner, "cycle")

    @cls.iface.probe
    def value(self):
        return self.cycle_iface.get_cycle_count()

    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "cpu.cycles"),
             (Probe_Key_Display_Name, "Cycles"),
             (Probe_Key_Description,
              "Number of cycles expired on this processor"),
             (Probe_Key_Type, "int"),
             (Probe_Key_Categories, ["cpu", "cycles", "time"]),
             (Probe_Key_Width, 12),
             (Probe_Key_Owner_Object, self.owner),
             (Probe_Key_Aggregates, [
                 [
                     (Probe_Key_Kind, "sim.cycles"),
                     (Probe_Key_Aggregate_Scope, "global"),
                     (Probe_Key_Owner_Object, conf.sim),
                     (Probe_Key_Aggregate_Function, "sum"),
                     (Probe_Key_Description,
                      "Total number of expired cycles on all processors."),
                 ],
                 [
                     (Probe_Key_Kind, "cell.cycles"),
                     (Probe_Key_Aggregate_Scope, "cell"),
                     (Probe_Key_Aggregate_Function, "sum"),
                     (Probe_Key_Categories, ["cell", "cpu", "cycles", "time"]),
                     (Probe_Key_Description,
                      "Total number of expired cycles in all"
                      " processors in a specific cell"),
                 ]
             ])])

class picoseconds:
    cls = confclass("probe_picoseconds", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for elapsed pico-seconds on a processor.")
    cls.attr.owner("o", default = None,
                   doc = "The cpu using the picosecond clock.")

    @cls.finalize
    def finalize_instance(self):
        self.cycle_iface = SIM_get_interface(self.owner, "cycle")

    @cls.iface.probe
    def value(self):
        ps = self.cycle_iface.get_time_in_ps().t
        return Int128Value._python_to_int128_attr(ps)

    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "cpu.time.virtual_ps"),
             (Probe_Key_Display_Name, "picoseconds"),
             (Probe_Key_Description,
              "Number of picoseconds expired on this processor"),
             (Probe_Key_Type, "int128"),
             (Probe_Key_Categories, ["cpu", "time", "picoseconds"]),
             (Probe_Key_Width, 20),
             (Probe_Key_Unit, "ps"),
             (Probe_Key_Owner_Object, self.owner),
             ])

class virtual_time:
    cls = confclass("probe_virtual_time", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for virtual time on a processor.")
    cls.attr.owner("o", default = None, doc = "The cycle object.")

    @cls.finalize
    def finalize_instance(self):
        self.cycle_iface = SIM_get_interface(self.owner, "cycle")

    @cls.iface.probe
    def value(self):
        return self.cycle_iface.get_time()

    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "cpu.time.virtual"),
             (Probe_Key_Display_Name, "Virtual-Time"),
             (Probe_Key_Unit, "hh:mm:ss.d"),
             (Probe_Key_Time_Format, True),
             (Probe_Key_Description,
              "The virtual time of this 'cpu'"),
             (Probe_Key_Type, "float"),
             (Probe_Key_Categories, ["cpu", "time"]),
             (Probe_Key_Width, 11),
             (Probe_Key_Owner_Object, self.owner)])

class hypersim_steps:
    cls = confclass("probe_hypersim_steps", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for hupersim steps on a processor.")
    cls.attr.owner("o", default = None, doc = "The step object")

    @cls.finalize
    def finalize_instance(self):
        self.step_info_iface = SIM_get_interface(self.owner, "step_info")

    @cls.iface.probe
    def value(self):
        return self.step_info_iface.get_ffwd_steps()

    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "cpu.exec_mode.hypersim_steps"),
             (Probe_Key_Display_Name, "Hypersim steps"),
             (Probe_Key_Description,
              "Number of steps executed in hypersim execution mode."),
             (Probe_Key_Type, "int"),
             (Probe_Key_Categories, ["hypersim", "performance", "steps"]),
             (Probe_Key_Width, 11),
             (Probe_Key_Owner_Object, self.owner),
             (Probe_Key_Aggregates, [
                 [
                     (Probe_Key_Kind, "sim.exec_mode.hypersim_steps"),
                     (Probe_Key_Aggregate_Scope, "global"),
                     (Probe_Key_Owner_Object, conf.sim),
                     (Probe_Key_Aggregate_Function, "sum"),
                     (Probe_Key_Description,
                      "Total number of instruction executed in hypersim mode."),
                 ],
                 [
                     (Probe_Key_Kind, "cell.exec_mode.hypersim_steps"),
                     (Probe_Key_Aggregate_Scope, "cell"),
                     (Probe_Key_Aggregate_Function, "sum"),
                     (Probe_Key_Description,
                      "Total number of instruction executed in hypersim mode for"
                      " all processors in a specific cell"),
                 ]])
             ])

class interpreter_steps:
    cls = confclass("probe_interpreter_steps", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for interpreter steps on a processor.")
    cls.attr.owner("o", default = None, doc = "The step object")

    @cls.finalize
    def finalize_instance(self):
        self.users = 0
        self.step_iface = SIM_get_interface(self.owner, "step")
        self.step_info_iface = SIM_c_get_interface(self.owner, "step_info")
        self.has_turbo = hasattr(self.owner, "turbo_stat")
        if self.has_turbo:
            turbo_counters = [x[0] for x in self.owner.turbo_stat]
            self.has_vmp = "vmp_run_steps" in turbo_counters
        else:
            self.has_vmp = False

    @cls.iface.probe_subscribe
    def subscribe(self):
        self.users += 1
        if self.has_turbo:
            if hasattr(self.owner, 'turbo_count_steps') and not self.owner.turbo_count_steps:
                SIM_flush_cell_caches(self.owner)
                self.owner.turbo_count_steps = True
            elif self.owner.turbo_debug_level == 0:
                SIM_flush_cell_caches(self.owner)
                self.owner.turbo_debug_level = 1

    @cls.iface.probe_subscribe
    def unsubscribe(self):
        self.users -= 1
        if self.users == 0 and self.has_turbo:
            if hasattr(self.owner, 'turbo_count_steps') and self.owner.turbo_count_steps:
                SIM_flush_cell_caches(self.owner)
                self.owner.turbo_count_steps = False
            elif self.owner.turbo_debug_level == 1:
                SIM_flush_cell_caches(self.owner)
                self.owner.turbo_debug_level = 0

    @cls.iface.probe_subscribe
    def num_subscribers(self):
        return self.users

    @cls.iface.probe
    def value(self):
        steps = self.step_iface.get_step_count()
        halt_steps = 0
        hypersim_steps = 0
        vmp_steps = 0
        jit_steps = 0

        if self.step_info_iface:
            halt_steps = self.step_info_iface.get_halt_steps()
            hypersim_steps = self.step_info_iface.get_ffwd_steps()

        if self.has_vmp:
            vmp_steps = self.owner.turbo_stat["vmp_run_steps"]

        if self.has_turbo:
            jit_steps = self.owner.turbo_stat["dynamic_instructions"]

        return steps - halt_steps - hypersim_steps - vmp_steps - jit_steps


    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "cpu.exec_mode.interpreter_steps"),
             (Probe_Key_Display_Name, "Interpreter steps"),
             (Probe_Key_Description,
              "Number of steps executed in interpreter mode."),
             (Probe_Key_Type, "int"),
             (Probe_Key_Categories, ["interpreter", "performance", "steps"]),
             (Probe_Key_Width, 11),
             (Probe_Key_Owner_Object, self.owner),
             (Probe_Key_Aggregates, [
                 [
                     (Probe_Key_Kind, "sim.exec_mode.interpreter_steps"),
                     (Probe_Key_Aggregate_Scope, "global"),
                     (Probe_Key_Owner_Object, conf.sim),
                     (Probe_Key_Aggregate_Function, "sum"),
                     (Probe_Key_Description,
                      "Total number of instruction executed in interpreter"
                      " mode."),
                 ],
                 [
                     (Probe_Key_Kind, "cell.exec_mode.interpreter_steps"),
                     (Probe_Key_Aggregate_Scope, "cell"),
                     (Probe_Key_Aggregate_Function, "sum"),
                     (Probe_Key_Description,
                      "Total number of instruction executed in interpreter mode"
                      " for all processors in a specific cell"),
                 ]
             ])])


class turbo_stat:
    cls = confclass("probe_turbo_stat", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for executed jit-steps on a processor.")
    cls.attr.owner("o", default = None, doc = "The cpu object.")

    @cls.finalize
    def finalize_instance(self):
        self.users = 0
        self.probes = { i : n for i, (n, _) in
                        enumerate(list(self.owner.turbo_stat)) }

    @cls.iface.probe_subscribe
    def subscribe(self):
        self.users += 1
        if hasattr(self.owner, 'turbo_count_steps') and not self.owner.turbo_count_steps:
            SIM_flush_cell_caches(self.owner)
            self.owner.turbo_count_steps = True
        elif self.owner.turbo_debug_level == 0:
            SIM_flush_cell_caches(self.owner)
            self.owner.turbo_debug_level = 1


    @cls.iface.probe_subscribe
    def unsubscribe(self):
        self.users -= 1
        if self.users == 0:
            if hasattr(self.owner, 'turbo_count_steps') and self.owner.turbo_count_steps:
                SIM_flush_cell_caches(self.owner)
                self.owner.turbo_count_steps = False
            elif self.owner.turbo_debug_level == 1:
                SIM_flush_cell_caches(self.owner)
                self.owner.turbo_debug_level = 0


    @cls.iface.probe_subscribe
    def num_subscribers(self):
        return self.users

    @cls.iface.probe_index
    def num_indices(self):
        return len(self.probes)

    @cached_probe_read
    def cached_turbo_stat(self):
        # Return entire big attribute, now as a dict, shared by cache
        return {k:v for (k,v) in self.owner.turbo_stat}

    @cls.iface.probe_index
    def value(self, idx):
        turbo_stat = self.cached_turbo_stat()
        return turbo_stat[self.probes[idx]]

    @cls.iface.probe_index
    def properties(self, idx):
        categories = ["turbo", "jit", "internals"]
        cpu = self.owner
        if hasattr(cpu, 'turbo_stat_module_globals'):
            if self.probes[idx] in cpu.turbo_stat_module_globals:
                categories.append("module-global")
        return listify(
            [(Probe_Key_Kind, "cpu.turbo." + self.probes[idx]),
             (Probe_Key_Display_Name, "turbo." + self.probes[idx]),
             (Probe_Key_Description, ""),
             (Probe_Key_Type, "int"),
             (Probe_Key_Categories, categories),
             (Probe_Key_Width, 10),
             (Probe_Key_Owner_Object, self.owner)])

class event_provider:
    cls = confclass("probe_event_provider", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for encapsulation of the"
                    " event_provider interface.")
    cls.attr.owner("o", default = None, doc = "The provider object.")

    @cls.finalize
    def finalize_instance(self):
        self.events = []
        i = 0
        while True:
            name = self.owner.iface.event_provider.event_name(i)
            if not name:
                break
            self.events.append(name)
            i += 1

    @cls.iface.probe_index
    def num_indices(self):
        return len(self.events)

    @cls.iface.probe_index
    def value(self, idx):
        return self.owner.iface.event_provider.event_value(idx)

    @cls.iface.probe_index
    def properties(self, idx):
        return listify(
            [(Probe_Key_Kind, "isim.event." + self.events[idx].lower()),
             (Probe_Key_Description, "ISIM event " + self.events[idx]),
             (Probe_Key_Type, "int"),
             (Probe_Key_Categories, ["isim"]),
             (Probe_Key_Width, 10),
             (Probe_Key_Owner_Object, self.owner)])

class telemetry:
    cls = confclass("probe_telemetry", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for encapsulation of the telemetry"
                    " interface.")
    cls.attr.owner("o", default = None, doc = "The telemetry provider object.")

    class Telemetry:
        def __init__(self, ci, cn, cd, ti, tn, td):
            self.class_id = ci
            self.class_name = cn
            self.class_desc = cd
            self.telemetry_id = ti
            self.telemetry_name = tn
            self.telemetry_desc = td

    @staticmethod
    def replace_colon(s):
        return s.replace(":", ".")

    @cls.finalize
    def finalize_instance(self):
        self.telemetry = []
        c = 0
        while True:
            cname = self.owner.iface.telemetry.get_telemetry_class_name(c)
            if not cname:
                break

            cname = self.replace_colon(cname)
            cdesc = self.owner.iface.telemetry.get_telemetry_class_description(c)

            t = 0
            iface = self.owner.iface.telemetry
            while True:
                tname = iface.get_telemetry_name(c, t)
                if not tname:
                    break

                tname = self.replace_colon(tname)
                tdesc = iface.get_telemetry_description(c, t)
                self.telemetry.append(
                    self.Telemetry(c, cname, cdesc, t, tname, tdesc))
                t += 1
            c += 1

    @cls.iface.probe_index
    def num_indices(self):
        return len(self.telemetry)

    @cls.iface.probe_index
    def value(self, idx):
        t = self.telemetry[idx]
        return self.owner.iface.telemetry.get_value(t.class_id, t.telemetry_id)

    @cls.iface.probe_index
    def properties(self, idx):
        t = self.telemetry[idx]
        cls = t.class_name.lower()
        pn = f"telemetry.{cls}.{t.telemetry_name.lower()}"
        return listify(
            [(Probe_Key_Kind, pn),
             (Probe_Key_Description, t.telemetry_desc),
             (Probe_Key_Type, "float"),
             (Probe_Key_Categories, ["telemetry", cls]),
             (Probe_Key_Width, 10),
             (Probe_Key_Value_Notifier, "isim-telemetry-update"),
             (Probe_Key_Owner_Object, self.owner)])
