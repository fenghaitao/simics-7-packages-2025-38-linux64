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

from cli import (
    arg,
    filename_t,
    flag_t,
    integer_t,
    new_command,
    new_info_command,
    new_status_command,
    )
from simics import *
import sys, os.path

#
# -------------------- info, status --------------------
#

def get_info(obj):
    return [(None,
             [('Base latency period', "%d ms" % obj.interval),
              ('Maximal number of data points', obj.max_points)])]

new_info_command("mtprof", get_info)

def get_status(obj):
    active = ["no", "yes"][obj.active]
    return [(None,
             [("Active", active)])]

new_status_command("mtprof", get_status)


#
# -------------------- cellstat, modelstat --------------------
#

def cellstat_cmd(obj):
    if len(obj.cells) < 2:
        print("Too few cells, results won't be printed.")
        return

    print("=" * 60)
    header = "  cellname                    rt   %elapsed  %cputime"
    print(header)
    table = [(obj.cellrt[i], obj.cells[i].name)
                for i in range(len(obj.cells))]
    print("-" * 60)
    table.sort(reverse=True)
    for v, n in table:
        print("  %-22s %6.1fs     %4.1f%%    %4.1f%% " % (
            n, v / 1000000.0,
            v * 100.0 / (obj.realtime + 1),
            v * 100.0 / (obj.totalrt + 1)))
    print("-" * 60)
    print("  %-22s %6.1fs    100.0%%    %4.1f%%" % (
            "elapsed_realtime", obj.realtime/1000000.0,
            obj.realtime * 100.0 / (obj.totalrt + 1)))
    print("=" * 60)


def modelstat_cmd(obj):
    if len(obj.cells) < 2:
        print("Too few cells, results won't be printed.")
        return

    print("=" * 60)
    print("  latency      rt_model  realtime/rt_model")
    print("-" * 60)
    for i in range(len(obj.models)):
        print("  %4d ms       %5.1fs       %5.1f%%" % (
            obj.models[i], obj.modelrt[i]/1000000.0,
            obj.realtime * 100.0 / (obj.modelrt[i] + 1)))
    print("=" * 60)


new_command("cellstat", cellstat_cmd,
            [],
            type  = ["Profiling", "Performance"],
            short = "display cell profiling information",
            cls = "mtprof",
            doc = """
Presents a table with per-cell information about how much cpu-time has been
spent simulating processors and devices.

The <i>rt</i> column contains the accumulated time
measured in seconds. The <i>%elapsed</i> column contains
the same data expressed as a fraction of the time the
simulation has been running. The <i>%cputime</i> column,
presents the data as a fraction of the total cpu time used for the
simulation.<br/>
""")

new_command("modelstat", modelstat_cmd,
            [],
            type  = ["Performance"],
            short = "display ideal execution time on a sufficiently "
                    "parallel host",
            cls = "mtprof",
            doc = """
Helps estimating how fast the simulation would run on a host machine with
enough cores to allow each cell to run on a dedicated host thread.

The <i>latency</i> column roughly corresponds to different
min-latency settings (see <cmd>set-min-latency</cmd>).

The performance model which generates the estimate
essentially models the time synchronization mechanism which
keeps the virtual time in different cells in sync. It is
important to note that the model does not factor in target
behavior changes due to a differing latency setting, and
this is often a major factor.

The lowest latency to be modeled can be specified with the
<cmd>enable-mtprof</cmd>.<br/>
""")

#
# -------------------- mtprof.save-data --------------------
#

def do_save_data(obj, f, include_models,
                 include_cells, octave_output, plot_output,
                 filename):
    x = obj.data.copy()
    if plot_output:
        octave_output = True
    if len(x) == 0:
        print("no data collected")
        return
    print("# Columns:\n#", file=f)
    print("#   Virtual time (s)", file=f)
    print("#   Elapsed real-time (s)", file=f)
    if include_models:
        for m in obj.models:
            print(("#   Predicted real-time [%d ms model] (s)" % m), file=f)
    if include_cells:
        for cell_obj in obj.cells:
            print("#   Host CPU time %s (s)" % cell_obj.name, file=f)
    print("#", file=f)

    if octave_output:
        print("M = [", file=f)
    n_models = len(obj.models)
    n_cells = len(obj.cells)
    for row in x:
        vt, model, ct = row
        print("%f %f" % (vt[0], vt[1]), end=' ', file=f)
        if include_models:
            for m in model:
                print("%f" % m, end=' ', file=f)
        if include_cells:
            for q in ct:
                print("%f" % q, end=' ', file=f)
        print(";", file=f)
    if octave_output:
        print("];", file=f)
    if plot_output:
        print("vt = M(:,1);\nrt = M(:,2);", file=f)
        plot_str = "plot (vt, [rt, "
        next = 3
        legend = ["real time"]
        if include_models:
            print("models = M(:,%d:%d);" % (next, next + n_models - 1), file=f)
            next += n_models
            plot_str += "models, "
            for m in obj.models:
                legend += ["model-%s-ms" % m]
        if include_cells:
            print("cells = M(:,%d:%d);" % (next, next + n_cells - 1), file=f)
            plot_str += "cells, "
            for c in obj.cells:
                legend += ["%s" % c.name]
        plot_str += "]);"
        print(plot_str, file=f)
        print('xlabel("virtual time (s)");', file=f)
        print('ylabel("wall-clock time (s)");', file=f)
        print('legend("location", "southeastoutside")', file=f)
        print('legend("%s")' % '","'.join(legend).replace("_", "-"), file=f)
        plotname, _ = os.path.splitext(filename)
        print(('#print -color -landscape %s.svg "-S1980,1080"'
                     % plotname), file=f)

def save_data_cmd(obj, filename, model_flag, no_cell_data_flag,
                  octave_flag, plot_flag):
    if filename != "":
        f = open(filename, "w")
    else:
        f = sys.stdout
    try:
        do_save_data(obj, f, model_flag,
                     not no_cell_data_flag, octave_flag, plot_flag,
                     filename)
    finally:
        if filename != "":
            f.close()

new_command("save-data", save_data_cmd,
            [arg(filename_t(exist = 0), "file", "?", ""),
             arg(flag_t, "-model"),
             arg(flag_t, "-no-cell-data"),
             arg(flag_t, "-octave"),
             arg(flag_t, "-oplot"),
             ],
            type  = ["Profiling", "Performance"],
            short = "save profiling data to file",
            cls = "mtprof",
            doc = """
Save collected cell performance data to <arg>file</arg>
in the form of a table. The default columns are
virtual time, real time and per-cell cpu time.

Predicted execution time on a sufficiently parallel
host machine is included in the table if the command is
<tt>-model</tt> switch is used.

The <tt>-octave</tt> or <tt>-oplot</tt> switches can be
used to generate output data suitable for Octave. The
later of these two options causes explicit plot commands
to be included in the output.

The <tt>-no-cell-data</tt> switch causes per-cell data
to be omitted from the table.

The output data is either printed on stdout or saved the
<arg>file</arg>, if specified.
""")


#
# -------------------- mtprof.enable --------------------
#

def enable_cmd(obj, interval):
    obj.active = True
    try:
        if interval > 0:
            obj.interval = interval
        print("Multithreaded simulation profiling enabled.", end=' ')
        print("Interval: %d ms" % obj.interval)

    except Exception as msg:
        print("Error starting profiling: %s" % msg)

new_command("enable", enable_cmd,
            [arg(integer_t, "interval", "?", 0)],
            type  = ["Profiling", "Performance"],
            short = "enable multithreaded simulation profiling",
            cls = "mtprof",
            doc = """
Enable multithreaded simulation profiling. The amount of
host cpu time required to simulate each cell is measured
every <arg>interval</arg> virtual ms.

The collected data is fed into a performance model which
estimates how fast the simulation would run on a system
with enough host cores and Simics Accelerator licenses to
allow each cell to run on a dedicated core. The performance
model also gives some insights into the performance implications
of various min-latency settings (settable though the
<cmd>set-min-latency</cmd> commands).

The <arg>interval</arg> parameter should normally be set to a value
of the some order as the min-latency setting of interest.<br/>
""")

#
# -------------------- mtprof.disable --------------------
#

def disable_cmd(obj):
    obj.active = False

new_command("disable", disable_cmd,
            [],
            type  = ["Profiling", "Performance"],
            short = "disable multithreaded simulation profiling",
            cls = "mtprof",
            doc = """Disable multithreaded simulation profiling.""")
