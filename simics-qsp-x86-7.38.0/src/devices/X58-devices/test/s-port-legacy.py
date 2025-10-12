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


def create_new_port(bus, port_index, link_width):
    return SIM_create_object('x58-pcie-port', f'new_dev{port_index}',
                             [["port_index", port_index],
                              ["link_width", link_width]])


def create_old_port(bus, port_index, link_width):
    status = ((link_width << 4) | 0x1)
    cap = ((link_width << 4) | 0x393C01)
    return SIM_create_object('x58-pcie-port-legacy', f'old_dev{port_index}',
                             [["pci_bus", dp],
                              ["secondary_bus", dp],
                              ["pci_config_device_id", 0x3407 + port_index],
                              ["pci_config_exp_link_status", status],
                              ["pci_config_exp_link_cap", cap]])


port_args = ((1, 2), (2, 2), (3, 4), (4, 4), (5, 8), (7, 16))
dp = SIM_create_object('pcie-downstream-port-legacy', 'dp', [])
new_ports = [create_new_port(dp, pi, lw) for (pi, lw) in port_args]
old_ports = [create_old_port(dp, pi, lw) for (pi, lw) in port_args]

# The diff for registers at these offsets have been verified
accepted_diffs = {0x60: 0x1029005,
                  0x90: 0x142e010}

for new_dev, old_dev in zip(new_ports, old_ports):
    compare_devs(
        new_dev.bank.pcie_config, old_dev.bank.pci_config, accepted_diffs)
