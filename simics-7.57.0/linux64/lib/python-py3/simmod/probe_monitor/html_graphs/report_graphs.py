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

import json
from functools import partial
import collections

import table

from . import graph
from . import prop
from . import common


# TODO:
#
# - Variable substitution such as $time, $obj
#   * $time could be used to switch between virtual or wallclock time.
#
# - Fix handling of histogram_probe data:
#   * Handle multiple_graphs
#   * star-expansion of probes.
#
# - Ideas:
#   * heatmap for final value of memory-profiler (x and y) is the matrix of all memory
#   * code in one color, data in another
#   * add "scatter" graphs.
#   * secondary Y-axis?
#   * logarithmic graphs
#
# - Annotations:
#   don't pass formatters to the underlying graphs.py object
#   create customdata with formatted x and y values according to probe-format
#
# - arith-mean - create a new trace instead with [xmin, ymin], [xmax, ymax]
#                We know the end result = (mean), we don't need graph.py to calculate it.
#
# - Fix diff-graphs, generating one or multiple graphs showing the difference
#                    between two sessions.
#
# Data shrink:
# - Reduce the number of decimals in output floating point probe-traces
# - Optimize the x/y data and remove y-data which are identical to the
#   previous data (including same annotations, (except x-value))
# - If we have an absurd amount of samples. Combine for example 10 samples
#   into a new sample point (calculated by the probe_type_class methods).
# - do javascript minification


# Benign-errors or warnings. Skip this graph definition due to missing
# probes, filters restricting it to be produced etc.
class GraphIgnoredException(Exception):
    pass

# Return type of generated graphs
class HtmlGraphs:
    __slots__ = ('html_page', 'title', 'tooltip', 'html_sections')
    def __init__(self, html_page, title, tooltip, html_sections):
        self.html_page = html_page
        self.title = title
        self.tooltip = tooltip
        self.html_sections = html_sections


# This holds all properties for one graph-specification and generates
# the associated plotly java-script code for the data in the probes
# associated with the graph. (The low-level plotly code is generated
# by the graph.py module.)
class GraphSpec:
    __slots__ = (
        # property values from graph-specification
        'p_title', 'p_x_title', 'p_y_title',
        'p_type', 'p_x_probe', 'p_y_probes',
        'p_histogram_probe',
        'p_histogram_data_set',
        'p_description', 'p_stacked',
        'p_arith_mean', 'p_percent', 'p_multi_graph',
        'p_y_range', 'p_min_data_series', 'p_max_data_series',
        'p_min_graphs', 'p_max_graphs', 'p_cutoff_percent',
        'p_html_page',

        # Other members
        'property_map',
    )

    def __init__(self, key_value_def):
        self.property_map = collections.OrderedDict()

        self.p_description = self.map_prop("description", prop.DescriptionProp)
        self.p_title = self.map_prop("title", prop.TitleProp)
        self.p_x_title = self.map_prop("x_axis_title", prop.XAxisTitleProp)
        self.p_y_title = self.map_prop("y_axis_title", prop.YAxisTitleProp)
        self.p_type  = self.map_prop("type", prop.GraphTypeProp)

        self.p_x_probe  = self.map_prop("x_probe", prop.XProbeProp)
        self.p_y_probes  = self.map_prop("y_probes", prop.YProbesProp)
        self.p_histogram_probe = self.map_prop("histogram_probe",
                                               prop.HistogramProbeProp)
        self.p_histogram_data_set = self.map_prop("histogram_data_set",
                                                  prop.HistogramDataSetProp)

        self.p_stacked = self.map_prop("stacked", prop.StackedProp)
        self.p_arith_mean = self.map_prop("arith_mean", prop.ArithMeanProp)
        self.p_percent = self.map_prop("percent", prop.PercentProp)
        self.p_multi_graph = self.map_prop("multi_graph", prop.MultiGraphProp)
        self.p_y_range = self.map_prop("y_range", prop.YRangeProp)
        self.p_min_data_series = self.map_prop("min_data_series",
                                               prop.MinDataSeriesProp)
        self.p_max_data_series = self.map_prop("max_data_series",
                                               prop.MaxDataSeriesProp)
        self.p_min_graphs = self.map_prop("min_graphs", prop.MinGraphsProp)
        self.p_max_graphs = self.map_prop("max_graphs", prop.MaxGraphsProp)
        self.p_cutoff_percent = self.map_prop("cutoff_percent", prop.CutoffProp)
        self.p_html_page = self.map_prop("html_page", prop.HtmlPageProp)

        self.assign_properties(key_value_def)

    # Remember which property-key is assigned which property object.
    # Simply return the object
    def map_prop(self, key, prop_cls):
        prop_obj = prop_cls(key)
        self.property_map[key] = prop_obj
        return prop_obj

    # Returns a list of PropDocumentation objects, one for each
    # property supported.
    def document(self):
        lst = []
        for (k, v) in self.property_map.items():
            doc = v.document()
            lst.append(doc)
        return lst

    # Set the value for the object matching the 'key' property
    def assign_properties(self, key_value_def):
        for key, value in key_value_def.items():
            if key in self.property_map:
                # Call the corresponding object and set the value
                self.property_map[key].set(value)
            else:
                raise common.GraphSpecException(f'illegal property: "{key}"')

    def validate_properties(self):
        if not self.p_title.assigned:
            raise common.GraphSpecException(
                'No "title" defined in graph-specification')

        if not ((self.p_y_probes.assigned and self.p_x_probe.assigned)
                or self.p_histogram_probe.assigned):
            raise common.GraphSpecException(
                'Neither x/y probes or histogram_probe defined')

    # Get hold of a property if assigned, otherwise take the default value
    def prop_get(self, prop, default):
        return prop.get() if prop.assigned else default

    def legend(self, rprobe):
        obj = rprobe.owner
        display_name = rprobe.display_name
        if not rprobe.global_probe:
            return obj + ":" + display_name
        return display_name

    def legends(self, session, probe_names):
        rprobes = [session.probes[p] for p in probe_names]
        owners = set([p.owner for p in rprobes])
        display_names = set([p.display_name for p in rprobes])

        if len(owners) == 1:
            return [p.display_name for p in rprobes]

        if len(display_names) == 1:
            return [p.owner for p in rprobes]

        # Both objects and display-name differs, return both
        return [self.legend(p) for p in rprobes]

    def get_probe_data(self, expanded_probe, session):
        samples = session.probes[expanded_probe.probe_name].sample_history
        fmts = [""] * len(samples)
        empty_array = fmts[:]
        for ann_probe_name in expanded_probe.annotation_probes:
            rprobe = session.probes[ann_probe_name]
            if rprobe.global_probe:
                legend = rprobe.display_name
            else:
                legend = f"{rprobe.owner}:{rprobe.display_name}"
            annotations = rprobe.sample_history
            if len(annotations) == 0:
                title = self.p_title.get()
                print(f"In '{title}', skipping annotation {ann_probe_name},"
                      " no samples recorded.")
                continue
            if len(annotations) != len(samples):
                title = self.p_title.get()
                print(f"In '{title}', skipping annotation {ann_probe_name},"
                      f" contains {len(annotations)} samples, which does not"
                      f" match {len(samples)} in {expanded_probe.probe_name}.")
                continue

            for (i, a) in enumerate(annotations):
                fmts[i] += fmt_annotation(rprobe, legend, a)
        if fmts == empty_array:
            fmts = []           # No annotations added
        return samples, fmts

    # For a given histogram's final key/values, reduce the keys according
    # to the cutoff_percent property. Putting keys below the threshold
    # in a single miss-bucket.
    def cutoff_histogram(self, final_value):
        total_values = sum([abs(v) for (_, v) in final_value])
        cutoff = total_values * (self.p_cutoff_percent.get() / 100.0)
        traces = collections.OrderedDict(
            {key: [] for (key, value) in final_value
             if abs(value) >= cutoff
             })

        missed_keys = {key for (key, value) in final_value
                       if abs(value) < cutoff}
        num_cutoff = len(missed_keys)

        if num_cutoff > 0:
            miss_bucket = f"Accumulated cutoff ({num_cutoff} series)"
            traces.setdefault(miss_bucket, [])
        else:
            miss_bucket = None
        return traces, miss_bucket

    # Reduce the precision of the float values to save space in the
    # loaded javascript files. This likely only reduce the size of the
    # HTML while the data representation is still as large.
    def optimize_xy_data(self, org_x_data, org_y_data):
        def shrink(v):
            if isinstance(v, float):
                v = float(f"{v:.5g}")
                if int(v) == v:
                    # fisketur[same-value-assign] turn a float to an int
                    v = int(v)
            return v

        assert len(org_y_data) == len(org_x_data)
        new_xl = []
        new_yl = []
        for i in range(len(org_y_data)):
            assert len(org_x_data[i]) == len(org_y_data[i])
            new_x = []
            new_y = []
            for (x, y) in zip(org_x_data[i], org_y_data[i]):
                x1 = shrink(x)
                y1 = shrink(y)
                new_y.append(y1)
                new_x.append(x1)

            new_xl.append(new_x)
            new_yl.append(new_y)
        return new_xl, new_yl


    # split up the expanded_probes in multiple lists, for each
    # wildcard object that has been used.
    def split_wildcard_traces(self):
        wildcard_objs = set(
            [ep.wildcard_obj for ep in self.p_y_probes.expanded_probes
             if ep.wildcard_obj != None])

        filtered_traces = []
        for wo in sorted(list(wildcard_objs)):
            new_list = []
            for ep in self.p_y_probes.expanded_probes:
                if ep.wildcard_obj == None or ep.wildcard_obj == wo:
                    new_list.append(ep)

            filtered_traces.append((wo, new_list))
        return filtered_traces

    def ignore_graphs(self, traces_per_plot):
        title = self.p_title.get()
        nc = len(traces_per_plot)
        min_graphs = self.p_min_graphs.get()
        if self.p_min_graphs.assigned and nc < min_graphs:
            print(f"Skipping '{title}', 'min_graphs' property {min_graphs}"
                  f" is larger then {nc} graphs.")
            return True

        max_graphs = self.p_max_graphs.get()
        if self.p_max_graphs.assigned and nc > max_graphs:
            print(f"Skipping '{title}', 'max_graphs' property {max_graphs}"
                  f" is less than {nc} graphs about to be produced")
            return True
        return False

    def ignore_graph_due_to_data_limits(self):
        title = self.p_title.get()
        num_series = len(self.p_y_probes.expanded_probes)
        min_series = self.p_min_data_series.get()
        if self.p_min_data_series.assigned and num_series < min_series:
            print(f"Skipping '{title}', 'min_data_series' property {min_series}"
                  f" is larger than {num_series} series.")
            return True

        max_series = self.p_max_data_series.get()
        if self.p_max_data_series.assigned and num_series > max_series:
            print(f"Skipping '{title}', 'max_data_series' property {max_series}"
                  f" is less than {num_series} series.")
            return True
        return False


    def produce_histogram_graph_over_time(self, session, hprobe):
        if not self.p_x_probe.assigned:
            raise common.GraphSpecException(
                'histogram-probe with samples, requires an "x_probe"')

        (traces, miss_bucket) = self.cutoff_histogram(hprobe.final_value)

        all_keys = set(traces.keys())
        for elements in hprobe.raw_sample_history:
            used_keys = {key for key,_ in elements}
            for (key, value) in elements:
                if key in traces:
                    traces[key].append(value)
                else:
                    traces[miss_bucket].append(value)

            # Append zero-values to all keys not specified
            for unused_key in all_keys - used_keys:
                traces[unused_key].append(0)

        # TODO: this is copied from x/y handling.
        (obj, probe_kind) = self.p_x_probe.get().split(":")
        all_xprobe_names = session.get_object_probes_from_wildcard(
            obj, probe_kind)
        org_x_data = [session.probes[x].sample_history
                      for x in all_xprobe_names]

        x_data = org_x_data
        y_data = []
        legends = []
        for (key, samples) in traces.items():
            y_data.append(samples)
            legends.append(key)

        if len(x_data) != len(y_data):
            x_data = x_data * len(y_data)

        default_x_title = session.probes[all_xprobe_names[0]].display_name
        default_y_title = "Frequency"
        y_title = self.prop_get(self.p_y_title, default_y_title)
        x_title = self.prop_get(self.p_x_title, default_x_title)
        return (x_data, y_data, legends, x_title, y_title)

    def produce_histogram_graph_for_final_value(self, session, hprobe):
        x_data = []
        y_data = []
        (traces, miss_bucket) = self.cutoff_histogram(hprobe.final_value)
        miss_count = 0
        for (k, v) in hprobe.final_value:
            if k in traces:
                x_data.append(k)
                y_data.append(v)
            else:
                miss_count += v
        if miss_count:
            x_data.append(miss_bucket)
            y_data.append(miss_count)

        x_data = [x_data]
        y_data = [y_data]
        legends = ["bar0"]
        y_title = self.prop_get(self.p_y_title, "Frequency")
        x_title = self.prop_get(self.p_x_title, "Label")
        return (x_data, y_data, legends, x_title, y_title)


    def produce_histogram_graph(self, session):
        # Expand to multiple-probes if we have *:<probe-kind>
        org_probe = self.p_histogram_probe.get()
        hprobes = self.p_histogram_probe.wildcard_expand(session)
        if not hprobes:
            raise GraphIgnoredException(
                f"no histogram-probes matching {org_probe}")

        plots = []
        for p in hprobes:
            rprobe = session.probes[p]
            if self.p_histogram_data_set.get() == "samples":
                (x_data, y_data, legends, x_title,
                 y_title) = self.produce_histogram_graph_over_time(session, rprobe)
            else:
                (x_data, y_data, legends, x_title,
                 y_title) = self.produce_histogram_graph_for_final_value(
                     session, rprobe)

            formatters = [None] * len(x_data)
            title = self.p_title.get()
            wildcard_obj=None
            if len(hprobes) > 1:
                (wildcard_obj, probe_kind) = p.split(":")
                title += f" ({wildcard_obj})"

            p = graph.PlotData(
                owner=wildcard_obj,
                # The traces-data [x,y,customdata] for each graph in the plot
                x_data=x_data,
                y_data=y_data,
                legends=legends, # The names for each trace
                graph_type=self.p_type.get(),
                title=html_esc(title),
                x_title=html_esc(x_title),
                y_title=html_esc(y_title),
                formatters=formatters,
                arith_mean=self.p_arith_mean.get(),
                percent=self.p_percent.get(),
                stacked=self.p_stacked.get(),
                y_range=self.p_y_range.get()
            )
            plots.append(p)
        return plots

    def produce_xy_graph(self, session):
        # x/y - based graph.

        # Expand all y-probes with wildcards, so we
        # have a list of actual probes to look at in
        # the .expanded_probes member of the property
        self.p_y_probes.wildcard_expand(session)

        if self.p_y_probes.expanded_probes == []:
            title = self.p_title.get()
            print(f"Skipping '{title}', no probes matching graph specification")
            return []

        if self.ignore_graph_due_to_data_limits():
            return []

        (obj, probe_kind) = self.p_x_probe.get().split(":")
        all_xprobe_names = session.get_object_probes_from_wildcard(
            obj, probe_kind)
        org_x_data = [session.probes[x].sample_history
                      for x in all_xprobe_names]

        # TODO: this is not true if we for example use
        # *:cpu.time.virtual-session and use multi_graph.
        if len(org_x_data) != 1:
            print("*** Cannot handle multiple x-values")
            return []

        if not self.p_multi_graph.get():
            # All traces in one plot
            traces_per_plot = [(None, self.p_y_probes.expanded_probes)]
        else:
            traces_per_plot = self.split_wildcard_traces()
            if self.ignore_graphs(traces_per_plot):
                return []

        plots = []
        for (wildcard_obj, trace) in traces_per_plot:
            all_yprobe_names = [ep.probe_name for ep in trace]
            y_data = []
            x_data = org_x_data
            ann_data = []
            for probe_name in trace:
                data, annotations = self.get_probe_data(probe_name, session)
                y_data.append(data)
                ann_data.append(annotations)

            if len(x_data) != len(y_data):
                x_data = x_data * len(y_data)

            title = self.p_title.get()
            if wildcard_obj:
                title += f" ({wildcard_obj})"

            # Apply plot attributes from graph data or from probes
            y0 = all_yprobe_names[0]
            x0 = all_xprobe_names[0]
            default_y_title = session.probes[y0].display_name
            default_x_title = session.probes[x0].display_name
            y_title = self.prop_get(self.p_y_title, default_y_title)
            x_title = self.prop_get(self.p_x_title, default_x_title)
            legends = self.legends(session, all_yprobe_names)

            # Construct helper functions, one for each y-probe which can
            # represent a calculated value in a probe formatted way (used
            # for mean value calculation).
            formatters = [partial(format_probe_value, session.probes[y])
                          for y in all_yprobe_names]

            x_data, y_data = self.optimize_xy_data(x_data, y_data)
            plot = graph.PlotData(
                owner=wildcard_obj,
                # The traces-data [x,y,customdata] for each graph in the plot
                x_data=x_data,
                y_data=y_data,
                customdata=ann_data,
                legends=legends, # The names for each trace

                graph_type=self.p_type.get(),
                title=html_esc(title),
                x_title=html_esc(x_title),
                y_title=html_esc(y_title),
                formatters=formatters,
                arith_mean=self.p_arith_mean.get(),
                percent=self.p_percent.get(),
                stacked=self.p_stacked.get(),
                y_range=self.p_y_range.get()
            )
            plots.append(plot)
        return plots

    def produce_graphs(self, session):
        if self.p_histogram_probe.assigned:
            return self.produce_histogram_graph(session)
        else:
            return self.produce_xy_graph(session)

    def produce_diff_graphs(self, session1, session2):
        # TODO: this currently just creates two graphs, one for each
        # session. With attributes, both sessions should sometimes
        # be put in the same graph instead.
        # Also, we should consider which time we want on the x-axis
        #
        p1 = self.produce_graphs(session1)
        p2 = self.produce_graphs(session2)
        return p1 + p2


# Construct a formatted table representation of the data in 'cell' format.
# Always returns a string, formatted according to the probe-properties
def format_probe_value(probe, cell_value):
    float_decimals = None
    # TODO: pass this instead of createing a new for each point
    prop_obj = table.cell_props.CellProps(probe.table_properties())
    cell = table.cell.data_to_cell(cell_value, float_decimals, prop_obj)
    val_str = "\n".join([cell.line(i) for i in range(cell.num_lines())])
    return val_str

def html_esc(s):
    if isinstance(s, str):
        # Escape string for html output
        s = s.replace("&", "&amp;")
        s = s.replace("<", "&lt;")
        s = s.replace(">", "&gt;")
        s = s.replace("\n", "<br>")
    return s

def fmt_annotation(rprobe, legend, value):
    name = f"<b>{legend}</b>:"
    if isinstance(value, str):
        s = html_esc(value)
        if "<br>" in s:  # Put multi-line strings on its own line
            s = f"<br>{s}"
    else:
        s = format_probe_value(rprobe, value)
    return name + s + "<br>"

def document_graph_specification():
    return GraphSpec({}).document()

# General data-flow:
#
#    GraphSpec -> [PlotData*] -> [PlotHtml*] -> HtmlGraphs
#         |  \-------------------^              ^
#          \------------------------------------/
#
# 1. A json file specifies what graphs that could be generated. Each
#    graph is represented as GraphSpec object with the user-selected
#    properties. All graph which have required probes, will be part of
#    the output.
#
# 2. To produce the graph, all probe data is extracted and replaced by
#    normal list of data and put in a PlotData object.  Each PlotData
#    is then converted to a PlotHtml object, which contains the html,
#    javascript and some additional meta-data.
#
# 3. A HtmlGraphs object then contain all PlotHtml objects and
#    additional data in a HtmlGraphs object which in the end will
#    produce an accordion item with the plots under this accordion.
#
# As shown by the picture above, the GraphSpec properties can
# influence the layout of many various stages of the plot generation.
#
def produce_session_graphs(session, graph_specification):

    # Iterate over all available graph specifications, which each
    # possibly should be generate one or several plots. Plots which
    # don't have the don't have any recorded probe data in the session
    # will be discarded.
    sections = []
    if not "graphs" in graph_specification:
        raise common.GraphSpecException(
            '*** Missing "graphs" dict element')

    for g in graph_specification["graphs"]:
        title = g.get("title", None)
        try:
            gs = GraphSpec(g)
        except common.GraphSpecException as msg:
            raise common.GraphSpecException(
                f'*** Illegal probe format in "{title}": {msg}')

        gs.validate_properties()

        try:
            plots = gs.produce_graphs(session)
        except GraphIgnoredException as msg:
            print(f"Graph-ignored: {msg}")
            continue

        html_sections = [graph.produce_graph(p) for p in plots]
        if not html_sections:   # Don't add empty-sections
            continue

        desc_prop = gs.p_description
        tooltip = desc_prop.get() if desc_prop.assigned else ""
        html_page = gs.p_html_page.get()
        sections.append(HtmlGraphs(html_page, title, tooltip, html_sections))

    return sections


def produce_diff_graphs(main_page, session1, session2, graph_specification):

    # Iterate over all available graph specifications, which each
    # possibly should be generate one or several plots. Plots which
    # don't have the don't have any recorded probe data in the session
    # will be discarded.
    sections = []
    for g in graph_specification["graphs"]:
        title = g.get("title", None)
        try:
            gs = GraphSpec(g)
        except common.GraphSpecException as msg:
            print(f'*** Illegal probe format in "{title}": {msg}')
            continue

        gs.validate_properties()

        try:
            plots = gs.produce_diff_graphs(session1, session2)
        except GraphIgnoredException as msg:
            print(f"Graph-ignored: {msg}")
            continue

        html_sections = []
        for p in plots:
            sub_html = graph.produce_graph(main_page, p)
            html_sections.append(sub_html)

        sections.append((title, html_sections))

    return sections # For test purposes
