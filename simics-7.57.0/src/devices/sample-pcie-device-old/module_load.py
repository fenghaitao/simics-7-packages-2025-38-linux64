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

import deprecation
import simics
from cli import new_info_command, new_status_command
import pci_common

def info(obj):
    return []

def status(obj):
    return [ (None,
              [("Power indicator", obj.attr.power_indicator),
               ("Attention indicator", obj.attr.attention_indicator)])]

new_info_command("sample_pcie_device_old", info)
new_status_command("sample_pcie_device_old", status)
pci_common.new_pci_config_regs_command('sample_pcie_device_old', None)
