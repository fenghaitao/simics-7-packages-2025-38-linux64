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

class StreamColumn(common_column.CommonColumn):
    __slots__ = (
    )
    def __init__(self, key_value_def, generated=False):
        super().__init__(generated)

        # Check that key/value pair list looks properly formatted
        prop.check_key_value(key_value_def)

        # Assign the properties for the column
        for (key, value) in key_value_def:
            if not self.assign_properties(key, value):
                raise TableException(
                    f"unknown column key: {prop.property_name(key)}")

class StreamColumnsProp(prop.ListProp):
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
            c = StreamColumn(col_prop)
            self._table.columns.append(c)
