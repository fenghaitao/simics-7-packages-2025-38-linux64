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


import math
import cli
from table import *

view = {"read-physical" : 0,
        "read-logical" : 1,
        "write-physical" : 2,
        "write-logical" : 3,
        "execute-physical" : 4,
        "execute-logical" : 5 }

def extract(data, start, stop, gran):
    gran_stat = {}

    for (low, high, g, counters) in data:
        if high < start or stop < low:
            continue
        counters_per_page = (high - low + 1) >> g
        for s in range(counters_per_page):
            addr = (low + (s << g))
            gran_addr = addr - (addr % gran)
            if counters[s] > 0:
                gran_stat[gran_addr] = gran_stat.get(gran_addr, 0) + counters[s]

    return iter(gran_stat.items())

def is_pow2(v):
    return ((v - 1) & v) == 0

def profile_cmd(obj, v, gran, start, stop, *table_args):
    gran_setting = 1 << obj.granularity_log2
    if gran == None:
        gran = gran_setting
    if gran < gran_setting:
        raise cli.CliError('The tool was not configured for a granularity less'
                           f' than {gran_setting}')

    if not is_pow2(gran) or gran == 0:
        raise cli.CliError('Granularity need to be a power of 2')

    data = obj.stat[view[v]]
    gran_data = extract(data, start, stop, gran)

    out_data = []
    for (a0, count) in gran_data:
        out_data.append((a0, a0 + gran - 1, count))

    # Table layout/properties
    props =  [[Table_Key_Default_Sort_Column, "Count"],
              [Table_Key_Columns, [
                  [[Column_Key_Name, "Start"],
                   [Column_Key_Int_Radix, 16],
                   [Column_Key_Sort_Descending, False],
                   [Column_Key_Description, "Start address"]
                  ],
                  [[Column_Key_Name, "Stop"],
                   [Column_Key_Int_Radix, 16],
                   [Column_Key_Description, "Stop address"]
                  ],
                  [[Column_Key_Name, "Count"],
                   [Column_Key_Int_Radix, 10],
                   [Column_Key_Sort_Descending, True],
                   [Column_Key_Footer_Sum, True],
                   [Column_Key_Generate_Percent_Column, []],
                   [Column_Key_Generate_Acc_Percent_Column, []],
                   [Column_Key_Description, "Access count"],
                  ]]]]

    # Print out the table using the supplied table arguments

    return cli.command_return(message = get(props, out_data, *table_args),
                              value = [list(line) for line in out_data])

new_table_command(
    "profile", profile_cmd,
    cls = "memory_profiler",
    args = [
        cli.arg(cli.string_set_t(view.keys()), "view"),
        cli.arg(cli.int_t, "granularity", "?"),
        cli.arg(cli.int_t, "start", "?", 0),
        cli.arg(cli.int_t, "stop", "?", pow(2,64)-1),
    ],
    type = ["Instrumentation"],
    short = "print memory profile",
    doc = '''
    Print profile of <arg>view</arg>, which is in the range 0-5.

    Set address <arg>granularity</arg>, which is 4096 by default.
    Give <arg>start</arg> address, which is 0 by default.
    Give <arg>stop</arg> address, which is 2^64 - 1 by default.
    ''',
    sortable_columns = ["Start", "Count"])
