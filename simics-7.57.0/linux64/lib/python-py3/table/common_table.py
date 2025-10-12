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


from .table_enums import *  # Table constants
from .common import (TableException,)

from . import prop
from . import extra_header
from . import cell

import simics                   # need conf_object_t

# Base class for Table and StreamTable
class CommonTable:
    __slots__ = (
        # Properties
        'p_name',               # Name of table
        'p_desc',               # Table description
        'p_headers',            # Additional headers (not column-headers)

        'headers',              # List HeaderRow
        'columns',              # List of Column
        'border_style',         # Decoration type
        'float_decimals',       # Default decimals
        'header_cells',

        'lines_printed',        # Number of lines of the table printed

        'property_map',
    )

    def __init__(self):
        self.property_map = {}

        # Table properties
        self.p_name = self.map_prop(Table_Key_Name, prop.StrProp(Table_Key_Name))
        self.p_desc = self.map_prop(Table_Key_Description,
                                    prop.StrProp(Table_Key_Description))
        self.p_headers = self.map_prop(Table_Key_Extra_Headers,
                                       extra_header.ExtraHeadersProp(self))
        self.float_decimals = None
        self.columns = []       # List of Column objects
        self.headers = []       # List of HeaderRow objects
        self.lines_printed = 0

    # Remember which property-key is assigned which property object.
    # Simply return the object
    def map_prop(self, key, prop_obj):
        self.property_map[key] = prop_obj
        return prop_obj

    # Set the value for the object matching the 'key' property
    def assign_properties(self, key, value):
        if key in self.property_map:
            # Call the corresponding object and set the value
            self.property_map[key].set(value)
            return True
        return False

    def _create_missing_header(self, header_row, first_idx, last_idx):
        first_name = self.columns[first_idx].unique_name()
        last_name = self.columns[last_idx].unique_name()
        header_row.add_header([
            (Extra_Header_Key_Name, ""),
            (Extra_Header_Key_First_Column, first_name),
            (Extra_Header_Key_Last_Column, last_name)
        ])

    def _validate_headers(self):
        column_names = [c.unique_name() for c in self.columns]
        for row in self.headers:
            row.validate_props(column_names)

    # Called when all properties have been set
    def finalize(self):
        self._validate_headers()

    def _fix_extra_header_row(self, row, column_names):
        ranges = row.column_ranges()
        if ranges == [(None, None)]: # Header spans all columns
            row.set_column_spans([self.columns])
            return

        range_sets = []
        for (first, last) in ranges:
            first_idx = column_names.index(first)
            last_idx = column_names.index(last)

            spans = set(range(first_idx, last_idx + 1)) # inclusive
            range_sets.append(spans)

        covering = set()
        for s in range_sets:
            covering.update(s)

        uncovered_range = []
        for c in range(len(self.columns)):
            if c not in covering:
                uncovered_range.append(c)
            elif uncovered_range:
                first_idx = uncovered_range[0]
                last_idx = uncovered_range[-1]
                self._create_missing_header(row, first_idx, last_idx)
                range_sets.append(set(uncovered_range))
                uncovered_range = []
        if uncovered_range:
            first_idx = uncovered_range[0]
            last_idx = uncovered_range[-1]
            self._create_missing_header(row, first_idx, last_idx)
            range_sets.append(set(uncovered_range))

        # Set the column objects the range spans over
        column_spans = []
        for r in range_sets:
            column_spans.append([self.columns[i] for i in r])
        row.set_column_spans(column_spans)
        # Make sure the row elements are sorted in the same order as the columns
        row.sort(self.columns)

    # Before any table output, but *after* any additional columns might have
    # been created: Create empty row elements for columns not covered.
    def finalize_extra_headers(self):
        column_names = [c.unique_name() for c in self.columns]
        for row in self.headers:
            self._fix_extra_header_row(row, column_names)

    # Convert a column's row 'data' to the Cell class which formats the
    # data accordingly and can return the formatted data as text.
    def _create_cell(self, col, data):
        if self.float_decimals != None:
            decimals = self.float_decimals  # Overridden with cmd-line args
        else:
            decimals = col.p_float_decimals.get() # Col specific (or default)

        return cell.data_to_cell(data, decimals, col)

    # Return a new matrix where all cells have been formatted to strings,
    # using Cell objects.
    def _cellify(self, table):
        nt = []
        for r_num, row in enumerate(table):
            nr = row[:]
            nt.append(nr)
            for c_num, data in enumerate(row):
                col = self.columns[c_num]
                try:
                    cell = self._create_cell(col, data)
                except TableException as ex:
                    raise TableException(
                        str(ex) + f" (at row:{r_num} column:{c_num})")
                nr[c_num] = cell
        return nt

    def _header_to_cells(self):
        col_names = [c.p_name.get() if c.p_name.get() else ""
                     for c in self.columns]
        # If columns exists, but no name set, do not print the headings
        if col_names == [""] * len(col_names):
            return []

        # Use "center" alignment if the columns has no default
        # alignment set.
        str_headings = [
            [cell.StrCell(col_names[i], c,
                          "center" if not c.p_alignment.get() else None)
             for i, c in enumerate(self.columns)]]
        return str_headings

    def _calc_extra_header_widths(self, header_row, draw_style):
        spans = header_row.get_column_spans()
        w = []
        for e in spans:
            num_columns = len(e)
            sep_length = len(draw_style.heavy.column_separator)
            e_w = (sum([c.column_width() for c in e]) +
                   (num_columns - 1) * sep_length)
            w.append(e_w)
        return w

    def _produce_headers(self, draw_style, widths):
        first = self.lines_printed == 0
        # Extra Headers
        s = ""
        prev_w = []
        up_widths = widths if not first else []
        for row in self.headers:
            w = self._calc_extra_header_widths(row, draw_style)

            if row == self.headers[0]:
                s += draw_style.row_separator_heavy_from_light(up_widths, w)
            else:
                s += draw_style.row_separator_heavy(prev_w, w)

            cells = row.to_cell_list(w)
            s += self._header_row(draw_style, cells, w)
            prev_w = w

        # Normal column headers
        if s or first:
            s += draw_style.row_separator_heavy(prev_w, widths)
        else:
            s += draw_style.row_separator_heavy_from_light(widths, widths)

        # Make sure the header fits in specified width
        for c, w in zip(self.header_cells[0], widths):
            c.narrow_width(w, force_max_width=True)

        s += self._header_row(draw_style, self.header_cells[0], widths)
        s += draw_style.row_separator_heavy_to_light(widths, widths)
        return s

    @staticmethod
    def _row(cells, widths, emit_func):
        s = ""
        max_lines = max([c.num_lines() for c in cells])
        for l in range(max_lines):
            row_data = [c.aligned_line(l, w)
                        for c, w in zip(cells, widths)]
            s += emit_func(row_data)
        return s

    def _header_row(self, draw_style, header_cells, widths):
        return self._row(header_cells, widths, draw_style.data_row_heavy)

    def _data_row(self, draw_style, data_cells, widths):
        return self._row(data_cells, widths, draw_style.data_row_heavy_light)

    def _data_rows(self, draw_style, cell_rows, widths):
        def max_lines(row):
            return max([c.num_lines() for c in row])

        any_multi_lines = any([max_lines(r) > 1 for r in cell_rows])
        s = ""
        last = len(cell_rows) - 1
        for i, row in enumerate(cell_rows):
            s += self._row(row, widths, draw_style.data_row_heavy_light)
            if any_multi_lines and not i == last:
                s += draw_style.row_separator_heavy_light_light(widths, widths)
        return s
