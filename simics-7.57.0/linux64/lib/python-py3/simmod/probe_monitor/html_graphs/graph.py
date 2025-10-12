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


# Low-level function for producing javascript code, which interfaces Plotly,
# producing graphs in an HTML file.
#
# The general flow is:
# - create a PlotData object with the requested data
# - get hold of an 'HtmlPage' object where new html should be added
# - Call the produce_graph() with these two arguments
#   This will return an PlotHtml object which data generated for
#   this graph only.
# - When the PlotHtml should be added to the main html-page,
#   the finalize() method should be called.

plot_div_id = 0

def get_unique_div_id():
    global plot_div_id
    plot_div_id += 1
    return f"plt_div{plot_div_id}"

# Output data for the graph-generation.
# Contains both html and javascript code dedicated to this plot.
class PlotHtml:
    def __init__(self):
        self.html = ""
        self.js = ""
        self.resize_divs = []   # list of plotly-divs that should support resize
        self.owner_divs = {}    # {owner: [divs]}

    def get_new_div(self, owner):
        new_div = get_unique_div_id()
        self.resize_divs.append(new_div)
        if owner:
            self.owner_divs.setdefault(owner, [])
            self.owner_divs[owner].append(new_div)
        return new_div

    def add_html(self, text):
        self.html += text

    def add_js(self, text):
        self.js += text

# Input data for the graph-generation
class PlotData:
    __slots__ = ('owner', 'graph_type', 'x_data', 'y_data', 'title',
                 'x_title', 'y_title', 'legends', 'formatters',
                 'customdata', 'percent', 'arith_mean', 'stacked',
                 'y_range')
    def __init__(self,
                 # Required data
                 owner,
                 graph_type,
                 x_data,
                 y_data,
                 # Optional data
                 title = "Graph", # TODO: make required
                 x_title = "x",
                 y_title = "y",
                 legends = (),
                 customdata = (),
                 formatters = (),
                 percent = False,
                 arith_mean = False,
                 stacked = False,
                 y_range = None
                 ):
        self.owner = owner # obj/class/module as string or None
        self.graph_type = graph_type
        self.x_data = x_data
        self.y_data = y_data
        self.title = title
        self.x_title = x_title
        self.y_title = y_title
        self.formatters = formatters
        self.legends = legends
        self.customdata = customdata
        self.percent = percent
        self.arith_mean = arith_mean
        self.stacked = stacked
        self.y_range = y_range

        # TODO: validate
        if stacked and graph_type not in ["line", "bar"]:
            assert 0

        if not self.legends:
            self.legends = [f"graph-{g}" for g in range(len(self.x_data))]


# Generic class which produces the common parts of the HTML and
# java-script for one plot.
class PlotlyPlot:
    __slots__ = ('plot')

    def __init__(self, plot):
        self.plot = plot

    def _generate_shape(self, xmin, xmax, ymean):
        return f"""
                            {{
                                 type: 'line',
                                 x0: {xmin},
                                 y0: {ymean},
                                 x1: {xmax},
                                 y1: {ymean},
                                 line: {{
                                    dash: 'dash',
                                    width: 1
                                 }}
                             }}
        """

    def _generate_annotation(self, xmax, ymean, legend, fmt_value):
        return f"""
                            {{
                              x: {xmax},
                              y: {ymean},
                              ax: 0,
                              ay: -10,
                              xref: 'x',
                              yref: 'y',
                              text: '{legend}-mean:{fmt_value}',
                             }}
        """


    # Add possible shapes and annotations needed when
    # generating additional information arithmetic mean graph.
    def _generate_shapes_and_annotatons(self):
        shapes = []
        annotations = []
        if self.plot.arith_mean:
            p = self.plot
            for i in range(len(p.y_data)):
                ylen = len(p.y_data[i])
                xmin = min(p.x_data[i])
                xmax = max(p.x_data[i])
                ymean = sum(p.y_data[i])/ylen if ylen else 0
                if p.formatters:
                    formatter = p.formatters[i]
                    fmt_value = formatter(ymean)
                else:
                    fmt_value = str(ymean)
                legend = p.legends[i]
                shapes.append(self._generate_shape(
                    xmin=xmin,
                    xmax=xmax,
                    ymean=ymean))
                annotations.append(self._generate_annotation(
                    xmax=xmax,
                    ymean=ymean,
                    legend=legend,
                    fmt_value=fmt_value
                ))

        shapes_txt = ",".join(shapes)
        annotations_txt = ",".join(annotations)
        return (shapes_txt, annotations_txt)

    def _generate_newPlot(self, traces, div, title, x_title, y_title,
                          yaxis_attributes,
                          shapes, annotations):
        if self.plot.graph_type == "bar" and self.plot.stacked:
            barmode = "barmode: 'stack',\n"
        else:
            barmode = ""

        return f"""
        Plotly.newPlot(graphDiv='{div}',
                       data=traces,
                       layout={{
                           title: '{title}',
                           height: 600,
                           {barmode}
                           xaxis: {{
                              title: '{x_title}',
                              rangemode: "nonnegative",
                           }},
                           yaxis: {{
                              title: '{y_title}',
                              {yaxis_attributes}
                           }},
                           legend: {{
                              orientation: 'h',
                              y: -0.2
                           }},
                           shapes: [{shapes}],
                           annotations: [{annotations}]
                       }},
                       );\n"""

    def generate(self) -> PlotHtml:
        section = PlotHtml()
        div = section.get_new_div(self.plot.owner)
        section.add_html(f'<div id="{div}" class="panel"></div>\n')

        # Test that we have same amount of x and y data for each trace.

        if self.plot.customdata:
            assert len(self.plot.legends) == len(self.plot.customdata)
            # Call the subclass's specific method
            new_traces = [
                self.generate_trace(x, y, legend, customdata)
                for (i, (x, y, legend, customdata)) in enumerate(
                        zip(self.plot.x_data,
                            self.plot.y_data,
                            self.plot.legends,
                            self.plot.customdata))
            ]
        else:
            # Call the subclass's specific method
            new_traces = [
                self.generate_trace(x, y, legend)
                for (i, (x, y, legend)) in enumerate(
                        zip(self.plot.x_data,
                            self.plot.y_data,
                            self.plot.legends))
            ]

        traces_str = ",\n".join(new_traces)

        (shapes_txt, annotations_txt) = self._generate_shapes_and_annotatons()
        section.add_js("{\n")
        section.add_js(f"  const traces = [{traces_str}];")

        if self.plot.percent:
            # Add a % and show zero decimals
            yaxis_attrs = "tickformat: '.0%',\n"
        else:
            # Use SI (k,M,G) with 3 decimals
            yaxis_attrs = "tickformat: '0.3s',\n"

        if self.plot.y_range:
            yaxis_attrs += f"range: {self.plot.y_range},\n"

        section.add_js(self._generate_newPlot(
            traces=traces_str,
            div=div,
            title=self.plot.title,
            x_title=self.plot.x_title,
            y_title=self.plot.y_title,
            yaxis_attributes=yaxis_attrs,
            shapes=shapes_txt,
            annotations=annotations_txt
        ))
        section.add_js("}\n")
        return section


class LinePlot(PlotlyPlot):
    __slots__ = ()
    def generate_trace(self, x, y, legend, customdata=None):
        stacked = "  stackgroup : 'plot0',\n" if self.plot.stacked else ""
        # Construct the hovertemplate
        ht = f"'<b>{legend}</b>:"
        ht += "%{y:.2f}<br>"
        ht += "<b>%{xaxis.title.text}</b>:"
        ht += "%{x:.2f}"
        ht += "<extra>%{customdata}</extra>'\n" if customdata else "'\n"
        cd = f" customdata: {customdata},\n" if customdata else ""
        return ("{"
                f"  x: {x},\n"
                f"  y: {y},\n"
                f"  name:'{legend}',\n"
                f"{cd}"
                f"{stacked}"
                "  type: 'line',\n"
                "  mode: 'lines+markers',\n"
                "  hoverlabel: { font: { family:'Courier New'} },\n"
                f"  hovertemplate: {ht}\n"
                "}")

class BarPlot(PlotlyPlot):
    __slots__ = ()
    def generate_trace(self, x, y, legend, customdata=None):
        use_labels = any([isinstance(e, str) for e in x])
        x_value = "%{x}" if use_labels else "%{x:.2f}"
        # Construct the hovertemplate
        ht = f"'<b>{legend}</b>:"
        ht += "%{y:.2f}<br>"
        ht += "<b>%{xaxis.title.text}</b>:"
        ht += f"{x_value}"
        ht += "<extra>%{customdata}</extra>'\n" if customdata else "'\n"
        cd = f" customdata: {customdata},\n" if customdata else ""
        return ("{"
                f"  x: {x},\n"
                f"  y: {y},\n"
                f"  name:'{legend}',\n"
                f"{cd}"
                "  type: 'bar',\n"
                "  hoverlabel: { font: { family:'Courier New'} },\n"
                f"  hovertemplate: {ht}\n"
                "}")

class PiePlot(PlotlyPlot):
    __slots__ = ()
    def generate_trace(self, x, y, legend, customdata=None):
        # Construct the hovertemplate
        ht = "'<b>%{label}</b>:"
        ht += "%{value:.2f}<br>"
        ht += "<extra>%{customdata}</extra>'\n" if customdata else "'\n"
        cd = f" customdata: {customdata},\n" if customdata else ""

        return ("{"
                f"  labels: {x},\n"
                f"  values: {y},\n"
                f"  name:'{legend}',\n"
                f"{cd}"
                "  type: 'pie',\n"
                "  hoverlabel: { font: { family:'Courier New'} },\n"
                f"  hovertemplate: {ht}\n"
                "}")

# Each "graph_type" has an associated class checking the required
# parameters and producing the html and javascript code.
graph_class = {
    "line" : LinePlot,
    "bar" : BarPlot,
    "pie" : PiePlot
}


def produce_graph(plot : PlotData) -> PlotHtml:
    plotobj = graph_class[plot.graph_type](plot)
    return plotobj.generate()
