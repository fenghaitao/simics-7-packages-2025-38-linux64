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
old_qp = [SIM_create_object('x58_qpi_port0_f0', 'p0_f0', [["pci_bus", dp]]),
          SIM_create_object('x58_qpi_port0_f1', 'p0_f1', [["pci_bus", dp]]),
          SIM_create_object('x58_qpi_port1_f0', 'p1_f0', [["pci_bus", dp]]),
          SIM_create_object('x58_qpi_port1_f1', 'p1_f1', [["pci_bus", dp]])]

new_qp = [SIM_create_object('x58-qpi-port', 'p0', []),
          SIM_create_object('x58-qpi-port', 'p1', [])]
new_qp[0].bank.pcie_config[0].device_id = 0x3425
new_qp[0].bank.pcie_config[1].device_id = 0x3426
new_qp[1].bank.pcie_config[0].device_id = 0x3427
new_qp[1].bank.pcie_config[1].device_id = 0x3428


new_banks = list(new_qp[0].bank.pcie_config) + list(new_qp[1].bank.pcie_config)
old_banks = [d.bank.pci_config for d in old_qp]

# The diff for registers at these offsets have been verified
accepted_diffs = {0x8: 0x8000013,
                  0xc: 0x800000}

for new_dev, old_dev in zip(new_banks, old_banks):
    compare_devs(new_dev, old_dev, accepted_diffs)
