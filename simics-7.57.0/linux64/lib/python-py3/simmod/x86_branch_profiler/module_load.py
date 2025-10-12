# © 2017 Intel Corporation
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
from table import *

def histogram_cmd(obj, *table_args):
    properties = obj.iface.table.properties()
    data = obj.iface.table.data()
    show(properties, data, *table_args)

new_table_command("histogram", histogram_cmd,
                  cls = "x86_branch_profiler",
                  args = [],
                  type = ["Profiling"],
                  short = "print histogram of branches used",
                  doc = """
                  Print an histogram over all normal branches used by the
                  connected processors.""")

def properties(obj):
    return [
        [Table_Key_Name,
         "Histogram of most commonly executed x86 branch instructions."],
        [Table_Key_Description,
         "The table shows how many times various x86 branch instructions"
         " have executed and how often they have beentaken or not taken"
         " (for conditional jumps)."],
        [Table_Key_Default_Sort_Column, "Total"],
        [Table_Key_Columns,
         [[[Column_Key_Name, "Branch\nInstruction"],
           [Column_Key_Description, "The x86 branch instruction mnemonic."],
           [Column_Key_Int_Radix, 10],
           [Column_Key_Sort_Descending, True]],
          [[Column_Key_Name, "Taken"],
           [Column_Key_Description, "Number of times the instruction branched."],
           [Column_Key_Int_Radix, 10],
           [Column_Key_Sort_Descending, True],
           [Column_Key_Footer_Sum, True],
           [Column_Key_Generate_Percent_Column, []],
           [Column_Key_Generate_Acc_Percent_Column, []],
          ],
          [[Column_Key_Name, "Non-taken"],
           [Column_Key_Description,
            "Number of times the instruction didn't branch."],
           [Column_Key_Int_Radix, 10],
           [Column_Key_Sort_Descending, True],
           [Column_Key_Alignment, "right"],
           [Column_Key_Footer_Sum, True],
           [Column_Key_Generate_Percent_Column, []],
           [Column_Key_Generate_Acc_Percent_Column, []],
          ],
          [[Column_Key_Name, "Total"],
           [Column_Key_Description, "Total amound of executed instructions."],
           [Column_Key_Int_Radix, 10],
           [Column_Key_Sort_Descending, True],
           [Column_Key_Footer_Sum, True],
           [Column_Key_Generate_Percent_Column, []],
           [Column_Key_Generate_Acc_Percent_Column, []],
          ]]
        ]
    ]

def data(obj):
    tbl = []
    for (b, t, n) in obj.stats:
        if b in ["jmp", "call", "ret"]:
            tbl.append([b, t, "-", t])
        else:
            tbl.append([b, t, n, t + n])
    return tbl

table_iface = simics.table_interface_t(
    properties = properties,
    data = data,
)

simics.SIM_register_interface(
    "x86_branch_profiler", 'table', table_iface)
