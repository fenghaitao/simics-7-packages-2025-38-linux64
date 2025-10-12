# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from .table_enums import *  # Table constatants
from .common import (TableException,)

from . import prop
from . import common_table
from . import stream_column
from . import border

import conf

from cli import (terminal_height,)

class StreamTable(common_table.CommonTable):
    __slots__ = (
        'p_columns',
        'p_header_repeat',

        'last_header',
        'multi_lines_since_header',
    )
    def __init__(self, key_value_def, border_style=None):
        super().__init__()
        self.p_columns = self.map_prop(Table_Key_Columns,
                                       stream_column.StreamColumnsProp(self))
        self.p_header_repeat = self.map_prop(
            Table_Key_Stream_Header_Repeat,
            prop.IntProp(Table_Key_Stream_Header_Repeat, default=None))

        if border_style:
            self.border_style = border_style
        else:
            self.border_style = conf.prefs.cli_table_border_style
        self.last_header = 0
        self.multi_lines_since_header = False
        # Assign properties
        for i, (key, value) in enumerate(key_value_def):
            if not self.assign_properties(key, value):
                raise TableException(
                    f"unknown stream-column key: {prop.property_name(key)}")

        self.header_cells = self._header_to_cells()
        self.finalize()
        self.finalize_extra_headers()


    def add_row(self, row_data):
        '''Return a string (which can be a multiline-string with \n separators)
        containing the corresponding table output for the given row_data.
        A header might be added before the actual table row.'''

        # Write the data as a table line
        if len(row_data) != len(self.columns):
            raise TableException(f"add_row() got data for {len(row_data)}"
                                 f" columns expected {len(self.columns)}")
        widths = [c.column_width() for c in self.columns]
        draw_style = border.border_style[self.border_style]

        if self.p_header_repeat.get() != None:
            max_h = self.p_header_repeat.get()
        else:
            max_h = terminal_height()

        s = ""
        lines_since_header = (self.lines_printed - self.last_header)
        if (self.lines_printed == 0 or lines_since_header >= max_h):
            s += self._produce_headers(draw_style, widths)
            self.multi_lines_since_header = False
            self.last_header = self.lines_printed

        cell_data = self._cellify([row_data])[0] # Just one row

        # Make sure the cell data fits in specified width
        for c, w in zip(cell_data, widths):
            c.narrow_width(w, force_max_width=True)

        any_multi_lines = max([c.num_lines() for c in cell_data]) > 1
        lines_since_header = (self.lines_printed - self.last_header)
        if any_multi_lines or self.multi_lines_since_header:
            if lines_since_header:
                s += draw_style.row_separator_heavy_light_light(widths, widths)
            self.multi_lines_since_header = True

        s += self._data_row(draw_style, cell_data, widths)
        lines = len(s.split("\n")) - 1  # Ignore empty-string after last \n
        self.lines_printed += lines
        return s
