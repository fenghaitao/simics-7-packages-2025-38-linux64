# © 2016 Intel Corporation
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
import instrumentation
from table import *

import cli

def icount_cmd(obj, *table_args):
    properties = obj.iface.table.properties()
    data = obj.iface.table.data()
    show(properties, data, *table_args)

new_table_command(
    "icount", icount_cmd,
    args = [],
    cls = "instruction_count",
    short = "print instruction count",
    doc = "Print the instruction count for the connected processors.")

def clear_cmd(obj):
    for c in obj.connections:
        c.icount = 0

cli.new_command(
    "clear", clear_cmd,
    args = [],
    cls = "instruction_count",
    type = ["Instrumentation"],
    short = "clear instruction counts",
    see_also = ["<instruction_count>.icount"],
    doc = ("Zeroes the instruction counts"))

def properties(obj):
    return [ [Table_Key_Name, "CPU specific exception histogram"],
             [Table_Key_Description, "Exception histogram for %s" % (obj.name)],
             [Table_Key_Default_Sort_Column, "Count"],
             [Table_Key_Columns, [[[Column_Key_Name, "Processor"]],
                                  [[Column_Key_Name, "Count"],
                                   [Column_Key_Int_Radix, 10],
                                   [Column_Key_Sort_Descending, True],
                                   [Column_Key_Footer_Sum, True],
                                   [Column_Key_Generate_Percent_Column, []],
                                   ]]]]

def data(obj):
    data = []
    for con in obj.connections:
        data.append([con.provider, con.icount])
    return data

table_iface = simics.table_interface_t(
    properties = properties,
    data = data,
)

simics.SIM_register_interface(
    "instruction_count", 'table', table_iface)
