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

# Common properties for columns that affects the cell-format.

from .table_enums import *  # Table constants
from .common import (TableException,)
from . import prop

class FormatProps:
    __slots__ = (
        'p_alignment',
        'p_radix',
        'p_grouping',
        'p_pad_width',
        'p_float_percent',
        'p_float_decimals',
        'p_metric_prefix',
        'p_binary_prefix',
        'p_time_format',
        'p_word_delimiters',

        'property_map',
    )

    def __init__(self):
        self.property_map = {}

        self.p_alignment = self.map_prop(Column_Key_Alignment,
                                         prop.AlignProp())
        self.p_radix = self.map_prop(Column_Key_Int_Radix,
                                     prop.RadixProp())
        self.p_grouping = self.map_prop(Column_Key_Int_Grouping,
                                        prop.BoolProp(Column_Key_Int_Grouping,
                                                      default=True))
        self.p_pad_width = self.map_prop(Column_Key_Int_Pad_Width,
                                         prop.IntProp(Column_Key_Int_Pad_Width,
                                                      default=1))
        self.p_float_percent = self.map_prop(Column_Key_Float_Percent,
                                             prop.BoolProp(Column_Key_Float_Percent))
        self.p_float_decimals = self.map_prop(Column_Key_Float_Decimals,
                                              prop.IntProp(Column_Key_Float_Decimals,
                                                           default=2))
        self.p_metric_prefix = self.map_prop(Column_Key_Metric_Prefix,
                                             prop.StrProp(Column_Key_Metric_Prefix,
                                                          default=None))
        self.p_binary_prefix = self.map_prop(Column_Key_Binary_Prefix,
                                             prop.StrProp(Column_Key_Binary_Prefix,
                                                          default=None))
        self.p_time_format = self.map_prop(Column_Key_Time_Format,
                                           prop.BoolProp(Column_Key_Time_Format))

        self.p_word_delimiters = self.map_prop(
            Column_Key_Word_Delimiters,
            prop.StrProp(Column_Key_Word_Delimiters, default=" -_:."))


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


class CellProps(FormatProps):
    __slots__ = (
    )

    def __init__(self, key_value_def):
        super().__init__()

        # Check that key/value pair list looks properly formatted
        prop.check_key_value(key_value_def)

        # Assign the properties for the column
        for (key, value) in key_value_def:
            if not self.assign_properties(key, value):
                raise TableException(
                    f"unknown column key: {prop.property_name(key)}")
