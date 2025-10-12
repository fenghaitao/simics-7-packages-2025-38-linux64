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

from simics import *
from cli import (
    CliError,
    add_unsupported,
    arg,
    filename_t,
    flag_t,
    float_t,
    new_command,
    string_set_t,
    )
import os
import math
sys_obj = None

def system_perfmeter_cmd(sample_time, mode, file_name,
                         deactivate, real_time, cpu_idle,
                         print_execution_mode,
                         cpu_host_ticks, host_ticks_raw,
                         cell_host_ticks, cell_host_ticks_raw,
                         print_summary, print_summary_always,
                         print_module_profile,
                         window, top,
                         print_disabled, print_mips, print_emips,
                         print_ma,
                         print_imem, print_shared, print_io, mips_win, no_log,
                         only_current_cell, include_stop_time):
    if sample_time <= 0.0:
        raise CliError("The sample_time argument must be > 0")
    global sys_obj
    if not sys_obj:
        from . import system_perfmeter
        sys_obj = system_perfmeter.system_perfmeter()

    if deactivate:
        sys_obj.deactivate()
        sys_obj = None
        return

    if mode:  ## shared flags
        print_emips = True
        print_summary = True
        real_time = True

    if mode == "minimum":
        pass  ## shared flags only
    elif mode == "normal":
        cpu_idle = True
        print_execution_mode = True
    elif mode == "detailed":
        cpu_host_ticks = True
        cpu_idle = True
        print_execution_mode = True
        print_imem = True
        print_io = True
        print_module_profile = True

    sys_obj.activate(sample_time = sample_time,
                         real_time = real_time,
                         cpu_idle = cpu_idle,
                         cpu_host_ticks = cpu_host_ticks,
                         host_ticks_raw = host_ticks_raw,
                         cell_host_ticks = cell_host_ticks,
                         cell_host_ticks_raw = cell_host_ticks_raw,
                         print_summary = print_summary,
                         print_summary_always = print_summary_always,
                         window = window,
                         top = top,
                         print_disabled = print_disabled,
                         print_mips = print_mips,
                         print_emips = print_emips,
                         print_ma = print_ma,
                         print_imem = print_imem,
                         mips_window = mips_win,
                         no_logging = no_log,
                         print_execution_mode = print_execution_mode,
                         print_module_profile = print_module_profile,
                         file_name = file_name,
                         print_page_sharing = print_shared,
                         print_io = print_io,
                         only_current_cell = only_current_cell,
                         include_stop_time = include_stop_time)

new_command("system-perfmeter", system_perfmeter_cmd,
            args = [arg(float_t, "sample_time", "?", 1.0),
                    arg(string_set_t(
                        ["minimum", "normal", "detailed"]),
                        "mode", "?", None),
                    arg(filename_t(), "file", "?", None),
                    arg(flag_t, "-deactivate"),
                    arg(flag_t, "-realtime"),
                    arg(flag_t, "-cpu-idle"),
                    arg(flag_t, "-cpu-exec-mode"),
                    arg(flag_t, "-cpu-host-ticks"),
                    arg(flag_t, "-cpu-host-ticks-raw"),
                    arg(flag_t, "-cell-host-ticks"),
                    arg(flag_t, "-cell-host-ticks-raw"),
                    arg(flag_t, "-summary"),
                    arg(flag_t, "-summary-always"),
                    arg(flag_t, "-module-profile"),
                    arg(flag_t, "-window"),
                    arg(flag_t, "-top"),
                    arg(flag_t, "-disabled"),
                    arg(flag_t, "-mips"),
                    arg(flag_t, "-emips"),
                    arg(flag_t, "-multicore-accelerator"),
                    arg(flag_t, "-mem"),
                    arg(flag_t, "-shared"),
                    arg(flag_t, "-io"),
                    arg(flag_t, "-mips-win"),
                    arg(flag_t, "-no-log"),
                    arg(flag_t, "-only-current-cell"),
                    arg(flag_t, "-include-stop-time")],
            type = ["Performance"],
            see_also = ["pselect", "system-perfmeter-summary"],
            short = "activate Simics performance monitoring",
            doc = """
Activates performance measurement on one or more systems running
within Simics. The resulting printouts gives an idea on how fast
Simics executes and can be useful to identify opportunities for
optimization.

The command periodically outputs various performance related counters
for the period, called a sample. Counters measure activity during the
period, unless otherwise noted. The counters are also accumulated and
can be presented in a summary. Each time the command is given, all
accumulated counters are reset to zero.

The sample output contains a number of columns;
<i>Total-vt</i> (virtual time) and <i>Total-rt</i> (real time) is the
accumulated number of seconds that has been executed on the system
since the command was issued. Similarly, <i>Sample-vt</i> and
<i>Sample-rt</i> is the sample time in seconds. <i>Slowdown</i>
measures the ratio between the sample virtual time and real time.
<i>CPU</i> indicates how much host CPU that was used by Simics during
the sample, where 100% equals to one cpu running during the whole
sample (as Simics is multi-threaded, this number can be much larger
than 100).
<i>Idle</i> represent how much all CPUs in the system was in
idle during the sample. Instructions that do not compute anything, like
the x86 halt instruction, and non-computing loops detected by Simics
(see <cmd>hypersim-status</cmd>) are defined as idle instructions.
A large idle percentage means that Simics can
fast-forward time more, and hence gives better performance.

Virtual time is measured on the current cycle object (selectable with
<cmd>pselect</cmd>) when the command is given.

To disable the system perfmeter use <tt>-deactivate</tt>.

<b>Output Presentation</b>

How frequent the measurements should be presented is controlled with
the <arg>sample_time</arg> parameter which represent the time that
should elapse for each sample, default is one second. Default is to
sample based on virtual time, but using <tt>-realtime</tt>
switches the sampling to be based on real (host) time.

The system-perfmeter will subtract any time when the simulation
is not running from the measured wall-clock time. This allows
the simulation to be temporary stopped in the middle of the execution
without corrupting the measurement. The <tt>-include-stop-time</tt>
flag prevents this subtraction from happening, allowing
the actual real-time to be shown.

The <tt>-summary</tt> causes a summary report to be printed out each
time simulation is stopped. It includes the same counters that you get
for each sample, but the numbers are calculated based on the whole
run, not just a sample, since the command was issued. The summary also
includes performance hints as well as system info about target and
host. A summary is only printed if at least one sample has been
printed since the last time Simics stopped. The
<tt>-summary-always</tt> flag prints the summary information each time
Simics stops instead. The <cmd>system-perfmeter-summary</cmd> command
also prints the summary report.

With <tt>-only-current-cell</tt>, metrics are only collected
for the cell of the currently selected frontend object at the time
when the command is run (selected with <cmd>pselect</cmd>). Global
metrics such as <i>mem</i> will still include the entire
simulation. If <tt>-only-current-cell</tt> is not specified, then
metrics are based on all cells.

<b>Output Redirection</b>

Normally a text line with results is written as an output each
measured sample. The <tt>-window</tt> flag opens a separate text
window where the continued output is written instead of printing this
in the Simics console. If no output is wanted at all,
<tt>-no-log</tt> can be used (can be useful when running with
only <tt>-top</tt> or <tt>-mips-win</tt>).

The console printouts can be sent to a file specified by the
<arg>file</arg> argument. The default is to output the result to the
Simics console. If <tt>-window</tt> is used together with a
specified <arg>file</arg>, the output is written both to the file and
to the separate window.

The <tt>-top</tt> flag opens a separate text window displaying some
statistics on the execution, similar to the Linux top utility.

Similar, <tt>-mips-win</tt> opens a window displaying only the
current MIPS value which can be useful for demonstration.

<b>Convenience Argument</b>

The optional <arg>mode</arg> argument can take one of "minimum", "normal" and
"detailed" as its value. Each mode selects a number of the flags described
below. Using a mode, flags can also be specified separately.<br/>
- The "minimum" mode includes <tt>-emips</tt>, <tt>-realtime</tt> and
  <tt>-summary</tt>.<br/>
- The "normal" mode includes <tt>-cpu-exec-mode</tt>, <tt>-cpu-idle</tt>,
  <tt>-emips</tt>, <tt>-realtime</tt> and <tt>-summary</tt>.<br/>
- The "detailed" mode includes <tt>-cpu-exec-mode</tt>,
  <tt>-cpu-host-ticks</tt>, <tt>-cpu-idle</tt>, <tt>-emips</tt>, <tt>-io</tt>,
  <tt>-mem</tt>, <tt>-module-profile</tt>, <tt>-realtime</tt> and
  <tt>-summary</tt>.

<b>Counter Selection</b>

All of the below flags are used to add various counters to the sample.
Instruction mode per cpu and host tick counters are grouped using
brackets. An explanation of the label of each column in the brackets
is printed when turning on profiling and when the summary is printed.

Instructions can be simulated in four different simulator modes: idle,
interpreter, JIT, or VMP. For each processor, the percentage run in this
mode out of all instructions run on the processor during the sample
can be shown. <tt>-cpu-exec-mode</tt> will show numbers for
processor instructions in JIT and VMP mode. <tt>-cpu-idle</tt> will
show numbers for idle mode instructions. Interpreter mode is not
shown, except in the summary. Columns are grouped per mode, and modes
are sorted idle, JIT, VMP from left to right. If no instructions at all
were executed during the sample, the processor is considered disabled and
DIS is shown. Note that the absolute
number of instructions may vary per processor (due to CPI, frequency,
idle). Also, note that clocks have no instructions and are not shown,
but are included in the number of processors in the summary.

Another group of values (one value per processor/cell, group placed to
the far right) is added by <tt>-cpu-host-ticks</tt>. This shows how
much real time each processor/cell takes to simulate. This can either
be a percentage value of total host time when processors simulate, or
an absolute value, counted in ticks, if using
<tt>-cpu-host-ticks-raw</tt>. Execution outside a cell are excluded
and such ticks are ignored. Execution inside a cell, but not
executing a processor are reported in the "Outside Processors"
column.  A tick is a time unit defined by the host OS, on Linux
usually 10 ms.

When running with a multi-cell configuration with many processors,
<tt>-cell-host-ticks</tt> or <tt>-cell-host-ticks-raw</tt> can be
used similar to the <tt>-cpu-host-ticks</tt>* switches. This
provides a more narrow list of how much host processor that is needed
to simulate each cell. Execution that falls outside any cell is
placed in an "Outside cell" ("oc") column.

The <tt>-mips</tt> flag appends some MIPS values indicating how many million
instruction per real second Simics has executed. The MIPS number printed is
the number of instruction executed, including idle instructions.
To see the MIPS value without the idle instructions (where only the instructions
that are really executed in Simics are counted) you can use
<tt>-emips</tt>.

The <tt>-multicore-accelerator</tt> tracks and prints the percentage
of execution when Multicore Accelerator is both enabled and actually
used. Even when Multicore Accelerator is enabled, it may not actually
be used since there is a mechanism that monitors the simulation and
falls back to classic non-threaded execution within each cell if there
would not be a benefit from additional threading. See the Accelerator
User's Guide for more information on Multicore Accelerator.

With <tt>-io</tt>, the number of instructions per I/O operation is
calculated and presented in the output. An I/O operation is any
memory access that is not terminated in a Simics ram or rom object
and thus includes memory mapped I/O.

In some configurations, processors might be disabled at start and
started later by software. To see how many of the processors that are
disabled at the end of each sample use <tt>-disabled</tt>.
The <i>Disabled</i> column shows how many CPUs and the percent
of the total system which are not currently activated.

The <tt>-mem</tt> flag show the total amount of memory consumed by all
instances of the image class (RAM, disk etc.) at the end of the
sample. It is measured as the percentage of the memory-limit. If this
number goes down compared to the previous sample it means that
memory-limit has been reached and Simics has swapped out dirty pages
to disk.

Simics can share identical pages across multiple simulated targets, if
this feature is enabled. If the targets for instance run the same OS,
Simics can keep one copy of a page instead of multiple copies, which
consequently reduces host memory consumption. To see how much memory
is currently saved at the end of the sample, <tt>-shared</tt> can
be used. Notice that this figure only shows how much "image" memory
that is saved. The page sharing mechanism can also reduce internal
state, but this memory reduction is not accounted for.

Specifying <tt>-module-profile</tt> enables profiling of the simulator.
Prints the percentage of real time spent in each module. Only printed in summary.
""")

def system_perfmeter_summary_cmd():
    global sys_obj
    if not sys_obj:
        raise CliError("system-perfmeter not activated")
    sys_obj.async_print_summary()

new_command("system-perfmeter-summary",
            system_perfmeter_summary_cmd, args = [],
            type = ["Performance"],
            see_also = ["system-perfmeter"],
            short = "prints system-perfmeter summary",
            doc = """
Prints same summary report as the -summary option to the <cmd>system-perfmeter</cmd>
command. See that command for details.""")
