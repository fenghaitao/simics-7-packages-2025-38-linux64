# © 2012 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Tests for the sample PCI device.

import stest
import dev_util as du
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

# Set up a PCI bus and a sample PCI device
pci_conf = SIM_create_object('memory-space', 'pci_conf')
pci_io = SIM_create_object('memory-space', 'pci_io')
pci_mem = SIM_create_object('memory-space', 'pci_mem')
# unused PCI bridge, required by bus
pci_bridge = du.Dev([du.iface('pci_bridge')])


pci_bus = SIM_create_object('pci-bus', 'pci_bus',
                            conf_space=pci_conf,
                            io_space=pci_io,
                            memory_space=pci_mem,
                            bridge=pci_bridge.obj)


pci = SIM_create_object('sample_pci_device', 'sample_pci',
                        [['pci_bus', pci_bus]])


# Test the PCI vendor and device IDs
def test_ids():
    stest.expect_equal(pci.attr.pci_config_vendor_id, 0x104c, "Bad vendor ID")
    stest.expect_equal(pci.attr.pci_config_device_id, 0xac10, "Bad device ID")


# Test the registers of the device
def test_regs():
    version = du.Register_LE(pci.bank.regs, 0x10)
    stest.expect_equal(version.read(), 0x4711)


# Test setting BAR to map the device in memory
def test_mapping():
    # PCI command register
    cmd_reg = du.Register_LE(pci.bank.pci_config, 0x4, 0x2)
    # PCI BAR register
    bar_reg = du.Register_LE(pci.bank.pci_config, 0x10, 0x4)

    addr = 0x100
    cmd_reg.write(2)     # Enable memory access
    bar_reg.write(addr)  # Map bank at addr
    stest.expect_equal(pci_mem.attr.map[0][1], pci.bank.regs,
                       "PCI device should have been mapped")

    value_bytes = pci_mem.iface.memory_space.read(None, addr + 0x10, 4, 0)
    stest.expect_equal(int.from_bytes(value_bytes, 'little'), 0x4711)


test_ids()
test_regs()
test_mapping()

print("All tests passed.")
