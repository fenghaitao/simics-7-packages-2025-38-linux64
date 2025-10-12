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


import simics
import collections
import conf
import probes

def make_chart(name: str, data: list, layout={}, config={}):
    simics.VT_update_session_key(f"plot:{name}", dict(
        data=data, layout=layout, config=config))


class LimitQueue:
    '''An optional size of the limit queue will, when used, remove
    the first entry of the queue when the limit is reached.'''

    def __init__(self, size=None):
        self.size = size
        self.queue = collections.deque()

    def add(self, value):
        self.queue.append(value)
        if self.size and len(self.queue) > self.size:
            self.queue.popleft()

    def get_list(self):
        return list(self.queue)

class Plot:
    def __init__(self, presentation, chart_name, x, ys, annotations,
                 old_rows=[], window_size=None):
        self.chart_name = chart_name
        self.presentation = presentation
        self.window_size = window_size

        self.x = x              # sprobe for x-values
        self.chart_x = LimitQueue(self.window_size)

        self.ys = ys            # sprobes for y-values
        self.chart_y = {}       # y-values indexed by sprobe (in ys)
        for y in self.ys:
            self.chart_y[y] = LimitQueue(self.window_size)

        self.anns = annotations # sprobes for annotations (for hover-over)
        self.chart_a = {}       # annotation indexed by sprobes
        for a in self.anns:
            self.chart_a[a] = LimitQueue(self.window_size)

        # Populate plot data with possible already generated rows
        for row in old_rows:
            self.add_table_data(row)

        self.produce_plot([])

    def contains_sprobe(self, sp):
        'Return True if a plot depends on a sprobe'
        return (sp == self.x
                or sp in self.ys
                or sp in self.anns)

    def add_table_data(self, row_data):
        def fmt_data(sp, value):
            name = f"<b>{self.legend(sp)}</b>:"
            if isinstance(value, str):
                # Escape string for html output
                s = value
                s = s.replace("&", "&amp;")
                s = s.replace("<", "&lt;")
                s = s.replace(">", "&gt;")
                s = s.replace("\n", "<br>")
                if "<br>" in s:  # Put multi-line strings on its own line
                    s = f"<br>{s}"
            else:
                # Fractions are already converted to a float
                s = sp.probe_proxy.format_value(value, converted=True)
            return name + s + "<br>"

        def scale_data(sp, value):
            if sp.probe_proxy.prop.percent and isinstance(value, (int, float)):
                return value * 100.0
            return value

        if row_data == []:
            return

        # Extract the X and Y values that should be used, from table row
        for i, sp in enumerate(self.presentation.select_sprobes(
                include_hidden=True, include_no_sampling=False)):
            if sp == self.x:
                self.chart_x.add(scale_data(sp, row_data[i]))
            if sp in self.ys:
                self.chart_y[sp].add(scale_data(sp, row_data[i]))
            if sp in self.anns:
                self.chart_a[sp].add(fmt_data(sp, row_data[i]))

    def legend(self, sprobe):
        obj = sprobe.probe_proxy.prop.owner_obj
        display_name = sprobe.probe_proxy.prop.display_name
        if not probes.is_singleton(obj):
            return obj.name + ":" + display_name
        return display_name

    def all_annotations(self):
        if not self.anns:
            return []
        l = [self.chart_a[a].get_list() for a in self.anns]
        queues = len(l)
        elems = len(l[0])
        nl = []
        for i in range(elems):
            s = ""
            for q in range(queues):
                s += l[q][i]
            nl.append(s)
        return nl

    def y_title(self):
        if len(self.ys) == 1:
            return self.legend(self.ys[0])
        return ""

    def produce_plot(self, row_data):
        self.add_table_data(row_data)

        datasets = []
        for y in self.ys:
            datasets.append(self.plotly_trace(y))

        make_chart(
            self.chart_name,
            datasets,
            layout=self.plotly_layout(),
            config=self.plotly_config())

    # Methods that can be overridden or extended by the subclasses
    def plotly_trace(self, y_sprobe):
        annotations = self.all_annotations()
        extra = '<extra>' + ('%{customdata}' if annotations else '') + '</extra>'
        hovertemplate = (f'<b>{self.legend(y_sprobe)}</b>: ' +
                         '%{y:.2f}<br>' +
                         '<b>%{xaxis.title.text}</b>: %{x:.2f}' +
                         f'{extra}')

        return dict(x = self.chart_x.get_list(),
                    y = self.chart_y[y_sprobe].get_list(),
                    name = self.legend(y_sprobe),
                    customdata = annotations,
                    hoverlabel=dict(font=dict(family="Courier New")),
                    hovertemplate= hovertemplate)

    def plotly_layout(self):
        return dict(title = self.chart_name, autosize=True,
                    xaxis = dict(title=self.legend(self.x)),
                    yaxis = dict(title=self.y_title()),
                    )

    def plotly_config(self):
        return dict(responsive=True,
                    editable=True
                    )


class ScatterPlot(Plot):
    def plotly_trace(self, y_sprobe):
        d = super().plotly_trace(y_sprobe)
        d["type"] = "scatter"
        return d

class StackedScatterPlot(ScatterPlot):
    def plotly_trace(self, y_sprobe):
        d = super().plotly_trace(y_sprobe)
        d["stackgroup"] = "some_group"  # Put all charts on-top of each other
        return d
