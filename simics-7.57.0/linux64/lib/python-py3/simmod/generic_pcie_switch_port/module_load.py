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


import simics
import deprecation
import pci_common
import cli
import sim_commands

cli.new_info_command(
    'generic_pcie_switch_port', sim_commands.get_pci_info)
cli.new_status_command(
    'generic_pcie_switch_port', sim_commands.get_pci_status)
pci_common.new_pci_config_regs_command('generic_pcie_switch_port', None)

deprecation.DEPRECATED(
    simics.SIM_VERSION_7,
    "This port uses the old PCIe library which is deprecated.",
    "A port can be implemented using the pcie_root_port template found in the new PCIe library",
)
