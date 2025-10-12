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
import cli
import conf
from table import *
from probes import *

def exception_histogram_cmd(obj, *table_args):
    properties = obj.iface.table.properties()
    data = obj.iface.table.data()
    show(properties, data, *table_args)

def clear_cmd(obj):
    for c in obj.connections:
        c.clear = True

new_table_command("histogram", exception_histogram_cmd,
                  cls = "exception_histogram",
                  args = [],
                  type = ["Instrumentation"],
                  short = "print taken exceptions with frequencies",
                  see_also = ["<exception_histogram>.clear"],
                  doc = ("""
                  Prints the exceptions taken (their names) with
                  frequencies."""))

cli.new_command("clear", clear_cmd,
                [],
                cls = "exception_histogram",
                type = ["Instrumentation"],
                short = "clear instruction sizes frequencies",
                see_also = ["<exception_histogram>.histogram"],
                doc = ("Removes information on exceptions"
                       " that has been gathered."))

generic_properties = [
    [Table_Key_Default_Sort_Column, "Count"],
    [Table_Key_Columns, [
        [
            [Column_Key_Name, "Exception"]
        ],
        [
            [Column_Key_Name, "Count"],
            [Column_Key_Int_Radix, 10],
            [Column_Key_Sort_Descending, True],
            [Column_Key_Footer_Sum, True],
            [Column_Key_Generate_Percent_Column, []],
            [Column_Key_Generate_Acc_Percent_Column, []],
        ]]
    ]
]

def con_properties(obj):
    l = [ [Table_Key_Name, "Exception histogram"],
          [Table_Key_Description, ("Accumulated exception histogram for all"
                               " connected processors")]]
    l.extend(generic_properties)
    return l

def properties(obj):
    l = [ [Table_Key_Name, "CPU specific exception histogram"],
          [Table_Key_Description, "Exception histogram for %s" % (obj.name)]]
    l.extend(generic_properties)
    return l

def con_data(obj):
    tbl = [[i, c] for (i, c) in obj.histogram if c > 0]
    return tbl

def data(obj):
    # Combine the data in the connections
    s = {}  # { exception : count}
    for con in obj.connections:
        for (e, c) in con.histogram:
            if not c:
                continue
            s.setdefault(e, 0)
            s[e] += c

    # Generate new table of the aggregated data
    tbl = [[e, c] for (e, c) in s.items()]
    return tbl

con_table_iface = simics.table_interface_t(
    properties = con_properties,
    data = con_data,
)
table_iface = simics.table_interface_t(
    properties = properties,
    data = data,
)

simics.SIM_register_interface(
    "exception_histogram_connection", 'table', con_table_iface)
simics.SIM_register_interface(
    "exception_histogram", 'table', table_iface)


def con_probe_num_indices(obj):
    return 2

def con_probe_value(obj, idx):
    if idx == 0:
        return obj.exception_count
    if idx == 1:
        return obj.histogram
    assert 0

def con_probe_properties(obj, idx):
    if idx == 0:
        probe_name = f"{obj.tool.classname}.{obj.tool.name}.exception_count"
        return [[Probe_Key_Kind, f"cpu.tool.{probe_name}"],
                [Probe_Key_Display_Name, "#Exc"],
                [Probe_Key_Description,
                 "Number of exceptions."
                 " Recorded by the exception-histogram tool."],
                [Probe_Key_Width, 5],
                [Probe_Key_Type, "int"],
                [Probe_Key_Owner_Object, obj.cpu],
                [Probe_Key_Categories, ["exception", "cpu"]],
                [Probe_Key_Aggregates, [
                    [
                        [Probe_Key_Kind, f"sim.tool.{probe_name}"],
                        [Probe_Key_Aggregate_Scope, "global"],
                        [Probe_Key_Owner_Object, conf.sim],
                        [Probe_Key_Aggregate_Function, "sum"],
                        [Probe_Key_Description,
                         "Total number of recorded exceptions on all processors."
                         " Monitored by the exception-histogram tool."]
                    ],
                    [
                        [Probe_Key_Kind, f"cell.tool.{probe_name}"],
                        [Probe_Key_Aggregate_Scope, "cell"],
                        [Probe_Key_Aggregate_Function, "sum"],
                        [Probe_Key_Description,
                         "Total number of recorded exceptions on all processor"
                         " in a cells. Monitored by the exception-histogram"
                         " tool."]
                    ]
                ]]]
    if idx == 1:
        probe_name = f"{obj.tool.classname}.{obj.tool.name}.histogram"
        return [[Probe_Key_Kind, f"cpu.tool.{probe_name}"],
                [Probe_Key_Display_Name, "Exception histogram"],
                [Probe_Key_Description, "Histogram of most frequent exceptions."],
                [Probe_Key_Width, 40],
                [Probe_Key_Type, "histogram"],
                [Probe_Key_Owner_Object, obj.cpu],
                [Probe_Key_Categories, ["exception", "cpu"]],
                [Probe_Key_Aggregates, [
                    [
                        [Probe_Key_Kind, f"sim.tool.{probe_name}"],
                        [Probe_Key_Aggregate_Scope, "global"],
                        [Probe_Key_Owner_Object, conf.sim],
                        [Probe_Key_Aggregate_Function, "sum"],
                        [Probe_Key_Description,
                         "Histogram of most frequent exceptions on all"
                         " processors. Monitored by the exception-histogram"
                         " tool"]
                    ],
                    [
                        [Probe_Key_Kind, f"cell.tool.{probe_name}"],
                        [Probe_Key_Aggregate_Scope, "cell"],
                        [Probe_Key_Aggregate_Function, "sum"],
                        [Probe_Key_Description,
                         "Histogram of most frequent exceptions on all"
                         " processor in a cell. Monitored by the exception-"
                         "histogram tool."]

                    ]
                ]]]
    assert 0

probe_iface = simics.probe_index_interface_t(
    num_indices = con_probe_num_indices,
    value = con_probe_value,
    properties = con_probe_properties
)
simics.SIM_register_interface(
    "exception_histogram_connection", 'probe_index', probe_iface)
