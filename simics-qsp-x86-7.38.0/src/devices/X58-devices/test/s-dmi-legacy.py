# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from simics import SIM_create_object
from legacy_common import compare_devs


dp = SIM_create_object('pcie-downstream-port-legacy', 'dp', [])
old_dev = SIM_create_object('x58_dmi', 'old', [["pci_bus", dp]])
new_dev = SIM_create_object('x58-dmi', 'new', [])

# The diff for registers at these offsets have been verified
accepted_diffs = {0x4: 0x100000}

compare_devs(new_dev.bank.pcie_config, old_dev.bank.pci_config, accepted_diffs)
