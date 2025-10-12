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


from simics import *
import table
from cli import (new_command, arg, int_t, str_t, flag_t, float_t, obj_t,
                 CliError, get_completions, command_return, string_set_t,
                 new_status_command, new_info_command, filename_t)

import webbrowser
import tempfile
import os
import cProfile

from dataclasses import dataclass
from typing import Callable

import probes

from . import common
from . import sampler
from .simics_start import expand_notifier_types, expand_notifier_objs

from . import html_graphs

def get_info(obj):
    p_sampler = obj.object_data

    mode = {
        sampler.REALTIME_SYNC_MODE: "Real time (synced)",
        sampler.REALTIME_MODE: "Real time",
        sampler.VIRTUAL_MODE: "Virtual time",
        sampler.NOTIFIER_MODE: "Notifier-based",
        sampler.TIMESTAMP_MODE: "Time stamp (from file)"
    }[p_sampler.mode]

    interval = "No interval used"
    if (p_sampler.mode in [sampler.REALTIME_SYNC_MODE, sampler.REALTIME_MODE,
                           sampler.VIRTUAL_MODE]):
        interval = f"{p_sampler.interval} s"

    clock = "No clock used"
    if p_sampler.mode in [sampler.VIRTUAL_MODE, sampler.TIMESTAMP_MODE]:
        clock = p_sampler.clock.name

    notifier_type = "No notifier type used"
    notifier_obj = "No notifier object used"
    if p_sampler.mode == sampler.NOTIFIER_MODE:
        notifier_type = p_sampler.notifier_type
        notifier_obj = p_sampler.notifier_obj.name

    return [("Sampling",
             [("Mode", mode),
              ("Interval", interval),
              ("Clock", clock),
              ("Notifier type", notifier_type),
              ("Notifier object", notifier_obj)]),
            ]


def get_status(obj):
    p_sampler = obj.object_data
    probes = []
    for sp in p_sampler.sampled_probes():
        flags = sp.mode
        flags += " -no-sampling" if sp.no_sampling else ""
        flags += " -hidden" if sp.hidden else ""
        probes.append((sp.probe_proxy.cli_id, flags))

    return [("Added Probes", probes)]


def start_cmd(obj):
    obj.object_data.start()


def start_kwargs(classname, shortname, see_also):
    return dict(
        see_also=see_also,
        cls=classname,
        type=["Probes"],
        short=f"start the {shortname}",
        doc=f"""
    Start {shortname} again if it has been stopped. The options used when
    creating the {shortname} will be restored.
    """
    )


def stop_cmd(obj):
    obj.object_data.stop()


def stop_kwargs(classname, shortname, see_also):
    return dict(
        see_also=see_also,
        cls=classname,
        type=["Probes"],
        short=f"stop the {shortname}",
        doc=f"""Stop {shortname}. No more samples will be printed.
        The {shortname} can be started with the <cmd>&lt;{classname}>.start
        </cmd> command again."""
    )

def reset_session_cmd(obj):
    obj.object_data.reset_session()

def reset_session_kwargs(classname, shortname, see_also):
    return dict(
        see_also=see_also,
        cls=classname,
        type=["Probes"],
        short="reset the probes' session start values",
        doc=f"""Reset the probes' start values.
        This causes the future session and delta values to be calculated
        based from the current values, and not from the values when the
        probe was originally added to the {classname}.
        \nThis can be useful between the <cmd>&lt;{classname}>.stop</cmd>
        and <cmd>&lt;{classname}>.start</cmd> commands,
        for example, to start measurement at wallclock zero.
        """
    )

def force_sample_cmd(obj):
    obj.object_data.force_sample()

def force_sample_kwargs(classname, shortname, see_also):
    return dict(
        args=[],
        see_also=see_also,
        cls=classname,
        type=["Probes"],
        short="manually trigger a sample",
        doc="""Force a sample to be triggered. For various testing
        scenarios, it can be useful to trigger a sample manually.
        For example to get a final sample of data measured, but
        not yet included in a sample.
        """
    )

def delete_cmd(obj):
    obj.object_data.stop()
    SIM_delete_objects([obj])


def delete_kwargs(classname, shortname, see_also):
    return dict(
        see_also=see_also,
        cls=classname,
        type=["Probes"],
        short=f"delete {shortname}",
        doc=f"Delete the {shortname} and all sampling activities."
    )


def probe_expander(prefix):
    ids = {p.cli_id for p in probes.get_all_probes()}
    return get_completions(prefix, ids)

def probe_kind_expander(prefix):
    kinds = probes.get_all_probe_kinds()
    return get_completions(prefix, kinds)


def add_probe_cmd(obj, verbose, hidden, no_sampling,
                  probe_kinds_to_add, probes_to_add, mode):
    if hidden and no_sampling:
        raise CliError('Cannot set both -hidden and -no-sampling')

    if not (probe_kinds_to_add or probes_to_add):
        raise CliError('Neither probe or probe-kind specified')

    p_sampler = SIM_object_data(obj)
    added_cli_ids = p_sampler.add_probes(mode, probe_kinds_to_add,
                                         probes_to_add,
                                         hidden, no_sampling)

    for cli_id in added_cli_ids:
        if verbose:
            flags = []
            if hidden:
                flags.append('hidden')
            if no_sampling:
                flags.append('no-sampling')
            flag_str = (" (" + ", ".join(flags) + ")") if flags else ""

            SIM_log_info(
                1, obj, 0,
                f"Added: {cli_id} with mode {mode}{flag_str}")

    return command_return(
        value=added_cli_ids,
        message=f"Added {len(added_cli_ids)} probes to {obj.name}")


def add_probe_kwargs(classname, shortname, see_also):
    return dict(
        args=[
            arg(flag_t, "-verbose"),
            arg(flag_t, "-hidden"),
            arg(flag_t, "-no-sampling"),
            arg(str_t, "probe-kind", "*",
                expander=probe_kind_expander),
            arg(str_t, "probe", "*",
                expander=probe_expander),
            arg(string_set_t(["current", "session", "delta"]),
                "mode", "?", "delta")],
        cls=classname,
        see_also=see_also,
        type=["Probes"],
        short=f"add a probe to the {shortname}",
        doc=(f"""

    Add probes to the {shortname}. Using the <arg>probe-kind</arg> argument
    will add all instances of that probe to the {shortname}, i.e. all objects
    that have that probe, will be added.

    To be more selective on which objects that should be monitored,
    the <arg>probe</arg> argument can be used instead, specific which object's
    probes that should be added.

    Either way a prefix which ends with a dot (.) is allowed to add any
    probes below the prefix in the probe name hierarchy, e.g.,
    probe="board.mb.cpu[0]:cpu." will add all probes that start with "cpu.". in
    the board.mb.cpu[0] object, and similarly, a probe-kind of just "cpu."
    will add all probes having "cpu." as prefix, in all objects.

    The <arg>mode</arg> argument tells the {shortname} how the probe values
    should be display in each sample, by default the <tt>delta</tt> value
    from last sample is shown.
    Other options are <tt>current</tt> and <tt>session</tt>. <tt>current</tt>
    means the actual probe value is displayed in each sample.
    With the <tt>session</tt> mode, the delta value since the probe
    was added to the {shortname} is displayed.

    For example, a <tt>steps</tt> probe might have a value of several
    millions when you add the probe to the {shortname}. With <tt>current</tt>
    the full number will be displayed, with <tt>session</tt> it will start
    at zero and increase. The <tt>delta</tt> will show the number of
    steps between each sample.

    A probe can be added with different modes by using the command
    repeatedly. A probe can only be added once in each mode and adding it
    several time will have no effect.

    If <tt>-verbose</tt> is given all the proves added are logged to the
    console.

    The <tt>-hidden</tt> flag can be used to collect a probe during
    sampling, but not print the value on the console. (Reducing the width
    and the amount of data being presented).
    Hidden probes will still be printed by the various commands that
    list or export the data.

    The <tt>-no-sampling</tt> flags tells the monitor to ignore the
    probe in each sample, and only display the final probe value. The
    probe will however be available in the
    <cmd>&lt;{classname}>.summary</cmd> and
    <cmd>&lt;{classname}>.export-to-json</cmd> commands. The purpose
    of this is to reduce memory footprint and to lower sampling
    overhead.

    The command returns a list of the probe names added if
    used as a value.  """)
    )


def remove_probe_kind_expander(prefix, obj, args):
    p_sampler = obj.object_data
    mode = args[0]
    if mode == None:
        mode = "delta"

    used_sprobes = {sp for sp in p_sampler.sampled_probes()
                    if sp.mode == mode}
    ids = set()
    for sp in used_sprobes:
        ids.add(sp.probe_proxy.prop.kind)
    return get_completions(prefix, list(ids))


def remove_probe_expander(prefix, obj, args):
    p_sampler = obj.object_data
    mode = args[0]
    if mode == None:
        mode = "delta"

    used_sprobes = {sp for sp in p_sampler.sampled_probes()
                    if sp.mode == mode}
    ids = set()
    for sp in used_sprobes:
        ids.add(sp.probe_proxy.cli_id)
    return get_completions(prefix, list(ids))

def remove_probe_cmd(obj, mode, verbose, probe_kinds_to_remove, probes_to_remove):
    if not (probe_kinds_to_remove or probes_to_remove):
        raise CliError('Neither probe or probe-kind specified')

    p_sampler = SIM_object_data(obj)
    removed_cli_ids = p_sampler.remove_probes(mode, probe_kinds_to_remove,
                                              probes_to_remove)

    for cli_id in removed_cli_ids:
        if verbose:
            SIM_log_info(1, obj, 0, f"Removing: {cli_id} in mode {mode}")

    return command_return(
        value=removed_cli_ids,
        message=f"Removed {len(removed_cli_ids)} probes from {obj.name}")

def remove_probe_kwargs(classname, shortname, see_also):
    return dict(
        args=[arg(string_set_t(["current", "session", "delta"]),
                  "mode", "?", "delta"),
              arg(flag_t, "-verbose"),
              arg(str_t, "probe-kind", "*",
                  expander=remove_probe_kind_expander),
              arg(str_t, "probe", "*",
                  expander=remove_probe_expander),
              ],
        see_also=see_also,
        cls=classname,
        type=["Probes"],
        short=f"remove probe from {shortname}",
        doc=f"""
    Remove probes previously added to the {shortname}.

    If <arg>mode</arg> is used the probes added in that mode will be removed,
    otherwise probes in delta mode will be removed. To remove a probe
    added in several modes, this command should be run repeatedly, one for each
    mode.

    Using the <arg>probe-kind</arg> argument will remove all instances of that
    probe to the {shortname}, i.e. all objects that have that probe, will be
    removed.

    To more selectively remove certain object probes the <arg>probe</arg>
    argument can be used instead.

    Just like in the <cmd>&lt;{classname}>.add-probe</cmd> command,
    it is possible to specify parts of the object or probe-kind to get multiple
    matches.

    If <tt>-verbose</tt> is given all the proves added are logged to the
    console.

    The command returns a list of the probe names added if used as a value.
    """)


def summary_cmd(obj, probe_name_substr, raw, max_lines, *table_args):
    print(obj.object_data.presentation.create_summary_table(
        probe_name_substr, raw, max_lines, *table_args))


def active_probes_expander(prefix, obj):
    p_sampler = SIM_object_data(obj)
    ids = {sp.probe_proxy.prop.kind for sp in p_sampler.sampled_probes()}
    return get_completions(prefix, list(ids))


def summary_kwargs(classname, shortname, see_also):
    return dict(
        args=[
            arg(str_t, "probe-name-substr", "?",
                expander=active_probes_expander),
            arg(flag_t, "-raw-value"),
            arg(int_t, "histogram-max-lines", "?"),
        ],
        see_also=see_also,
        cls=classname,
        type=["Probes"],
        short="show total summary of probes",
        doc=(f"""
    Shows summary of all added probes. The total value from the start of the
    {shortname} will be shown.  The <arg>probe-name-substr</arg> argument can be
    used to filter for probes with a given substring in their name. The
    <tt>-raw-value</tt> flag adds an extra column showing the raw format of the
    probe value. The <arg>histogram-max-lines</arg> can be used to set the
    maximum number of lines printed for historam probes. The default is to use
    the table settings that can be controlled by the
    <cmd>&lt;{classname}>.table-settings</cmd> command in the monitor.
    """),
        sortable_columns=[
            "Display Name",
            "Probe Name",
            "Object",
            "Session Raw Value",
            "Session Formatted Value",
            "Current Raw Value",
            "Current Formatted Value"
        ]
    )


def sampling_settings_cmd(obj, mode, interval, clock, notifier_type,
                          notifier_obj):
    p_sampler = obj.object_data
    p_sampler.stop()

    if mode != None:
        p_sampler.mode = mode

    if interval != None:
        if p_sampler.mode not in [
                sampler.REALTIME_SYNC_MODE,
                sampler.REALTIME_MODE,
                sampler.VIRTUAL_MODE]:
            raise CliError(f'Setting an interval is only relevant '
                           f'when mode is "{sampler.REALTIME_MODE}", '
                           f' "{sampler.REALTIME_SYNC_MODE}" '
                           f'or {sampler.VIRTUAL_MODE}"')
        p_sampler.interval = interval

    if clock != None:
        if p_sampler.mode != sampler.VIRTUAL_MODE:
            raise CliError(f'Setting a clock is only relevant '
                           f'when mode is "{sampler.VIRTUAL_MODE}"')
        p_sampler.clock = clock

    if notifier_type != None:
        if p_sampler.mode != sampler.NOTIFIER_MODE:
            raise CliError(f'Setting a notifier type is only relevant '
                           f'when mode is "{sampler.NOTIFIER_MODE}"')
        p_sampler.notifier_type = notifier_type

    if notifier_obj != None:
        if p_sampler.mode != sampler.NOTIFIER_MODE:
            raise CliError(f'Setting a notifier object is only relevant '
                           f'when mode is "{sampler.NOTIFIER_MODE}"')
        p_sampler.notifier_obj = notifier_obj

    p_sampler.start()


def sampling_settings_kwargs(classname, shortname, see_also):
    return dict(
        args=[arg(string_set_t([sampler.REALTIME_SYNC_MODE,
                                sampler.REALTIME_MODE,
                                sampler.VIRTUAL_MODE,
                                sampler.NOTIFIER_MODE]),
              "sampling-mode", "?"),
              arg(float_t, "interval", "?"),
              arg(obj_t("clock", "cycle"), "clock", "?"),
              arg(str_t, "notifier-type", "?", expander=expand_notifier_types),
              arg(obj_t("notifier-obj"), "notifier-obj", "?", expander=expand_notifier_objs(
                  notifier_type_arg_idx=3)) # notifier type is the 3rd arg in the args list
              ],
        see_also=see_also,
        cls=classname,
        type=["Probes"],
        short="set sampling settings",
        doc=f"""
    Reset the <arg>sampling-mode</arg> of sampling and the attributes attached
    to each mode: the <arg>interval</arg> if the selected mode is
    "{sampler.REALTIME_MODE}", the <arg>interval</arg> and <arg>clock</arg> if
    the selected mode is "{sampler.VIRTUAL_MODE}", the <arg>notifier-type</arg>
    and <arg>notifier-obj</arg> if the selected mode is
    "{sampler.NOTIFIER_MODE}"."""
    )


def table_settings_cmd(obj, repeat_height, histogram_rows):
    p_sampler = obj.object_data
    p_sampler.stop()

    if repeat_height != None:
        p_sampler.presentation.set_repeat_height(repeat_height)

    if histogram_rows != None:
        p_sampler.presentation.create_cell_formatter(histogram_rows)

    p_sampler.start()


def table_settings_kwargs(classname, shortname, see_also):
    return dict(
        args=[arg(int_t, "repeat-height", "?", None),
              arg(int_t, "histogram-rows", "?", None)],
        see_also=see_also,
        cls=classname,
        type=["Probes"],
        short="set the table settings",
        doc="""
    Reset the table settings.

    The <arg>repeat-height</arg> option tells when the header will repeat
    in the sampling table. Whenever the table height grows to a multiple of
    this value it will repeat the headings.

    The <arg>histogram-rows</arg> controls the maximum number of rows that
    should be printed in histogram. One additional row may be printed indicating
    the total amount of discarded rows. Default is 5 rows.""")


def unique_sprobes_expander(prefix, obj):
    p_sampler = SIM_object_data(obj)
    ids = {sp.unique_id for sp in p_sampler.sampled_probes()}
    l = []
    for i in ids:
        l.append(i)  # add complete name (possibly with object)
        if ":" in i:
            l.append(i.split(":")[1])  # add probe_name without object

    return get_completions(prefix, l)


def plot_graph_cmd(obj, graph_name, graph_type, from_now, window_size,
                   x, ys, annotations):
    if not common.running_in_simics_client():
        raise CliError(
            "Simics must be running in simics-client for plot support")

    p_sampler = SIM_object_data(obj)
    x_sp = p_sampler.sprobes_matching_name(x)

    if x_sp == []:
        raise CliError(f"No such probe: {x}")
    if len(x_sp) > 1:
        raise CliError(f"X-axis matches multiple columns: {x}")

    y_sps = []
    for y in ys:
        y_sp = p_sampler.sprobes_matching_name(y)
        if y_sp == []:
            raise CliError(f"No such probe: {y}")
        y_sps.extend(y_sp)

    annotation_sprobes = []
    for ann in annotations:
        a_sp = p_sampler.sprobes_matching_name(ann)
        if len(a_sp) == 0:
            raise CliError(
                f"Annotation probe not found: {ann}")
        annotation_sprobes.extend(a_sp)

    p_sampler.presentation.add_plot(graph_name, graph_type, from_now,
                                    window_size, x_sp[0],
                                    y_sps, annotation_sprobes)


def plot_graph_kwargs(classname, shortname, see_also):
    return dict(
        args=[arg(str_t, "graph-name"),
              arg(string_set_t(["line", "line-stacked"]),
                  "graph-type", "?", "line"),
              arg(flag_t, "-from-now"),
              arg(int_t, "window-size", "?", None),
              arg(str_t, "x", expander=unique_sprobes_expander),
              arg(str_t, "ys", "+", expander=unique_sprobes_expander),
              arg(str_t, "annotations", "*", None,
                  expander=unique_sprobes_expander),
              ],
        see_also=see_also,
        cls=classname,
        type=["Probes"],
        short="produce a plot of probes",
        doc=f"""This command only works when Simics runs inside simics-client.
    This command produces a graphical graph which is updated while
    Simics is running.

    The <arg>graph-name</arg> argument specifies a unique name for the graph.

    The <arg>graph-type</arg> can be any of "line" or "line-stacked",
    where "line" is default. With "line-stacked" all graphs are put
    on-top of each-other.

    The <tt>-from-now</tt> flag allows the plot to start from this point in time,
    otherwise the already collected data in the {shortname} is used also.

    The <arg>window-size</arg> may be used to only look at the latest 'n' points
    in the history. If not specied all points are drawn.

    The <arg>x</arg> argument specifies which of the probes (added to the
    monitor) should be used for the x-axis values. Note that it is important for
    this probe to be monotonically increasing if a normal graph with growing x
    values is to be plotted. All probes in the monitor are added with a mode
    option (see the add-probe command), and the delta mode is not suitable for
    the x-axis probes for this reason.

    <arg>ys</arg> argument specifies one, or several, probes for the y-axis.

    The <arg>annotations</arg> argument can be used to add one or
    several annotations to each dot in the graph. When the user hover
    over the dot with the mouse pointer the information will be
    displayed.  Each value in the graph will be annotated with the
    values from the probes given in this argument (using the probes
    display settings). If several graphs are displayed in the same window
    (due to multiple 'ys'), these annotations will be displayed for all
    graphs.
    """)

def print_history_cmd(obj, include_hidden, *table_args):
    mon = obj.object_data
    tprops = mon.presentation.build_table_properties(include_hidden)
    tdata = mon.presentation.get_data_history(include_hidden)
    msg = table.get(tprops, tdata, *table_args)
    return command_return(value=tdata, message=msg)


def print_history_kwargs(classname, shortname, see_also):
    return dict(
        args=[arg(flag_t, "-include-hidden"),
              ],
        see_also=see_also,
        cls=classname,
        type=["Probes"],
        short="print sample history of the probes",
        doc=f"""
        The <tt>&lt;{classname}&gt;</tt> prints the samples during
        execution, but the data is also saved in a history buffer.
        This command allows to look at the collected data afterwards.
        Using <tt>-include-hidden</tt> also prints the probes which
        have been added with the <i>-hidden</i> flag (in the
        <tt>&lt;{classname}&gt;.add-probe</tt> command).


        """
    )

def clear_history_cmd(obj):
    mon = obj.object_data
    mon.presentation.clear_history()

def clear_history_kwargs(classname, shortname, see_also):
    return dict(
        args=[],
        see_also=see_also,
        cls=classname,
        type=["Probes"],
        short="clear the sample history of the probes",
        doc="""
        Clear the collected history of sampled data.
        """
    )


def export_json_cmd(obj, filename, workload, indent):
    mon = obj.object_data
    js = mon.export_to_json(workload, indent)
    try:
        with open(filename, "w") as f:
            f.write(js)
    except OSError as msg:
        raise CliError(f"Error:{msg}")

def export_json_kwargs(classname, shortname, see_also):
    return dict(
        args=[arg(filename_t(), 'filename'),
              arg(str_t, 'workload', "?", None),
              arg(flag_t, '-indent')],
        see_also=see_also,
        cls=classname,
        type=["Probes"],
        short="save probe data in json format",
        doc="""Save all probe data to the JSON file <arg>filename</arg>.
        The <arg>workload</arg> specifies what that has been executed,
        this is also saved in the JSON file.
        The <tt>-indent</tt> flag causes the json output to be properly
        indented for readability, but also makes the file larger.

        Additional information on Simics, the host and target is also
        saved."""
    )


def merge_json_cmd(obj, in_files, out_file, indent, truncate_samples):
    mon = obj.object_data
    js = mon.merge_json(in_files, truncate_samples)
    try:
        with open(out_file, "w") as f:
            f.write(js)
    except OSError as msg:
        raise CliError(f"Error:{msg}")

def merge_json_kwargs(classname, shortname, see_also):
    return dict(
        args=[
            arg(filename_t(exist=True), "input-filenames", "+"),
            arg(filename_t(exist=False), 'output-filename'),
            arg(flag_t, '-indent'),
            arg(flag_t, '-truncate-samples'),
            #arg(flag_t, '-compress'),
        ],
        see_also=see_also,
        cls=classname,
        type=["Probes"],
        short="save probe data in json format",
        doc="""Combine multiple runs in JSON format into one file.
        This can be used to combine multiple runs with different probes,
        represented as one run. The <arg>input-filenames</arg> lists
        all json files that should be merged. When data exists in
        several files, the last file with the data is used.

        The <arg>output-filename</arg> specifies the name of the generated
        merged json file.

        With the <tt>-indent</tt> switch, the output file becomes readable
        by indenting the json text output, but leads to larger in file-size.

        When several json files are merged, the probes needs to have
        equal amount of samples in order to align the sample data properly.
        If this is not true, the command will abort complain that this
        was not the case. However, the difference between runs can be
        due to indeterministic execution of the models.
        The <tt>-truncate-samples</tt> flag can be used to ignore the
        error and truncate the samples to the smallest amount.
        """
        #The <tt>-compress</tt> switch can be used to automatically compress
        #the output file.
    )


def html_report_cmd(obj, html_dir, probe_json_filename,
                    graph_spec_json_filename,  open_browser, one_page):
    mon = obj.object_data

    if not html_dir and not open_browser:
        raise CliError(
            "Must either specify directory to generate or use -open-browser")

    if html_dir and not os.path.exists(html_dir):
        try:
            os.makedirs(html_dir)
        except OSError as msg:
            raise CliError(f"Error:{msg}")

    if not html_dir:
        html_dir = tempfile.mkdtemp(prefix="html")

    # Test that we can generate the main page here.
    filename = os.path.join(html_dir, "index.html")
    try:
        fd = open(filename, "w+b")
    except OSError as msg:
        raise CliError(f"Error:{msg}")
    fd.close()

    if not graph_spec_json_filename:
        # The default for system_perfmeter, use it for other
        # probe-monitor classes too at the moment.
        default_file = ('%simics%/targets/common/benchmark/'
                        + 'system_perfmeter_graphs.json')
        graph_spec_json_filename = SIM_lookup_file(default_file)
        if not graph_spec_json_filename:
            raise CliError(
                f"Failed finding default graph specification: {default_file}")

    mon.create_html_report(html_dir, probe_json_filename,
                           graph_spec_json_filename, one_page)

    if open_browser:
        try:
            webbrowser.open(filename)
        except Exception as msg:
            raise CliError(f"Failed starting browser: {msg}")

def generate_graph_property_documentation():
    doc = ""
    for pd in html_graphs.document_graph_specification():
        doc += '<br/>'
        doc += f'Key:"<b>{pd.name}</b>" Type:<i>{pd.type}</i>'
        doc += f' Default:<i>{pd.default}</i>'
        if pd.valid_values:
            doc += f' Valid-values:<i> {pd.valid_values}</i>'
        doc += '<br/>'
        doc += pd.desc.replace('\n', '<br/>')
        doc += '<br/>'
    return doc



def html_report_kwargs(classname, shortname, see_also):
    graph_doc = generate_graph_property_documentation()
    return dict(
        args=[arg(filename_t(dirs=True), 'html-dir', "?", None),
              arg(filename_t(exist=True), 'probe-json-file', "?", None),
              arg(filename_t(exist=True), 'graph-spec-json-file', "?", None),
              arg(flag_t, "-open-browser"),
              arg(flag_t, "-one-page"),
              ],
        see_also=see_also,
        cls=classname,
        type=["Probes"],
        short="produce an HTML report with graphs and performance data",
        doc=f"""
        Produce a performance report in HTML. The graphs that are included
        depend on the probes that have been monitored. The <arg>html-dir</arg>
        argument specifies the directory for the HTML report. If not specified,
        a temporary directory will be created. The file "index.html" is the
        start page.

        The <arg>probe-json-file</arg> can specify an already generated
        json file containing the probe information, and a report of its
        data will be presented (instead of the current session).

        The <arg>graph-spec-json-file</arg> argument points out an
        json file used for selecting which graphs to produce. If not
        specified, a default file will be used.

        The <tt>-open-browser</tt> switch starts a web-browser directly
        on the generated file.

        To decrease browser load time, and to make the main-page more
        high-level, some graphs can request to be added to sub-pages
        instead of the main page. The <tt>-one-page</tt> switch prevents
        this and puts all graphs on the same page.

        The graph specification (see <arg>graphs-spec-json-file</arg)
        defines which graphs that should be generated. The top-level
        <tt>"graphs"</tt> key holds a value-list of all defined graphs.
        In this list, each graph support the following key/value pairs:

        {graph_doc}

        Please note that some key/value pairs only affect certain graphs. Future
        improvements to the graph generation process may result in changes,
        additions, or removals of the supported key/value pairs. Therefore,
        backward compatibility of the JSON file is not guaranteed."""
    )

def profile_probes_cmd(obj, samples):
    name = obj.name
    cmd = f"for _ in range({samples}): conf.{name}.object_data.presentation.process_sample()"
    cProfile.run(cmd, sort="cumtime")

def profile_probes_kwargs(classname, shortname, see_also):
    return dict(
        args=[arg(int_t, "samples", "?", 100),
              ],
        see_also=see_also,
        cls=classname,
        type=["Probes"],
        short="fake samples and do a python profile of the collection",
        doc="""
        On the given set of defined probes, fake <arg>samples</arg> without actually
        executing any code in the processors and provide a Python profile of where
        the most of the time is spent.
        """
    )


class CmdSet:

    @dataclass(frozen=True)
    class CmdDef:
        cli_cmd_create: Callable
        cli_cmd_name: str
        cli_cmd_impl: Callable
        cli_cmd_args: Callable

        def create_see_also(self, cmd_set, classname):
            cmd_names = cmd_set.cmd_names()
            cmd_names.remove(self.cli_cmd_name)
            return [f"<{classname}>.{cmd_name}"
                    for cmd_name in sorted(cmd_names)]

        def apply_to(self, cmd_set, classname, shortname):
            see_also = self.create_see_also(cmd_set, classname)
            self.cli_cmd_create(self.cli_cmd_name, self.cli_cmd_impl,
                                **self.cli_cmd_args(classname, shortname,
                                                    see_also))

    def __init__(self, cmd_set=None):
        self._set = cmd_set._set.copy() if cmd_set else set()

    def _add(self, type, name, impl, args):
        self._set.add(self.CmdDef(type, name, impl, args))

    def add_command(self, name, impl, args):
        self._add(new_command, name, impl, args)

    def add_table_command(self, name, impl, args):
        self._add(table.new_table_command, name, impl, args)

    def cmd_names(self):
        return [cmd_def.cli_cmd_name for cmd_def in self._set]

    def apply_to(self, classname, shortname):
        for cmd_def in self._set:
            cmd_def.apply_to(self, classname, shortname)


sampler_cmd_set = CmdSet()
sampler_cmd_set.add_command("start", start_cmd, start_kwargs)
sampler_cmd_set.add_command("stop", stop_cmd, stop_kwargs)
sampler_cmd_set.add_command("reset-session", reset_session_cmd, reset_session_kwargs)
sampler_cmd_set.add_command("delete", delete_cmd, delete_kwargs)
sampler_cmd_set.add_command("add-probe", add_probe_cmd, add_probe_kwargs)
sampler_cmd_set.add_command(
    "remove-probe", remove_probe_cmd, remove_probe_kwargs)
sampler_cmd_set.add_table_command("summary", summary_cmd, summary_kwargs)
sampler_cmd_set.add_command(
    "sampling-settings", sampling_settings_cmd, sampling_settings_kwargs)
sampler_cmd_set.add_command("force-sample", force_sample_cmd, force_sample_kwargs)

sampler_cmd_set.apply_to("probe_streamer", "streamer")

monitor_cmd_set = CmdSet(sampler_cmd_set)
monitor_cmd_set.add_command(
    "table-settings", table_settings_cmd, table_settings_kwargs)
monitor_cmd_set.add_command("plot-graph", plot_graph_cmd, plot_graph_kwargs)
monitor_cmd_set.add_table_command("print-history", print_history_cmd,
                                  print_history_kwargs)
monitor_cmd_set.add_command("clear-history", clear_history_cmd,
                            clear_history_kwargs)
monitor_cmd_set.add_command("export-json", export_json_cmd, export_json_kwargs)
monitor_cmd_set.add_command("merge-json", merge_json_cmd, merge_json_kwargs)
monitor_cmd_set.add_command("html-report", html_report_cmd, html_report_kwargs)
monitor_cmd_set.add_command("profile-probes", profile_probes_cmd, profile_probes_kwargs)
monitor_cmd_set.apply_to("probe_system_perfmeter", "system-perfmeter")
monitor_cmd_set.apply_to("probe_monitor", "monitor")

for cls in ["probe_monitor", "probe_system_perfmeter", "probe_streamer"]:
    new_info_command(cls, get_info)
    new_status_command(cls, get_status)
