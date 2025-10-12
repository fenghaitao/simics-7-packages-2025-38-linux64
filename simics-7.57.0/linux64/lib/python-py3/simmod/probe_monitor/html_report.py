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

import os
import subprocess
import errno

from . import html
from . import probe_session
from . import html_graphs

# Note, this is just to get hold of probes.probe_type_classes
# We need this functionality to be available outside of Simics too
import probes

# TODO:
# - Comparison of two runs, generate nice diff report...
# - Zoom in graphs and update all histograms?
# - Make plot-graph command to dump HTML in a similar way
# - Push HTML to simics-client
# - Add wrapper script for running simics and generating this report easily

# Done:
# - Add load charts (global and per cpu)
# - Table with the benchmark final results
# - Check that the probes really exists, otherwise don't generate the graph
# - Put all java-scripts in one <script> section
# - Table with Simics, host and target CPU information
# - Skip some graphs if there is only one CPU
# - Accordions?
# - Add annotations
# - Benchmarking, merge 2 json files into 1.
# - Possibly links from this page to Flamegraph
# - Annotate exec-modes with JIT and INT service-routine histogram
# - Make it possible to add a probe but only save the end-result
# - Should we have cell charts?

class HtmlReport:
    __slots__ = ('html_dir', 'simics_sessions', 'graph_specification')
    def __init__(self, html_dir, simics_sessions, graph_specification):
        self.html_dir = html_dir
        self.simics_sessions = simics_sessions
        self.graph_specification = graph_specification

    @staticmethod
    def fmt_annotation(legend, value):
        name = f"<b>{legend}</b>:"
        if isinstance(value, str):
            s = html.html_esc(value)
            if "<br>" in s:  # Put multi-line strings on its own line
                s = f"<br>{s}"
        else:
            s = str(value)
        return name + s + "<br>"

    # TODO: remove used in old graphs only
    def get_cls_probes(self, probe_name):
        y_probes = []
        for p in self.cls_probes:
            (cls, pn) = p.split(":")
            if pn == probe_name:
                y_probes.append(p)
        return y_probes

    # Present overview of some important figures from a mix of host,
    # target, simics and probes figures.
    def generate_summary_table(self, html_page):
        assert len(self.simics_sessions) == 1
        table = html.HtmlKeyValueTable(html_page)
        d = self.simics_sessions[0].summary_data()
        for (key, value) in d.items():
            table.add_row(key, value)
        table.finalize()

    def generate_host_table(self, html_page):
        assert len(self.simics_sessions) == 1
        table = html.HtmlKeyValueTable(html_page)
        d = self.simics_sessions[0].host_data()
        for (key, value) in d.items():
            table.add_row(key, value)
        table.finalize()

    def generate_simics_table(self, html_page):
        assert len(self.simics_sessions) == 1
        table = html.HtmlKeyValueTable(html_page)
        d = self.simics_sessions[0].simics_data()
        for (key, value) in d.items():
            table.add_row(key, value)
        table.finalize()

    def generate_target_table(self, html_page):
        assert len(self.simics_sessions) == 1
        table = html.HtmlKeyValueTable(html_page)
        d = dict(self.simics_sessions[0].target_data())
        for (key, value) in d.items():
            table.add_row(key, value)
        table.finalize()

    def generate_global_probe_table(self, html_page):
        assert len(self.simics_sessions) == 1
        ss = self.simics_sessions[0]
        ss_probes = ss.probes_data()
        # Remove histogram probes, better present these as graphs
        global_probes = ss.global_probe_names(type_exclude=["histogram"])
        table = html.HtmlGlobalProbeTable(html_page)
        for pn in global_probes:
            p = ss_probes[pn]
            table.add_global_probe_result(
                p.kind, p.display_name, p.final_value_cell,
                p.final_value_fmt)
        table.finalize()

    @staticmethod
    def _sort_tuples(lst):
        values = [(a, b, c) for (a, b, c) in lst
                  if not isinstance(b, str)]
        strings = [(a, b, c) for (a, b, c) in lst
                   if isinstance(b, str)]
        values.sort(reverse=True, key=lambda x: x[1])
        strings.sort(reverse=True, key=lambda x: x[1])
        return values + strings

    def generate_obj_probe_table(self, html_page, obj_probes):
        ss = self.simics_sessions[0]
        ss_probes = ss.probes_data()

        # Fetch all probes using the object probes
        long_obj_probes = [ss.get_object_probes(p) for p in obj_probes]
        table = html.HtmlObjectProbeTable(html_page)
        for pn in long_obj_probes:
            p = ss_probes[pn[0]]
            probe_kind = p.kind
            display_name = p.display_name
            vect = [(html.html_esc(ss_probes[p].owner),
                     ss_probes[p].final_value_cell,
                     ss_probes[p].final_value_fmt)
                    for p in pn]
            vect = self._sort_tuples(vect)
            table.add_object_probe_results(probe_kind, display_name, vect)
        table.finalize()

    # Returns True if any of the probes are not present
    def probes_missing(self, probe_names):
        return not set(probe_names).issubset(self.no_prefix_probe_names)

    # From a set of probes on the y-axis, produce graph-data using
    # the same same probe for the x-axis.
    # The legend for each probe is taken from the object owning the data
    def create_obj_traces(self, y_probes, x_probe):
        common_x = x_probe.sample_history
        x_data = []
        y_data = []
        legends = []
        for p in y_probes:
            obj = p.owner
            x_data.append(common_x)
            y_data.append(p.sample_history)
            legends.append(obj)
        return (x_data, y_data, legends)

    # Similar to above but here the y-probes are global
    # and we take the legends from the probes' display_name
    def create_global_traces(self, y_probes, x_probe):
        common_x = x_probe.sample_history
        x_data = []
        y_data = []
        legends = []
        for p in y_probes:
            x_data.append(common_x)
            y_data.append(p.sample_history)
            legends.append(p.display_name)
        return (x_data, y_data, legends)


    @staticmethod
    def run_flamegraph(flatten_lines, thread_group):
        def try_start_program(args, **kwords):
            try:
                return subprocess.Popen(args, **kwords)
            except OSError as e:
                print(f'Failed running flamegraphs.pl: OSError: {e}')
                return None

        p = try_start_program(
            ["flamegraph.pl",
             "--title", "Flame Graph",
             "--subtitle", f"Thread-group: {thread_group}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE)
        if p == None:
            return
        blob = bytearray("\n".join(flatten_lines), encoding="utf-8")
        (out, err) = p.communicate(blob)
        return out

    def generate_flamegraphs(self, html_page):
        # Get generated height of the canvas from the svg contents
        def svg_height(svg):
            lines = svg.decode('utf-8').split('\n')
            for l in lines:
                if l.startswith('<svg '):
                    i = l.find("height=")
                    l = l[i:].split('"')
                    height = l[1]
                    return height

        assert len(self.simics_sessions) == 1
        flamegraphs = self.simics_sessions[0].flamegraph_data()

        if not flamegraphs:
            return

        flamegraph_html = (
            '<a href="https://www.brendangregg.com/flamegraphs.html">'
            'Flamegraph</a>')

        for (k, v) in flamegraphs.items():
            if not k.startswith("thread-group-"):
                continue
            thread_group = k[13:]
            stacks = v["folded_stacks"]
            svg = self.run_flamegraph(stacks, thread_group)
            if svg:
                # Create a stand-alone file for the .svg
                # Embedding it in the HTML causes namespace collisions
                fn = f"flamegraph-{thread_group}.svg"
                full_fn = os.path.join(self.html_dir, fn)
                with open(full_fn, "w+b") as f:
                    f.write(svg)

                height = svg_height(svg)
                t = thread_group if thread_group != "None" else ""
                thread_info = {
                    "": "All Simics threads are included",
                    "execution": (
                        "Only profiling Simics' <i>execution</i> threads")
                }[t]

                tooltip = (
                    f"The {flamegraph_html} shows the performance profile"
                    f" of the run. {thread_info}. Read the link for more details"
                    " on how to understand the flamegraph representation."
                )

                html_page.add_accordion(f"Flamegraph {t}", tooltip)
                html_page.add_svg(fn, height)


    def generate_tables(self, html_page):
        html_page.add_accordion(
            "Summary",
            "Summary of the benchmark run. Shows some selected"
            " numbers of the measurement, target and host information")
        self.generate_summary_table(html_page)

        html_page.add_accordion(
            "Host Information",
            "Various information on the host where the benchmark was"
            " executed.")
        self.generate_host_table(html_page)

        html_page.add_accordion(
            "Simics Information",
            "Details on the Simics version used for the benchmark."
            " This also includes threading modes and thread information.")
        self.generate_simics_table(html_page)

        html_page.add_accordion(
            "Target Information",
            "Information on the target system being simulated in the benchmark."
        )
        self.generate_target_table(html_page)

        html_page.add_separator()

        html_page.add_accordion(
            "Probe Information (global)",
            "Global (singleton) probes that has been collected in the benchmark."
            " Histogram-probes are excluded."
        )
        self.generate_global_probe_table(html_page)

        assert len(self.simics_sessions) == 1
        ss = self.simics_sessions[0]

        mod_probes = ss.module_probe_names(type_exclude=["histogram"])
        if mod_probes:
            html_page.add_accordion(
                "Probe Information (module-globals)",
                "Some probes on objects might be global to the module and not"
                " specific to the object itself. This section lists those"
                " derived probes and their final-values."
            )
            self.generate_obj_probe_table(html_page, mod_probes)

        cls_probes = ss.class_probe_names(type_exclude=["histogram"])
        if cls_probes:
            html_page.add_accordion(
                "Probe Information (classes)",
                "Derived probe values by taking the probes from the same class"
                " and aggregating over them. Histogram-probes are excluded."
            )
            self.generate_obj_probe_table(html_page, cls_probes)

        obj_probes = ss.object_probe_names(type_exclude=["histogram"])
        if obj_probes:
            html_page.add_accordion(
                "Probe Information (object)",
                "Object probe values used in the benchmark."
                " Histogram-probes are excluded."
            )
            self.generate_obj_probe_table(html_page, obj_probes)

    # All graphs for this session, certain graphs might be discarded
    # if there are probes missing
    def generate_graphs(self, main_page, one_page):
        known_pages = {"index.html": main_page}

        session = self.simics_sessions[0]
        sections = html_graphs.produce_session_graphs(
            session, self.graph_specification)

        # Sections is a list of HtmlGraphs
        for go in sections:
            title = go.title.replace('\n', ' - ')
            if one_page:
                current_page = main_page
            else:
                page = go.html_page
                if page not in known_pages:
                    # Create a new html-subpage
                    new_page = html.HtmlPage(self.html_dir, page)
                    known_pages.setdefault(page, new_page)
                current_page = known_pages[page]

            current_page.start_section(title, go.tooltip)
            for s in go.html_sections:
                current_page.add_owner_divs(s.owner_divs)
                current_page.add_section(s.html, s.js, s.resize_divs)
            current_page.end_section()

        # Return the created HtmlPage objects
        return known_pages.values()

    # Single page with all data from this session
    def report(self, one_page):
        main_page = html.HtmlPage(self.html_dir, "index.html", main_page=True)
        main_page.add_heading("<h3>Performance Report</h3>")
        self.generate_tables(main_page)
        main_page.add_separator()
        self.generate_flamegraphs(main_page)
        main_page.add_separator()
        pages = self.generate_graphs(main_page, one_page)
        sub_links = ", ".join(
            [p.html_reference()
             for p in sorted(pages, key=lambda obj: obj.page_name)
             if not p.main_page])
        if sub_links:
            main_page.add_heading(f"Sub-pages: {sub_links}")

        # Generate the main-page and any sub-pages
        for p in pages:
            if not p.main_page:
                p.add_heading(
                    f'<h4>Performance Report <i>{p.link_name}</i> sub-page</h4>'
                    f'{main_page.html_reference("back to main page")}<br/><br/>')
            p.finalize()

def produce(probes_dict, html_dir, graph_specification, one_page):
    ss = probe_session.SimicsSession(probes_dict)
    r = HtmlReport(html_dir, [ss], graph_specification)
    return r.report(one_page)
