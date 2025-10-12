# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import cli
import simics
from deprecation import DEPRECATED

# Common functionality for PCI devices

def get_pci_info(obj):
    info = [("PCI bus",  obj.attr.pci_bus)]
    return [(None, info)]

def get_pci_status(obj):
    return []

def hex_str(val, size): return "%0*x" % (size, val)

def print_config_regs_cmd(obj, verbose):
    reg_info = obj.attr.config_register_info
    config_regs = obj.attr.config_registers
    regs = []
    for i in range(len(reg_info)):
        val = 0
        for j in range(reg_info[i][2]):
            word_indx = (reg_info[i][0] + j) // 4
            byte_indx = (reg_info[i][0] + j) - word_indx*4
            word_val = config_regs[word_indx]
            byte_val = (word_val >> (byte_indx * 8)) & 0xff
            val = val | (byte_val << (j * 8))
        regs.append(["0x%02x" % reg_info[i][0], reg_info[i][1], reg_info[i][2], hex_str(reg_info[i][3], reg_info[i][2] * 2), hex_str(val, reg_info[i][2] * 2)])
    if verbose:
        cli.print_columns([cli.Just_Left, cli.Just_Left, cli.Just_Left,
                           cli.Just_Left, cli.Just_Left],
                      [ [ "Offset", "Name", "Size", "Write-mask", "Value" ] ] + regs)
    else:
        cli.print_columns([cli.Just_Left, cli.Just_Left, cli.Just_Left],
                      [ [ "Offset", "Name", "Value" ] ] + [[x[0], x[1], x[4]] for x in regs])

# ------------- command registration --------------

def new_pci_commands(device_name):
    if simics.SIM_class_has_attribute(device_name, "config_register_info") and simics.SIM_class_has_attribute(device_name, "config_registers"):
        cli.new_command("print-config-regs", print_config_regs_cmd,
                    [cli.arg(cli.flag_t, "-v")],
                    short = "print configuration registers",
                    cls = device_name,
                    doc = """
                    Print the PCI device's configuration space registers. Use
                    the <arg>-v</arg> flag for more verbose output.
                    """)

def new_pci_config_regs_command(cls, get_conf = None):
    DEPRECATED(
        simics.SIM_VERSION_7,
        "Calling 'new_pci_config_regs_command' is deprecated and has no"
        " effect.", "Use print-device-regs command instead.")
