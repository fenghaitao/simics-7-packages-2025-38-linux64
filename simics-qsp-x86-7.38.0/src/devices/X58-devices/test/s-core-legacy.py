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


import simics
from legacy_common import compare_devs

dev = simics.SIM_create_object('x58-core', 'dev', [])
dp = simics.SIM_create_object('pcie-downstream-port-legacy', 'dp', [])
ru0 = simics.SIM_create_object('x58_remap_unit0', 'ru0', [])
ru1 = simics.SIM_create_object('x58_remap_unit1', 'ru1', [])
f0 = simics.SIM_create_object('x58_core_f0', 'f0', [['pci_bus', dp],
                                                    ['remap_unit0', ru0],
                                                    ['remap_unit1', ru1]])
f1 = simics.SIM_create_object('x58_core_f1', 'f1', [['pci_bus', dp]])
f2 = simics.SIM_create_object('x58_core_f2', 'f2', [['pci_bus', dp]])
f3 = simics.SIM_create_object('x58_core_f3', 'f3', [['pci_bus', dp]])

# The diff for registers at these offset have been verified
accepted_diffs = {dev.bank.f0: {0x40: 0x920010},
                  dev.bank.f1: {0x40: 0x920010},
                  dev.bank.f2: {0x40: 0x920010}}

for (new_dev, old_dev) in zip([getattr(dev.bank, f'f{d}') for d in range(4)],
                              [f.bank.pci_config for f in (f0, f1, f2, f3)]):
    diffs = accepted_diffs.get(new_dev, {})
    compare_devs(new_dev, old_dev, diffs)
