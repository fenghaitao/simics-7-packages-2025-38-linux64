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
import re
from table import *
from probes import *

def histogram_cmd(obj, reg_exp, agg_filtered_out, *table_args):
    properties = obj.iface.table.properties()
    data = obj.iface.table.data()
    out_data = data
    if reg_exp:
        # Filter the data using the regexp
        try:
            ins_re = re.compile(reg_exp)
        except re.error:
            raise cli.CliError(
                "The regular expression '%s' is invalid" % reg_exp)

        out_data = [r for r in data if ins_re.match(str(r[0]))]
        if agg_filtered_out:
            filtered = [r for r in data if not ins_re.match(str(r[0]))]
            total = sum([r[1] for r in filtered])
            out_data += [["*FILTERED OUT*", total]]
        org_num_rows = len(data)
        new_num_rows = len(out_data)
        print("Table reduced from %d to %d rows" % (
            org_num_rows, new_num_rows))

    # Print out the table using the supplied table arguments
    show(properties, out_data, *table_args)

    if obj.view == "size":
        total_size = 0
        total_instructions = 0
        for (i, c) in out_data:
            total_size += int(i) * c
            total_instructions += c
        if total_instructions:
            average_length = float(total_size) / total_instructions
            print("Average size of executed instruction: %f (%d bits)" % (
                average_length, average_length * 8))
    print()

def clear_cmd(ht):
    for obj in ht.connections:
        obj.clear = True


new_table_command("histogram", histogram_cmd,
                  cls = "instruction_histogram",
                  args = [cli.arg(cli.str_t, "instruction-regexp", "?", None),
                          cli.arg(cli.flag_t, "-aggregate-filtered-out")],
                  type = ["Instrumentation"],
                  short = "print instruction histogram",
                  doc = '''
                  Print instruction histogram for executed
                  instructions.

                  The <arg>instruction-regexp</arg> argument can be used
                  to filter out only certain instructions which matches
                  the given regular expression.

                  The <tt>-aggregate-filtered-out</tt> flag merges all
                  filtered out data into a single row, which keeps the
                  total amount of instructions executed correct.
                  ''')

cli.new_command("clear", clear_cmd,
                [],
                cls = "instruction_histogram",
                type = ["Instrumentation"],
                short = "remove old data",
                doc = "Remove any data already measured.")

def object_properties(obj, view):
    d = {
        "size": (
            "Size\n(bytes)",
            "Size of the instruction in bytes",
            "How many time instructions of this size have executed.",
            ),
        "mnemonic": (
            "mnemonic",
            "The first part of the disassembled instruction.",
            "How many times this instruction mnemonic has executed",
            ),
        "xed-iform": (
            "xed-iform",
            "Intel® X86 Encoder Decoder (Intel® XED) instruction format.",
            "How many times this instruction format has executed",
            ),
        "xed-extension": (
            "xed-extension",
            "Intel® X86 Encoder Decoder (Intel® XED) instruction extension.",
            "How many times this instruction extension has executed",
            ),
        "xed-isa-set": (
            "xed-isa-set",
            "Intel® X86 Encoder Decoder (Intel® XED) instruction isa-set.",
            "How many times this instruction isa-set has executed",
            ),
        "xed-iclass": (
            "xed-iclass",
            "Intel® X86 Encoder Decoder (Intel® XED) instruction iclass.",
            "How many times this instruction iclass has executed",
            ),
        "xed-category": (
            "xed-category",
            "Intel® X86 Encoder Decoder (Intel® XED) instruction category.",
            "How many times this instruction category has executed",
            ),
        "x86-normalized": (
            "x86 normalized",
            "x86 format with register numbers and immediate values reduced.",
            "How many times this instruction format has executed",
            ),
        }
    (name, name_desc, count_desc) = d[view]
    return [[Table_Key_Default_Sort_Column, "Count"],
            [Table_Key_Columns, [
                [[Column_Key_Name, name],
                 [Column_Key_Description, name_desc]
                ],
                [[Column_Key_Name, "Count"],
                 [Column_Key_Int_Radix, 10],
                 [Column_Key_Sort_Descending, True],
                 [Column_Key_Footer_Sum, True],
                 [Column_Key_Generate_Percent_Column, []],
                 [Column_Key_Generate_Acc_Percent_Column, []],
                 [Column_Key_Description, count_desc],
                ]]]]

def con_properties(obj):
    l = [[Table_Key_Name, "Instruction histogram for %s" % (obj.cpu.name)],
         [Table_Key_Description, "View: %s" % (obj.parent.view)]]
    l.extend(object_properties(obj, obj.parent.view))
    return l

def properties(obj):
    num_cpus = len(obj.connections)
    cpu_names = [o.cpu.name for o in obj.connections]
    cpus = ", ".join(cpu_names)
    l = [[Table_Key_Name, "Instruction histogram for %d processors" % (num_cpus)],
         [Table_Key_Description, "View: %s Monitored processors: %s" % (
             obj.view, cpus)]]
    l.extend(object_properties(obj, obj.view))
    return l

def con_data(obj):
    tbl = [[i, c] for (i, c) in obj.histogram if c > 0]
    return tbl

def data(obj):
    # Combine the data in all the connections into
    # a summary
    s = {}  # { instruction : count}
    for con in obj.connections:
        for (i, c) in con.histogram:
            if not c:
                continue
            s.setdefault(i, 0)
            s[i] += c

    # Generate new table of the aggregated data
    tbl = [[i, c] for (i, c) in s.items()]
    return tbl

con_table_iface = simics.table_interface_t(
    properties = con_properties,
    data = con_data,
)
table_iface = simics.table_interface_t(
    properties = properties,
    data = data,
)

def con_probe_value(obj):
    if len(obj.histogram) and isinstance(obj.histogram[0][0], int):
        # If keys are integer, convert them to strings for histogram-probes
        return [[str(k),v] for (k, v) in obj.histogram]

    return obj.histogram

def con_probe_properties(obj):
    probe_name = f"{obj.parent.classname}.{obj.parent.name}.histogram"
    return [[Probe_Key_Kind, f"cpu.tool.{probe_name}"],
            [Probe_Key_Display_Name, "Instruction histogram"],
            [Probe_Key_Description, "Most frequently executed instructions."],
            [Probe_Key_Width, 40],
            [Probe_Key_Type, "histogram"],
            [Probe_Key_Owner_Object, obj.cpu],
            [Probe_Key_Categories, ["instruction", "cpu"]],
            [Probe_Key_Aggregates, [
                [
                    [Probe_Key_Kind, f"sim.tool.{probe_name}"],
                    [Probe_Key_Aggregate_Scope, "global"],
                    [Probe_Key_Owner_Object, conf.sim],
                    [Probe_Key_Aggregate_Function, "sum"],
                    [Probe_Key_Description,
                     "Most frequently executed instructions on all processors,"
                     " monitored by the instruction-histogram tool."],
                ],
                [
                    [Probe_Key_Kind, f"cell.tool.{probe_name}"],
                    [Probe_Key_Aggregate_Scope, "cell"],
                    [Probe_Key_Aggregate_Function, "sum"],
                    [Probe_Key_Description,
                     "Most frequently executed instructions on all processor"
                     " in a cell, monitored by the instruction-histogram"
                     " tool."]
                ]
            ]]]

probe_iface = simics.probe_interface_t(
    value = con_probe_value,
    properties = con_probe_properties
)

for view in ["mnemonic", "size", "x86_normalized", "xed"]:
    cls = "%s_histogram_connection" % view
    if hasattr(conf.classes, cls):
        simics.SIM_register_interface(cls, 'table', con_table_iface)
        simics.SIM_register_interface(cls, 'probe', probe_iface)

simics.SIM_register_interface(
    "instruction_histogram", 'table', table_iface)
