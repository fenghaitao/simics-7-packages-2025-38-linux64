# © 2022 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import instrumentation
import cli
import conf

from table import *
from simics import *

exe_modes = {
    X86_Detailed_Exec_Mode_Real_16 : "RealMode16",
    X86_Detailed_Exec_Mode_Real_32 : "RealMode32",
    X86_Detailed_Exec_Mode_V86     : "Virtual86",
    X86_Detailed_Exec_Mode_Protected_16 : "ProtectedMode16",
    X86_Detailed_Exec_Mode_Protected_32 : "ProtectedMode32",
    X86_Detailed_Exec_Mode_Protected_64 : "ProtectedMode64",
    X86_Detailed_Exec_Mode_Compatibility_16 : "CompatibilityMode16",
    X86_Detailed_Exec_Mode_Compatibility_32 : "CompatibilityMode32" }

def describe_exe(exe):
    return exe_modes[exe]

def describe_smm(smm):
    return "SMM/" if smm else ""

def describe_vmx(vmx):
    return { Vmx_Off : "",
             Vmx_Root : "VMX-Root/",
             Vmx_Non_Root : "VMX-NonRoot/" }[vmx]

def get_mode(smm, vmx, exe):
    return f"{describe_smm(smm)}{describe_vmx(vmx)}{describe_exe(exe)}"

def histogram_data(obj):
    return [[get_mode(smm, vmx, exe), c]
            for [[smm, vmx, exe], c] in obj.histogram]

def histogram_properties(obj):
    return [[Table_Key_Name,
             "Histogram of instructions in different x86 modes."],
            [Table_Key_Description,
             "The table shows how many steps in each x86 mode have"
             " been executed."],
            [Table_Key_Default_Sort_Column, "Steps"],
            [Table_Key_Columns,
             [[[Column_Key_Name, "Mode"],
               [Column_Key_Description, "The x86 mode as smm-vmx-exe."],
               [Column_Key_Int_Radix, 10],
               [Column_Key_Sort_Descending, True]],
              [[Column_Key_Name, "Steps"],
               [Column_Key_Description, "Number of steps in this mode"],
               [Column_Key_Int_Radix, 10],
               [Column_Key_Sort_Descending, True],
               [Column_Key_Footer_Sum, True],
               [Column_Key_Generate_Percent_Column, []],
               [Column_Key_Generate_Acc_Percent_Column, []],
               ]]]]

SIM_register_interface("x86_mode_histogram_connection", "table",
                       table_interface_t(
                           data = histogram_data,
                           properties = histogram_properties))

def aggregate_histograms(connections):
    h = {}
    for con in connections:
        for [mode, c] in con.iface.table.data():
            h[mode] = h.get(mode, 0) + c
    return list(h.items())

def histogram_cmd(obj, *table_args):
    data = aggregate_histograms(obj.connections)
    prop = histogram_properties(None)
    show(prop, data, *table_args)

new_table_command("histogram", histogram_cmd,
                  args = [],
                  cls = "x86_mode_histogram",
                  type = ["Instrumentation"],
                  short = "print x86 mode histogram",
                  doc = """
Show aggregated x86 mode histogram for all connected processors. The
histogram shows how many instructions that have been executed in the
System Management mode, Vmx Root mode and Non-Root mode, and the
various 16/32/64 bit execution modes, and combinations thereof.""")

def con_probe_value(obj):
    return histogram_data(obj)

def con_probe_properties(obj):
    probe_name = f"{obj.tool.classname}.{obj.tool.name}.histogram"
    return [[Probe_Key_Kind, f"cpu.tool.{probe_name}"],
            [Probe_Key_Display_Name, "X86 Mode"],
            [Probe_Key_Description, "Steps executed in different x86 modes"],
            [Probe_Key_Width, 40],
            [Probe_Key_Type, "histogram"],
            [Probe_Key_Owner_Object, obj.cpu],
            [Probe_Key_Categories, ["x86", "cpu", "smm", "vmx", "execution-mode",
                                    "16bit", "32bit", "64bit"]],
            [Probe_Key_Aggregates, [
                [
                    [Probe_Key_Kind, f"sim.tool.{probe_name}"],
                    [Probe_Key_Aggregate_Scope, "global"],
                    [Probe_Key_Owner_Object, conf.sim],
                    [Probe_Key_Aggregate_Function, "sum"],
                    [Probe_Key_Description,
                     "Most frequent mode used on x86 processors,"
                     " monitored by an x86-mode-histogram tool"]
                ],
                [
                    [Probe_Key_Kind, f"cell.tool.{probe_name}"],
                    [Probe_Key_Aggregate_Scope, "cell"],
                    [Probe_Key_Aggregate_Function, "sum"],
                    [Probe_Key_Description,
                     "Most frequently mode on x86 processors"
                     " in a cell, monitored by an x86-mode-histogram tool"]
                ]
            ]]]

probe_iface = probe_interface_t(
    value = con_probe_value,
    properties = con_probe_properties
)
SIM_register_interface(
    "x86_mode_histogram_connection", 'probe', probe_iface)
