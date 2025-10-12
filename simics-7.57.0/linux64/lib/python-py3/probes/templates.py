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
import conf
from simics import *
from . import factories
from . import probes
from . import host_probes
from . import common
from . import probe_type_classes
from . import procfs_probes
from . import sketch

probe_templates = None

# Get hold of the ProbeTemplate object, or create it, if it does not exist.
# The actual template_list will be created when .get_all() method is called,
# this to avoid references to conf.host, which otherwise might not have
# been created yet.
def get_probe_templates():
    global probe_templates
    if not probe_templates:
        probe_templates = ProbeTemplates()
    return probe_templates


# Exported interface

def template_exist(name):
    t_obj = get_probe_templates()
    return t_obj.template_exists(name)

def add_aggregate_template(t):
    t_obj = get_probe_templates()
    return t_obj.add_aggregate_template(t)

def add_command_template(t):
    t_obj = get_probe_templates()
    return t_obj.add_command_template(t)

def remove_template(t):
    t_obj = get_probe_templates()
    t_obj.all_templates.remove(t)

def all_templates():
    # Return a list with all templates registered
    t_obj = get_probe_templates()
    return t_obj.get_all()[:] # make a copy

def create_new_probe_objects():
    # Iterate through the derived probes until no probes
    # are created anymore. Probes can depend on other probes
    while True:
        new_objs = []
        for t in all_templates():
            added = t.create()
            new_objs += added
            if added and not t.is_persistent():
                remove_template(t)

        if not new_objs:
            break

        sketch.create_configuration_objects(new_objs)

        # Make sure out probes dict are updated
        probes.get_probes_data().update_probes()

# command interface for user manual adding probes
# -----------------------------------------------

def add_percent(name, display_name, numerator, denominator):
    new = factories.PercentProbeFactory(name, numerator, denominator,
                                        [(Probe_Key_Display_Name, display_name)])
    add_command_template(new)
    create_new_probe_objects()

def add_fraction(name, display_name, numerator, denominator, factor):
    new = factories.FractionProbeFactory(
        name, numerator, denominator, [(Probe_Key_Display_Name, display_name)],
        factor)
    add_command_template(new)
    create_new_probe_objects()

def add_attribute(class_name, attribute_name, kind, display_name):
    desc = f"Attribute '{attribute_name}' in '{class_name}' class"
    new = factories.AttributeProbeFactory(
        class_name, attribute_name, kind,
        [(Probe_Key_Kind, kind),
         (Probe_Key_Display_Name, display_name),
         (Probe_Key_Description, desc)])
    add_command_template(new)
    create_new_probe_objects()

def add_aggregate(name, display_name, probe_kind, function, object_names, keys):
    f = factories.AggregateProbeFactory(
        name, probe_kind, function, object_names, keys=keys)
    add_command_template(f)
    create_new_probe_objects()


# This class defines all probes which should be created automatically
# based on various conditions:
#  - New objects detected implementing certain interfaces
#  - Probes with aggregates, the aggregate probes are delayed and put here first
#  - Various special conditions on how probes are added for VMP counters,
#    alias probes, and other hand-written factories
#  - User commands adding new probes.
class ProbeTemplates:
    def __init__(self):
        self.all_templates = (
            self.get_derived_templates()
            + self.get_iface_templates()
            + self.get_vmp_templates()
            + self.get_special_templates()
            )
        self.templates_by_name = {}
        self.update_templates_by_name()

    def get_all(self):
        return self.all_templates

    def update_templates_by_name(self):
        for t in self.get_all():
            self.templates_by_name[t.name] = t

    def template_exists(self, name):
        return name in self.templates_by_name

    def add_aggregate_template(self, t):
        self.all_templates.append(t)
        self.templates_by_name[t.name] = t

    def add_command_template(self, t):
        self.all_templates.append(t)
        self.templates_by_name[t.name] = t

    def get_derived_templates(self):
        return (
            self.derived_percent_probes()
            + self.derived_fraction_probes()
            + self.derived_aggregate_probes()
            + self.derived_alias_probes()
        )

    def get_iface_templates(self):
        return [
            factories.IfaceProbeFactory(name, ifaces, cls)
            for (ifaces, name, cls) in [
                    (["cycle"], "cpu.cycles", "probe_cycles"),
                    (["cycle"], "cpu.event.cycle.triggered",
                     "probe_cycle_triggered"),
                    (["cycle"], "cpu.event.cycle.histogram",
                     "probe_cycle_histogram"),
                    (["cycle"], "cpu.time.virtual_ps", "probe_picoseconds"),
                    (["cycle"], "cpu.time.virtual", "probe_virtual_time"),
                    (["event_provider"], "isim", "probe_event_provider"),
                    (["step"], "cpu.steps", "probe_steps"),
                    (["step"], "cpu.esteps", "probe_esteps"),
                    (["step_info"], "cpu.exec_mode.hypersim_steps",
                     "probe_hypersim_steps"),
                    (["telemetry"], "telemetry", "probe_telemetry"),
                    (["step", "cycle", "processor_info_v2"], "cpu.load_percent",
                     "probe_load_percent")]]

    def get_vmp_templates(self):
        return [
            factories.VmpProbeFactory(name, cls, space, idx, prefix)
            for (name, cls, space, idx, prefix) in
            [
                ("vmp.vmexits",
                 "probe_vmp_probe_group", "_vmexits", 0, "VMEXIT_"),
                ("vmp.total_vmexits",
                 "probe_vmp_probe_group_total", "_vmexits", 0, "VMEXIT_"),
                ("vmp.histogram_vmexits",
                 "probe_vmp_probe_group_histogram", "_vmexits", 0, "VMEXIT_"),
                ("vmp.vmrets",
                 "probe_vmp_probe_group", "_vmrets", 2, "VMRET_"),
                ("vmp.total_vmrets",
                 "probe_vmp_probe_group_total", "_vmrets", 1, "VMRET_"),
                ("vmp.pctrs",
                 "probe_vmp_probe_group", "_pctrs", 1, ""),
            ]]

    def get_special_templates(self):
        return [
            factories.TimeScheduledProbeFactory(),
            factories.TurboProbeFactory(),
            factories.InterpreterProbeFactory(),
            factories.CpuDisabledFactory(),
            factories.CellIoAccessProbeFactory(),
        ]

    def derived_percent_probes(self):
        # The percent-probes are just fraction probes, but presents the
        # result as a percent value instead.
        return [
            factories.PercentProbeFactory(
                new_kind, numerator_kind, denominator_kind, props)
            for (new_kind, numerator_kind, denominator_kind, props) in
            [
                ("cpu.schedule_percent",
                 "cpu.time.schedule",
                 "sim.time.schedule",
                 [(Probe_Key_Display_Name, "Sched%"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Width, 6),
                  (Probe_Key_Description,
                   "Percent of total schedule time for this cpu")]),

                ("cell.schedule_percent",
                 "cell.time.schedule",
                 "sim.time.schedule",
                 [(Probe_Key_Display_Name, "Sched%"),
                  (Probe_Key_Float_Decimals, 0),
                 (Probe_Key_Width, 6),
                 (Probe_Key_Description,
                  "Percent of total schedule time for this cell.")]),

                # Exec-modes
                ("cpu.exec_mode.interpreter_percent",
                 "cpu.exec_mode.interpreter_steps",
                 "cpu.esteps",
                 [(Probe_Key_Display_Name, "INT%"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Width, 4),
                  (Probe_Key_Description,
                   "Percent of instructions executed in interpreter."),
                  ]),

                # Explicitly calculated, cannot sum fractions if cpus
                # do not have interpreter
                ("cell.exec_mode.interpreter_percent",
                 "cell.exec_mode.interpreter_steps",
                 "cell.esteps",
                 [(Probe_Key_Display_Name, "INT%"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Width, 4),
                  (Probe_Key_Description,
                   "Percent of instructions executed in interpreter mode for a"
                   " specific cell")]),

                # Explicitly calculated, cannot sum fractions if cpus
                # do not have interpreter
                ("sim.exec_mode.interpreter_percent",
                 "sim.exec_mode.interpreter_steps",
                 "sim.esteps",
                 [(Probe_Key_Display_Name, "INT%"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Width, 4),
                  (Probe_Key_Owner_Object, conf.sim),
                  (Probe_Key_Description,
                   "Percent of instructions executed in interpreter for all"
                   " processors.")]),

                ("cpu.exec_mode.jit_percent",
                 "cpu.exec_mode.jit_steps",
                 "cpu.esteps",
                 [(Probe_Key_Display_Name, "JIT%"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Width, 4),
                  (Probe_Key_Description,
                   "Percent of instructions executed in JIT mode."),
                  ]),

                ("cell.exec_mode.jit_percent",
                 "cell.exec_mode.jit_steps",
                 "cell.esteps",
                 [(Probe_Key_Display_Name, "JIT%"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Width, 4),
                  (Probe_Key_Description,
                   "Percent of instructions executed in JIT mode in a"
                   " specific cell")]),

                ("sim.exec_mode.jit_percent",
                 "sim.exec_mode.jit_steps",
                 "sim.esteps",
                 [(Probe_Key_Display_Name, "JIT%"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Width, 4),
                  (Probe_Key_Owner_Object, conf.sim),
                  (Probe_Key_Description,
                   "Percent of instructions executed in JIT mode for all"
                   " processors.")]),

                ("cpu.exec_mode.vmp_percent",
                 "cpu.exec_mode.vmp_steps",
                 "cpu.esteps",
                 [(Probe_Key_Display_Name, "VMP%"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Width, 4),
                  (Probe_Key_Description,
                   "Percent of instructions executed in VMP execution mode."),
                  ]),

                ("cell.exec_mode.vmp_percent",
                 "cell.exec_mode.vmp_steps",
                 "cell.esteps",
                 [(Probe_Key_Display_Name, "VMP%"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Width, 4),
                  (Probe_Key_Description,
                   "Percent of instructions executed in VMP mode for all"
                   " processors in a specific cell.")]),

                ("sim.exec_mode.vmp_percent",
                 "sim.exec_mode.vmp_steps",
                 "sim.esteps",
                 [(Probe_Key_Display_Name, "VMP%"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Width, 4),
                  (Probe_Key_Description,
                   "Percent of instructions executed in VMP mode for all"
                   " processors.")]),

                ("cpu.exec_mode.hypersim_percent",
                 "cpu.exec_mode.hypersim_steps",
                 "cpu.esteps",
                 [(Probe_Key_Display_Name, "HYP%"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Categories, ["cpu", "instructions", "steps",
                                          "hypersim"]),
                 (Probe_Key_Width, 4),
                 (Probe_Key_Description,
                  "Percent of instructions executed in hypersim mode."),
                 ]),

                # Explicitly calculated, cannot sum fractions if cpus
                # do not have hypersim
                ("cell.exec_mode.hypersim_percent",
                 "cell.exec_mode.hypersim_steps",
                 "cell.esteps",
                 [(Probe_Key_Display_Name, "HYP%"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Categories, ["cpu", "instructions", "steps",
                                          "hypersim"]),
                  (Probe_Key_Width, 4),
                  (Probe_Key_Description,
                   "Percent of instructions executed in hypersim mode in a"
                   " specific cell")]),

                # Explicitly calculated, cannot sum fractions if cpus
                # do not have hypersim
                ("sim.exec_mode.hypersim_percent",
                 "sim.exec_mode.hypersim_steps",
                 "sim.esteps",
                 [(Probe_Key_Display_Name, "HYP%"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Categories, ["cpu", "instructions", "steps",
                                          "hypersim"]),
                  (Probe_Key_Width, 4),
                  (Probe_Key_Description,
                   "Percent of instructions executed in hypersim mode for all"
                   " processors.")]),

                ("cpu.load_sim_percent",
                 "cpu.esteps",
                 "sim.cycles",
                 [(Probe_Key_Display_Name, "Sim Load%\nof all CPUs"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Width, 6),
                  (Probe_Key_Description,
                   "Percent of how much this cpu is loaded compared to the"
                   " entire system.")]),

                ("cpu.load_cell_percent",
                 "cpu.esteps",
                 "cell.cycles",
                 [(Probe_Key_Display_Name, "Sim Load%\nof cell CPUs"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Width, 6),
                  (Probe_Key_Description,
                   "Percent of how much this cpu is loaded compared to the cell"
                   " system.")]),

                ("sim.process.cpu_percent",
                 "sim.time.host_threads",
                 "sim.time.wallclock",
                 [(Probe_Key_Display_Name, "Host CPU%"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Width, 4),
                  (Probe_Key_Owner_Object, conf.sim),
                  (Probe_Key_Description,
                   "Percent of one host CPU utilized. Maximum is N * 100% where,"
                   " N is the number of host processors in the system."
                   " 200% means that Simics has run on two host processors.")]),

                ("sim.process.cpu_usage_percent",
                 "sim.time.host_threads",
                 "host.time.work",
                 [(Probe_Key_Display_Name, "Host CPU Usage%"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Width, 4),
                  (Probe_Key_Owner_Object, conf.sim),
                  (Probe_Key_Description,
                   "How much Simics has been scheduled on the actually scheduled"
                   " host processors. Close to 100% is good here, lower numbers"
                   " indicate other parallel load on the same system."
                   " Greater than 100% numbers can sometimes be shown, due to"
                   " the different mechanisms are used to extract data.")]),

                ("sim.process.memory.resident_percent",
                 "sim.process.memory.resident",
                 "host.memory.total",
                 [(Probe_Key_Display_Name, "MEM%"),
                  (Probe_Key_Float_Decimals, 1),
                  (Probe_Key_Width, 6),
                  (Probe_Key_Owner_Object, conf.sim),
                  (Probe_Key_Description,
                   "Percent the Simics process uses of total memory.")]),
            ]
        ]

    def derived_fraction_probes(self):
        return [
            factories.FractionProbeFactory(
                new_kind, numerator_kind, denominator_kind, props)
            for (new_kind, numerator_kind, denominator_kind, props) in
            [
                ("cpu.mips",
                 "cpu.esteps",
                 "cpu.time.schedule",
                 [(Probe_Key_Display_Name, "IPS"),
                  (Probe_Key_Metric_Prefix, ""),
                  (Probe_Key_Width, 8),
                  (Probe_Key_Categories, ["performance"]),
                  (Probe_Key_Description,
                   "How fast a processor executes instructions during scheduled"
                   " time. cpu.esteps / cpu.time.schedule"),
                  (Probe_Key_Aggregates, [
                      [
                          (Probe_Key_Kind, "cell.mips"),
                          (Probe_Key_Aggregate_Scope, "cell"),
                          (Probe_Key_Aggregate_Function, "weighted-arith-mean"),
                          (Probe_Key_Description,
                           "How fast this cell has been executed based on the"
                           "total scheduled time. cell.esteps /"
                           " cell.time.schedule"),
                      ]
                      # No sim.mips here, this is calculated differently
                  ])]),

                # NOTE Simulator total MIPS is based on the simulation time
                ("sim.mips",
                 "sim.esteps",
                 "sim.time.wallclock",
                 [(Probe_Key_Display_Name, "IPS"),
                  (Probe_Key_Metric_Prefix, ""),
                  (Probe_Key_Width, 8),
                  (Probe_Key_Categories, ["performance"]),
                  (Probe_Key_Description,
                   "How fast Simics executes instructions."
                   " Instructions per host-simulation-seconds.")
                  ]),

                ("sim.slowdown",
                 "sim.time.wallclock",
                 "sim.time.virtual",
                 [(Probe_Key_Display_Name, "Slowdown"),
                  (Probe_Key_Width, 8),
                  (Probe_Key_Float_Decimals, 2),
                  (Probe_Key_Description,
                   "How fast virtual time progresses compared to simulation"
                   " time."),
                  ]),

                ("cpu.instructions_per_cycle",
                 "cpu.esteps",
                 "cpu.cycles",
                 [(Probe_Key_Display_Name, "IPC"),
                  (Probe_Key_Width, 4),
                  (Probe_Key_Float_Decimals, 2),
                  (Probe_Key_Description,
                   "Number of executed instruction per cycle"),
                  ]),

                ("cpu.vmp.esteps_per_vmexit",
                 "cpu.esteps",
                 "cpu.vmp.vmexits.total",
                 [(Probe_Key_Display_Name, "Esteps/vmexit"),
                  (Probe_Key_Width, 6),
                  (Probe_Key_Metric_Prefix, ""),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Description,
                   "Intensity of vmexits. How many steps we execute per vmexit.")
                  ]),

                ("sim.io_intensity",
                 "sim.esteps",
                 "sim.io_access_count",
                 [(Probe_Key_Display_Name, "IO intensity"),
                  (Probe_Key_Categories, ["device", "io"]),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Description,
                   "Number of steps per IO access."),
                  ]),

                ("cell.io_intensity",
                 "cell.esteps",
                 "cell.io_access_count",
                 [(Probe_Key_Display_Name, "IO intensity"),
                  (Probe_Key_Categories, ["device", "io"]),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Description,
                   "Number of steps per IO access on a cell."),
                  ]),

                ("cpu.event.step.intensity",
                 "cpu.esteps",
                 "cpu.event.step.triggered",
                [(Probe_Key_Display_Name, "Step Event Intensity"),
                 (Probe_Key_Float_Decimals, 0),
                 (Probe_Key_Description,
                  "Number of steps per event in a cpu."),
                 ]),

                ("cpu.event.cycle.intensity",
                 "cpu.cycles",
                 "cpu.event.cycle.triggered",
                 [(Probe_Key_Display_Name, "Cycle Event Intensity"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Description,
                   "Number of cycles per event in a cpu."),
                  ]),

                ("cell.event.step.intensity",
                 "cell.esteps",
                 "cell.event.step.triggered",
                 [(Probe_Key_Display_Name, "Step Event Intensity"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Description,
                   "Number of steps per event in a cell."),
                  ]),

                ("cell.event.cycle.intensity",
                 "cell.cycles",
                 "cell.event.cycle.triggered",
                 [(Probe_Key_Display_Name, "Cycle Event Intensity"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Description,
                   "Number of cycles per event in a cell."),
                  ]),

                ("sim.event.step.intensity",
                 "sim.esteps",
                 "sim.event.step.triggered",
                 [(Probe_Key_Display_Name, "Step Event Intensity"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Description,
                   "Number of steps per event globally."),
                  ]),

                ("sim.event.cycle.intensity",
                 "sim.cycles",
                 "sim.event.cycle.triggered",
                 [(Probe_Key_Display_Name, "Cycle Event Intensity"),
                  (Probe_Key_Float_Decimals, 0),
                  (Probe_Key_Description,
                   "Number of cycles per event globally."),
                  ]),
            ]
        ]

    def derived_aggregate_probes(self):
        return [
            factories.AggregateProbeFactory(
                "sim.vmp.vmexits.total",
                "cpu.vmp.vmexits.total",
                "sum", keys=[
                    (Probe_Key_Owner_Object, conf.sim),
                    (Probe_Key_Description,
                     "Total number of vmexists in VMP mode for all"
                     " processors."),
                    (Probe_Key_Type, "int"),
                    (Probe_Key_Width, 10),
                ]),

            factories.CellAggregateProbeFactory(
                "cell.vmp.vmexits.total",
                "cpu.vmp.vmexits.total",
                "sum", [
                    (Probe_Key_Description,
                     "Total number of vmexists in VMP mode for all"
                     " processors."),
                    (Probe_Key_Type, "int"),
                    (Probe_Key_Width, 10),
                ]),
            ]

    def derived_alias_probes(self):
        return [
            factories.AliasProbeFactory(
                new_kind, source_kind, props)
            for (new_kind, source_kind, props) in
            [
                ("cpu.exec_mode.vmp_steps",
                 "cpu.turbo.vmp_run_steps",
                 [(Probe_Key_Display_Name, "VMP steps"),
                  (Probe_Key_Width, 11),
                  (Probe_Key_Categories, ["vmp", "performance", "steps"]),
                  (Probe_Key_Description,
                   "Number of steps executed in VMP execution mode"),
                  (Probe_Key_Aggregates, [
                     [
                         (Probe_Key_Kind, "sim.exec_mode.vmp_steps"),
                         (Probe_Key_Aggregate_Scope, "global"),
                         (Probe_Key_Owner_Object, conf.sim),
                         (Probe_Key_Aggregate_Function, "sum"),
                         (Probe_Key_Description,
                          "Total number of steps executed in VMP mode for all"
                          " processors."),
                     ],
                      [
                          (Probe_Key_Kind, "cell.exec_mode.vmp_steps"),
                          (Probe_Key_Aggregate_Scope, "cell"),
                          (Probe_Key_Aggregate_Function, "sum"),
                          (Probe_Key_Description,
                           "Total number of steps executed in VMP mode in a"
                           " specific cell."),
                      ]
                  ])]),

                ("cpu.exec_mode.jit_steps",
                 "cpu.turbo.dynamic_instructions",
                 [(Probe_Key_Display_Name, "JIT steps"),
                  (Probe_Key_Width, 11),
                  (Probe_Key_Categories, ["jit", "performance"]),
                  (Probe_Key_Description,
                   "Number of steps executed in JIT execution mode"),
                  (Probe_Key_Aggregates, [
                      [
                          (Probe_Key_Kind, "sim.exec_mode.jit_steps"),
                          (Probe_Key_Aggregate_Scope, "global"),
                          (Probe_Key_Owner_Object, conf.sim),
                          (Probe_Key_Aggregate_Function, "sum"),
                          (Probe_Key_Description,
                           "Total number of steps executed in JIT mode for all"
                           " processors."),
                      ],
                      [
                          (Probe_Key_Kind, "cell.exec_mode.jit_steps"),
                          (Probe_Key_Aggregate_Scope, "cell"),
                          (Probe_Key_Aggregate_Function, "sum"),
                          (Probe_Key_Description,
                           "Total number of steps executed in JIT mode in a"
                           " specific cell."),
                      ]
                  ])
                  ]),
            ]
        ]
