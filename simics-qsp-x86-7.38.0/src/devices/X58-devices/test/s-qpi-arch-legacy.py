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
ms = SIM_create_object('memory-space', 'ms', [])
old_qpi = [SIM_create_object('x58_qpi_ncr_f0', 'old_f0', [["pci_bus", dp]]),
           SIM_create_object('x58_qpi_sad_f1', 'old_f1',
                             [["pci_bus", dp],
                              ["socket_id", 0],
                              ["socket_pci_config", ms]])]

new_qpi = SIM_create_object('x58-qpi-arch', 'new',
                            [["cfg_space", dp.cfg_space]])

new_banks = [new_qpi.bank.f0, new_qpi.bank.f1]
old_banks = [d.bank.pci_config for d in old_qpi]

# The diff for registers at these offsets have been verified
accepted_diffs = {0x8: 0x6000000}

for new_dev, old_dev in zip(new_banks, old_banks):
    compare_devs(new_dev, old_dev, accepted_diffs)
