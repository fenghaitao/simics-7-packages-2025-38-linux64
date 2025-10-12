# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import contextlib
import os
import re
import sys
import unittest
from functools import cmp_to_key

import cli
import simics
import conf
import table
import cli_impl
import cmputil
import debugger_commands
from deprecation import DEPRECATED

from simics import (
    SIM_VERSION_5,
    SIM_VERSION_6,
    SIM_VERSION_8,
    Sim_Access_Execute,

    Column_Key_Float_Decimals,
    Column_Key_Footer_Sum,
    Column_Key_Hide_Homogeneous,
    Column_Key_Int_Pad_Width,
    Column_Key_Int_Radix,
    Column_Key_Metric_Prefix,
    Column_Key_Name,
    Table_Key_Columns,
    Table_Key_Default_Sort_Column,

    SIM_hap_add_callback,
    SIM_hap_add_callback_obj,
    SIM_hap_delete_callback_id,
    SIM_hap_delete_callback_obj_id,

    SIM_get_object,
    SIM_object_iterator,
)

from cli import (
    addr_t,
    arg,
    filename_t,
    flag_t,
    float_t,
    int_t,
    integer_t,
    list_t,
    obj_t,
    range_t,
    sint64_t,
    str_t,
    string_set_t,
    uint_t,
    uint64_t,
    new_command,
    new_unsupported_command,
    new_operator,
    new_info_command,
    new_status_command,
    CliError,
    Markup,
    command_quiet_return,
    command_return,
    command_verbose_return,
    current_cpu_obj,
    current_cycle_obj,
    current_cycle_obj_null,
    current_cycle_queue,
    current_frontend_object,
    current_ps_queue_null,
    current_step_obj,
    current_step_obj_null,
    current_step_queue,
    current_step_queue_null,
    get_completions,
    number_str,
    object_expander,

    # script-branch related imports:
    sb_in_main_branch,
    sb_run_in_main_branch,
)

from script_branch import (
    sb_wait_for_hap_internal,
    sb_wait_for_simulation_started_internal,
)

from sim_commands import (
    conf_class_expander,
    common_exp_regs,
    obj_write_reg_cmd,
    obj_read_reg_cmd,
    abbrev_value,
    abbrev_size,
)

from mem_commands import translate_to_physical
from prompt_information import set_sim_started_cmdline
import update_checkpoint

from simicsutils.internal import py3_cmp
from simics_common import pr_warn

def exp_regs(prefix, obj, arg):
    return common_exp_regs(prefix, obj, arg, False)

# asserts that Simics is stopped
def assert_stopped():
    if simics.SIM_simics_is_running():
        raise CliError("Simics is already running.")

def local_print_disassemble_line(cpu, prefix, address, print_cpu=1,
                                 mnemonic=None):
    di = simics.SIM_c_get_interface(cpu, "processor_cli")
    if not di:
        # No disassembly function found, no disassembly on command line
        return 0
    (len, disasm) = di.get_disassembly(prefix, address, print_cpu, mnemonic)
    print(disasm)
    return len

#
# -------------------- set-time-quantum --------------------
#

# Scale factor: unit => ps
time_units = { "s": 10**12, "ms": 10**9, "us": 10**6, "ns": 10**3, "ps": 1,
               "m": 60*(10**12), "h": 3600*(10**12) }

clock_units = ["cycles"] + list(time_units)
run_units = ["steps"] + clock_units

def time_unit_expander(value):
    return get_completions(value, list(time_units))

def clock_unit_expander(value):
    return get_completions(value, clock_units)

def run_unit_expander(value):
    return get_completions(value, run_units)

def cell_time_quantum_text(cells):
    # find out if we use the same quantum everywhere
    tqs = [c.time_quantum for c in cells]
    tqs_equal = all(tq == tqs[0] for tq in tqs[1:])
    if tqs_equal:
        qval = cells[0].time_quantum
        tq_str = cli.format_seconds(qval)
        msg = f"Current time quantum: {tq_str}\n"
    else:
        qval = -1
        msg = ""
        for cell in cells:
            tq = cell.time_quantum
            tq_str = cli.format_seconds(tq)
            msg += f"Current time quantum for {cell.name}: {tq_str}\n"

    data = []
    for cell in cells:
        tq = cell.time_quantum_ps
        data.extend([[tq / 10**12 * clk.iface.cycle.get_frequency(),
                      clk.name] for clk in cell.clocks])

    properties = [(Table_Key_Columns,
                   [[(Column_Key_Name, h)]
                    for h in ["Cycles/quantum", "Clock"]])]
    tbl = table.Table(properties, data)
    return [msg + tbl.to_string(rows_printed=0, no_row_column=True) + "\n",
            qval]

def default_time_quantum_text():
    try:
        dtq_str = cli.format_seconds(conf.sim.time_quantum)
        return f"Default time quantum: {dtq_str}"
    except simics.SimExc_Attribute:
        try:
            return f"Default time quantum: {conf.sim.cpu_switch_time} cycles"
        except simics.SimExc_Attribute:
            return "Default time quantum not set yet"

def set_time_quantum(obj, value):
    try:
        obj.time_quantum = value
    except simics.SimExc_IllegalValue as ex:
        raise CliError('Failed setting time quantum: %s' % ex)

def inspect_time_quantum():
    cells = list(sorted(
        o for o in simics.SIM_object_iterator_for_class("cell") if o.clocks))
    if cells:
        (msg, val) = cell_time_quantum_text(cells)
    else:
        msg = ""
        val = -1
    msg += default_time_quantum_text()
    return command_verbose_return(msg, val)

def check_time_quantum_input(count, unit, picos):
    if count:
        if picos is not None:
            raise CliError('Only use one of count, cycles,'
                           ' seconds, or picoseconds.')
        if count[2] == 'count':
            check_count_unit(count[1], unit, set(clock_units))
        else:
            assert count[2] in {'cycles', 'seconds'}
            if unit is not None:
                raise CliError("The unit argument must only be used with count.")
            if count[1] <= 0:
                raise CliError('CPU switch time must be positive')
    else:
        if picos is not None:
            if picos <= 0:
                raise CliError('CPU switch time must be positive')
            if unit is not None:
                raise CliError("The picoseconds and unit arguments"
                               " cannot be used together.")

def get_time_quantum_value(count, unit, picos):
    if count is None:
        assert picos is not None
        value = (float_t, picos / 10**12)
        DEPRECATED(SIM_VERSION_8,
                   'The "picoseconds" argument to the "set-time-quantum"'
                   ' command is deprecated.', 'Use the "count" and "unit"'
                   ' arguments instead.')
    elif count[2] == 'count':
        assert isinstance(count[1], int)
        if unit != 'cycles':
            value = (float_t, count[1] * time_units[unit] / 10**12)
        else:
            value = (int_t, count[1])
    elif count[2] == 'seconds':
        assert isinstance(count[1], float)
        value = (float_t, count[1])
        DEPRECATED(SIM_VERSION_8,
                   'The "seconds" argument to the "set-time-quantum"'
                   ' command is deprecated.', 'Use the "count" and "unit"'
                   ' arguments instead.')
    else:
        assert count[2] == 'cycles' and isinstance(count[1], int)
        value = (int_t, count[1])
        DEPRECATED(SIM_VERSION_8,
                   'The "cycles" argument to the "set-time-quantum"'
                   ' command is deprecated.', 'Use the "count" and "unit"'
                   ' arguments instead.')
    return value

def set_time_quantum_cmd(count, unit, picos, cell):
    check_time_quantum_input(count, unit, picos)
    if cell is not None:
        return cell_set_time_quantum_cmd(cell, count, unit, picos)
    if count is None and picos is None:
        return inspect_time_quantum()

    (t, value) = get_time_quantum_value(count, unit, picos)
    if t == float_t:
        set_time_quantum(conf.sim, value)
        return command_return(f"Default time quantum set to"
                              f" {cli.format_seconds(conf.sim.time_quantum)}",
                              conf.sim.time_quantum)
    else:
        try:
            conf.sim.cpu_switch_time = value
        except simics.SimExc_IllegalValue as ex:
            raise CliError("Error: " + str(ex))
        return command_return(f"Default time quantum set to {value} cycles",
                              value)

new_command("set-time-quantum", set_time_quantum_cmd,
            alias="cpu-switch-time",
            args=[
                arg((uint_t, float_t, uint64_t),
                    ("cycles", "seconds", "count"), "?"),
                arg(str_t, "unit", "?", None, expander=clock_unit_expander),
                arg(uint_t, "picoseconds", "?"),
                arg(obj_t("cell", "cell"), "cell", "?", None),
            ],
            type=["Execution", "Performance"],
            short="set time quantum",
            see_also=[
                '<cell>.set-time-quantum',
                'set-max-time-span',
            ],
            doc="""
Change the time between processor switches for processors in the cell
<arg>cell</arg>. The time can be specified using the <arg>count</arg>
and <arg>unit</arg> arguments, or, for legacy purposes, using the
<arg>cycles</arg>, <arg>picoseconds</arg> or <arg>seconds</arg>
arguments.

The time unit, specified by the <arg>unit</arg> argument, can be one
of <tt>cycles, s, ms, us, ns, ps</tt>, <tt>m</tt> or <tt>h</tt>.

The command sets the processor switch time globally if the
<arg>cell</arg> argument is omitted, and all existing cells will have
their time quantum reset to the new value, and cells created later
will use the new value.

Without arguments, <cmd>set-time-quantum</cmd> prints the time quantum
of all cells in the system, as well as the default time quantum (if
set). In this case the output is printed also when run
non-interactively.

If the argument is given in cycles the <attr class="sim">time_quantum</attr>
attribute is unset. And if the argument is given in seconds then the <attr
class="sim">cpu_switch_time</attr> attribute is unset, both in the
<class>sim</class> class.

When used in an expression, the command returns the given value, in seconds or
cycles, or an exception is raised. Without arguments the current time quantum
is returned, or -1 if no cell exists, or if there are cells with different
time quantum values.
""")

def cell_set_time_quantum_cmd(cell, count, unit, picos):
    check_time_quantum_input(count, unit, picos)
    if count is None and picos is None:
        (msg, val) = cell_time_quantum_text([cell])
        return command_verbose_return(msg, val)
    (t, value) = get_time_quantum_value(count, unit, picos)

    if t == float_t:
        set_time_quantum(cell, value)
        return command_return(
            f"Time quantum for {cell.name} updated to {value} s",
            cell.time_quantum)

    if cell.clocks:
        first_clock = cell.clocks[0]
        freq = first_clock.freq_mhz * 1e6
        set_time_quantum(cell, value / freq) # NB: "/" operator returns a float
        return command_return(f"Time quantum for {cell.name} updated to"
                              f" {cell.time_quantum} s ({value} cycles of"
                              f" {first_clock.name} running at {freq} MHz)",
                              cell.time_quantum)

    raise CliError(f'There is no CPU or clock in the cell {cell.name} to compute'
                   ' the new time quantum from the cycle value provided.')

new_command("set-time-quantum", cell_set_time_quantum_cmd,
            alias="cpu-switch-time",
            args=[arg((uint_t, float_t, uint64_t),
                      ("cycles", "seconds", "count"), "?"),
                  arg(str_t, "unit", "?", None, expander=clock_unit_expander),
                  arg(uint_t, "picoseconds", "?")],
            cls="cell",
            type=["Execution", "Performance"],
            short="get/set the time quantum for a given cell",
            see_also=['set-time-quantum'],
            doc="""
Change the time between processor switches for processors in the
cell. The time can be specified using the <arg>count</arg> and
<arg>unit</arg> arguments, or, for legacy purposes, using the
<arg>cycles</arg>, <arg>picoseconds</arg> or <arg>seconds</arg>
arguments.

The time unit, specified by the <arg>unit</arg> argument, can be one
of <tt>cycles, s, ms, us, ns, ps</tt>, <tt>m</tt> or <tt>h</tt>.

Simics will simulate each processor for a specified number of cycles
before switching to the next one. Specifying cycles (which is default)
refers to the number of cycles on the first processor in the cell.
The following processors's cycle switch times are calculated from
their processor frequencies. When the command is issued with no
argument, the current time quantum is reported.""")

def natural_sort(cpu_list):
    """Returns the 'cpu_list' sorted alphabetically by name of each cpu object,
    and if any integers are present they are ordered naturally from lowest to
    highest. """
    return sorted(cpu_list,
                  key=lambda c: [int(s) if s.isdigit() else s for s in
                                 re.split(r'(\d+)', c.name)])

def print_time_cmd(cpu, steps, cycles, seconds, picoseconds, all_flag = False):

    def get_default_obj():
        if steps:
            cpu = current_step_obj_null()
        elif cycles or seconds or picoseconds:
            cpu = current_cycle_obj_null()
        else:
            cpu = current_step_obj_null() or current_cycle_obj_null()

        if not cpu:
            # backward compatibility
            o = current_frontend_object()
            cpu = o.queue

        return cpu

    if (steps + cycles + seconds + picoseconds) > 1:
        raise CliError("Only one of the -s, -c, -t or -pico-seconds flags"
                       " can be used at a time.")

    if all_flag:
        cpus = (set(simics.SIM_object_iterator_for_interface(["step"]))
                | set(simics.SIM_object_iterator_for_interface(["cycle"])))
        if not cpus:
            raise CliError("No time source objects were found.")
    else:
        if not cpu:
            cpu = get_default_obj()
            if not cpu:
                raise CliError("No proper time source object was found.")

        # Some sanity checks
        if steps and not hasattr(cpu.iface, "step"):
            raise CliError(f"The selected processor ('{cpu.name}')"
                           " does not implement the 'step' interface.")
        if ((cycles or seconds or picoseconds)
            and not hasattr(cpu.iface, "cycle")):
            raise CliError(f"The selected processor ('{cpu.name}')"
                           " does not implement the 'cycle' interface.")

        cpus = [cpu]

    def get_step_count(cpu):
        if hasattr(cpu.iface, "step"):
            return cpu.iface.step.get_step_count()
        else:
            return "n/a"

    def get_cycle_count(cpu):
        if hasattr(cpu.iface, "cycle"):
            return cpu.iface.cycle.get_cycle_count()
        else:
            return "n/a"

    def get_time(cpu):
        if hasattr(cpu.iface, "cycle"):
            return cpu.iface.cycle.get_time()
        else:
            return "n/a"

    def get_picoseconds(cpu):
        if hasattr(cpu.iface, "cycle"):
            return cpu.iface.cycle.get_time_in_ps().t
        else:
            return "n/a"

    def natural_sort(cpus):
        return sorted(cpus,
                      key=lambda c: [int(s) if s.isdigit() else s for s in
                                     re.split(r'(\d+)', c.name)])

    def get_data_row(cpu):
        if steps:
            return [cpu, get_step_count(cpu)]
        if cycles:
            return [cpu, get_cycle_count(cpu)]
        if seconds:
            return [cpu, get_time(cpu)]
        if picoseconds:
            return [cpu, get_picoseconds(cpu)]

        # We don't return picoseconds not to clutter output with large number.
        # Those who are interested in picoseconds can pass -pico-seconds.
        return [cpu, get_step_count(cpu), get_cycle_count(cpu), get_time(cpu)]

    def get_table_columns():
        key_columns = []
        if steps:
            key_columns = [
                [(Column_Key_Name, "Steps"), (Column_Key_Int_Radix, 10)]]
        if cycles:
            key_columns = [
                [(Column_Key_Name, "Cycles"), (Column_Key_Int_Radix, 10)]]
        if seconds:
            key_columns = [
                [(Column_Key_Name, "Time (s)"), (Column_Key_Float_Decimals, 3)]]
        if picoseconds:
            key_columns = [
                [(Column_Key_Name, "Picoseconds"), (Column_Key_Int_Radix, 10)]]
        if not key_columns:
            key_columns = [
                [(Column_Key_Name, "Steps"), (Column_Key_Int_Radix, 10)],
                [(Column_Key_Name, "Cycles"), (Column_Key_Int_Radix, 10)],
                [(Column_Key_Name, "Time (s)"), (Column_Key_Float_Decimals, 3)]
            ]
        key_columns = [[(Column_Key_Name, "Processor")]] + key_columns
        return [(table.Table_Key_Columns, key_columns)]

    def calculate_return_value(table_data):
        if (steps or cycles or seconds or picoseconds) and not all_flag:
            # This "conversion" is here to provide backward compatibility.
            return table_data[0][1]
        return table_data

    table_data = [get_data_row(cpu)
                  for cpu in natural_sort(cpus)]
    table_props = get_table_columns()
    tbl = table.Table(table_props, table_data)
    msg = tbl.to_string(rows_printed=0, no_row_column=True)
    return command_verbose_return(msg, calculate_return_value(table_data))

for iface in (None, "cycle"):
    args = [arg(flag_t, "-s"),
            arg(flag_t, "-c"),
            arg(flag_t, "-t"),
            arg(flag_t, "-pico-seconds"),
            ]
    if iface is None:
        args = ([arg(obj_t('cycle object', 'cycle'), "cpu-name", "?")]
                + args
                + [arg(flag_t, "-all")])
    new_command("print-time", print_time_cmd,
                args,
                iface = iface,
                alias = "ptime",
                type  = ["Execution", "Profiling"],
                short = "print number of steps and cycles executed",
                repeat = print_time_cmd,
                doc = """
Prints the number of steps and cycles that a processor has executed.
The cycle count is also displayed as simulated time in seconds.

If called from an object namespace (e.g., <cmd>cpu0.print-time</cmd>), the time
for that object is printed. The object can also be supplied using the
<arg>cpu-name</arg> argument. Otherwise, the time for the current frontend
processor is printed, or, if the <tt>-all</tt> flag is given, the time for all
processors is printed.

The <tt>-c</tt>, <tt>-s</tt>, <tt>-t</tt>, or <tt>-pico-seconds</tt> flags
can be used to limit the output to include only the cycle count for
the processor, the step count, the time in seconds, or the number of picoseconds
respectively. This may be especially useful
when the command's return value is used, for example, like this:
"$num_steps = (<tt>cpu-object</tt>.print-time -s)".

A step is a completed instruction or an exception. An instruction that fails
to complete because of an exception will count as a single step, including the
exception.""")

#
# -------------------- penable / enable --------------------
#

def cpu_enable(cpu):
    try:
        # iface returns 1 if no state change
        p = not not cpu.iface.processor_info.enable_processor()
        if p:
            return "Already enabled, %s" % cpu.name
        else:
            return "Enabling processor %s" % cpu.name
    except Exception as ex:
        return "Failed enabling processor %s: %s" % (cpu.name, ex)

def penable_cmd(poly): # flag_t or obj_t
    def penable_helper(poly):
        if not poly:
            return penable_helper((obj_t, current_cpu_obj()))
        elif poly[0] == flag_t: # -all
            str = ""
            for o in simics.SIM_object_iterator_for_interface(["processor_info"]):
                str += penable_helper((obj_t, o))
                str += '\n'
            return str[:-1]
        else:
            cpu = poly[1]
            return cpu_enable(cpu)

    msg = penable_helper(poly)
    return command_return(message = msg, value = msg)

new_command("penable", penable_cmd,
            [arg((obj_t('processor', 'processor_info'), flag_t),
                 ("cpu-name", "-all"), "?")],
            type = ["Execution", "Processors"],
            short = "switch processor on",
            see_also = ["processor-status"],
            doc = """
Enables or disables a processor.

If no <arg>cpu-name</arg> is given, the current processor will be acted on. If
the flag <tt>-all</tt> is passed, all processors will be enabled/disabled.

A disabled processor is simply stalled for an infinite amount of time.
""")

def obj_enable_cmd(obj):
    msg = cpu_enable(obj)
    return command_return(message = msg, value = msg)

new_command("enable", obj_enable_cmd,
            [],
            type = ["Execution", "Processors"],
            iface = "processor_info",
            short = "switch processor on",
            doc_with = "penable")

#
# -------------------- enabled --------------------
#

def obj_enabled_cmd(obj):
    e_str = ['disabled', 'enabled']
    val = bool(obj.iface.processor_info.get_enabled())
    msg = "Processor %s is %s" % (obj.name, e_str[val])
    return command_return(message = msg, value = val)

new_command("enabled", obj_enabled_cmd,
            [],
            type = ["Processors"],
            iface = "processor_info",
            short = "get enable status",
            doc = """
Get enable status for the processor. Returns TRUE or FALSE when used
in expression and string when used interactively. Enabled is the
architectural state of the processor and not its simulation state.
""")

#
# -------------------- pdisable / disable --------------------
#

def cpu_disable(cpu):
    try:
        # iface returns 1 if no state change
        p = not not cpu.iface.processor_info.disable_processor()
        if p:
            return "Already disabled, %s" % cpu.name
        else:
            return "Disabling processor %s" % cpu.name
    except Exception as ex:
        raise CliError("Failed disabling processor %s: %s" % (cpu.name, ex))

def pdisable_cmd(poly):
    def pdisable_helper(poly):
        if not poly:
            return pdisable_helper((obj_t, current_cpu_obj()))
        elif poly[0] == flag_t: # -all
            str = ""
            for o in simics.SIM_object_iterator_for_interface(["processor_info"]):
                str += pdisable_helper((obj_t, o))
                str += '\n'
            return str[:-1]
        else:
            cpu = poly[1]
            return cpu_disable(cpu)

    msg = pdisable_helper(poly)
    return command_return(message = msg, value = msg)

new_command("pdisable", pdisable_cmd,
            [arg((obj_t('processor', 'processor_info'), flag_t),
                 ("cpu-name", "-all"), "?")],
            short = "switch processor off",
            doc_with = "penable")

def obj_disable_cmd(obj):
    msg = cpu_disable(obj)
    return command_return(message = msg, value = msg)

new_command("disable", obj_disable_cmd,
            [],
            iface = "processor_info",
            short = "switch processor off",
            doc_with = "pdisable")

#
# -------------------- processor-status / pstatus --------------------
#

def objects_implementing_iface(iface):
    return list(simics.SIM_object_iterator_for_interface([iface]))

def pstatus_cmd():
    cpus = objects_implementing_iface('processor_info')
    if not cpus:
        print("No processors defined")
        return
    data = [[cpu.name,
             "enabled" if cpu.iface.processor_info.get_enabled()
             else "disabled"]
            for cpu in cpus]
    props = [(Table_Key_Columns,
              [[(Column_Key_Name, n)] for n in ["Processor", "Status"]])]
    tbl = table.Table(props, data)
    print(tbl.to_string(rows_printed=0, no_row_column=True))

new_command("processor-status", pstatus_cmd,
            [],
            type = ["Processors", "Inspection"],
            short = "show processors' status",
            see_also = ["penable", "pdisable"],
            alias = "pstatus",
            doc = """
Show the enabled/disabled status of all processors in the Simics session.
            """)

#
# -------------------------- memory profiling --------------------------
#

cpu_mem_prof_type = {"read"  : simics.Sim_RW_Read,
                     "write" : simics.Sim_RW_Write}
def cpu_mem_prof_type_expander(prefix):
    return get_completions(prefix, list(cpu_mem_prof_type.keys()))
def print_valid_mem_prof_types():
    print("Valid types are: %s" % ", ".join(list(cpu_mem_prof_type.keys())))

def add_memory_profiler_cmd(cpu, type, obj):
    try:
        i = cpu_mem_prof_type[type]
    except:
        print("'%s' is not a valid profiler type." % type)
        print_valid_mem_prof_types()
        return

    if cpu.iface.memory_profiler.get(i) != None:
        print(("There is an active profiler for memory %s already: %s"
               % (type, cpu.iface.memory_profiler.get(i).name)))
        return

    if obj:
        cpu.iface.memory_profiler.set(i, obj)
    else:
        # create a new profiler
        name = cmputil.derived_object_name(cpu, '_%s_mem_prof' % type)
        try:
            prof = SIM_get_object(name)
            print(("[%s] Existing profiler added for memory %s: %s"
                   % (cpu.name, type, name)))
        except:
            gran = cpu.iface.memory_profiler.get_granularity_log2()
            desc = "data profiler"
            prof = simics.SIM_create_object('data-profiler', name,
                                            [['description', desc],
                                             ['granularity', gran],
                                             ['physical_addresses', 1]])
            print(("[%s] New profiler added for memory %s: %s"
                   % (cpu.name, type, name)))
        cpu.iface.memory_profiler.set(i, prof)

def remove_memory_profiler_cmd(cpu, type):
    if not type in cpu_mem_prof_type:
        print("'%s' is not a valid profiler type." % type)
        print_valid_mem_prof_types()
    else:
        cpu.iface.memory_profiler.set(cpu_mem_prof_type[type], None)

def list_memory_profilers_cmd(cpu):
    for t in list(cpu_mem_prof_type.keys()):
        obj = cpu.iface.memory_profiler.get(cpu_mem_prof_type[t])
        if obj:
            name = obj.name
        else:
            name = ""
        print("%20s: %s" % (t, name))

new_command("add-memory-profiler", add_memory_profiler_cmd,
            [arg(str_t, "type", expander = cpu_mem_prof_type_expander),
             arg(obj_t("data-profiler", "data-profiler"), "profiler", "?")],
            iface = "memory_profiler",
            type  = ["Memory", "Profiling"],
            short="add a memory profiler to the processor",
            doc  = """
Adds a data profiler to the specified processor that will record either
reads or writes to memory (indexed on physical address) depending on
whether the <arg>type</arg> argument is 'read' or 'write'. An existing
data profiler may be specified with the <arg>profiler</arg> argument;
otherwise, a new data profiler will be created.""")

new_command("remove-memory-profiler", remove_memory_profiler_cmd,
            [arg(str_t, "type", expander = cpu_mem_prof_type_expander)],
            iface = "memory_profiler",
            type  = ["Memory", "Profiling"],
            short="remove a memory profiler from the processor",
            doc  = """
Remove any memory profiler of the specified <arg>type</arg> ('read' or
'write') currently attached to the processor.""")

new_command("list-memory-profilers", list_memory_profilers_cmd,
            [],
            iface = "memory_profiler",
            type  = ["Memory", "Profiling"],
            short="list memory profilers connected to the processor",
            doc  = """
Lists all memory profilers connected to the processor, and what kind of
data they are collecting.""")

#
# -------------------- run --------------------
#

_run_cmd_finished = False
user_run_queue = None

def user_time_stop(obj, arg):
    global _run_cmd_finished
    (clock, queue, units_left) = arg
    if step_info.obj and _register_trace:
        _register_trace.show(step_info.obj)
    if units_left == 0:
        _run_cmd_finished = True
        simics.VT_stop_finished(None)
    else:
        if queue == 'step':
            simics.SIM_event_post_step(clock, user_time_stop_ev, conf.sim, 1,
                                       (clock, queue, units_left - 1))
        else:
            simics.SIM_event_post_cycle(clock, user_time_stop_ev, conf.sim, 1,
                                        (clock, queue, units_left - 1))

user_time_stop_ev = simics.SIM_register_event(
    "user time stop", "sim", simics.Sim_EC_Notsaved, user_time_stop,
    None, None, None, None)

class StepInfo:
    """Keep track of current step command object. Used to print disassembly."""
    def __init__(self):
        self.obj = None
        self.hap = 0

step_info = StepInfo()

def step_trace_instruction(arg, obj, la, va, pa, opcode):
    assert obj == step_info.obj
    local_print_disassemble_line(obj, "v", va)

def step_trace_exception(arg, obj, exc):
    assert obj == step_info.obj
    print('[%s] Exception: %s' % (obj.name, obj.iface.exception.get_name(exc)))

def prepare_step_handler(obj):
    if not hasattr(obj.iface, simics.EXEC_TRACE_INTERFACE):
        return
    step_info.obj = obj
    obj.iface.exec_trace.register_tracer(step_trace_instruction, None)
    step_info.hap = SIM_hap_add_callback_obj("Core_Exception",
                                             obj, 0,
                                             step_trace_exception, None)

def cleanup_step_handler():
    if not step_info.obj:
        return
    step_info.obj.iface.exec_trace.unregister_tracer(
        step_trace_instruction, None)
    SIM_hap_delete_callback_obj_id("Core_Exception", step_info.obj,
                                   step_info.hap)
    step_info.obj = None

about_to_start = False

def run_continue(cmdline, asynch, final_clbk):
    global about_to_start
    about_to_start = False

    # Let prompt_information know from which cmdline the command was originally
    # issued, so it prints the stop information to the correct frontend later
    # on. See prompt_information.py.
    set_sim_started_cmdline(cmdline)
    _started_sim()
    try:
        simics.SIM_continue(0)
    except simics.SimExc_General as ex:
        if asynch:
            # we are run from the work queue, cannot throw cli exception
            print("failed to run simulation: %s" % ex)
            return
        else:
            raise CliError("failed to run simulation: %s" % ex)
    finally:
        if final_clbk:
            final_clbk()

def run_simulation(asynch, final_clbk, force_asynch = False):
    cmdline = cli.get_current_cmdline()
    global about_to_start
    if about_to_start:
        raise CliError("Simics is already running.")
    about_to_start = True
    if force_asynch or (asynch and cli.async_cmdline()):
        simics.SIM_run_alone(
            lambda x: run_continue(cmdline, True, final_clbk), None)
    else:
        run_continue(cmdline, False, final_clbk)

def user_continue(cmd, sb_block, force_asynch):
    global _run_cmd_finished

    _run_cmd_finished = False
    if sb_in_main_branch():
        run_simulation(True, None, force_asynch)
    else:
        if sb_block:
            sb_run_in_main_branch(cmd, lambda: simics.SIM_continue(0))
        else:
            simics.SIM_thread_safe_callback(simics.SIM_continue, 0)
            sb_wait_for_simulation_started_internal()

_sim_stop_handler_id = None

def _started_sim():
    global _sim_stop_handler_id

    if _sim_stop_handler_id == None:
        _sim_stop_handler_id = SIM_hap_add_callback("Core_Simulation_Stopped",
                                                    simulation_stopped_handler,
                                                    None)

def simulation_stopped_handler(arg, obj, exc, str):
    global _sim_stop_handler_id, user_run_queue

    SIM_hap_delete_callback_id("Core_Simulation_Stopped", _sim_stop_handler_id)
    _sim_stop_handler_id = None
    if user_run_queue:
        try:
            simics.SIM_event_cancel_step(user_run_queue, user_time_stop_ev,
                                         conf.sim, None, None)
        except simics.SimExc_InterfaceNotFound:
            pass
        simics.SIM_event_cancel_time(user_run_queue, user_time_stop_ev,
                                     conf.sim, None, None)
        user_run_queue = None
    # Cleanup step handler if any
    cleanup_step_handler()

def get_diff_regs(cpu):
    """Yields the registers to trace."""
    if (not hasattr(cpu.iface, "processor_cli") or
        cpu.iface.processor_cli.get_diff_regs == None):
        return
    diff_regs = cpu.iface.processor_cli.get_diff_regs()

    if callable(diff_regs):
        diff_regs = diff_regs(cpu)
    for r in cpu.iface.int_register.all_registers():
        if cpu.iface.int_register.get_name(r) in diff_regs:
            yield r

class RegisterTrace:
    """Trace registers for a processor."""
    def __init__(self, cpu):
        self.cpu = cpu
        self.old_regs = {}
        if hasattr(cpu.iface, "int_register"):
            for r in get_diff_regs(cpu):
                self.old_regs[r] = cpu.iface.int_register.read(r)
    def show(self, cpu):
        if cpu != self.cpu:
            return
        for r in get_diff_regs(cpu):
            new_val = cpu.iface.int_register.read(r)
            try:
                old_val = self.old_regs[r]
            except KeyError:
                self.old_regs[r] = new_val
            else:
                if new_val != old_val:
                    self.old_regs[r] = new_val
                    print("\t%s <- %s" % (
                        cpu.iface.int_register.get_name(r),
                        number_str(new_val)))

def cpu_disabled_state(cpu):
    if (hasattr(cpu.iface, simics.PROCESSOR_INFO_INTERFACE)
        and not cpu.iface.processor_info.get_enabled()):
        return 'disabled'
    elif (hasattr(cpu.iface, simics.STALL_INTERFACE)
          # compare with arbitrarily chosen high value:
          and simics.SIM_stalled_until(cpu) > 100000):
        return 'stalling'
    elif (hasattr(cpu.iface, simics.X86_REG_ACCESS_INTERFACE)
          and cpu.iface.x86_reg_access.get_activity_state()
          != simics.X86_Activity_Normal):
        return 'sleeping/waiting'
    else:
        return None

_register_trace = None

def run_with_current_ps_queue(cmd, ps, force_asynch):
    assert ps >= 0

    clock = current_ps_queue_null()
    if not clock:
        raise CliError("Current frontend object (%s) does not"
                       " support ps queue. Use 'run-cycles' instead."
                       % (current_frontend_object().name,))
    try:
        simics.SIM_event_post_cycle(clock, user_time_stop_ev,
                                    conf.sim, ps, (clock, 'cycle', 0))
    except (simics.SimExc_General, OverflowError) as ex:
        raise CliError(str(ex))

    global user_run_queue
    user_run_queue = clock
    user_continue(cmd, True, force_asynch)

def check_count_unit(count, unit, units):
    if unit not in units:
        if not unit:
            raise CliError("A time unit must be provided.")
        else:
            raise CliError("Unknown time unit: %s" % unit)
    if unit and count is None:
        raise CliError("Unit specified without a value")
    if count is not None and count < 0:
        raise CliError("Negative time %d specified" % count)

def run_cmd(count, unit, non_blocking):
    from targets import target_commands
    global user_run_queue

    if non_blocking and not sb_in_main_branch():
        raise CliError("run -non-blocking not allowed in a script-branch")

    target_commands.config.run_cmd()
    assert_stopped()

    check_count_unit(count, unit, set(run_units) | {"cycle", "step", None})
    if unit == "step":
        unit = "steps"
    if unit == "cycle":
        unit = "cycles"

    clock = None
    if unit == "steps":
        clock = current_step_queue_null()
        if not clock:
            raise CliError("Current frontend object does not support"
                           " stepping. Use cycles or time instead.")
    elif unit is None:
        clock = current_step_queue_null()
        # fall back to cycles if no unit specified and no step object
        unit = "steps" if clock else "cycles"

    if count is None:
        cli.disable_command_repeat()
    else:
        if unit == "steps":
            assert clock is not None
            state = cpu_disabled_state(clock)
            if state and cli.interactive_command():
                # warn that it may take a long time for command to finish
                print(
                    "Processor %s is %s - may take a long time to finish."
                    % (clock.name, state))
            simics.SIM_event_post_step(clock, user_time_stop_ev,
                                       conf.sim, count, (clock, 'step', 0))
        elif unit == "cycles":
            clock = current_cycle_queue()
            try:
                simics.SIM_event_post_cycle(
                    clock, user_time_stop_ev,
                    conf.sim, count, (clock, 'cycle', 0))
            except simics.SimExc_General as ex:
                raise CliError(str(ex))
        else:
            run_with_current_ps_queue("run", count * time_units[unit],
                                      non_blocking)
            if non_blocking:
                raise cli.CliQuietError(None)
            return

    user_run_queue = clock
    user_continue('run', count is not None, non_blocking)
    if non_blocking:
        raise cli.CliQuietError(None)

async_note = """
Unlike other commands, the <cmd>run</cmd> and <cmd>run-cycles</cmd> commands
will not block the command line when run interactively.
"""

async_sb_note = """
In script branches, the command will not block the script execution when run
without the <arg>count</arg> argument. It will instead continue executing the
next command as soon as the simulation has been started. When run with the
<arg>count</arg> argument, the command will block until reaching the specified
point in time."""

new_command("run", run_cmd,
            [arg(sint64_t, "count", "?", None),
             arg(str_t, "unit", "?", None, expander = run_unit_expander),
             arg(flag_t, "-non-blocking")],
            alias = ["continue", "c", "r"],
            type = ["Execution"],
            repeat = run_cmd,
            short = "start execution",
            see_also = ["step-instruction", "run-cycles",
                        "bp.time.run-until", "bp.cycle.run-until"],
            doc = """
Starts running the simulation. If the <arg>count</arg> argument is provided,
Simics will execute <arg>count</arg> number of time units on the currently
selected frontend processor and then stop. The time unit, provided by the
<arg>unit</arg> argument, can be one of <tt>steps, cycles, s, ms, us, ns,
ps</tt>, <tt>m</tt> or <tt>h</tt>. If no time unit is supplied,
<arg>count</arg> is interpreted as steps
if supported by the frontend processor, or else as cycles.

The command will raise an error if the simulation is already running.

When it is needed to reach a specified point in the simulation time one can use
commands <cmd>bp.time.run-until</cmd> and <cmd>bp.cycle.run-until</cmd> that
accept the <tt>-absolute</tt> flag. See the documentation of these command for
information about their usage.

When used in a script, the <cmd>run</cmd> command will block further script
execution until the simulation stops, similar to other CLI commands. This
behavior can be overridden by the <tt>-non-blocking</tt> flag, that also has
the side-effect of exiting all script execution. This flag is typically used
at the end of a script to start simulation and still get an interactive
command line.
""" + async_note + async_sb_note)

def run_cycles_cmd(count):
    global user_run_queue

    assert_stopped()

    if count is None:
        user_run_queue = None
    elif count >= 0:
        queue = current_cycle_queue()

        simics.SIM_event_post_cycle(queue, user_time_stop_ev,
                                    conf.sim, count,
                                    (queue, 'cycle', 0))
        user_run_queue = queue
    else:
        raise CliError("Negative number of cycles: %d" % count)

    user_continue('run-cycles', count is not None, False)

new_command("run-cycles", run_cycles_cmd,
            [arg(sint64_t, "count", "?", None)],
            alias = ["continue-cycles", "cc", "rc"],
            type = ["Execution"],
            see_also = ["step-cycle", "run"],
            repeat = run_cycles_cmd,
            short = "start execution",
            doc = """
Starts or continues executing cycles. If a <arg>count</arg> argument is
provided, Simics will execute <arg>count</arg> number of cycles on the
currently selected frontend processor and then stop. Running <arg>count</arg>
cycles may or may not be equivalent to running <arg>count</arg> instructions
depending on the processor configuration.
"""  + async_note + async_sb_note)

def stop_cmd(a_flag, msg):
    if a_flag:
        simics.VT_interrupt_script(True)
    simics.VT_stop_user(msg)
    if not sb_in_main_branch():
        sb_wait_for_hap_internal(
            'stop', "Core_Simulation_Stopped", None, 0)

new_command("stop", stop_cmd,
            [arg(flag_t, "-a"),
             arg(str_t, "message", "?", None)],
            type = ["Execution"],
            repeat = stop_cmd,
            short = "interrupt simulation",
            see_also = ["run", "interrupt-script"],
            doc = """
Stops the simulation as soon as possible. If the <tt>-a</tt> argument is
given, any command script running will also be interrupted. A
<arg>message</arg> to be printed on the console when the simulation stops
can also be supplied. If the <cmd>stop</cmd> command is called from a script
branch, then the branch will wait for the simulation to finish before the
command returns. When called from the main branch, the simulation may still
execute when the command returns.
""")

def run_seconds_cmd(secs):
    assert_stopped()
    if secs < 0:
        raise CliError("Negative number of seconds: %f" % secs)
    run_with_current_ps_queue("run-seconds", int(secs * 1e12), False)

new_command("run-seconds", run_seconds_cmd,
            [arg(float_t, "seconds")],
            alias = ["continue-seconds"],
            type = ["Execution"],
            see_also = ["run-cycles"],
            repeat = run_seconds_cmd,
            short = "execute for seconds",
            doc = """
Starts or continues executing instructions for a period of
<arg>seconds</arg> of virtual time and stops the simulation.
""")

#
# -------------------- stepi --------------------
#

@contextlib.contextmanager
def blocked_vmp_warnings(cpu, quiet):
    # Block VMP warnings. The step implementation uses the
    # Core_Exception hap which is not possible in VMP
    # mode. This prevents Simics from printing a warning.
    block = hasattr(cpu, "block_vmp_warnings") and not quiet
    if block:
        saved = cpu.block_vmp_warnings
        cpu.block_vmp_warnings = True
    yield cpu
    if block:
        cpu.block_vmp_warnings = saved

def run_stepi(count, register_trace, quiet):
    global user_run_queue, _register_trace

    with blocked_vmp_warnings(current_step_queue(), quiet) as cpu:
        state = cpu_disabled_state(cpu)
        if state:
            # stepi command may block for a very long time, disallow instead
            raise CliError(
                'Cannot run steps on %s processor %s.' % (state, cpu.name))

        if not quiet:
            # The step handler will use exec-trace that flushes
            # turbo/icode and may affect the simulation state when
            # debugging Simics. Use -q to reduce side effects.
            prepare_step_handler(cpu)

        simics.SIM_event_post_step(cpu, user_time_stop_ev, conf.sim, 1,
                                   (cpu, 'step', count - 1))
        user_run_queue = cpu

        if register_trace:
            _register_trace = RegisterTrace(cpu)
        else:
            _register_trace = None
        run_simulation(False, None)

def stepi_cmd(count, r, quiet):
    if count < 0:
        raise CliError("Negative number of steps: %d" % count)
    elif count == 0:
        return
    assert_stopped()
    run_stepi(count, r, quiet)

new_command("step-instruction", stepi_cmd,
            [arg(sint64_t, "count", "?", 1),
             arg(flag_t, "-r"), arg(flag_t, "-q")],
            alias = [ "si", "stepi" ],
            type = ["Execution"],
            short = "step one or more instructions",
            repeat = stepi_cmd,
            see_also = ["run", "step-cycle", "force-step-instruction"],
            doc = """
Executes <arg>count</arg> instructions, printing instruction executed, or
exception taken, at each step. <arg>count</arg> defaults to one. With the
<tt>-r</tt> flag, register changes will also be printed. The <tt>-q</tt> flag
tells the command not to disassemble the executed instruction.
""")

#
# -------------------- step-cycle --------------------
#

def run_stepc(count):
    global user_run_queue

    with blocked_vmp_warnings(current_cycle_obj(), False) as cpu:
        prepare_step_handler(cpu)
        simics.SIM_event_post_cycle(cpu, user_time_stop_ev, conf.sim, 1,
                                    (cpu, 'cycle', count - 1))
        user_run_queue = cpu

        run_simulation(False, None)

def step_cycle_cmd(count):
    if count < 0:
        raise CliError("Negative number of cycles: %d" % count)
    elif count == 0:
        return
    assert_stopped()
    run_stepc(count)

new_command("step-cycle", step_cycle_cmd,
            [arg(sint64_t, "count", "?", 1)],
            alias = "sc",
            type = ["Execution"],
            repeat = step_cycle_cmd,
            see_also = ["run", "step-instruction", "force-step-instruction"],
            short = "step one or more cycles",
            doc = """
Executes <arg>count</arg> cycles, printing the next instruction to be executed
at each cycle. <arg>count</arg> defaults to one.
""")

#
# ------------------ force-step-instruction ------------------
#

def next_in_cyclic_list(entry, lst):
    """return the element after entry in the list, treated as a cyclic one"""
    return lst[(lst.index(entry) + 1) % len(lst)]

class _test_next_in_cyclic_list(unittest.TestCase):
    def test(self):
        self.assertEqual(next_in_cyclic_list(3, [2, 3, 5, 7]), 5)
        self.assertEqual(next_in_cyclic_list(7, [2, 3, 5, 7]), 2)

def next_step_object(obj):
    return next_in_cyclic_list(obj, conf.sim.current_cell.schedule_list)

def force_stepi_cleanup(stallable_cpus):
    for (cpu, (count, stall)) in stallable_cpus.items():
        # adjust the old stall count with time elapsed during the force-step
        elapsed = simics.SIM_cycle_count(cpu) - count
        simics.SIM_stall_cycle(cpu, max(0, stall - elapsed))

def run_force_stepi(cpu, count, register_trace, quiet):
    global user_run_queue, _register_trace

    if not quiet:
        prepare_step_handler(cpu)

    simics.SIM_event_post_step(cpu, user_time_stop_ev, conf.sim, 1,
                               (cpu, 'step', count - 1))
    user_run_queue = cpu

    if register_trace:
        _register_trace = RegisterTrace(cpu)

    stallable_cpus = {}
    for obj in simics.SIM_object_iterator_for_interface(
            [simics.EXECUTE_INTERFACE, simics.STALL_INTERFACE]):
        if obj == cpu:
            continue
        stallable_cpus[obj] = (
            simics.SIM_cycle_count(obj), simics.SIM_stalled_until(obj))
        simics.SIM_stall_cycle(obj, 0x7fffffffffffffff)
    run_simulation(False, lambda: force_stepi_cleanup(stallable_cpus))
    # remove step handler since next step may be on a different processor

    if not quiet:
        cleanup_step_handler()

def force_step_instruction_cmd(count, regs, next, quiet):
    assert_stopped()
    for _ in range(count):
        cpu = current_step_obj()
        state = cpu_disabled_state(cpu)
        if state:
            # refuse to step if processor is stalling
            raise CliError(f"Cannot force-step on {state} processor")
        run_force_stepi(cpu, 1, regs, quiet)
        if next:
            cli.set_current_frontend_object(next_step_object(cpu), silent = True)

new_command("force-step-instruction", force_step_instruction_cmd,
            [arg(range_t(0, cli_impl.int32_max, "a nonnegative number"),
                 "count", "?", 1),
             arg(flag_t, "-r"),
             arg(flag_t, "-n"),
             arg(flag_t, "-q")],
            type = ["Execution"],
            short = "step instructions while other processors stall",
            alias = ["fstepi", "fsi"],
            repeat = force_step_instruction_cmd,
            see_also = ["step-instruction", "step-cycle"],
            doc = """
Executes <arg>count</arg> instructions on the currently selected frontend
processor, printing the instruction executed at each step. The default value
for <arg>count</arg> is 1. No instructions are run on other processors,
although their virtual time may pass. As a result, the default round-robin
scheduling of processors is not obeyed. The <cmd>force-step-instruction</cmd>
command will refuse to run if the processor is stalling.

The <tt>-n</tt> flag tells the command to switch to the next processor in the
scheduling list of the cell after each instruction.

With the <tt>-r</tt> flag, register changes are printed after every step.

The <tt>-q</tt> flag tells the command not to disassemble the executed
instruction.

Since the <cmd>force-step-instruction</cmd> command changes the default
scheduling order of processors, the same execution path will not be followed if
the simulation is rerun using reverse execution for example.
""")

def obj_force_step_instruction_cmd(cpu, count, regs, quiet):
    # Since the force-step runs instructions outside the normal scheduling, keep
    # the frontend processor untouched
    old_cpu = current_step_obj()
    cli.set_current_frontend_object(cpu, silent = True)
    try:
        force_step_instruction_cmd(count, regs, False, quiet)
    finally:
        cli.set_current_frontend_object(old_cpu, silent = True)

new_command("force-step-instruction", obj_force_step_instruction_cmd,
            [arg(range_t(0, cli_impl.int32_max, "a nonnegative number"),
                 "count", "?", 1),
             arg(flag_t, "-r"),
             arg(flag_t, "-q")],
            type = ["Execution"],
            short = "step instructions while other processors stall",
            alias = ["fstepi", "fsi"],
            iface = simics.STEP_INTERFACE,
            repeat = obj_force_step_instruction_cmd,
            doc_with = "force-step-instruction")

#
# -------------------- pselect --------------------
#

def pselect_cmd(obj):
    if not obj:
        cfo = current_frontend_object()
        return command_return(f"\"{cfo.name}\"", cfo)
    else:
        cli.set_current_frontend_object(obj)
        debugger_commands.update_debug_object(obj)

new_command("pselect", pselect_cmd,
            [arg(obj_t('processor/clock', ('processor_info', 'step', 'cycle')),
                 "obj", "?")],
            alias = "psel",
            type = ["CLI"],
            see_also = ['cpu'],
            short = "get or set the currently selected processor/clock",
            doc = """
Sets the default processor or clock object for the command line frontend.
Many global commands operate on this object when no other is specified.
Without any argument, the command returns the currently selected object for
the frontend.

The currently selected object is also available via the built-in <cmd>cpu</cmd>
alias. For example, the <cmd>cpu.info</cmd> command runs the 'info' command
of the currently selected object, and entering
<cmd>cpu.&lt;TAB&gt;&lt;TAB&gt;</cmd> on command-line interface provides
tab completion for the currently selected object.

The specified object, <arg>obj</arg>, must implement one of the
<iface>processor_info</iface>, <iface>step</iface> or <iface>cycle</iface>
interfaces.""")

#
# -------------------- print-event-queue --------------------
#

def print_event_queue_cmd(cpu, queue, internal):
    def hide(name):
        if ("clock source counter wrap" in name
            or "local time wrap" in name):
            return True
        return not internal and name.startswith('Internal:')

    msg = ""
    step_queue = []
    cycle_queue = []

    def add_events(evs, lst):
        data = []
        data.extend([t, obj, desc or name]
                    for (obj, name, t, desc) in evs
                    if not hide(name))
        lst.extend([t, obj, desc or name]
                   for (obj, name, t, desc) in evs
                   if not hide(name))
        return data

    def fill_table(head0, data):
        if data:
            header = [head0, "Object", "Description"]
            props = [(Table_Key_Columns,
                      [[(Column_Key_Name, n), (Column_Key_Int_Radix, 10)]
                       for n in header])]
            tbl =  table.Table(props, data)
            return tbl.to_string(rows_printed=0, no_row_column=True) + "\n\n"
        else:
            return ""

    if cpu and hasattr(cpu.iface, 'cycle_event'):
        data = add_events(cpu.iface.cycle_event.events(), cycle_queue)
        msg = fill_table("Cycle", data)
    else:
        if queue in (None, "step"):
            obj = cpu or current_step_obj_null()
            if obj and hasattr(obj.iface, 'step'):
                data = add_events(obj.iface.step.events(), step_queue)
                msg = fill_table("Step", data)
        if queue in (None, "cycle"):
            obj = cpu or current_cycle_obj_null()
            if obj and hasattr(obj.iface, 'cycle'):
                data = add_events(obj.iface.cycle.events(), cycle_queue)
                msg += fill_table("Cycle", data)

    if internal:
        obj = cpu or current_cycle_obj_null()
        ps_obj = simics.SIM_object_descendant(obj, "vtime.ps")
        if ps_obj and hasattr(ps_obj.iface, 'cycle_event'):
            data = add_events(ps_obj.iface.cycle_event.events(), cycle_queue)
            msg += fill_table("Time (ps)", data)
        if obj and hasattr(obj.iface, 'sc_simcontext'):
            data = add_events(obj.iface.sc_simcontext.events(), cycle_queue)
            msg += fill_table("SystemC (ps)", data)
    msg = msg.rstrip()

    if queue == "step":
        val = step_queue
    elif queue == "cycle":
        val = cycle_queue
    else:
        val = [step_queue, cycle_queue] if step_queue or cycle_queue else []
    return command_verbose_return(message=msg, value=val)

new_command("print-event-queue", print_event_queue_cmd,
            [arg(obj_t('step or cycle object',
                       ('step', 'cycle', 'cycle_event')), "obj", "?"),
             arg(string_set_t(["cycle", "step"]), "queue", "?", None),
             arg(flag_t, "-i")],
            alias = "peq",
            type = ["Inspection", "Processors", "Debugging"],
            short = "print event queue for processor",
            see_also = ['print-realtime-queue', 'pselect'],
            doc = """
Prints the event queues for a processor, i.e. an object implementing a step
or cycle queue. Events such as interrupts and exceptions are posted on these
event queues. For each event, the time to its execution, the object posting it
and a brief description is printed.

If the command is used in an expression, if no <arg>queue</arg> is given it
returns a list of lists of triplets, with the step queue as the first inner
list. Otherwise it returns a list of triplets for the given queue.

If no processor is specified in <arg>obj</arg>, the currently selected
frontend processor is used.

The <arg>queue</arg> can be used to select the "cycle" or the "step"
queue. The old integer values are deprecated.

The <tt>-i</tt> flag enables printing of Simics-internal events.""")

#
# --------------- print-realtime-queue ------------------
#

def print_realtime_queue_cmd():
    val =  simics.CORE_get_realtime_queue()
    msg = ""
    if val:
        props = [(Table_Key_Columns,
                  [[(Column_Key_Name, h)]
                   for h in ["Id", "Delay", "Left", "Function", "Data",
                             "Description"]])]
        tbl = table.Table(props, val)
        msg = tbl.to_string(rows_printed=0, no_row_column=True)

    return command_verbose_return(msg, val)

new_command("print-realtime-queue", print_realtime_queue_cmd,
            [],
            type  = ["Inspection", "Debugging"],
            short = "list all callbacks in the realtime event queue",
            see_also = ["print-event-queue"],
            doc = """
Prints a list of all callbacks in the realtime event queue. The output includes
an internal callback identifier, the delay in milliseconds from the time the
callback was posted until it will run, how much time is currently left of the
delay, a description of the function installed as callback with its
corresponding data and a user supplied description.
""")

#
# -------------------- read-reg --------------------
#
def exp_int_register(comp):
    """Expand to objects with int_register that has at least one register"""
    return get_completions(comp, (obj.name for obj in SIM_object_iterator(None)
                                  if hasattr(obj.iface, "int_register")
                                  and obj.iface.int_register.all_registers()))

def read_reg_cmd(cpu, reg_name):
    if not cpu:
        cpu = current_frontend_object()
    return obj_read_reg_cmd(cpu, reg_name)

def read_default_reg_cmd(reg_name):
    try:
        cpu = current_frontend_object()
        val = obj_read_reg_cmd(cpu, reg_name)
    except:
        (exception, value, tb) = sys.exc_info()
        raise CliError(("'%%' command: reading register '%s' failed (%s).\n\n"
                        + "If you meant to use a path like %%simics%%,"
                        + " verify that you quote the string properly: %s") % (
                reg_name,
                value,
                '"%%simics%%%s..."' % os.sep.replace('\\', '\\\\')))
    return val

# This command is namespace_copied to processor_info instead of int_register
#  to avoid having it show up on DML 1.2 bank port-objects
# do not change command parameters without updating exp_regs
new_command("read-reg", read_reg_cmd,
            [arg(obj_t('object implementing int_register interface',
                       'int_register'), "cpu-name", "?",
                 expander = exp_int_register),
             arg(str_t, "reg-name", expander = exp_regs)],
            type  = ["Registers", "Inspection"],
            short = "read a register",
            namespace_copy = ("processor_info", obj_read_reg_cmd),
            see_also = ['%', 'write-reg', 'print-processor-registers', 'pselect'],
            doc = """
Reads the register <arg>reg-name</arg> from an object implementing the
<iface>int_register</iface> interface.

To read the <tt>eax</tt> register in an x86 processor called <obj>cpu0</obj>,
the command invocation is <cmd>read-reg cpu0 eax</cmd>. There is also a
namespace version <cmd>cpu0.read-reg eax</cmd> or the more convenient variant
<tt>%eax</tt> that reads a register from the current frontend processor.

If no processor is selected using <arg>cpu-name</arg>, the current frontend
processor is used.""")

new_operator("%", read_default_reg_cmd,
             [arg(str_t, doc = "reg", expander = exp_regs)],
             pri = 1000,
             check_args = False,
             type  = ["Registers", "Inspection", "CLI"],
             short = "read register by name, module or string formatting",
             synopses = [[Markup.Keyword('%'), Markup.Arg('reg')],
                         [Markup.Arg('arg1'), ' ',
                          Markup.Keyword('%'), ' ', Markup.Arg('arg2')]],
             see_also = ["read-reg", "write-reg", "print-processor-registers",
                         "pselect"],
             doc ="""
When used as a prefix on a register name, the register <arg>reg</arg> for the
current frontend processor is accessed. This is a convenient way to use
register values in expressions like
<cmd>disassemble (%pc <math>-</math> 4*3) 10</cmd> or <cmd>%pc = 0x1000</cmd>.

The % operator is also used for arithmetic modulo of integer and floating
point values.

If the argument to the left of the % operator is a string, then string
formatting using Python format specifiers such as %s and %d is performed. To
provide multiple values to be formatted, a CLI list should be used as right
hand argument. For example:<br/>
<pre>
simics> "about %.2f %s" % [5.12345, "hours"]
about 5.12 hours
</pre>
""")

def modulo_cmd(a, b):
    if a[0] in (int_t, float_t) and b[0] in (int_t, float_t):
        if b[1] == 0:
            raise CliError("Modulo by zero")
        return a[1] % b[1]
    elif a[0] == str_t:
        try:
            s = a[1].replace("%simics%", "%%simics%%").replace("%script%",
                                                               "%%script%%")
            return s % (tuple(b[1]) if b[0] == list_t else b[1])
        except TypeError as ex:
            raise CliError("%s" % ex)
    else:
        raise CliError("Unsupported types for % operator")

new_operator("%%", modulo_cmd,
             [arg((int_t, str_t, float_t)),
              arg((int_t, str_t, list_t, float_t))],
             pri = 200, infix = 1, hidden = True,
             doc ="")

#
# -------------------- write-reg --------------------
#

def write_reg_cmd(cpu, reg_name, value):
    if not cpu:
        cpu = current_frontend_object()
    obj_write_reg_cmd(cpu, reg_name, value)

# This command is namespace_copied to processor_info instead of int_register
#  to avoid having it show up on DML 1.2 bank port-objects
# do not change command parameters without updating exp_regs
new_command("write-reg", write_reg_cmd,
            [arg(obj_t('object implementing int_register interface',
                       'int_register'), "cpu-name", "?",
                 expander = exp_int_register),
             arg(str_t, "reg-name", expander = exp_regs),
             arg(integer_t, "value")],
            type  = ["Registers"],
            short = "write to register",
            namespace_copy = ("processor_info", obj_write_reg_cmd),
            see_also = ['%', 'read-reg', 'print-processor-registers',
                        'pselect'],
            doc = """
Set the register <arg>reg-name</arg> to <arg>value</arg>.

To set the <tt>eax</tt> register on the x86 processor <obj>cpu0</obj> to 3,
the command invocation is <cmd>write-reg cpu0 eax 3</cmd>. There is also a
namespace version <cmd>cpu0.write-reg eax 3</cmd> or the more convenient
variant <tt>%eax = 3</tt> that writes a register on the current frontend
processor.

This function may or may not have the correct side-effects, depending on
target and register. If no <arg>cpu-name</arg> is given, the current frontend
processor is used.""")


#
# -------------------- print-processor-registers --------------------
#

def local_pregs(cpu, all):
    try:
        pregs = cpu.iface.processor_cli.get_pregs
    except simics.SimExc_Lookup:
        print("Command pregs not available for object %s" % cpu.name)
        return
    str = pregs(all)
    print(str)

def pregs_cmd(cpu, a):
    if not cpu:
        cpu = current_cpu_obj()
    local_pregs(cpu, a)

def obj_pregs_cmd(obj, all):
    local_pregs(obj, all)

new_command("print-processor-registers", pregs_cmd,
            [arg(obj_t('processor', 'processor_info'), "cpu-name", "?"),
             arg(flag_t, "-all")],
            type  = ["Registers", "Inspection", "Processors"],
            short = "print cpu registers",
            namespace_copy = ("processor_info", obj_pregs_cmd),
            alias = "pregs",
            doc = """
Prints the current integer register file of the processor
<arg>cpu-name</arg>. If no CPU is specified, the current CPU will be
selected. The <tt>-all</tt> flag causes additional registers, such as control
registers and floating point registers to be printed.
""")

#
# -------------------- logical-to-physical --------------------
#

def obj_logical_to_physical_cmd(obj, laddr):
    try:
        return translate_to_physical(obj, laddr)
    except simics.SimExc_Memory as ex:
        raise CliError(str(ex))

def logical_to_physical_cmd(cpu, laddr):
    if not cpu:
        cpu = current_cpu_obj()
    return obj_logical_to_physical_cmd(cpu, laddr)

new_command("logical-to-physical", logical_to_physical_cmd,
            [arg(obj_t('processor', 'processor_info'), "cpu-name", "?"),
             arg(addr_t,"address")],
            alias = "l2p",
            type  = ["Memory", "Inspection", "Processors"],
            short = "translate logical address to physical",
            namespace_copy = ("processor_info", obj_logical_to_physical_cmd),
            doc = """
Translate the given logical <arg>address</arg> to a physical one. The
operation is performed as data read from processor <arg>cpu-name</arg>.

For x86 CPUs, a logical address can be specified as &lt;segment
register&gt;:&lt;offset&gt; or l:&lt;linear address&gt;. If no prefix
is given ds:&lt;offset&gt; will be assumed.

If the CPU is omitted the current CPU will be used.

No side-effects will be triggered; e.g., if the translation is not in
the TLB.""")

#
# -------------------- disassemble --------------------
#

def disassemble_cmd_sub(cpu, prefix, addr, count, bytes = -1):

    start_addr = addr
    if bytes >= 0:
        count = 99999
    for i in range(count):
        instr_len = local_print_disassemble_line(cpu, prefix, addr, 0)
        if instr_len <= 0:
            break
        addr = addr + instr_len
        if bytes >= 0 and addr >= start_addr + bytes:
            break

    # save the last address if repeat
    cli.set_repeat_data(disassemble_cmd_sub, addr)

def disassemble_cmd_rep(cpu, address, count, bytes):
    if not cpu:
        cpu = current_cpu_obj()
    addr = cli.get_repeat_data(disassemble_cmd_sub)
    disassemble_cmd_sub(cpu, address[0], addr, count, bytes)

def disassemble_cmd(cpu, address, count, bytes):
    if not cpu:
        cpu = current_cpu_obj()
    if count <= 0:
        raise CliError("Illegal instruction count.")
    if address[1] == -1:
        if address[0] == "p":
            pc = cpu.iface.processor_info.get_program_counter()
            tagged_addr = cpu.iface.processor_info.logical_to_physical(pc, Sim_Access_Execute)
            if tagged_addr.valid:
                addr = tagged_addr.address
            else:
                raise simics.SimExc_Memory("Address not mapped")
        else:
            addr = cpu.iface.processor_info.get_program_counter()
    else:
        addr = address[1]

    disassemble_cmd_sub(cpu, address[0], addr, count, bytes)

new_command("disassemble", disassemble_cmd,
            [arg(obj_t('processor', 'processor_info'), "cpu-name", "?"),
             arg(addr_t, "address", "?", ("v",-1)),
             arg(int_t, "count", "?", 1),
             arg(int_t, "bytes", "?", -1)],
            alias = "da",
            repeat = disassemble_cmd_rep,
            type  = ["Memory", "Inspection", "Processors"],
            short = "disassemble instructions",
            namespace_copy = ("processor_info", disassemble_cmd),
            see_also = ["x", "disassemble-settings"],
            doc = """
Disassembles <arg>count</arg> instructions or <arg>bytes</arg> octets starting
at <arg>address</arg> for processor <arg>cpu-name</arg>. If the processor is
not given the current frontend processor will be used. You may also select a
processor, e.g. <cmd>cpu0.disassemble</cmd>.

On some architectures, <arg>address</arg> must be word aligned. A
physical address is given by prefixing the address with <tt>p:</tt>
(e.g., <tt>p:0xf000</tt>). With no prefix, a virtual address will be
assumed. If the address is omitted the current program counter will be
used. <arg>count</arg> defaults to 1 instruction.

Global disassembly settings, such as whether to print the raw opcodes,
can be set by the <cmd>disassemble-settings</cmd> command.

If supported by the processor, this command will also include various
profiling statistics for the address of each instruction. One column
is printed for each selected profiler. See the <tt>aprof-views</tt>
command in each processor for more information.""")

#
# -------------------- set-pc --------------------
#

def cpu_set_pc_cmd(cpu_obj, address):
    try:
        cpu_obj.iface.processor_info.set_program_counter(address)
    except Exception as ex:
        raise CliError("Failed setting program counter: %s" % ex)

def set_pc_cmd(address):
    try:
        cpu = current_cpu_obj()
        cpu.iface.processor_info.set_program_counter(address)
    except Exception as ex:
        raise CliError("Failed setting program counter: %s" % ex)

new_command("set-pc", set_pc_cmd,
            [arg(uint64_t, "address",)],
            type  = ["Registers", "Execution", "Processors"],
            short = "set the current processor's program counter",
            doc = """
Set program counter (instruction pointer) of the processor (defaults to
the current frontend processor) to <arg>address</arg>.
""")

for n in ["processor_info"]:
    new_command("set-pc", cpu_set_pc_cmd,
                [arg(uint64_t, "address",)],
                iface = n,
                short = "set the program counter",
                doc_with = "set-pc")

#
# -------------------- instruction-fetch-mode --------------------
#
instruction_fetch_modes = ["no-instruction-fetch", "instruction-cache-access-trace", "instruction-fetch-trace"]

def instruction_fetch_mode(cpu, mode):
    if mode:
        try:
            num = instruction_fetch_modes.index(mode)
        except ValueError:
            raise CliError("Unknown instruction fetch mode: %s" % mode)
        cpu.iface.instruction_fetch.set_mode(num)
    else:
        mode = cpu.iface.instruction_fetch.get_mode()
        print(cpu.name + ": " + instruction_fetch_modes[mode])

def ifm_expander(prefix):
    return get_completions(prefix, instruction_fetch_modes)

new_command("instruction-fetch-mode", instruction_fetch_mode,
            args = [arg(str_t, "mode", "?", "", expander = ifm_expander)],
            alias = "ifm",
            type = ["Execution", "Profiling", "Tracing"],
            iface = "instruction_fetch",
            short="set or get current mode for instruction fetching",
            doc = """
This command selects in which <arg>mode</arg> instruction fetches are sent for
the memory hierarchy
during simulation. If set to <i>no-instruction-fetch</i>, the memory hierarchy
will not receive any instruction fetch. If set to
<i>instruction-cache-access-trace</i>, the memory hierarchy will receive
exactly one instruction fetch every time a new cache line is accessed. The size
of this cache line is defined by the attribute
<i>instruction-fetch-line-size</i> in the processor object. If set to
<i>instruction-fetch-trace</i>, all instruction fetches will be visible.

Note that for x86 CPUs, <i>instruction-cache-trace-access</i> is not available.
On some other CPU architectures, <i>instruction-fetch-trace</i> is actually
<i>instruction-cache-trace-access</i> with a line size equal to the instruction
size (SPARC-V9).

Using this command without argument displays the current mode.
""")

def instruction_fetch_mode_global(mode):
    cpus = objects_implementing_iface(simics.INSTRUCTION_FETCH_INTERFACE)
    if not cpus:
        raise CliError('No objects supporting instruction fetch found.')
    for cpu in cpus:
        instruction_fetch_mode(cpu, mode)

new_command("instruction-fetch-mode", instruction_fetch_mode_global,
            args = [arg(str_t, "mode", "?", "", expander = ifm_expander)],
            alias = "ifm",
            type = ["Execution", "Profiling", "Tracing"],
            short="set or get current mode for instruction fetching",
            doc_with = "<instruction_fetch>.instruction-fetch-mode")

def istc_enable():
    try:
        if not conf.sim.instruction_stc_enabled:
            print("Turning I-STC on")
            conf.sim.instruction_stc_enabled = True
        else:
            print("I-STC was already turned on")
    except:
        print("Enable I-STC failed. Make sure a configuration is loaded.")

new_command("istc-enable", istc_enable,
            args = [],
            type = ["Execution", "Performance"],
            short="enable I-STC",
            group_short = "enable or disable internal caches",
            doc = """
These commands are for advanced usage only. They allow the user to control the
usage of Simics-internal caches.

The Simulator Translation Caches (STCs) are designed to increase execution
performance. The D-STC caches data translations (logical to physical to real
(host) address). The I-STC caches instruction translations of taken
jumps. Finally, the IO-STC caches logical to physical address translation for
device accesses.

By default the STCs are <b>on</b>.

When a memory hierarchy is connected (such as a cache module) it must have been
designed to work along with the STCs, or it may not be called for all the
memory transactions it is interested in. These commands can be used to detect
if too many translations are kept in the STCs, causing the simulation to be
incorrect.

Turning the STCs off means that current contents will be flushed and no more
entries will be inserted into the STCs.
""")

def istc_disable():
    try:
        if conf.sim.instruction_stc_enabled:
            print("Turning I-STC off and flushing old data")
            conf.sim.instruction_stc_enabled = False
        else:
            print("I-STC was already turned off")
    except:
        print("Disable istc failed. Make sure a configuration is loaded.")

new_command("istc-disable", istc_disable,
            args = [],
            type = ["Execution", "Performance"],
            short = "disable I-STC",
            doc_with = "istc-enable")

def dstc_enable():
    try:
        if not conf.sim.data_stc_enabled:
            print("Turning D-STC on")
            conf.sim.data_stc_enabled = True
        else:
            print("D-STC was already turned on")
    except:
        print("Enable D-STC failed. Make sure a configuration is loaded.")

new_command("dstc-enable", dstc_enable,
            args = [],
            type = ["Execution", "Performance"],
            short = "enable D-STC",
            doc_with = "istc-enable")

def dstc_disable():
    try:
        if conf.sim.data_stc_enabled:
            print("Turning D-STC off and flushing old data")
            conf.sim.data_stc_enabled = False
        else:
            print("D-STC was already turned off")
    except:
        print("Disable D-STC failed. Make sure a configuration is loaded.")

new_command("dstc-disable", dstc_disable,
            args = [],
            type = ["Execution", "Performance"],
            short = "disable D-STC",
            doc_with = "istc-enable")

def iostc_enable():
    print("The IO-STC has been removed.")

new_command("iostc-enable", iostc_enable,
            args = [],
            type = ["Execution", "Performance"],
            short = "enable IO-STC",
            doc_with = "istc-enable")

def iostc_disable():
    print("The IO-STC has been removed.")

new_command("iostc-disable", iostc_disable,
            args = [],
            type = ["Execution", "Performance"],
            short = "disable IO-STC",
            doc_with = "istc-enable")


def stc_status():
    try:
        if conf.sim.data_stc_enabled:
            print("D-STC is currently  *ON*")
        else:
            print("D-STC is currently  *OFF*")
        if conf.sim.instruction_stc_enabled:
            print("I-STC is currently  *ON*")
        else:
            print("I-STC is currently  *OFF*")
    except:
        print("Failed getting stc status. Make sure a configuration is loaded.")

new_command("stc-status", stc_status,
            args = [],
            type = ["Performance"],
            short = "show I- and D-STC status",
            doc_with = "istc-enable")

#
# ----------------- current-processor ----------------
#

def cur_proc_cmd():
    pr_warn("The 'current-processor' command will be removed in Simics 7."
            " Please use the built-in 'cpu' object alias or 'pselect' instead.")
    return current_cpu_obj().name

new_command("current-processor", cur_proc_cmd,
            short = "return current processor",
            deprecated = ["pselect", "cpu"],
            deprecated_version = SIM_VERSION_5,
            doc = """
Returns the name of the currently selected processor,
similar to <cmd>pselect</cmd>.
""")

def gcd(a, b):
    if a < b:
        return gcd(b, a)
    elif b == 0:
        return a
    else:
        return gcd(b, a % b)

def simplify_rational(q, p):
    g = gcd(p, q)
    (q, p) = (q // g, p // g)
    return q, p

def rational_to_float(r):
    (q, p) = r
    return float(q)/p

def float_to_rational_step_rate(ipc):
    '''Convert a floating point ipc to a rational number q/p where
    p is a power of 2. The value of ipc must be in the range [1/128, 128].'''
    assert ipc >= 1./128
    assert ipc <= 128

    if ipc <= 1: # Use highest resolution q/128
        p = 128
        q = min(128, int(round(ipc * 128)))
        assert q >= 1 # Post cond. check
    else: # Find closest matching q/p from all possible q/p
        all_denoms = tuple(2**x for x in range(8))   # [1, 128] powers of 2
        candidates = tuple((min(128, int(round(ipc * p))), p)
                           for p in all_denoms)
        (q, p) = min(candidates, key = lambda r: abs(rational_to_float(r) - ipc))

    return simplify_rational(q, p)

class _test_float_to_rational_step_rate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        all_denoms = tuple(2**x for x in range(8))
        cls.all_quotients = set(simplify_rational(q, p)
                                for q in range(1,129)
                                for p in all_denoms)

    def test_integers(self):
        '''All integers in the range [1..128] should return themselves
        as q and one as p.'''
        for ipc in range(1,129):
            (q, p) = float_to_rational_step_rate(ipc)

            self.assertEqual((q, p), (ipc, 1),
                             'IPC %d yielded %d/%d = %f'
                             % (ipc, q, p, rational_to_float((q,p))))

    def test_exact(self):
        '''Values that can be represented "exactly" should have 1:1 mapping.'''
        for r in self.all_quotients:
            ipc = rational_to_float(r)
            (q, p) = float_to_rational_step_rate(ipc)

            self.assertEqual(ipc, rational_to_float((q,p)),
                             '%d/%d did not yield the expected ipc %f'
                             % (q, p, ipc))

    def assert_rounding(self, exp, actual, test):
        self.assertEqual(exp, actual,
                         'value = %f but selected %d/%d = %f, not %d/%d = %f'
                         % (test,
                            actual[0], actual[1], rational_to_float(actual),
                            exp[0], exp[1], rational_to_float(exp)))

    def test_rounding(self):
        all_quotients = list(self.all_quotients)
        all_quotients.sort(key = rational_to_float)

        # Pair of adjacent values to check
        test_values = zip(all_quotients, all_quotients[1:])
        # Small value to offset from mean
        eps = 0.000001

        # Any value should be rounded towards its closest value in
        # all_quotients. That is, for any two adjacent quotients q/p,
        # q'/p' where q/p < q'/p' and their mean is m the following
        # will hold for any small e:
        #
        # m + e -> q'/p'
        # m - e -> q/p
        for lo, hi in test_values:
            lof = rational_to_float(lo)
            hif = rational_to_float(hi)
            mid = (hif + lof) / 2

            # Round up
            r = float_to_rational_step_rate(mid + eps)
            self.assert_rounding(hi, r, mid + eps)

            # Round down
            r = float_to_rational_step_rate(mid - eps)
            self.assert_rounding(lo, r, mid - eps)

    def test_bug18078(self):
        rational = float_to_rational_step_rate(0.07)
        self.assertEqual((9, 128), rational)
        rational = float_to_rational_step_rate(1.7)
        self.assertEqual((109, 64), rational)


def set_step_rate_cmd(cpu, rate):

    def set_step_rate(cpu, ipc):
        if ipc < 1./128:
            raise CliError("Error: Step rate %.6g smaller than 1/128" % float(ipc))
        if ipc > 128:
            raise CliError("Error: Step rate %.6g greater than 128" % float(ipc))

        (q, p) = float_to_rational_step_rate(ipc) # ipc in [1,128]
        cpu.iface.step_cycle_ratio.set_ratio(q, p)
        return f"Setting step rate to {q}/{p} steps/cycle"

    def step_rate_from_str(ipc):
        m = re.match(r'^(\d+)/(\d+)$', ipc)
        if not m:
            raise CliError('Quotient must be on the form "integer/integer"')

        # OK, either round as for float_t or be exact (when p is a power of 2).
        (q, p) = list(map(float, m.groups()))
        return q / p


    if rate == None:
        r = cpu.iface.step_cycle_ratio.get_ratio()
        ipc = r.steps / r.cycles  # NB: "/" operator always returns a float
        return cli.command_verbose_return(
            message=("Current step rate - i.e. instructions per cycle (IPC) -"
                     f" is {r.steps}/{r.cycles} (={ipc:.2f}). The inverse"
                     f" value - i.e. cycles per instruction (CPI) -"
                     f" is {r.cycles}/{r.steps} (={1 / ipc:.2f})."),
            value=[r.steps, r.cycles])

    (type, ipc, _) = rate
    if type not in (float_t, str_t):
        raise simics.SimExc_General('Unexpected type in set_step_rate_cmd')
    msg = set_step_rate(
        cpu, ipc if type == float_t else step_rate_from_str(ipc))
    return cli.command_return(message=msg)

new_command("set-step-rate", set_step_rate_cmd,
            [arg((float_t, str_t), ("ipc", "quotient"),
                 "?", None)],
            type = ["Performance", "Execution"],
            iface = "step_cycle_ratio",
            short = "set steps per cycle rate",
            doc = """
Sets the in-order step rate - also known as instructions per cycle (IPC) -
to the floating-point number
<arg>ipc</arg> or the string <arg>quotient</arg>. The quotient is a
string on the form "<i>q</i>/<i>p</i>". The given step rate must be in
the range [1/128,128] and it will be rounded to the closest rational
number q/p in the range [1/128,128], where p is a power of 2.

The argument specifies how many steps should be issued per cycle in the
absence of stalling. The inverse of this value is
cycles per instruction (CPI).
Without an argument, the current rate is displayed.""")

#
# -------------------- print-turbo-allocation --------------------
#

def print_turbo_allocation():
    print("global pool:")
    for pool in conf.sim.turbo_allocation:
        print()
        print("  %s" % pool[0])
        for (addr, used, left) in pool[1]:
            tot = used + left
            print("    address 0x%x, size 0x%x" % (addr, tot))
    print()
    print("cell pools:")
    machine_list = list(simics.SIM_object_iterator_for_class("cell"))
    for m in machine_list:
        print()
        print("  %s" % m.name)
        for pool in m.turbo_allocation:
            print("    %s" % pool[0])
            for (addr, used, left) in pool[1]:
                tot = used + left
                proc_used = (100.0 * used) / tot
                print("      address 0x%x, total 0x%x, used 0x%x (%.1f%%)" % (addr, tot, used, proc_used))

new_unsupported_command("print-turbo-allocation", "internals",
                        print_turbo_allocation, [],
                        short = "print timer allocation",
                        doc = """Print information about turbo allocation.""")

#
# -------------------- cell partitioning --------------------
#

check_cell_partitioning_global = None

def cell_partitioning():
    global check_cell_partitioning_global

    def list_iter(val):
        if isinstance(val, list):
            for v in val:
                for v2 in list_iter(v):
                    yield v2
        elif isinstance(val, dict):
            for k in val:
                yield k    # dict keys are always atomic
                for v2 in list_iter(val[k]):
                    yield v2
        else:
            yield val

    def preconf_iter(conf):
        for obj in conf.values():
            for attr in dir(obj):
                if attr.startswith('_'):
                    continue
                for val in list_iter(getattr(obj, attr)):
                    if isinstance(val, simics.pre_conf_object):
                        yield (obj, attr, val)
            # Create edges from objects to their port objects
            try:
                # Need to go through the classname as this isn't a conf-object
                cls = simics.SIM_get_class(obj.classname)
            except simics.SimExc_General:
                # The conversion from classname to class can fail.
                # In these cases we just assume there are no
                # ports as there is nothing else we can do.
                continue
            ports = simics.VT_get_port_classes(cls)
            for child_name in ports:
                child = conf.get(obj.name + '.' + child_name, None)
                if child:
                    yield (obj, f'port:{child_name}', child)

    def realconf_iter():
        for obj in simics.SIM_object_iterator(None):
            for attr in simics.VT_get_attributes(obj.classname):
                aa = (simics.SIM_get_attribute_attributes(obj.classname, attr)
                      & simics.Sim_Attr_Flag_Mask)
                if (aa == simics.Sim_Attr_Pseudo
                    and attr not in ("same_cell_as",)):
                    continue
                if 'o' not in simics.VT_get_attribute_type(obj.classname, attr):
                    # Optimization: we never need to look inside attribute
                    # which has no object inside
                    continue
                try:
                    val = simics.SIM_get_attribute(obj, attr)
                except (simics.SimExc_Attribute, simics.SimExc_General):
                    # Some attributes can't be converted to Python.
                    # That's OK, we just ignore them.
                    continue
                for v in list_iter(val):
                    if isinstance(v, simics.conf_object_t):
                        yield (obj, attr, v)
            # Create edges from objects to their port objects
            for child_name in simics.VT_get_port_classes(obj.classname):
                child = simics.SIM_get_object(obj.name + '.' + child_name)
                if child:
                    yield (obj, f'port:{child_name}', child)

    def conf_iter(conf = None):
        if conf:
            return preconf_iter(conf)
        else:
            return realconf_iter()

    def class_name(obj):
        return getattr(obj, '__class_name__', getattr(obj, 'classname', None))

    def is_new_link(obj):
        return all(hasattr(obj, x)
                   for x in ['goal_latency', 'immediate_delivery', 'global_id'])

    def ignore_obj(obj):
        return (cli.is_component(obj) or is_new_link(obj)
                or class_name(obj) in ['sim', 'sync_domain', 'tcf-agent',
                                       'magic_pipe', 'transaction-ckpt']
                or getattr(obj, "outside_cell", False))

    def read_conf(filename):
        if not filename:
            return None
        conf = simics.VT_get_configuration(filename)
        update_checkpoint.update_configuration(conf, filename)
        return conf

    def is_cell(obj):
        return class_name(obj) == 'cell'

    def memoise(f):
        mem = {}
        def fmem(x):
            if x not in mem:
                mem[x] = f(x)
            return mem[x]
        return fmem

    # Return the set of interesting attribute edges (obj1, attr, obj2)
    # for the current configuration, meaning that obj1.attr contains obj2.
    def conf_edges(conf):
        ignore = memoise(ignore_obj)
        return frozenset((obj1, attr, obj2)
                         for (obj1, attr, obj2) in conf_iter(conf)
                         if not (ignore(obj1) or ignore(obj2)))

    # Convert a set of edges to an adjacency list:
    # obj1 -> set of (attr, dir, obj2)
    # where dir = +1 if obj1.attr contains obj2,
    #             -1 if obj2.attr contains obj1
    def adjlist_from_edges(edges):
        adj = {}
        for (obj1, attr, obj2) in edges:
            if obj1 not in adj:
                adj[obj1] = set()
            if obj2 not in adj:
                adj[obj2] = set()
            adj[obj1].add((attr, 1, obj2))
            adj[obj2].add((attr, -1, obj1))
        return adj

    # Return a list of (obj1, attr, obj2) where obj1.attr contains obj2,
    # forming a chain from obj_start to obj_end.
    def object_path(edges, obj_start, obj_end):
        adj = adjlist_from_edges(edges)
        path = {obj_start: None}   # obj -> (prev-obj, attr, dir) or None
        # Simple breadth-first search to get the shortest path.
        queue = [obj_start]
        while True:
            obj = queue.pop(0)     # O(n²), but the constant is small.
            if obj == obj_end:
                seq = []
                p = obj
                while path[p]:
                    (o, a, d) = path[p]
                    if d > 0:
                        (o1, o2) = (o, p)
                    else:
                        (o1, o2) = (p, o)
                    seq.append((o1.name, a, o2.name))
                    p = o
                return list(reversed(seq))
            for (attr, d, obj2) in adj[obj]:
                if obj2 not in path:
                    path[obj2] = (obj, attr, d)
                    queue.append(obj2)

    def check_cell_partitioning(conf):
        edges = conf_edges(conf)

        # First partition the objects by (undirected) connectivity.
        # (Union-find would be asymptotically faster, but this ends up
        # being better in practice since the set primitives are so much
        # faster than explicit code in Python. It is also simpler.)

        # A map from each object to the partition it is in (a mutable set)
        part = {}
        for (obj1, attr, obj2) in edges:
            if obj1 not in part:
                part[obj1] = set([obj1])
            if obj2 not in part:
                part[obj2] = set([obj2])
            p1 = part[obj1]
            p2 = part[obj2]
            if p1 is not p2:
                for obj in p2:
                    part[obj] = p1
                p1 |= p2

        # Collect all partitions, eliminating duplicates (by set object
        # identity). We can't just do set(part.values()) because a set
        # cannot contain mutable sets.
        partitions = list(dict((id(p), p) for p in list(part.values())).values())

        # Now verify that each partition contains at most one cell.
        errors = 0
        for p in partitions:
            cells = list(filter(is_cell, p))
            if len(cells) > 1:
                # At least two cells in a partition - use the first two
                # as an example.
                print(("The cells %s\n      and %s\n"
                       "are connected in the following way:"
                       % (cells[0].name, cells[1].name)))
                for (obj1, attr, obj2) in object_path(edges,
                                                      cells[0], cells[1]):
                    print("  %s->%s contains %s" % (obj1, attr, obj2))
                errors += 1

        return errors

    def check_all(conf):
        errors = check_cell_partitioning(conf)
        if errors != 0:
            print('%d error%s found' % (errors, ['s', ''][errors == 1]))
        return errors == 0

    global check_part_of_conf
    check_part_of_conf = check_all

    def check_cell_partitioning_fun(checkpoint):
        if check_all(read_conf(checkpoint)):
            print('Cell partitioning OK.')
            return command_quiet_return(True)
        return command_quiet_return(False)

    def check_cell_partitioning_export():
        return check_all(read_conf(None))
    check_cell_partitioning_global = check_cell_partitioning_export

    new_command('check-cell-partitioning', check_cell_partitioning_fun,
                [arg(filename_t(simpath = True, checkpoint=True),
                     'checkpoint', '?', None)],
                type = ['Configuration'],
                short = 'verify that cell partitioning is OK',
                doc = """
Verify that the cell partitioning into cells of the given
<arg>checkpoint</arg> is correct; that is, that no objects in one cell have
references to objects in another cell.

If no checkpoint is given, check the currently loaded configuration.

Objects having a boolean attribute <b>outside_cell</b> that is set to True are
not considered part of any cell and are thus exempted from the check.

When used in an expression, command returns True if no errors were found.
 False is returned if any errors were found.""")

cell_partitioning()

#
# -------------------- page-sharing-info --------------------
#
def page_sharing_info_cmd(all_pages):
    if not all_pages:
        # No options, print summary information
        stat = list(conf.sim.page_sharing_statistics)
        for i in stat:
            print("%40s : %d" % (i[0],i[1]))

    if all_pages:
        # sort function
        pages = [(r, csum) for (r, csum) in conf.sim.page_sharing_pages
                 if r > 1]
        pages = sorted(pages, reverse = True)
        print("  #refs   Checksum        ")
        print("------- ----------------")
        for (refs, csum) in pages:
            print("%7d %016x" % (refs, csum))

new_unsupported_command("page-sharing-info", "internals", page_sharing_info_cmd,
                        args = [arg(flag_t, "-all-pages")],
                        short = "details on page-sharing",
                        see_also = [],
                        doc = """
Print details on page-sharing. Without any arguments, an overview
of the page-sharing statistics is shown.

With the <tt>-all-pages</tt> flag all shared pages is printed. It includes and
how many that shares it, sorted in least users order (the interesting ones are
at the bottom, since this list could be very long).""")

def gt_to_int(attr):
    return (attr[0] << 64) + attr[1] - ((attr[0] >> 63) << 128)

def get_current_global_time(cell):
    g = cell.ps.global_time
    return float(gt_to_int(g)) / 1e12

def print_sync_domain_info(dom, indent):
    if hasattr(dom, "server"):
        print(indent + "Server     :", dom.server)
    print(indent + "Min-latency:", cli.format_seconds(dom.min_latency))
    print(indent + f"Report time: {dom.report_time:.5f} s")
    print(indent + f"Stop time  : {dom.stop_time:.5f} s")
    for n in dom.nodes:
        if n.classname == "sync_domain":
            print(indent + "Subdomain:", n.name)
            print_sync_domain_info(n, indent+"  ")
        elif n.classname == "remote_sync_node":
            print(indent + "Remote subdomain:", n.name)
        else:
            info = ""
            if n.classname == "cell":
                if not n.clocks:
                    info += "(inactive)"
                else:
                    t = get_current_global_time(n)
                    info = f"{t:.5f} s"
                    evs = n.ps.iface.cycle_event.events()
                    (evobj, evtype, delta, _) = evs[0]
                    if delta == 0 and evobj == n and evtype == "sync: report":
                        info += " BLOCKING"
            print(indent + f"Node {n.name}: {info}")

def sync_info_cmd():
    syncgroups = [o for o in simics.SIM_object_iterator(None)
                  if cli.matches_class_or_iface(o, "sync_domain_controller")]
    topgroups = set(syncgroups)
    for g in syncgroups:
        topgroups -= set(g.nodes)
    for g in topgroups:
        if g.classname == "remote_sync_domain":
            print("Remote top sync domain:", g.name)
        else:
            print("Top sync domain:", g.name)
        print_sync_domain_info(g, "  ")

new_command('print-sync-info', sync_info_cmd,
            [],
            type = ["Configuration"],
            short = "print synchronization configuration",
            see_also = ["set-min-latency"],
            alias="sync-info",
            doc = """
            Print the synchronization tree.""")

new_info_command(
    'sync_domain',
    lambda obj: [(None,
                  [("Min-latency", cli.format_seconds(obj.min_latency)),
                   ("Nodes", obj.nodes),
                   ("Parent", obj.sync_domain)])])

def sync_domain_status_cmd(obj):
    return [(None,
             [("Report time", obj.report_time),
              ("Block time", obj.stop_time)])]
new_status_command('sync_domain', sync_domain_status_cmd)

new_info_command(
    'remote_sync_domain',
    lambda obj: [(None,
                  [("Min-latency", cli.format_seconds(obj.min_latency)),
                   ("Nodes", obj.nodes),
                   ("Server", obj.server)])])
new_status_command('remote_sync_domain', sync_domain_status_cmd)

new_info_command('remote_sync_node',
                 lambda obj: [(None,
                               [("Parent", obj.domain),
                                ("Server", obj.server),
                                ("Peer", obj.peer)])])
new_status_command('remote_sync_node', lambda obj: None)

new_info_command('remote_sync_server',
                 lambda obj: [(None,
                               [("Port", obj.port), ("Domain", obj.domain)])])
new_status_command('remote_sync_server', lambda obj: None)

#
# -------------------- list-processors --------------------
#
class DefaultProperties:
    __slots__ = ("obj", "cls", "cls_desc", "cell", "arch", "pc",
                 "pc_pa", "cycles", "time", "pico", "hz", "steps", "da",
                 "scheduled")

    def __init__(self, cpu):
        self.obj = cpu
        self.cls = cpu.classname
        self.cls_desc = cpu.class_desc
        self.cell = simics.VT_object_cell(cpu)

        self.arch = "n/a"
        self.pc = "n/a"
        self.pc_pa = "n/a"
        self.cycles = "n/a"
        self.time = "n/a"
        self.pico = "n/a"
        self.hz = "n/a"
        self.steps = "n/a"
        self.da = "n/a"
        self.scheduled = "n/a"


class CpuProperties(DefaultProperties):
    __slots__ = ()
    def __init__(self, cpu):
        super().__init__(cpu)

        if hasattr(cpu.iface, "processor_info"):
            self.arch = cpu.iface.processor_info.architecture()
            self.pc = cpu.iface.processor_info.get_program_counter()
            pb = cpu.iface.processor_info.logical_to_physical(
                self.pc, Sim_Access_Execute)
            self.pc_pa = pb.address if pb.valid else "no-translation"

        if hasattr(cpu.iface, "cycle"):
            self.cycles = cpu.iface.cycle.get_cycle_count()
            self.time = cpu.iface.cycle.get_time()
            self.pico = cpu.iface.cycle.get_time_in_ps().t
            self.hz = cpu.iface.cycle.get_frequency()

        if hasattr(cpu.iface, "step"):
            self.steps = cpu.iface.step.get_step_count()

        if hasattr(cpu.iface, "processor_cli"):
            (len, disasm) = cpu.iface.processor_cli.get_disassembly(
                "v", self.pc, False, None)
            self.da = disasm

        if hasattr(cpu, "do_not_schedule"):
            self.scheduled = "no" if cpu.do_not_schedule else "yes"

    def get_freq_in_hertz(self):
        return self.hz

def list_processors_cmd(
        cell_obj, parent, class_name, substr,
        steps_flag, cycles_flag, time_flag, pico_flag,
        virt_pc_flag, phys_pc_flag,
        disass_flag, all_flag):
    cpus = set(objects_implementing_iface("processor_info"))
    if all_flag:
        cpus.update(objects_implementing_iface("execute"))
    cpus = natural_sort(list(cpus))
    cpu_props = [
        CpuProperties(x) for x in cpus if (
            (cell_obj == None or x.cell == cell_obj)
            and (parent == None or x.name.startswith(parent.name + "."))
            and (class_name == None or x.classname == class_name)
            and (substr == "" or substr in x.name)
        )
    ]

    rows = []
    a_cell = cpu_props[0].cell if cpu_props else None

    # Default columns
    cols =  [
        [(Column_Key_Name, "CPU Name")],
        [(Column_Key_Name, " ")],
        [(Column_Key_Name, "CPU Class")],
        [(Column_Key_Name, "Freq"),
         (Column_Key_Float_Decimals, 2), (Column_Key_Metric_Prefix, "Hz")],
        [(Column_Key_Name, "Cell"),
         (Column_Key_Hide_Homogeneous, a_cell)],
        [(Column_Key_Name, "Scheduled"),
         (Column_Key_Hide_Homogeneous, "yes")],

    ]

    # Add optional columns
    if steps_flag:
        cols += [[(Column_Key_Name, "Steps"), (Column_Key_Int_Radix, 10)]]

    if cycles_flag:
        cols += [[(Column_Key_Name, "Cycles"), (Column_Key_Int_Radix, 10)]]

    if time_flag:
        cols += [[(Column_Key_Name, "Time (s)"), (Column_Key_Float_Decimals, 3)]]

    if pico_flag:
        cols += [[(Column_Key_Name, "Time (ps)"), (Column_Key_Int_Radix, 10)]]

    if virt_pc_flag:
        cols += [[(Column_Key_Name, "PC (virt)"),
                 (Column_Key_Int_Radix, 16), (Column_Key_Int_Pad_Width, 16)]]

    if phys_pc_flag:
        cols += [[(Column_Key_Name, "PC (phys)"),
                 (Column_Key_Int_Radix, 16), (Column_Key_Int_Pad_Width, 16)]]

    if disass_flag:
        cols += [[(Column_Key_Name, "Disassembly")]]

    props = [
        (Table_Key_Default_Sort_Column, "CPU Name"),
        (Table_Key_Columns, cols)
    ]

    try:
        psel = current_frontend_object().name
    except CliError as exc:
        if exc.value() == "No frontend object selected":
            raise CliError("No processor found")
        else:
            raise exc

    psel_found = False
    for c in cpu_props:
        if c.obj.name == psel:
            cpu_sel = "*"
            psel_found = True
        else:
            cpu_sel = ""

        row = [
            c.obj,
            cpu_sel,
            c.cls,
            c.get_freq_in_hertz(),
            c.cell,
            c.scheduled,
        ]

        # Optional columns
        if steps_flag:
            row += [c.steps]

        if cycles_flag:
            row += [c.cycles]

        if time_flag:
            row += [c.time]

        if pico_flag:
            row += [c.pico]

        if virt_pc_flag:
            row += [c.pc]

        if phys_pc_flag:
            row += [c.pc_pa]

        if disass_flag:
            row += [c.da]

        rows.append(row)

    # Get hold of a formatted table
    tbl = table.Table(props, rows)
    msg = tbl.to_string(rows_printed=0, no_row_column=True) if rows else ""
    if psel_found:
        msg += "\n* = selected CPU\n"
    return command_verbose_return(msg, rows)

new_command(
    "list-processors", list_processors_cmd,
    args = [
        # Filters
        arg(cli.obj_t('cell object', 'cell'), "cell", "?"),
        arg(obj_t("parent"), "parent", "?"),
        arg(str_t, "class", "?", None, expander = conf_class_expander()),
        arg(str_t, "substr", "?", ""),

        # Optional columns printed
        arg(flag_t, "-steps"),
        arg(flag_t, "-cycles"),
        arg(flag_t, "-time"),
        arg(flag_t, "-pico-seconds"),
        arg(flag_t, "-pc-va"),
        arg(flag_t, "-pc-pa"),
        arg(flag_t, "-disassemble"),
        arg(flag_t, "-all")
    ],
    type = ["CLI", "Processors"],
    see_also = ["list-processors-summary"],
    short = "list processors",
    doc  = """
    Lists all processors in the system, and various associated properties.
    By default, all processors found in the system are listed, together
    with class-name, frequency, and cell (object the processor belongs to).

    With the <tt>-all</tt> flag "execute" objects will also be included
    in addition to processors, for example clocks. If any execute object
    is not scheduled by Simics itself (possibly scheduled indirectly
    by another object) an additional "Scheduled" column appears telling
    if the object is scheduled by Simics or not.

    To only see a reduced set of the processors, the <arg>cell</arg>,
    <arg>parent</arg>, <arg>class</arg> and <arg>substr</arg> arguments can be
    used.

    The <arg>cell</arg> only prints processors that belong to
    the specified cell. The <arg>parent</arg> only prints processors
    underneath a certain object in the hierarchy.
    The <arg>class</arg> only prints processor objects of a specific class.
    Finally, the <arg>substr</arg> argument only prints processors
    which have a certain string found somewhere in the object hierarchy name.

    A number of optional columns can be printed for each processor
    by using the following flags:

    <tt>-steps</tt> executed steps

    <tt>-cycles</tt> executed cycles

    <tt>-time</tt> executed time in seconds

    <tt>-pico-seconds</tt> executed time in pico-seconds

    <tt>-pc-va</tt> virtual address program counter

    <tt>-pc-pa</tt> physical address program counter

    <tt>-disassemble</tt> current disassembly.
    """,
)

def list_processors_summary_cmd(cell_obj, parent, class_name, substr,
                                all_flag):
    if all_flag:
        cpus = objects_implementing_iface("execute")
    else:
        cpus = objects_implementing_iface("processor_info")

    # Accumulate processors of the same class
    d = {}                      # {cls : [CpuProperties]]
    cpu_props = [
        CpuProperties(x) for x in cpus if (
            (cell_obj == None or x.cell == cell_obj)
            and (parent == None or x.name.startswith(parent.name + "."))
            and (class_name == None or x.classname == class_name)
            and (substr == "" or substr in x.name)
        )
    ]

    for c in cpu_props:
        if c.cls in d:
            d[c.cls].append(c)
        else:
            d[c.cls] = [c]

    a_cell = cpu_props[0].cell if cpu_props else None
    props = [
        (Table_Key_Default_Sort_Column, "CPU Class"),
        (Table_Key_Columns,
         [
             [(Column_Key_Name, "Num CPUs"),
              (Column_Key_Int_Radix, 10),
              (Column_Key_Footer_Sum, True)],
             [(Column_Key_Name, "CPU Class")],
             [(Column_Key_Name, "Description")],
             [(Column_Key_Name, "Freq")],
             [(Column_Key_Name, "Cells"),
              (Column_Key_Hide_Homogeneous, a_cell)]
         ]
        )]

    # Produce the rows with summary of processors
    rows = []
    for cls in d:
        cl = d[cls]              # list of cpus
        num = len(cl)
        freqs = set(x.hz if isinstance(x.hz, str) else abbrev_value(x.hz, "Hz") for x in cl)
        cells = set(x.cell.name for x in cl)
        rows.append(
            [num,
             cl[0].cls,
             cl[0].cls_desc,
             ", ".join(freqs),
             ", ".join(cells)
         ])

    # Get hold of a formatted table
    tbl = table.Table(props, rows)
    msg = tbl.to_string(rows_printed=0, no_row_column=True) if rows else ""
    return command_verbose_return(msg, rows)

new_command(
    "list-processors-summary", list_processors_summary_cmd,
    args = [
        arg(cli.obj_t('cell object', 'cell'), "cell", "?"),
        arg(obj_t("parent"), "parent", "?"),
        arg(str_t, "class", "?", None, expander = conf_class_expander()),
        arg(str_t, "substr", "?", ""),
        arg(flag_t, "-all")
    ],
    type = ["CLI", "Processors"],
    see_also = ["list-processors"],
    short = "prints a summary for processors",
    doc  = """
    Produces a short summary list of all processors being
    simulated in the system. Each row lists:
    the processor class with description, how many processor found of
    this class, the frequencies used, and the cells the processors are
    found in.

    The <tt>-all</tt> flag includes all "execute" objects, even those
    objects which do not execute instructions (processors).

    Without any argument, all processors in the system are
    considered, giving an overview of what is currently being simulated.

    Similarly to the <cmd>list-processors</cmd> command, you can
    examine fewer processors using the <arg>cell</arg>,
    <arg>parent</arg>, <arg>class</arg> and <arg>substr</arg> filter
    arguments.""",
)


#
# -------------------- enable-jit / disable-jit -------------
#

def all_processor_classes_supporting_jit():
    cpus = [x for x in simics.SIM_object_iterator_for_interface(
        ['processor_info']) if hasattr(x, "turbo_execution_mode")]
    cpu_classes = set()
    for cpu in cpus:
        cpu_classes.add(simics.SIM_object_class(cpu))
    return cpu_classes

def toggle_jit(enable):
    status = 'enabled' if enable else 'disabled'
    if conf.sim.enable_jit == enable:
        print(f"JIT compilation for new CPUs is already {status}")
    else:
        conf.sim.enable_jit = enable

    for cpu_class in all_processor_classes_supporting_jit():
        if cpu_class.turbo_execution_mode == enable:
            print(f"JIT compilation is already {status} on {cpu_class.name}")
        else:
            cpu_class.turbo_execution_mode = enable

def enable_jit():
    toggle_jit(True)

def disable_jit():
    toggle_jit(False)

new_command("enable-jit",
            enable_jit,
            args=[],
            type = ["CLI"],
            see_also = ["disable-jit"],
            short="enable JIT compilation for all JIT-capable processors",
            doc="Enable JIT compilation for all JIT-capable processors")
new_command("disable-jit",
            disable_jit,
            args=[],
            type = ["CLI"],
            see_also = ["enable-jit"],
            short="disable JIT compilation for all JIT-capable processors",
            doc="Disable JIT compilation for all JIT-capable processors")

#
# -------------------- list-exceptions -------------
#

def list_exceptions_command(obj, substr, sort_on_names):
    data = []
    for exc_num in obj.iface.exception.all_exceptions():
        exc_name = obj.iface.exception.get_name(exc_num)
        if not substr or substr in exc_name:
            data.append([exc_num, exc_name])

    if sort_on_names:
        data.sort(key=lambda x: x[1])

    props = [(Table_Key_Columns,
              [[(Column_Key_Name, h)] for h in ["Number", "Exception Name"]])]

    tbl = table.Table(props, data)
    msg = tbl.to_string(rows_printed=0, no_row_column=True) if data else ""
    return command_verbose_return(msg, data)

new_command("list-exceptions", list_exceptions_command,
            args = [arg(str_t, "substr", "?", ""),
                    arg(flag_t, "-sort-on-names")],
            iface = "exception",
            type  = ["Processors"],
            short = "list exceptions on a processor",
            see_also = ["bp.exception.break", "bp.exception.trace"],
            doc = """
            List the exceptions (and interrupts) available on a processor.

            By default the list is sorted in exception number order,
            the <tt>-sort-on-names</tt> flag can instead sort
            on the exception names.

            The <arg>substr</arg> argument can be used to filter
            for certain exception names (case sensitive)."""
)

def key_count_cmp(a, b):
    return py3_cmp(b[1], a[1])

def page_stat_cmp(a, b):
    return py3_cmp(b[6], a[6])

permission_states = ["Invalid", "Read", "ReadWriteOne",
                     "ReadWriteMany", "ReadExecute"]

def a2s(a):
    str = ""
    if a & 1: # Sim_Access_Read
        str += "R"
    else:
        str += "-"

    if a & 2: # Sim_Access_Write
        str += "W"
    else:
        str += "-"

    if a & 4: # Sim_Access_Execute
        str += "X"
    else:
        str += "-"

    return str

def multicore_accelerator_stats_cmd(clear, num):
    # process page protocol transitions
    if clear:
        conf.sim.page_stats = []
    else:
        i = 0
        for (obj, addr, a_fr, a_to, i_fr, i_to, count) in sorted(
            conf.sim.page_stats, key = cmp_to_key(page_stat_cmp)):
            if i == num:
                break
            print(("[%40s] paddr: %16x count: %8d [%s,%s]->[%s,%s]"
                   % (obj.name, addr, count, a2s(a_fr), a2s(i_fr),
                      a2s(a_to), a2s(i_to))))
            i = i + 1

    # process processor events
    dict = {}
    for cpu in simics.SIM_get_all_processors():
        if clear:
            cpu.event_stat = []
        else:
            print("- events %s -" % cpu.name)
            event_stats = cpu.event_stat
            for (key, count) in sorted(event_stats,
                                       key = cmp_to_key(key_count_cmp)):
                val = dict.get(key, 0)
                dict[key] = val + count
                print("%8d %s" % (count, key))

    if not clear:
        print("- events summary -")
        for (key, count) in sorted(list(dict.items()),
                                   key = cmp_to_key(key_count_cmp)):
            print("%8d %s" % (count, key))

    # process translator stats
    dict = {}
    for cpu in simics.SIM_get_all_processors():
        if clear:
            cpu.translator_stat = []
        else:
            print("- translator %s -" % cpu.name)
            translator_stats = cpu.translator_stat
            for (key, count) in sorted(translator_stats,
                                       key = cmp_to_key(key_count_cmp)):
                val = dict.get(key, 0)
                dict[key] = val + count
                print("%8d %s" % (count, key))

    if not clear:
        print("- translator summary -")
        for (key, count) in sorted(list(dict.items()),
                                   key = cmp_to_key(key_count_cmp)):
            print("%8d %s" % (count, key))

new_unsupported_command("multicore-accelerator-stats", "internals",
                        multicore_accelerator_stats_cmd,
                        [arg(flag_t, "-clear"), arg(int_t, "num", "?", None)],
                        short = "print MCA statistics",
                        doc = """
Print statistics of serial-domain statistics, IO-obj statistics, and page
permission transitions.

The <tt>-clear</tt> will drop all gathered data. Limit number of printed page
permission transitions with the <arg>num</arg> argument.
""")

class PageSharing:
    def __init__(self, now=False):
        self.now = now
    def what(self):
        return "Page sharing"
    def is_enabled(self):
        return conf.sim.page_sharing
    def set_enabled(self, enabled):
        conf.sim.page_sharing = enabled
    def done(self):
        if self.now and conf.sim.page_sharing:
            print("Detecting identical pages (could take a while)...")
            mem = conf.sim.do_global_page_sharing
            print("Done, saved %s" % (abbrev_size(mem)))

new_command('enable-page-sharing', cli.enable_cmd(PageSharing),
            args = [arg(flag_t, "-now")],
            type = ["Execution", "Performance"],
            short = "enable page-sharing",
            doc = """
Enable the page-sharing feature, which detects identical pages in
the systems being simulated. Pages can be RAM, ROM, flash, disk, or any page
represented by <class>image</class> objects.

Pages detected to have identical contents are replaced with a single read-only
copy, consequently reducing the amount of host memory used. If an identical
page is written to, it will again get a private writable instance of the
page.

Identical pages are detected during run-time by certain triggers. If the
<tt>-now</tt> switch is used, all currently active pages will be examined for
sharing directly. Disabling page-sharing only means that no more pages will be
shared, pages which have already been shared will not be un-shared.
""")

new_command('disable-page-sharing', cli.disable_cmd(PageSharing),
            args = [], short = "disable page-sharing",
            type = ["Execution", "Performance"],
            doc = "Disable page sharing.")

def set_min_latency_cmd(count, unit):
    min_latency = 0.0
    if count:
        if count[2] == 'min-latency':
            assert count[0] == float_t and isinstance(count[1], float)
            min_latency = count[1]
            if unit is not None:
                raise CliError("The min-latency and unit arguments"
                               " cannot be used together.")
            DEPRECATED(SIM_VERSION_8,
                       'The "min-latency" argument to the "set-min-latency"'
                       ' command is deprecated.', 'Use the "count" and "unit"'
                       ' arguments instead.')
        else:
            assert count[2] == "count" and isinstance(count[1], int)
            check_count_unit(count[1], unit, set(time_units))
            if count[1] is not None:
                min_latency = count[1] * time_units[unit] / 10**12
    try:
        dom = conf.default_sync_domain
    except AttributeError:
        dom = simics.CORE_process_top_domain()
    if not min_latency:
        print("Min-latency:", cli.format_seconds(dom.min_latency))
        return
    try:
        dom.min_latency = min_latency
    except simics.SimExc_AttrNotWritable:
        print("The min-latency in", dom.name, "cannot be changed")
    except simics.SimExc_IllegalValue as ex:
        msg = str(ex).split(':', 1)[-1]
        print("The min-latency in", dom.name, "cannot be changed: %s" % msg)

new_command('set-min-latency', set_min_latency_cmd,
            args=[arg((float_t, uint64_t), ("min-latency", "count"), "?"),
                  arg(str_t, "unit", "?", None, expander=time_unit_expander)],
            type=["Configuration", "Performance"],
            short="set the min latency of the sync domain",
            see_also=["print-sync-info"],
            doc="""
Set the minimum synchronization latency between cells in the
<obj>default_sync_domain</obj> object (creating it if it does not
exist). The latency value can be specified using the <arg>count</arg>
and <arg>unit</arg> arguments or, for legacy usage, using the
<arg>min-latency</arg> argument (in seconds).

The time unit, specified by the <arg>unit</arg> argument, can be one
of <tt>s, ms, us, ns, ps</tt>, <tt>m</tt> or <tt>h</tt>.

Without argument the minimum latency is printed.""")

#
# -------------------- context --------------------
#

def context_on_cmd(obj):
    simics.SIM_set_attribute(obj, "active", 1)

def context_off_cmd(obj):
    simics.SIM_set_attribute(obj, "active", 0)

new_command("on", context_on_cmd,
            [],
            cls = "context",
            type  = ["Debugging"],
            short = "switch on context object",
            doc = """
<cmd class="context">on</cmd> activates the effects of a context object,
i.e., breakpoints on virtual addresses. <cmd class="context">off</cmd>
deactivates a context object.""")

new_command("off", context_off_cmd,
            [],
            cls = "context",
            type  = ["Debugging"],
            short = "switch off context object",
            doc_with = "<context>.on")

def obj_set_context_cmd(cpu, ctx_name):
    try:
        ctx = SIM_get_object(ctx_name)
        msg = "Context '%s' was set." % ctx.name
    except simics.SimExc_General:
        if ctx_name and '-' in ctx_name:
            raise CliError("Name contains hyphen, use underscore instead:"
                           " '%s'" % ctx_name)
        ctx = simics.SIM_create_object("context", ctx_name)
        msg = "New context '%s' created." % ctx.name

    if ctx.classname != "context":
        raise CliError("'%s' is not a context object." % ctx_name)

    if not cpu.iface.context_handler.set_current_context(ctx):
        raise CliError("Setting context failed.")

    return command_return(msg, ctx)

def set_context_cmd(ctx_name):
    return obj_set_context_cmd(current_cpu_obj(), ctx_name)

new_command("set-context", set_context_cmd,
            [arg(str_t, "context",
                 expander = object_expander("context"))],
            type  = ["Debugging"],
            see_also = ['new-context'],
            short = "set the current context of a CPU",
            doc = """
Sets the current context of a processor to <arg>context</arg>. If the context
does not exist, it is created.""")

new_command("set-context", obj_set_context_cmd,
            [arg(str_t, "context",
                 expander = object_expander("context"))],
            iface = "context_handler",
            short = "set the current context of a CPU",
            doc_with = "set-context")

def new_context_cmd(name):
    if not name:
        name = cli.get_available_object_name("ctx")
    try:
        SIM_get_object(name)
    except simics.SimExc_General:
        pass
    else:
        raise CliError("An object called '%s' already exists." % name)
    try:
        simics.SIM_create_object("context", name)
        return name
    except simics.SimExc_General as ex:
        raise CliError("Error creating context '%s': %s" % (name, ex))

new_command("new-context", new_context_cmd,
            [arg(str_t, "name", "?", "")],
            type  = ["Debugging"],
            see_also = ['set-context'],
            short = "create a new context",
            doc = """
Create a new context object called <arg>name</arg>. The context is initially
not bound to any processor.""")

def get_context_info(ctx):
    return [(None, [])]

new_info_command("context", get_context_info)

def get_context_status(ctx):
    return [(None,
             [("Active", "yes" if ctx.active else "no")])]

new_status_command("context", get_context_status)

def context_until_activated(ctx, activate):
    hap = 'Core_Context_%s' % ('Activate' if activate else 'Deactivate')
    def context_change(data, ctx, other_ctx, cpu):
        simics.VT_stop_finished(
            '%s is %s current context on %s'
            % (ctx.name, 'now' if activate else 'no longer', cpu.name))
    hap_handle = SIM_hap_add_callback_obj(hap, ctx, 0, context_change, None)
    run_simulation(True, lambda: SIM_hap_delete_callback_id(hap, hap_handle))

context_until_activated_cmds = [
    ('run-until-activated', True, 'run until context becomes active',
     """
Run until the context is activated on a processor."""),

    ('run-until-deactivated', False, 'run until context becomes inactive',
     """
Run until the context is deactivated on a processor."""),

    ]
for (cmd, activate, short, doc) in context_until_activated_cmds:
    def get_fun(activate):
        return lambda ctx: context_until_activated(ctx, activate)
    kw = dict(
        name = cmd, cls = 'context', short = short, doc = doc,
        fun = get_fun(activate),
        see_also = ['<context>.' + x[0] for x in
                    context_until_activated_cmds if x[0] != cmd])
    new_command(**kw)
