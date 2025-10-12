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


# Export table constants (from wrapped enum-types in the interface)
# Import these to make them available in the table namespace

# This list must be up-to-date with the enum values defined
# in core/src/include/simics/simulator-iface/table.h
from simics import (
    Table_Key_Name,
    Table_Key_Description,
    Table_Key_Default_Sort_Column,
    Table_Key_Columns,
    Table_Key_Extra_Headers,
    Table_Key_Stream_Header_Repeat,

    Column_Key_Name,
    Column_Key_Description,
    Column_Key_Alignment,
    Column_Key_Int_Radix,
    Column_Key_Int_Grouping,
    Column_Key_Int_Pad_Width,
    Column_Key_Float_Percent,
    Column_Key_Float_Decimals,
    Column_Key_Binary_Prefix,
    Column_Key_Metric_Prefix,
    Column_Key_Time_Format,
    Column_Key_Sort_Descending,
    Column_Key_Hide_Homogeneous,
    Column_Key_Generate_Percent_Column,
    Column_Key_Generate_Acc_Percent_Column,
    Column_Key_Footer_Sum,
    Column_Key_Footer_Mean,
    Column_Key_Unique_Id,
    Column_Key_Width,
    Column_Key_Word_Delimiters,

    Extra_Header_Key_Row,
    Extra_Header_Key_Name,
    Extra_Header_Key_Description,
    Extra_Header_Key_First_Column,
    Extra_Header_Key_Last_Column
)
