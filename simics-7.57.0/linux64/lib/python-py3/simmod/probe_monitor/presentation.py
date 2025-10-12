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


import abc
import collections
import csv

import probes
import conf

from table import *

from . import common
from . import sprobes
from . import plot


def sort_sprobes(sprobe_list):
    sorted_sprobe_list = []
    sprobes_obj_dict = collections.OrderedDict()
    # {obj: [sprobe, sprobe, ...]}
    for sp in sprobe_list:
        obj = sp.probe_proxy.prop.owner_obj
        if probes.is_singleton(obj):  # a "global" probe
            sorted_sprobe_list.append(sp)  # the global probes first
        else:
            sprobes_obj_dict.setdefault(obj, [])
            sprobes_obj_dict[obj].append(sp)

    for obj in sorted(sprobes_obj_dict):
        # the object probes second
        sorted_sprobe_list.extend(sprobes_obj_dict[obj])

    return sorted_sprobe_list


def get_delta_sprobes(sprobe_list):
    return [sp for sp in sprobe_list if sp.mode == "delta"]


# Return the summary table as a string
def create_summary_table(max_lines, sprobe_list, probe_name_substr, raw,
                         *table_args):
    class ValueType:
        fmt_str = "-"
        raw_str = "-"

    class ProbeData:
        def __init__(self, sprobe):
            self.sprobe = sprobe
            self.mode = {"current": ValueType(),
                         "session": ValueType()}

    def substr_filter(sprobe_list, substr):
        if not substr:
            return sprobe_list      # Nothing filtered out
        res = []
        for sp in sprobe_list:
            name = sp.probe_proxy.prop.kind
            if substr in name:
                res.append(sp)
        return res

    def current_sprobes(column_sprobe_list):
        return [sp for sp in column_sprobe_list if sp.mode == sprobes.CURRENT_MODE]

    def session_sprobes(column_sprobe_list):
        return [sp for sp in column_sprobe_list if sp.mode != sprobes.CURRENT_MODE]

    def histogram_sprobes(sprobe_list):
        return [sp for sp in sprobe_list if sp.probe_proxy.prop.type == "histogram"]

    def merge_sprobes(current_sprobe_list, session_sprobe_list, max_lines,
                      max_current_widths, max_session_widths):
        used = {}

        def set_probes_data(sprobe, max_widths, m):
            (max_keys, max_val) = max_widths
            id = sprobe.probe_proxy.cli_id
            used.setdefault(id, ProbeData(sprobe))
            val = sprobe.actual_value()
            float_decimals = get_table_arg_value(
                "float-decimals", table_args)
            cf = probes.CellFormatter(max_lines=max_lines,
                                      key_col_width=max_keys,
                                      val_col_width=max_val,
                                      float_decimals=float_decimals)
            used[id].mode[m].fmt_str = sprobe.probe_proxy.format_value(val, cf)
            if raw:
                used[id].mode[m].raw_str = sprobe.probe_proxy.raw_value(val, cf)

        for sp in current_sprobe_list:
            set_probes_data(sp, max_current_widths, "current")
        for sp in session_sprobe_list:
            set_probes_data(sp, max_session_widths, "session")

        return used.values()

    def get_histogram_max_widths(lines, sprobe_list):
        max_key = 0
        max_val = 0
        for sp in histogram_sprobes(sprobe_list):
            val = sp.actual_value()
            (mk, mv) = sp.probe_proxy.type_class.histogram_max_widths(val, lines)
            max_key = max([max_key, mk])
            max_val = max([max_val, mv])
        return (max_key, max_val)

    tcols = [[(Column_Key_Name, "Display Name")],
             [(Column_Key_Name, "Probe-kind")],
             [(Column_Key_Name, "Object"),
                 (Column_Key_Hide_Homogeneous, "")],
             [(Column_Key_Name, "Session Formatted Value"),
                 (Column_Key_Int_Radix, 10),
                 (Column_Key_Hide_Homogeneous, "-"),
                 (Column_Key_Alignment, "right")],
             [(Column_Key_Name, "Session Raw Value"),
                 (Column_Key_Int_Radix, 10),
                 (Column_Key_Hide_Homogeneous, "-"),
                 (Column_Key_Alignment, "right")],
             [(Column_Key_Name, "Current Formatted Value"),
                 (Column_Key_Int_Radix, 10),
                 (Column_Key_Hide_Homogeneous, "-"),
                 (Column_Key_Alignment, "right")],
             [(Column_Key_Name, "Current Raw Value"),
                 (Column_Key_Int_Radix, 10),
                 (Column_Key_Hide_Homogeneous, "-"),
                 (Column_Key_Alignment, "right")],
             ]

    tprops = [(Table_Key_Columns, tcols)]
    tdata = []
    match_sprobe_list = substr_filter(sprobe_list, probe_name_substr)
    current_sprobe_list = current_sprobes(match_sprobe_list)
    session_sprobe_list = session_sprobes(match_sprobe_list)

    current_max_widths = get_histogram_max_widths(max_lines, current_sprobe_list)
    session_max_widths = get_histogram_max_widths(max_lines, session_sprobe_list)

    probe_datas = merge_sprobes(
        current_sprobe_list, session_sprobe_list,
        max_lines, current_max_widths, session_max_widths)

    for pd in probe_datas:
        sp = pd.sprobe
        so = sp.probe_proxy.prop.owner_obj
        source = so.name

        tdata.append(
            [sp.probe_proxy.prop.display_name,
                sp.probe_proxy.prop.kind,
                source,
                pd.mode["session"].fmt_str,
                pd.mode["session"].raw_str,
                pd.mode["current"].fmt_str,
                pd.mode["current"].raw_str])

    return get(tprops, tdata, *table_args)


def format_probe_data(sprobe_list, raw_data, cell_formatter=None):
    data = []
    for (sp, raw) in zip(sprobe_list, raw_data):
        data.append(sp.probe_proxy.table_cell_value(raw, cell_formatter))
    return data


def format_probe_history_data(sprobe_list, history_idx, cell_formatter):
    data = []
    for sp in sprobe_list:
        cell_formatter.total_width = sp.probe_proxy.prop.width
        val = sp.probe_proxy.table_cell_value(
            sp.get_history_index(history_idx), cell_formatter)
        data.append(val)
    return data


class BasePresentation(abc.ABC):
    __slots__ = ()

    @abc.abstractmethod
    def update_probes(self, sprobe_list):
        pass

    @abc.abstractmethod
    def process_sample(self):
        pass

    @abc.abstractmethod
    def create_summary_table(self, probe_name_substr, raw, max, *table_args):
        return ""

    @abc.abstractmethod
    def sampler_stopped(self):
        pass

    @abc.abstractmethod
    def simulation_stopped(self):
        pass

    @abc.abstractmethod
    def terminate(self):
        pass


class StreamPresentation(BasePresentation):
    __slots__ = ("sampler", "sprobe_list", "delta_sprobe_list",
                 "csv_output_file", "writer",
                 "metadata_enabled", "needs_header")

    def __init__(self, sampler, csv_output_file_name, metadata_enabled):
        super().__init__()
        self.sampler = sampler
        self.csv_output_file = open(csv_output_file_name, "w",
                                    encoding="utf-8",
                                    newline="")
        self.writer = csv.writer(self.csv_output_file,
                                 delimiter=",", quotechar=None, doublequote=False,
                                 escapechar="\\", quoting=csv.QUOTE_NONE)
        self.metadata_enabled = metadata_enabled

        self.sprobe_list = []
        self.delta_sprobe_list = []
        self.needs_header = True
        self.update_probes([])

    def add_header_rows(self):
        def add_metadata_row(sprobe_list, writer):
            def build_metadata(index, sprobe):
                def single_quote_and_escape(desc):
                    return "\'" + desc.replace("\\", "\\\\").replace("'", r"\'") + "\'"

                def double_quote(val):
                    return "\"" + val + "\""

                prop = sprobe.probe_proxy.prop
                probe_obj = prop.owner_obj.name if not probes.is_singleton(prop.owner_obj) else ""
                probe_name = prop.kind
                type = prop.type
                # Set unit metadata to "s" (instead of "hh:mm:ss.d") in the case of a time format
                # To be fixed directly in the probe properties ?
                unit = "s" if prop.time_fmt else prop.unit
                mode = sprobe.mode
                # categories is an array whose values are separated by semi-colons
                categories = ';'.join(prop.categories)
                desc = prop.desc

                meta_names = ["probe_obj", "probe_name", "type", "mode", "unit", "categories", "desc"]
                meta_values = [probe_obj, probe_name, type, mode, unit, categories, desc]

                metadata = [f"#{index}"]
                for name, value in zip(meta_names, meta_values):
                    if value:
                        metadata.append(f"{name}={single_quote_and_escape(value)}")
                return double_quote(" ".join(metadata))

            metadata = []
            for index, sp in enumerate(sprobe_list):
                metadata.append(build_metadata(index, sp))
            writer.writerow(metadata)


        def add_name_row(sprobe_list, writer):
            def build_name(sprobe):
                prop = sprobe.probe_proxy.prop
                return f"{prop.display_name}" if prop.display_name else f"{prop.kind}"

            names = []
            for sp in sprobe_list:
                names.append(build_name(sp))
            writer.writerow(names)


        if self.metadata_enabled:
            add_metadata_row(self.sprobe_list, self.writer)
        add_name_row(self.sprobe_list, self.writer)

    def add_data_row(self):
        raw_data = self.sampler.get_raw_data(self.sprobe_list, self.delta_sprobe_list)
        data = format_probe_data(self.sprobe_list, raw_data)
        self.writer.writerow(data)

    def update_probes(self, sprobe_list):
        self.sprobe_list = sprobe_list
        self.delta_sprobe_list = get_delta_sprobes(sprobe_list)
        self.needs_header = True

    def process_sample(self):
        if self.needs_header:
            self.add_header_rows()
            self.needs_header = False
        self.add_data_row()

    def create_summary_table(self, probe_name_substr, raw, max, *table_args):
        return create_summary_table(10 if max == None else max, self.sprobe_list,
                                    probe_name_substr, raw, *table_args)

    def sampler_stopped(self):
        self.csv_output_file.flush()

    def simulation_stopped(self):
        self.csv_output_file.flush()

    def terminate(self):
        self.csv_output_file.close()


class BaseTablePresentation(BasePresentation):
    __slots__ = ("table_properties",)

    def __init__(self):
        self.table_properties = []

    @abc.abstractmethod
    def get_table_properties(self):
        return self.table_properties

    @abc.abstractmethod
    def get_data_history(self, include_hidden):
        assert 0

    @abc.abstractmethod
    def set_repeat_height(self, repeat_height):
        pass

    @abc.abstractmethod
    def create_cell_formatter(self, histogram_rows):
        return None

    @abc.abstractmethod
    def add_plot(self, graph_name, graph_type, from_now, window_size, x, ys,
                 annotations):
        pass


class TablePresentation(BaseTablePresentation):
    __slots__ = ("sampler", "sorted_sprobe_list", "log_win", "print_to_console",
                 "summary", "output_file", "repeat_height", "plots",
                 "print_disabled", "cell_formatter", "plot_formatter",
                 "stream_table", "num_samples")

    def __init__(self, sampler,
                 log_win, print_to_console, summary, output_file_name):
        super().__init__()
        self.sampler = sampler  # The sampler using us
        self.log_win = log_win
        self.print_to_console = print_to_console
        self.summary = summary
        self.output_file = open(output_file_name, "w",
                                encoding="utf-8") if output_file_name else None

        self.repeat_height = 0
        histogram_rows = 5  # Default value
        self.create_cell_formatter(histogram_rows)
        self.create_plot_formatter()
        self.num_samples = 0  # Number of samples taken and data in history
        self.plots = []

        self.sorted_sprobe_list = []
        self.update_probes([])

        # a flag to disable any printing
        # used by t130_probes performance tests to measure probe performance
        # without any printing
        self.print_disabled = False

    def set_repeat_height(self, repeat_height):
        self.repeat_height = repeat_height
        self.build_stream_table()

    def create_cell_formatter(self, histogram_rows):
        self.cell_formatter = probes.CellFormatter(max_lines=histogram_rows)

    def create_plot_formatter(self):
        self.plot_formatter = probes.CellFormatter(
            max_lines=5,
            ignore_column_widths=True)

    def select_sprobes(self, include_hidden, include_no_sampling):
        def discard(sp):
            return ((sp.hidden and not include_hidden)
                    or (sp.no_sampling and not include_no_sampling))

        return [sp for sp in self.sorted_sprobe_list if not discard(sp)]

    def build_column_properties(self, sprobe):
        probe_proxy = sprobe.probe_proxy

        props = probe_proxy.table_properties()
        d = dict(props)

        unit = probe_proxy.prop.unit if probe_proxy.prop.unit != None else ""

        if probe_proxy.prop.time_fmt:
            if sprobe.mode == "delta":
                del d[Column_Key_Time_Format]
                d[Column_Key_Width] = 9
                d[Column_Key_Metric_Prefix] = "s"
                unit = "s"
            else:
                d[Column_Key_Float_Decimals] = 0
                d[Column_Key_Width] = 10
                unit = "hh:mm:ss"
                # Avoid breaking on ":"
                d[Column_Key_Word_Delimiters] = " -_."

        name = probe_proxy.prop.display_name
        if unit:  # If Unit is specified, add it to the header
            name += f" ({unit})"

        if sprobe.mode != "delta":
            name = f"{sprobe.mode.capitalize()} {name}"
            # Make sure "mode" does not wrap
            d[Column_Key_Width] = max(
                d.get(Column_Key_Width, 0), len(sprobe.mode))
        d[Column_Key_Name] = name

        props = list(d.items())
        props.append((Column_Key_Unique_Id, sprobe.unique_id))
        return props

    def build_table_properties(self, include_hidden=False):
        col_props = []
        sprobes_obj_dict = collections.OrderedDict()
        # {obj: [first_sprobe, last_sprobe]}
        for sp in self.select_sprobes(include_hidden=include_hidden,
                                      include_no_sampling=False):
            col_props.append(self.build_column_properties(sp))
            obj = sp.probe_proxy.prop.owner_obj
            if not probes.is_singleton(obj):
                sprobes_obj_dict.setdefault(obj, [sp, sp])
                sprobes_obj_dict[obj][1] = sp
        props = [(Table_Key_Columns, col_props)]

        extra_headers = []
        for (obj, [first_probe, last_probe]) in sprobes_obj_dict.items():
            extra_headers.append([
                (Extra_Header_Key_Name, obj.name),
                (Extra_Header_Key_First_Column, first_probe.unique_id),
                (Extra_Header_Key_Last_Column, last_probe.unique_id)])
        if extra_headers:
            props.insert(0,
                         (Table_Key_Extra_Headers, [
                             (Extra_Header_Key_Row, extra_headers)]))

        if self.repeat_height:
            props.append((Table_Key_Stream_Header_Repeat, self.repeat_height))

        return common.listify(props)

    def build_stream_table(self):
        self.table_properties = self.build_table_properties()

        args = {}
        if self.log_win and not common.running_in_simics_client():
            # Textcons does not support UTF-8 characters
            args["border_style"] = "ascii"

        self.stream_table = StreamTable(self.table_properties, **args)

    def add_plot(self, graph_name, graph_type, from_now, window_size, x, ys,
                 annotations):

        old_rows = [] if from_now else self.get_plot_history()

        d = {"line": plot.ScatterPlot,
             "line-stacked": plot.StackedScatterPlot}

        if not graph_type in d:
            raise CliError(f"Unknown graph_type={graph_type}")

        plt = d[graph_type](self, graph_name, x, ys, annotations, old_rows,
                            window_size)
        self.plots.append(plt)

    def produce_plots(self, sprobe_list, raw_data):
        if not self.plots:
            return
        data = format_probe_data(sprobe_list, raw_data, self.plot_formatter)
        for p in self.plots:
            p.produce_plot(data)

    def print(self, lines):
        if self.print_disabled:
            return

        if self.print_to_console:
            if self.log_win:
                self.log_win.log(lines)
            else:
                print(lines, end="")

        if self.output_file:
            self.output_file.write(lines)

    def add_row_to_table(self, data):
        return self.stream_table.add_row(data)

    def print_sample(self, data):
        will_print = self.print_to_console or self.output_file
        if will_print:
            table_row_str = self.add_row_to_table(data)
            self.print(table_row_str)

    def get_table_properties(self):
        return super().get_table_properties()

    def update_probes(self, sprobe_list):
        prev_sprobe_set = set(self.sorted_sprobe_list)

        self.sorted_sprobe_list = sort_sprobes(sprobe_list)

        self.build_stream_table()

        deleted_sprobe_set = prev_sprobe_set - set(self.sorted_sprobe_list)
        added_sprobe_set = set(self.sorted_sprobe_list) - prev_sprobe_set

        for sp in added_sprobe_set:
            sp.add_missing_samples_to_history(self.num_samples)

        # Remove any plots which depends on a deleted probe
        for sp in deleted_sprobe_set:
            self.plots = [p for p in self.plots if not p.contains_sprobe(sp)]

    def process_sample(self):
        sampled_sprobe_list = self.select_sprobes(include_hidden=True,
                                                  include_no_sampling=False)
        sampled_delta_sprobe_list = get_delta_sprobes(sampled_sprobe_list)
        raw_data = self.sampler.get_raw_data(sampled_sprobe_list, sampled_delta_sprobe_list)
        for (sp, d) in zip(sampled_sprobe_list, raw_data):
            sp.add_to_history(d)

        self.produce_plots(sampled_sprobe_list, raw_data)

        # Only show the probes which are not hidden
        shown_sprobe_list = self.select_sprobes(include_hidden=False,
                                                include_no_sampling=False)
        if shown_sprobe_list:
            data = format_probe_history_data(shown_sprobe_list, self.num_samples,
                                             self.cell_formatter)
            self.print_sample(data)

        self.num_samples += 1

    def get_history(self, formatter, include_hidden):
        sprobe_list = self.select_sprobes(include_hidden=include_hidden,
                                          include_no_sampling=False)
        return [format_probe_history_data(sprobe_list, i, formatter)
                for i in range(self.num_samples)]

    def get_data_history(self, include_hidden=False):
        return self.get_history(self.cell_formatter, include_hidden)

    def get_plot_history(self):
        return self.get_history(self.plot_formatter, include_hidden=True)

    def clear_history(self):
        for sp in self.sorted_sprobe_list:
            sp.clear_history()
        self.num_samples = 0

    def create_summary_table(self, probe_name_substr, raw, max, *table_args):
        return create_summary_table(
            self.cell_formatter.max_lines if max == None else max,
            self.select_sprobes(include_hidden=True,
                                    include_no_sampling=True),
            probe_name_substr, raw, *table_args)

    def sampler_stopped(self):
        if self.output_file:
            self.output_file.flush()

    def simulation_stopped(self):
        if self.summary:
            tbl_args = default_table_args({"max": 0})
            tbl = self.create_summary_table(
                None, False, self.cell_formatter.max_lines, *tbl_args)
            self.print(tbl + "\n")

        if self.output_file:
            self.output_file.flush()

    def terminate(self):
        if self.output_file:
            self.output_file.close()
