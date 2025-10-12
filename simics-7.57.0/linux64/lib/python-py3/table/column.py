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
from . import common_column

class Column(common_column.CommonColumn):
    __slots__ = (
        # Column properties
        'p_sort_descending',
        'p_footer_sum',
        'p_footer_mean',
        'p_percent_col',
        'p_hide_homogeneous',
        'p_acc_percent_col',

        # Others
        'generated',            # automatically generated
        'sum',                  # calculated sum (all)
        'shown_sum',            # calculated sum (shown)
        'mean',                 # calculated mean (all)
        'shown_mean',           # calculated mean (shown)
        'column_data',          # row data for column
        '_used_for_sorting'     # this column sorted upon
    )

    def __init__(self, key_value_def, generated=False):
        super().__init__(generated)

        # Additional properties
        self.p_sort_descending = self.map_prop(Column_Key_Sort_Descending,
                                               prop.BoolProp(
                                                   Column_Key_Sort_Descending))
        self.p_footer_sum = self.map_prop(Column_Key_Footer_Sum,
                                          prop.BoolProp(Column_Key_Footer_Sum))
        self.p_footer_mean = self.map_prop(Column_Key_Footer_Mean,
                                           prop.BoolProp(Column_Key_Footer_Mean))
        self.p_percent_col = self.map_prop(
            Column_Key_Generate_Percent_Column,
            prop.ListProp(Column_Key_Generate_Percent_Column))
        self.p_hide_homogeneous = self.map_prop(
            Column_Key_Hide_Homogeneous,
            prop.MultiProp(Column_Key_Hide_Homogeneous))
        self.p_acc_percent_col = self.map_prop(
            Column_Key_Generate_Acc_Percent_Column,
            prop.ListProp(Column_Key_Generate_Acc_Percent_Column))

        # Others
        self.generated = generated
        self.sum = None
        self.shown_sum = None
        self.mean = None
        self.shown_mean = None
        self.column_data = []
        self._used_for_sorting = False

        # Check that key/value pair list looks properly formatted
        prop.check_key_value(key_value_def)

        # Assign the properties for the column
        for (key, value) in key_value_def:
            if not self.assign_properties(key, value):
                raise TableException(
                    f"unknown column key: {prop.property_name(key)}")

    def assign_properties(self, key, value):
        if self.generated and key in [
                Column_Key_Generate_Percent_Column,
                Column_Key_Generate_Acc_Percent_Column]:
            raise TableException(
                "Cannot create new columns of generated columns")

        return super().assign_properties(key, value)

    def rows(self):
        'Number of rows in the column'
        return len(self.column_data)

    def canonical_name(self):
        return self.p_name.get().replace('\n', ' ')

    # Assign all the data for the column
    def set_data(self, data):
        self.column_data = data

    def get_row_data(self, row):
        return self.column_data[row]

    def set_row_data(self, row, value):
        self.column_data[row] = value

    # Returns True if the column data entirely consists of
    # the Column_Key_Hide_Homogeneous data value.
    def hide(self):
        if self._used_for_sorting:
            return False
        if not self.p_hide_homogeneous._assigned:
            return False

        val = self.p_hide_homogeneous.get()
        return self.column_data == [val] * len(self.column_data)

    # Calculate the sum of all data in a column
    def _col_sum(self, start=None, rows=None):
        if start:
            start = start - 1 # row 1 = element 0
            stop = start + rows
        else:
            stop = rows
        # Ignore any strings in the column
        l = [v for v in self.column_data[start:stop]
             if not isinstance(v, str)]
        return sum(l)

    def calc_sum(self):
        if self.p_footer_sum.get() or (self.p_percent_col.get() != None):
            self.sum = self._col_sum()

    def calc_shown_sum(self, start_row, rows):
        if self.p_footer_sum.get() or (self.p_percent_col.get() != None):
            self.shown_sum = self._col_sum(start_row, rows)

    def calc_mean(self):
        if not self.p_footer_mean.get():
            return
        rows = len(self.column_data)
        if rows:
            self.mean = self._col_sum() / float(rows)
        else:
            self.mean = 0

    def calc_shown_mean(self, start_row, rows):
        if not self.p_footer_mean.get():
            return
        if rows:
            self.shown_mean = self._col_sum(start_row, rows) / float(rows)
        else:
            self.shown_mean = 0

class ColumnsProp(prop.ListProp):
    __slots__ = ('_table')
    def __init__(self, table):
        super().__init__(Table_Key_Columns, [])
        self._table = table      # Table object this column belongs to

    def set(self, value):
        # Validate and set the list first
        super().set(value)
        # Create the column objects and populate another list in the
        # table which owns this property.
        self._table.columns = []
        for i, col_prop in enumerate(value):
            c = Column(col_prop)
            self._table.columns.append(c)
