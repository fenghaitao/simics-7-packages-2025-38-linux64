# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import re
import cli
import table
import simics

from probes import *

def histogram_cmd(obj, add_object, add_method, reg_exp, agg_filtered_out, *table_args):
    data = list(obj.histogram) # from attribute object

    new = {}
    for [s, c] in data:
        mo = re.match(r'(.*)[|]([a-zA-Z0-9_]+)->([a-zA-Z0-9_]+)', s)
        if mo is None:
            raise cli.CliError("Corrupted histogram data")

        ns  = (mo.group(1) + "|") if add_object else "|"
        ns += mo.group(2)
        ns += ("->" + mo.group(3)) if add_method else ""
        new.setdefault(ns, 0)
        new[ns] += c

    out_data = []

    for (s, c) in new.items():
        (o, im) = s.split("|")
        out_data.append([o, im, c])

    if reg_exp:
        data = out_data
        # Filter the data using the regexp
        try:
            ins_re = re.compile(reg_exp)
        except re.error:
            raise cli.CliError(
                "The regular expression '%s' is invalid" % reg_exp)

        out_data = [r for r in data if ins_re.match(str(r[1]))]
        if agg_filtered_out:
            filtered = [r for r in data if not ins_re.match(str(r[1]))]
            total = sum([r[2] for r in filtered])
            out_data += [["*FILTERED OUT*", "*FILTERED OUT*", total]]
        org_num_rows = len(data)
        new_num_rows = len(out_data)
        print("Table reduced from %d to %d rows" % (
            org_num_rows, new_num_rows))

    cols = [[(table.Column_Key_Name, "Object"),
             (table.Column_Key_Hide_Homogeneous, "")],
            [(table.Column_Key_Name, "Interface")],
            [(table.Column_Key_Name, "Calls"),
             (table.Column_Key_Footer_Sum, True),
             (table.Column_Key_Generate_Percent_Column, []),
             (table.Column_Key_Generate_Acc_Percent_Column, [])]]

    properties = [(table.Table_Key_Columns, cols),
                  (table.Table_Key_Default_Sort_Column, "Calls")]

    # Print out the table using the supplied table arguments
    table.show(properties, out_data, *table_args)

table.new_table_command(
    "histogram", histogram_cmd,
    args = [cli.arg(cli.flag_t, "-object"),
            cli.arg(cli.flag_t, "-method"),
            cli.arg(cli.str_t, "interface-regexp", "?", None),
            cli.arg(cli.flag_t, "-aggregate-filtered-out")],
    cls = "interface_histogram_tool",
    short = "control blocked interfaces",

    doc = """Displays the histogram over all called interfaces and there methods
    in a Simics session. Default output consists of just the interface, and how
    many times that interface has been called. Adding the <tt>-method</tt>
    flag, the command will print how many times the method in each interface is
    called. There is also an <tt>-object</tt> flag that adds
    information about which object the interface call was made to.

    The <arg>interface-regexp</arg> argument can be used to only show
    interfaces matching this regular expression. If
    <tt>-aggregate-filtered-out</tt> flag is given all interfaces that does not
    match the regular expression will be aggregated into one line that show how
    many of those did not match.""",

    sortable_columns = ["Object", "Interface", "Calls"])

def method_histogram(data):
    d = {}
    for (key, count) in data:
        iface_meth = key.split('|')[1]
        d[iface_meth] = d.get(iface_meth, 0) + count
    return [[k,v] for (k, v) in d.items()]

def iface_histogram(data):
    d = {}
    for (key, count) in data:
        iface = (key.split('|')[1]).split('->')[0]
        d[iface] = d.get(iface, 0) + count
    return [[k,v] for (k, v) in d.items()]

def probe_indices(obj):
    return 3

def probe_value(obj, idx):
    # fisketur[syntax-error]
    match idx:
        case 0:
            return list(obj.histogram)
        case 1:
            return method_histogram(obj.histogram)
        case 2:
            return iface_histogram(obj.histogram)
        case _:
            return None

def probe_properties(obj, idx):
    # fisketur[syntax-error]
    match idx:
        case 0:
            return [[Probe_Key_Kind,
                 f"{obj.classname}.{obj.name}.object_method_histogram"],
                [Probe_Key_Display_Name, "Interface histogram"],
                [Probe_Key_Description, "Called interfaces+methods with object"],
                [Probe_Key_Width, 80],
                [Probe_Key_Type, "histogram"],
                [Probe_Key_Categories, ["API", "interface"]]]
        case 1:
            return [[Probe_Key_Kind,
                 f"{obj.classname}.{obj.name}.method_histogram"],
                [Probe_Key_Display_Name, "Interface histogram"],
                [Probe_Key_Description, "Called interfaces+methods"],
                [Probe_Key_Width, 64],
                [Probe_Key_Type, "histogram"],
                [Probe_Key_Categories, ["API", "interface"]]]
        case 2:
            return [[Probe_Key_Kind,
                 f"{obj.classname}.{obj.name}.histogram"],
                [Probe_Key_Display_Name, "Interface histogram"],
                [Probe_Key_Description, "Called interfaces"],
                [Probe_Key_Width, 40],
                [Probe_Key_Type, "histogram"],
                [Probe_Key_Categories, ["API", "interface"]]]
        case _:
            return None

probe_iface = simics.probe_index_interface_t(
    num_indices = probe_indices,
    value = probe_value,
    properties = probe_properties
)

simics.SIM_register_interface("interface_histogram_tool", 'probe_index',
                              probe_iface)
