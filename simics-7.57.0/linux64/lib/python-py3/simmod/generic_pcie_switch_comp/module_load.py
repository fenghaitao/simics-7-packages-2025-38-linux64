# © 2015 Intel Corporation
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
from . import generic_pcie_switch_comp
generic_pcie_switch_comp.generic_pcie_switch.register()

deprecation.DEPRECATED(
    simics.SIM_VERSION_7,
    "This switch uses ports written with the old PCIe library which is deprecated.",
    "The standard-pcie-switch is a generic PCIe switch written with the new PCIe library",
)
