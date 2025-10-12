# © 2019 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Standard python libraries
import os
import tempfile
import csv
import re
import webbrowser
import json

# Simics stuff
import cli
import pyobj
import table
import simics
import conf
from . import vtune
from . import flamegraph
from simicsutils.host import is_windows

def log(obj, msg, level=1):
    simics.SIM_log_info(level, obj, 0, msg)


class ThreadProfile:
    def __init__(self, thread_name, tid, time):
        self.thread_name = thread_name
        self.tid = tid
        self.time = time

class vtune_measurement(pyobj.ConfObject):
    '''Extension which runs VTune&trade; from Simics which connects to the
    current Simics session.'''
    _class_desc = "runs and controls VTune&trade; from Simics"
    _class_kind = simics.Sim_Class_Kind_Pseudo

    def _initialize(self):
        super()._initialize()
        self.data_collected = False
        self.vtune_process = None
        self.vtune_collect = None
        self.result_dir = None
        self.thread_dict = {}
        self.thread_profile = []

    def _finalize(self):
        super()._finalize()
        vtune_path = self.vtune_path.getter()
        log(self.obj, "Running VTune from: %s" % (
            vtune_path if vtune_path else "PATH"))

    class vtune_path(pyobj.Attribute):
        "path to vtune binaries, saved in prefs"
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = "s|n"
        def getter(self):
            pref_iface = conf.prefs.iface.preference
            try:
                attr = pref_iface.get_preference_for_module_key(
                    "vtune-measurement", "vtune_path")
            except simics.SimExc_General:
                attr = None
            return attr

        def setter(self, val):
            if not os.path.isdir(val):
                return simics.Sim_Set_Illegal_Value

            conf.prefs.iface.preference.set_preference_for_module_key(
                val, "vtune-measurement", "vtune_path")

    # Command-functions are marked as staticmethods to be part of the
    # class, but to get the commands registered outside.

    # Tab-completion expander for threads
    @staticmethod
    def thread_group_expander(name, obj):
        pyobj = obj.object_data
        return cli.get_completions(name, pyobj.thread_dict.keys())

    # Command handlers
    @staticmethod
    def start_cmd(obj, collect):
        pyobj = obj.object_data
        pyobj.result_dir = tempfile.mkdtemp(
            prefix = "vtune_", dir = os.getcwd())
        log(obj, f"VTune data stored in {pyobj.result_dir}")
        log(obj, f"Starting VTune with '{collect}' analysis and connecting it to"
          " this Simics session...")
        (success, p) = vtune.start(obj, collect, pyobj.result_dir)
        if not success:
            if not p:
                log(obj,
                    "Failed to run 'vtune', VTune must be installed"
                    " on the machine and either be in the PATH or"
                    " pointed out with prefs->vtune_path")
            else:
                # Discovered some error output
                vtune.wait_for_exit(obj, p)
            pyobj.vtune_process = None
            raise cli.CliError("Failed to launch VTune")
        pyobj.vtune_process = p
        pyobj.vtune_collect = collect

    @staticmethod
    def stop_cmd(obj):
        pyobj = obj.object_data
        vtune_process = pyobj.vtune_process
        if not vtune_process:
            raise cli.CliError("VTune is not running")

        res_dir = pyobj.result_dir
        log(obj, "Stopping data collection...")
        _ = vtune.stop(obj, res_dir)

        # Wait for the main VTune process to exit, the database must be created
        # before we can request reports on it.
        log(obj, "Waiting for VTune to finish...")
        vtune.wait_for_exit(obj, vtune_process)
        pyobj.vtune_process = False
        pyobj.data_collected = True
        if is_windows():
            pyobj.thread_dict = {}
        else:
            log(obj, "Retrieving thread information...")
            threads = vtune.get_threads(obj, res_dir)
            pyobj.thread_dict = collect_threads(obj, threads)
            pyobj.thread_profile = collect_thread_profile(obj, threads)

    @staticmethod
    def summary_cmd(obj):
        pyobj = obj.object_data
        if not pyobj.data_collected:
            raise cli.CliError("You must run %s.stop first" % (obj.name,))

        res_dir = pyobj.result_dir
        r = vtune.summary(obj, res_dir)
        for l in r:
            print(l)

    @staticmethod
    def thread_group_cmd(obj):
        pyobj = obj.object_data
        if not pyobj.data_collected:
            raise cli.CliError("You must run %s.stop first" % (obj.name,))
        threads = list(pyobj.thread_dict.keys())
        threads_info = "\n".join(threads)
        return cli.command_return(
            value = threads,
            message = threads_info)

    @staticmethod
    def launch_gui_cmd(obj):
        pyobj = obj.object_data
        if not pyobj.data_collected:
            raise cli.CliError("You must run %s.stop first" % (obj.name,))
        vtune.launch_gui(obj, [pyobj.result_dir])

    @staticmethod
    def profile_cmd(obj, thread_group,
                    function_re, module_re, file_re, agg_filtered_out,
                    csv, csv_output_filename, no_inline, *table_args):
        pyobj = obj.object_data
        if not pyobj.data_collected:
            raise cli.CliError("You must run %s.stop first" % (obj.name,))

        if pyobj.vtune_collect != "hotspots":
            print(f"use {obj.name}.launch-gui to see the result of the"
                  f" {pyobj.vtune_collect} collection\n")

        td = pyobj.thread_dict
        if thread_group:
            if thread_group not in td:
                raise cli.CliError(
                    "Invalid thread-group '%s', available: %s" % (
                        thread_group, ", ".join(td)))
            tid_filter = td[thread_group]
        else:
            tid_filter = None

        re1 = reg_ex_arg(function_re)
        re2 = reg_ex_arg(module_re)
        re3 = reg_ex_arg(file_re)

        res_dir = pyobj.result_dir
        output = vtune.profile(obj, res_dir, tid_filter, no_inline)

        if csv:
            if csv_output_filename:
                with open(csv_output_filename, "w") as f:
                    for l in output:
                        f.write(l)
            else:
                for l in output:
                    print(l, end='')
            return

        (t_prop, t_data) = csv_to_table(output)

        if not any((re1, re2, re3)):
            table.show(t_prop, t_data, *table_args)
            return

        # Filtered output
        out_data = [r for r in t_data
                    if ((not re1 or re1.match(str(r[0])))
                        and (not re2 or re2.match(str(r[2])))
                        and (not re3 or re3.match(str(r[3]))))]
        if agg_filtered_out:
            filtered = [r for r in t_data
                        if not ((not re1 or re1.match(str(r[0])))
                                and (not re2 or re2.match(str(r[2])))
                                and (not re3 or re3.match(str(r[3]))))]
            total = sum([r[1] for r in filtered])
            out_data += [["*FILTERED OUT*", total, "", ""]]
        org_num_rows = len(t_data)
        new_num_rows = len(out_data)
        log(obj, f"Table reduced from {org_num_rows} to {new_num_rows} rows")
        table.show(t_prop, out_data, *table_args)

    @staticmethod
    def module_profile_cmd(obj, thread_group, csv,
                           csv_output_filename, *table_args):
        pyobj = obj.object_data
        if not pyobj.data_collected:
            raise cli.CliError("You must run %s.stop first" % (obj.name,))

        if pyobj.vtune_collect != "hotspots":
            print(f"use {obj.name}.launch-gui to see the result of the"
                  f" {pyobj.vtune_collect} collection\n")

        td = pyobj.thread_dict
        if thread_group:
            if thread_group not in td:
                raise cli.CliError(
                    "Invalid thread-group '%s', available: %s" % (
                        thread_group, ", ".join(td)))
            tid_filter = td[thread_group]
        else:
            tid_filter = None

        res_dir = pyobj.result_dir
        output = vtune.module_profile(obj, res_dir, tid_filter)

        if csv:
            if csv_output_filename:
                with open(csv_output_filename, "w") as f:
                    for l in output:
                        f.write(l)
            else:
                for l in output:
                    print(l, end='')
            return

        (t_prop, t_data) = csv_to_table(output)
        table.show(t_prop, t_data, *table_args)

    @staticmethod
    def flamegraph_cmd(obj, open_browser, discard_module, modules_only,
                       svg_file, thread_group):
        pyobj = obj.object_data
        if not pyobj.data_collected:
            raise cli.CliError("You must run %s.stop first" % (obj.name,))

        if not svg_file and not open_browser:
            raise cli.CliError(
            "Must either specify svg file to generate or use -open-browser")

        if svg_file:
            fd = open(svg_file, "w+b")
        else:
            fd = tempfile.NamedTemporaryFile(suffix=".svg", delete=False)
            svg_file = fd.name

        tid_filter = pyobj._tid_filter_for_thread_group(thread_group)
        res_dir = pyobj.result_dir
        log(obj, "Extracting call-stack")
        output = vtune.callstack(obj, res_dir, tid_filter)

        log(obj, "Flattening call-stack to flamegraph input")
        flatten = flamegraph.flatten_stack(output[1:], discard_module,
                                           modules_only)
        log(obj, f"Found {len(flatten)} stack-entries")
        blob = bytearray("\n".join(flatten), encoding="utf-8")

        log(obj, f"Creating {svg_file} by running flamegraph")
        svg = flamegraph.run(blob, thread_group if thread_group else "All")
        fd.write(svg)
        fd.close()

        if open_browser:
            log(obj, f"Starting webbrowser on {svg_file}")
            try:
                webbrowser.open(svg_file)
            except Exception as msg:
                raise cli.CliError(f"Failed starting browser: {msg}")


    @staticmethod
    def save_folded_stacks_cmd(obj, discard_module, modules_only, json_fmt,
                               thread_group, out_file):
        pyobj = obj.object_data
        if not pyobj.data_collected:
            raise cli.CliError("You must run %s.stop first" % (obj.name,))

        tid_filter = pyobj._tid_filter_for_thread_group(thread_group)
        res_dir = pyobj.result_dir
        log(obj, "Extracting call-stack")
        output = vtune.callstack(obj, res_dir, tid_filter)

        log(obj, "Flattening call-stack to flamegraph input")
        flatten = flamegraph.flatten_stack(output[1:], discard_module,
                                           modules_only)
        log(obj, f"Found {len(flatten)} stack-entries")

        if json_fmt:
            d = {
                "flamegraph": {
                    "contents": "Simics Flame Graph folded stacks",
                    f"thread-group-{thread_group}" : {
                        "discard_module": discard_module,
                        "modules_only": modules_only,
                        "folded_stacks" : flatten,
                    }
                }
            }
            contents = json.dumps(d, indent=4)
        else:
            contents = "\n".join(flatten)

        blob = bytearray(contents, encoding="utf-8")
        fd = open(out_file, "w+b")
        log(obj, f"Generating {out_file}")
        fd.write(blob)
        fd.close()

    def _thread_profile_full(self):
        prop = [
            (table.Table_Key_Default_Sort_Column, "CPU Time"),
            (table.Table_Key_Columns, [
                [(table.Column_Key_Name, "Thread name"),],
                [(table.Column_Key_Name, "TID"),
                 (table.Column_Key_Int_Radix, 10)],
                [(table.Column_Key_Name, "CPU Time"),
                 (table.Column_Key_Generate_Percent_Column, []),
                 (table.Column_Key_Generate_Acc_Percent_Column, []),
                 (table.Column_Key_Footer_Sum, True)]]
             )
        ]
        data = [
            (t.thread_name, t.tid, t.time) for t in self.thread_profile
        ]
        return (prop, data)

    def _thread_profile(self):
        prop = [
            (table.Table_Key_Default_Sort_Column, "CPU Time"),
            (table.Table_Key_Columns, [
                [(table.Column_Key_Name, "Thread name"),],
                [(table.Column_Key_Name, "Num threads"),
                 (table.Column_Key_Footer_Sum, True),
                 (table.Column_Key_Int_Radix, 10)],
                [(table.Column_Key_Name, "TIDs"),],
                [(table.Column_Key_Name, "CPU Time"),
                 (table.Column_Key_Generate_Percent_Column, []),
                 (table.Column_Key_Generate_Acc_Percent_Column, []),
                 (table.Column_Key_Footer_Sum, True)]]
             )
        ]
        # Iterate over our thread-profile and accumulate the data with
        # the same thread-name
        d = {}
        for p in self.thread_profile:
            tn = p.thread_name
            if tn not in d:
                d[tn] = ThreadProfile(tn, [str(p.tid)], p.time)
            else:
                d[tn].tid.append(str(p.tid))
                d[tn].time += p.time

        data = [
            (p.thread_name, len(p.tid), ", ".join(p.tid), p.time)
            for p in d.values()
        ]
        return (prop, data)


    @staticmethod
    def thread_profile_cmd(obj, thread_details, *table_args):
        pyobj = obj.object_data
        if not pyobj.data_collected:
            raise cli.CliError("You must run %s.stop first" % (obj.name,))

        if not pyobj.thread_profile:
            raise cli.CliError("No thread-details gathered")

        if thread_details:
            (t_prop, t_data) = pyobj._thread_profile_full()
        else:
            (t_prop, t_data) = pyobj._thread_profile()
        table.show(t_prop, t_data, *table_args)


    def _tid_filter_for_thread_group(self, thread_group):
        td = self.thread_dict
        if thread_group:
            if thread_group not in td:
                raise cli.CliError(
                    "Invalid thread-group '%s', available: %s" % (
                        thread_group, ", ".join(td)))
            tid_filter = td[thread_group]
        else:
            tid_filter = None
        return tid_filter

# Helper functions
Hex_Data = 1
Float_Data = 2
String_Data = 3

# Convert a data all in strings to the correct types and associated
# useful properties to the detected columns
def string_data_to_table_data(headings, data):
    float_re = re.compile(r'^-?\d+(?:\.\d+)?$')

    def is_hex(s):
        try:
            _ = int(s, 16)
            return True
        except ValueError:
            return False

    def data_type(s):
        if is_hex(s):
            return Hex_Data
        elif float_re.match(s):
            return Float_Data
        else:
            return String_Data

    # Use the information in the first row to detect what
    # kind of data there is in each column
    column_types = [data_type(s) for s in data[0]]

    # Convert the strings to other python types useful in the table
    nd = []
    for row in data:
        nr = []
        for i, c in enumerate(row):
            if column_types[i] == Hex_Data:
                try:
                    v = int(c,16)
                    nr.append(v)
                except ValueError:
                    nr.append(c)
            elif column_types[i] == Float_Data:
                if c == "":
                    nr.append(0.0)
                else:
                    nr.append(float(c))
            elif column_types[i] == String_Data:
                nr.append(c)
            else:
                assert 0
        nd.append(nr)

    # Create the table properties for each column
    column_props = []
    for i, c in enumerate(column_types):
        name = headings[i]
        if c == Hex_Data:
            column_props.append([
                (table.Column_Key_Name, name),
                (table.Column_Key_Int_Radix, 16),
                (table.Column_Key_Hide_Homogeneous, 0)])
        elif column_types[i] == Float_Data:
            column_props.append([
                (table.Column_Key_Name, name),
                (table.Column_Key_Hide_Homogeneous, 0.0),
                (table.Column_Key_Generate_Percent_Column, []),
                (table.Column_Key_Generate_Acc_Percent_Column, []),
                (table.Column_Key_Footer_Sum, True),
            ])
        elif column_types[i] == String_Data:
            column_props.append([
                (table.Column_Key_Name, name),
                (table.Column_Key_Hide_Homogeneous, "")])
        else:
            assert 0

    # Create the table properties
    table_props = [
        (table.Table_Key_Name, "VTune data"),
        (table.Table_Key_Default_Sort_Column, headings[1]),
        (table.Table_Key_Columns, column_props)]

    return (table_props, nd)

def csv_to_table(csv_output):
    # Use the CSV reader to break the elements
    d = csv.reader(csv_output, delimiter=',')
    data = []
    for (i, row) in enumerate(d):
        if i == 0:
            headings = row
        else:
            data.append(row)

    return string_data_to_table_data(headings, data)

def collect_threads(obj, threads):
    data = csv.reader(threads, delimiter=',')
    # The threads are called things like: "simics-common (TID: 30285)"
    # Group all threads with the same name in a dict, such as:
    # d["simics-common" : set(30285, 30286)]
    d = {}
    for (i, row) in enumerate(data):
        if i == 0: # skip header of csv
            continue

        (name, _, tid_str) = row   # Skip CPU time for the thread
        tid = int(tid_str)
        group_name = name.split(' ')[0]
        if group_name not in d:
            d[group_name] = set()
        d[group_name].add(tid)

    return d

# Returns a list of ThreadProfile elements
def collect_thread_profile(obj, threads):
    data = csv.reader(threads, delimiter=',')
    l = []
    for (i, row) in enumerate(data):
        if i == 0: # skip header of csv
            continue

        (name, time_str, tid_str) = row
        tid = int(tid_str)
        time = float(time_str)
        thread_name = name.split(' ')[0]
        l.append(ThreadProfile(thread_name, tid, time))
    return l


# If an regular expression argument has been supplied, parse it and
# give an error upon errors, otherwise return the compiled
# reg-expression.
def reg_ex_arg(r):
    if r:
        try:
            re_comp = re.compile(r)
        except re.error:
            raise cli.CliError(
                "The regular expression '%s' is invalid" % r)
        return re_comp
    return None


# Register commands
cli.new_command(
    "start", vtune_measurement.start_cmd,
    args = [
        cli.arg(cli.string_set_t(
            [
                "performance-snapshot",
                "hotspots",
                "uarch-exploration",
                "memory-access",
                "threading",
                "io",
                # "memory-consumption", gave no result
            ]), "collect", "?", "hotspots")
    ],
    cls = "vtune_measurement",
    type = ["Profiling"],
    see_also = ['<vtune_measurement>.stop',
                '<vtune_measurement>.summary',
                '<vtune_measurement>.module-profile',
                '<vtune_measurement>.profile'],
    short = "start measurement",
    doc = ("Start VTune measurements."
           " The <arg>collect</arg>"
           " argument is optional and defaults to 'hotspots'"
           " which identifies the most time consuming functions"
           " and lines of source code."
           " There are other types of analyses that can be"
           " used, use tab-completion to see the list"
           " it is unsure how well these works and the"
           " result needs to be examined inside vtune-gui")
)

cli.new_command(
    "stop", vtune_measurement.stop_cmd,
    args = [],
    cls = "vtune_measurement",
    type = ["Profiling"],
    see_also = ['<vtune_measurement>.start',
                '<vtune_measurement>.summary',
                '<vtune_measurement>.module-profile',
                '<vtune_measurement>.profile'],
    short = "stop measurement",
    doc = ("Stop VTune measurements."))

cli.new_command(
    "summary", vtune_measurement.summary_cmd,
    args = [],
    cls = "vtune_measurement",
    type = ["Profiling"],
    see_also = ['<vtune_measurement>.start',
                '<vtune_measurement>.stop',
                '<vtune_measurement>.module-profile',
                '<vtune_measurement>.profile'],
    short = "show VTune summary of the run",
    doc = ("Show VTune&trade; summary of the run."))

cli.new_command(
    "thread-groups", vtune_measurement.thread_group_cmd,
    args = [],
    cls = "vtune_measurement",
    type = ["Profiling"],
    see_also = ['<vtune_measurement>.start',
                '<vtune_measurement>.stop',
                '<vtune_measurement>.module-profile',
                '<vtune_measurement>.profile'],
    short = "show available thread groups",
    doc = ("Show available thread groups."))

cli.new_command(
    "launch-gui", vtune_measurement.launch_gui_cmd,
    args = [],
    cls = "vtune_measurement",
    type = ["Profiling"],
    see_also = ['<vtune_measurement>.start',
                '<vtune_measurement>.stop',
                ],
    short = "start vtune-gui on collected data",
    doc = ("Start the VTune&trade; GUI on the collected data, allowing more"
           " detailed inspection and analysis of the performance profile.")
    )


cli.new_command(
    "flamegraph", vtune_measurement.flamegraph_cmd,
    args = [
        cli.arg(cli.flag_t, "-open-browser"),
        cli.arg(cli.flag_t, "-discard-module"),
        cli.arg(cli.flag_t, "-modules-only"),
        cli.arg(cli.filename_t(), "svg-output-filename", "?", None),
        cli.arg(cli.str_t, "thread-group", "?", None,
                expander = vtune_measurement.thread_group_expander)
    ],
    cls = "vtune_measurement",
    type = ["Profiling"],
    see_also = ['<vtune_measurement>.start',
                '<vtune_measurement>.stop',
                ],
    short = "produce a flamegraph (.svg) file of the profile",

    doc = """This command produces a Scalable Vector Graphics (SVG) file,
    suitable to view the profile in a web-browser. A flamegraph is a graphical
    presentation of the profile, providing a good overview of where the time
    is spent and the call-chains for the bottlenecks.

    In order to use this feature the <i>flamegraph</i> package must be
    installed on the host where Simics runs. See
    <url>http://www.brendangregg.com/flamegraphs.html</url>.

    The <file>flamegraph.pl</file> file, must have executable
    permissions and be located within the <tt>PATH</tt> environment
    variable when Simics is started.

    The graphic is dynamic, allowing you to hover over the mouse
    to get further details on the functions, or click to zoom-in
    on all a particular function and its children.

    In the browser, it is also possible to search in the flamegraph
    by pressing CTRL-f and giving a regular expression for functions
    to locate and see how much percent the hits represents.

    The <tt>-open-browser</tt> flag will attempt to open the
    generated file on the default webbrowser on the system.

    The <tt>-discard-module</tt> flag only includes the function
    names in the profile, causing shorter identifiers in the graph.

    The <tt>-modules-only</tt> flag only lists the modules and
    tries to collapse intra-module calls, providing an overview
    of the profile on module level and how the modules are called.

    The output file is optional and specified with the
    <arg>svg-output-filename</arg> argument. If omitted, a temporary
    file will be created.

    The <arg>thread-group</arg> argument allow filtering on threads
    which have a certain name.
    """
)

cli.new_command(
    "save-folded-stacks", vtune_measurement.save_folded_stacks_cmd,
    args = [
        cli.arg(cli.flag_t, "-discard-module"),
        cli.arg(cli.flag_t, "-modules-only"),
        cli.arg(cli.flag_t, "-json"),
        cli.arg(cli.str_t, "thread-group", "?", None,
                expander = vtune_measurement.thread_group_expander),
        cli.arg(cli.filename_t(), "output-filename"),
    ],
    cls = "vtune_measurement",
    type = ["Profiling"],
    see_also = ['<vtune_measurement>.start',
                '<vtune_measurement>.stop',
                ],
    short = "fold stacks of the profile and write it to a file",

    doc = """Produce a file with folded stack from the profile.

    This is the intermediate file format which <tt>flamegraph</tt>
    works on. This file can be used to run flamegraph manually
    or to make diffs comparing two runs.

    With the <tt>-json</tt> switch the output file is instead
    written as a json file.

    The <tt>-discard-module</tt> flag only includes the function
    names in the profile, causing shorter identifiers in the graph.

    The <tt>-modules-only</tt> flag only lists the modules and
    tries to collapse intra-module calls, providing an overview
    of the profile on module level and how the modules are called.

    The <arg>thread-group</arg> argument allow filtering on threads
    which have a certain name.

    The output file is specified with the <arg>output-filename</arg>
    argument."""
)

table.new_table_command(
    "profile", vtune_measurement.profile_cmd,
    args = [
        cli.arg(cli.str_t, "thread-group", "?", None,
                expander = vtune_measurement.thread_group_expander),
        cli.arg(cli.str_t, "function-regexp", "?", None),
        cli.arg(cli.str_t, "module-regexp", "?", None),
        cli.arg(cli.str_t, "file-regexp", "?", None),
        cli.arg(cli.flag_t, "-aggregate-filtered-out"),
        cli.arg(cli.flag_t, "-csv"),
        cli.arg(cli.filename_t(), "csv-output-filename", "?", None),
        cli.arg(cli.flag_t, "-no-inline"),
    ],
    cls = "vtune_measurement",
    type = ["Profiling"],
    see_also = ['<vtune_measurement>.start',
                '<vtune_measurement>.stop',
                '<vtune_measurement>.module-profile',
                '<vtune_measurement>.summary'],
    short = "show profile of run",
    doc = """
    Show hotspot profile of the run. The <arg>thread-group</arg>
    argument allow filtering on threads which have a certain name.

    By default inline functions are included in the report,
    which might cause multiple instances of the same function
    to be reported. The <tt>-no-inline</tt> switch accounts
    the caller of the inline functions instead.

    The <arg>function-regexp</arg>, <arg>module-regexp</arg> and
    <arg>file-regexp</arg> allows the profile to contain the rows that
    matches one or all of these regular expressions.

    The <tt>-aggregate-filtered-out</tt> flag merges all reg-exp rows
    which are filtered out, into a single row. (This flag does not
    effect the thread-group filtering).

    By default, the output will be presented in a table, for a more
    machine readable format, use the <tt>-csv</tt> flag which prints
    the entire profile in a comma separated value list. With
    <arg>csv-output-filename</arg> the csv formatted profile can be
    written to a file. Regular expression filters are discarded with
    this flag.  """,
    sortable_columns = ["Function", "CPU Time", "Module",
                        "Source File"])

table.new_table_command(
    "module-profile", vtune_measurement.module_profile_cmd,
    args = [cli.arg(cli.str_t, "thread-group", "?", None,
                    expander = vtune_measurement.thread_group_expander),
            cli.arg(cli.flag_t, "-csv"),
            cli.arg(cli.filename_t(), "csv-output-filename", "?", None)
    ],
    cls = "vtune_measurement",
    type = ["Profiling"],
    see_also = ['<vtune_measurement>.start',
                '<vtune_measurement>.stop',
                '<vtune_measurement>.profile',
                '<vtune_measurement>.summary'],
    short = "show module profile of run",
    doc = """
    Show hotspot profile of the run based on modules. The
    <arg>thread-group</arg> argument allow filtering on threads which
    have a certain name.

    By default, the output will be presented in a table, for a more
    machine readable format, use the <tt>-csv</tt> flag which prints
    the entire profile in a comma separated value list. With
    <arg>csv-output-filename</arg> the csv formatted profile can be
    written to a file """,
    sortable_columns = ["Module", "CPU Time"])


table.new_table_command(
    "thread-profile", vtune_measurement.thread_profile_cmd,
    args = [
        cli.arg(cli.flag_t, "-thread-details"),
    ],
    cls = "vtune_measurement",
    type = ["Profiling"],
    see_also = ['<vtune_measurement>.start',
                '<vtune_measurement>.stop',
                '<vtune_measurement>.profile',
                '<vtune_measurement>.summary'],
    short = "show thread profile of run",
    doc = """
    Show which threads that have executed most during the measurement.
    All threads registered to the same thread-group are accumulated
    into one row, unless the <tt>-thread-details</tt> flag is used
    where each row represents a thread-id (tid).
    """,
    sortable_columns = ["CPU Time"])
