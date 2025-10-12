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
import re
from cli import (
    arg,
    flag_t,
    str_t,
)
from table import *
from probes import *

def histogram_cmd(obj, reg_exp, no_turbo, *table_args):
    properties = obj.iface.table.properties()
    data = obj.iface.table.data()

    if reg_exp:
        # Filter the data using the regexp
        try:
            ins_re = re.compile(reg_exp)
        except re.error:
            raise cli.CliError(
                "The regular expression '%s' is invalid" % reg_exp)

        org_num_rows = len(data)
        data = [r for r in data if ins_re.match(str(r[0]))]
        new_num_rows = len(data)
        print("Table reduced from %d to %d rows" % (
            org_num_rows, new_num_rows))

    if no_turbo:
        # Only show the rows of where the instruction has never executed in JIT
        org_num_rows = len(data)
        data = [r for r in data if r[2]==0]
        new_num_rows = len(data)
        print("Table reduced from %d to %d rows" % (
            org_num_rows, new_num_rows))

    # Print out the table using the supplied table arguments
    show(properties, data, *table_args)


def ticks_cmd(obj, reg_exp, *table_args):
    properties = obj.iface.table.properties()
    data = obj.iface.table.data()

    if reg_exp:
        # Filter the data using the regexp
        try:
            ins_re = re.compile(reg_exp)
        except re.error:
            raise cli.CliError(
                "The regular expression '%s' is invalid" % reg_exp)

        org_num_rows = len(data)
        data = [r for r in data if ins_re.match(str(r[0]))]
        new_num_rows = len(data)
        print("Table reduced from %d to %d rows" % (
            org_num_rows, new_num_rows))

    # Print out the table using the supplied table arguments
    show(properties, data, *table_args)

new_unsupported_table_command(
                  "histogram", "internals", histogram_cmd,
                  cls = "sr_histogram",
                  args = [arg(str_t, "sr-regexp", "?", None),
                          arg(flag_t, "-no-turbo")],
                  short = "print service-routine histogram",
                  doc = '''
                  Print service-routine histogram for executed
                  instructions.

                  The <arg>sr-regexp</arg> argument can be used
                  to filter out only certain service-routines which matches
                  the given regular expression.

                  The <tt>-no-turbo</tt> flag filters out the instruction
                  which has never executed in turbo.
                  ''')


new_unsupported_table_command(
                  "ticks", "internals", ticks_cmd,
                  cls = "sr_ticks",
                  args = [arg(str_t, "sr-regexp", "?", None)],
                  short = "print time spent in each service-routine",
                  doc = '''
                  Print accumulated time spent in each service-routine
                  for executed instructions.

                  The <arg>sr-regexp</arg> argument can be used
                  to filter out only certain service-routines which matches
                  the given regular expression.
                  ''')

def hist_properties(obj):
    return [
        [Table_Key_Name, "Summary"],
        [Table_Key_Description, "bla bla bla"],
        [Table_Key_Default_Sort_Column, "total"],
        [Table_Key_Columns,
         [[[Column_Key_Name, "service-routine"],
         ],
          [[Column_Key_Name, "interpreter"],
           [Column_Key_Int_Radix, 10],
           [Column_Key_Sort_Descending, True],
           [Column_Key_Footer_Sum, True],
           [Column_Key_Generate_Percent_Column, []],
           [Column_Key_Generate_Acc_Percent_Column, []]],
          [[Column_Key_Name, "turbo"],
           [Column_Key_Int_Radix, 10],
           [Column_Key_Sort_Descending, True],
           [Column_Key_Footer_Sum, True],
           [Column_Key_Generate_Percent_Column, []],
           [Column_Key_Generate_Acc_Percent_Column, []]],
          [[Column_Key_Name, "total"],
           [Column_Key_Int_Radix, 10],
           [Column_Key_Sort_Descending, True],
           [Column_Key_Footer_Sum, True],
           [Column_Key_Generate_Percent_Column, []],
           [Column_Key_Generate_Acc_Percent_Column, []]],
         ]
        ]
    ]

def hist_data(obj):
    # Combine the data in the connections
    s = {}  # { sr : (interpreter, turbo)}
    for con in obj.connections:
        for (sr, i, t) in con.histogram:
            if not i and t:
                continue
            s.setdefault(sr, (0, 0))
            (oi, ot) = s[sr]
            s[sr] = (i + oi, t + ot)

    # Generate new table of the aggregated data
    tbl = [[sr, i, t, i + t] for (sr, (i, t)) in s.items()]
    return tbl

def ticks_properties(obj):
    return [
        [Table_Key_Name, "Summary"],
        [Table_Key_Description, "bla bla bla"],
        [Table_Key_Default_Sort_Column, "total ticks"],
        [Table_Key_Columns,
         [[[Column_Key_Name, "service-routine"],
         ],
          [[Column_Key_Name, "executed"],
           [Column_Key_Int_Radix, 10],
           [Column_Key_Sort_Descending, True],
           [Column_Key_Footer_Sum, True],
           [Column_Key_Generate_Percent_Column, []],
           [Column_Key_Generate_Acc_Percent_Column, []]],
          [[Column_Key_Name, "longjmps"],
           [Column_Key_Int_Radix, 10],
           [Column_Key_Sort_Descending, True],
           [Column_Key_Footer_Sum, True],
           [Column_Key_Generate_Percent_Column, []],
           [Column_Key_Generate_Acc_Percent_Column, []]],
          [[Column_Key_Name, "total ticks"],
           [Column_Key_Int_Radix, 10],
           [Column_Key_Sort_Descending, True],
           [Column_Key_Footer_Sum, True],
           [Column_Key_Generate_Percent_Column, []],
           [Column_Key_Generate_Acc_Percent_Column, []]],
          [[Column_Key_Name, "average ticks"],
           [Column_Key_Int_Radix, 10],
           [Column_Key_Sort_Descending, True],
           [Column_Key_Footer_Mean, True],
          ]]
        ]
    ]

def ticks_data(obj):
    # Combine the data in the connections
    s = {}  # { sr : (exec, dnf, ticks)}
    for con in obj.connections:
        for (sr, ex, dnf, ticks) in con.ticks:
            if not ex:
                continue
            s.setdefault(sr, (0, 0, 0))
            (oex, odnf, oticks) = s[sr]
            s[sr] = (ex + oex, dnf + odnf, ticks + oticks)

    # Generate new table of the aggregated data
    tbl = [[sr, e, d, t, ((t/(e-d)) if (e-d) else 0)]
           for (sr, (e, d, t)) in s.items()]
    return tbl

hist_table_iface = simics.table_interface_t(
    properties = hist_properties,
    data = hist_data,
)

ticks_table_iface = simics.table_interface_t(
    properties = ticks_properties,
    data = ticks_data,
)

simics.SIM_register_interface(
    "sr_histogram", 'table', hist_table_iface)

simics.SIM_register_interface(
    "sr_ticks", 'table', ticks_table_iface)


def con_num_indices(obj):
    return 4

def con_probe_value(obj, idx):
    data = obj.histogram
    if idx == 0:
        data = [[name, icount+jcount] for (name, icount, jcount) in data]
    elif idx == 1:
        data = [[name, icount] for (name, icount, jcount) in data
                if jcount == 0] # Only SRs that never has run in JIT
    elif idx == 2:
        data = [[name, icount] for (name, icount, jcount) in data]
    elif idx == 3:
        data = [[name, jcount] for (name, icount, jcount) in data]
    else:
        assert 0
    return data

def con_probe_properties(obj, idx):
    probe_name = f"cpu.tool.{obj.parent.classname}.{obj.parent.name}"
    if idx == 0:
        return [[Probe_Key_Kind, f"{probe_name}.all_sr.histogram"],
                [Probe_Key_Display_Name, "SR histogram"],
                [Probe_Key_Description, "Service-routine histogram"],
                [Probe_Key_Width, 50],
                [Probe_Key_Type, "histogram"],
                [Probe_Key_Owner_Object, obj.cpu],
                [Probe_Key_Categories, ["cpu"]],
            ]
    elif idx == 1:
        return [[Probe_Key_Kind, f"{probe_name}.non_jit_sr.histogram"],
                [Probe_Key_Display_Name, "Non-JIT histogram"],
                [Probe_Key_Description, "Service-routine histogram, "
                 "with only service-routines not executed in JIT"],
                [Probe_Key_Width, 50],
                [Probe_Key_Type, "histogram"],
                [Probe_Key_Owner_Object, obj.cpu],
                [Probe_Key_Categories, ["cpu"]],
            ]
    elif idx == 2:
        return [[Probe_Key_Kind, f"{probe_name}.int_sr.histogram"],
                [Probe_Key_Display_Name, "INT SR histogram"],
                [Probe_Key_Description, "Service-routine histogram, "
                 "in interpreter."],
                [Probe_Key_Width, 50],
                [Probe_Key_Type, "histogram"],
                [Probe_Key_Owner_Object, obj.cpu],
                [Probe_Key_Categories, ["cpu"]],
            ]
    elif idx == 3:
        return [[Probe_Key_Kind, f"{probe_name}.jit_sr.histogram"],
                [Probe_Key_Display_Name, "JIT SR histogram"],
                [Probe_Key_Description, "Service-routine histogram, "
                 "in JIT compiler."],
                [Probe_Key_Width, 50],
                [Probe_Key_Type, "histogram"],
                [Probe_Key_Owner_Object, obj.cpu],
                [Probe_Key_Categories, ["cpu"]],
            ]

probe_iface = simics.probe_index_interface_t(
    num_indices = con_num_indices,
    value = con_probe_value,
    properties = con_probe_properties
)
simics.SIM_register_interface(
    "sr_histogram_connection", 'probe_index', probe_iface)
