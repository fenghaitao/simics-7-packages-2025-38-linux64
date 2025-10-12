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
from . import cell_props

class CommonColumn(cell_props.FormatProps):
    __slots__ = (
        # Column properties
        'p_name',
        'p_desc',
        'p_width',              # Only in stream?
        'p_unique_id',

        'auto_resized_width',
    )

    def __init__(self, generated=False):
        super().__init__()
        # Column properties (implemented through property objects)
        self.p_name = self.map_prop(Column_Key_Name,
                                    prop.StrProp(Column_Key_Name))
        self.p_desc = self.map_prop(Column_Key_Description,
                                    prop.StrProp(Column_Key_Description))

        self.p_width = self.map_prop(Column_Key_Width,
                                     prop.IntProp(Column_Key_Width,
                                                  default=None))

        self.p_unique_id = self.map_prop(Column_Key_Unique_Id,
                                          prop.StrProp(Column_Key_Unique_Id,
                                                       default=None))
        self.auto_resized_width = None


    def unique_name(self):
        ref = self.p_unique_id.get()
        return ref if ref != None else self.p_name.get()

    def set_auto_width(self, width):
        self.auto_resized_width = width

    def column_width(self):
        if self.auto_resized_width != None:
            return self.auto_resized_width

        if self.p_width.get() != None:
            return self.p_width.get() # Fixed width by column property

        return len(self.p_name.get()) # Header width
