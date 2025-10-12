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
from . import cell
from . import cell_props

import itertools

class HeaderElement:
    __slots__ = (
        # Header properties
        'p_name',
        'p_desc',
        'p_first_column',
        'p_last_column',

        'property_map',
        'col_spans',            # list of column objects header spans

        'cell_props',
    )

    def __init__(self, key_value_def):
        # Header properties (implemented through property objects)
        self.property_map = {}

        self.p_name = self.map_prop(Extra_Header_Key_Name,
                                    prop.StrProp(Extra_Header_Key_Name))
        self.p_desc = self.map_prop(Extra_Header_Key_Description,
                                    prop.StrProp(Extra_Header_Key_Description))
        self.p_first_column = self.map_prop(Extra_Header_Key_First_Column,
                                            prop.StrProp(Extra_Header_Key_First_Column))
        self.p_last_column = self.map_prop(Extra_Header_Key_Last_Column,
                                           prop.StrProp(Extra_Header_Key_Last_Column))

        prop.check_key_value(key_value_def)

        # Assign the properties for the column
        for (key, value) in key_value_def:
            if not self.assign_properties(key, value):
                raise TableException(
                    f"unknown extra-header key: {prop.property_name(key)}")

        self.cell_props = cell_props.CellProps([
            (Column_Key_Alignment, "center")
        ])

    def __repr__(self):
        return self.p_name.get()

    # Return the column names which this header spans over
    def column_range(self):
        return (self.p_first_column.get(),
                self.p_last_column.get())

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


class ExtraHeaderRow:
    __slots__ = (
        'elements',
        'ranges'
    )
    def __init__(self, value):
        self.elements = []
        self.ranges = []        # Column idx ranges
        for key_value_list in value:
            new = HeaderElement(key_value_list)
            self.elements.append(new)

    # Return all first/last names of the columns
    def column_ranges(self):
        return [h.column_range() for h in self.elements]

    # Set/get the column objects which spans [first, last]
    def set_column_spans(self, columns):
        for i, h in enumerate(self.elements):
            h.col_spans = columns[i]

    def get_column_spans(self):
        return [h.col_spans for h in self.elements]

    # Sort the elements vector in the same order as the covering columns
    def sort(self, columns):
        self.elements.sort(key=lambda x: columns.index(x.col_spans[0]))

    # Create an additional header, typically to fill uncovered ranges
    def add_header(self, key_value_list):
        new = HeaderElement(key_value_list)
        self.elements.append(new)

    def to_cell_list(self, widths):
        cells = [cell.StrCell(e.p_name.get(), e.cell_props)
                 for e in self.elements]

        # Make sure the header fits in specified width
        for c, w in zip(cells, widths):
            c.narrow_width(w, force_max_width=True)
        return cells

    # Returns a list of tuples: [(name, desc), (name, desc)]
    def descriptions(self):
        l = []
        for e in self.elements:
            desc = e.p_desc.get()
            if desc:
                l.append((e.p_name.get(), desc))
        return l

    # Validate the properties when finalizeing the table
    def validate_props(self, column_names):
        prop_name = prop.property_name(Table_Key_Extra_Headers)
        def all_disjoint(x):
            return all([p0.isdisjoint(p1)
                       for p0, p1 in itertools.combinations(x, 2)])

        def num_matches(value, lst):
            return sum([1 for x in lst if x == value])

        def check_col_ref(ref):
            if ref not in column_names:
                raise TableException(
                    f"{prop_name}: Invalid column ref in header: {ref}")

            if num_matches(ref, column_names) > 1:
                raise TableException(
                    f"{prop_name}: Multiple columns matches in header: {ref}")

        range_sets = []
        ranges = self.column_ranges()

        if ranges == [(None, None)]:
            return     # Only one element that should span all columns

        for (first, last) in ranges:
            check_col_ref(first)
            check_col_ref(last)

            first_idx = column_names.index(first)
            last_idx = column_names.index(last)
            if last_idx < first_idx:
                raise TableException(
                    f"{prop_name}: Header column last:{last} is before first:{first}")

            spans = set(range(first_idx, last_idx + 1)) # inclusive
            range_sets.append(spans)

        if not all_disjoint(range_sets):
            raise TableException(f"{prop_name}: Header columns overlap")

class ExtraHeadersProp(prop.ListProp):
    __slots__ = ('_table')
    def __init__(self, table):
        super().__init__(Table_Key_Extra_Headers, [])
        self._table = table      # Table object the headers belongs to

    def set(self, value):
        # Validate and set the list first
        super().set(value)

        prop.check_key_value(value)

        self._table.headers = []
        for (key, row_data) in value:
            if not isinstance(key, int):
                raise TableException(
                    f"{prop.property_name(Table_Key_Extra_Headers)} expected"
                    f" Extra_Header_Key_Row, got: {key}")

            if key != Extra_Header_Key_Row:
                raise TableException(
                    f"{prop.property_name(Table_Key_Extra_Headers)} expected"
                    f" Extra_Header_Key_Row, got: {prop.property_name(key)}")
            if not isinstance(row_data, list):
                raise TableException(f"Header element not a list: {row}")

            new = ExtraHeaderRow(row_data)
            self._table.headers.append(new)
