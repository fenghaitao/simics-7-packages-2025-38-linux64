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
abus = SIM_create_object('apic-bus', 'abus', [['apics', []]])
ioapic = SIM_create_object('io-apic', 'ioapic', [['apic_bus', abus]])
old_dev = SIM_create_object('x58_ioxapic', 'old', [['pci_bus', dp],
                                                   ['ioapic', ioapic]])
new_dev = SIM_create_object('x58-ioxapic', 'dev',
                            [['ioapic.apic_bus', abus]])

simics.SIM_run_command('log-level 4')
compare_devs(new_dev.bank.pcie_config, old_dev.bank.pci_config)
