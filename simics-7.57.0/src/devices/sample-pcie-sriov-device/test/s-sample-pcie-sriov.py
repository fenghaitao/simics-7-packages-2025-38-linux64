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


# Tests for the sample PCI SRIOV device.

import info_status
import simics
import stest
import dev_util as du
import conf
# SIMICS-21543
conf.sim.deprecation_level = 0

# Set up a PCIe bus and a sample PCIe device
dp = simics.SIM_create_object('pcie-downstream-port', 'dp')
pci = simics.SIM_create_object('sample_pcie_sriov_device', 'pci')
f0 = simics.SIM_object_descendant(pci, 'f0')
f5 = simics.SIM_object_descendant(pci, 'f5')
dp.devices = [[0, pci]]


# Test the PCI vendor and device IDs
def test_ids():
    stest.expect_equal(pci.f0.PF.bank.pcie_config.vendor_id, 0x104C, "Bad vendor ID")
    stest.expect_equal(pci.f0.PF.bank.pcie_config.device_id, 0xAC10, "Bad device ID")
    stest.expect_equal(pci.f5.PF.bank.pcie_config.vendor_id, 0x104C, "Bad vendor ID")
    stest.expect_equal(pci.f5.PF.bank.pcie_config.device_id, 0xAC10, "Bad device ID")


# Test the registers of the device
def test_regs():
    # test ARI
    next_function = du.Register_LE(pci.f0.PF.bank.pcie_config, 0x100 + 0x05, size=1)
    stest.expect_equal(next_function.read(), 5)  # next PF
    next_function = du.Register_LE(pci.f5.PF.bank.pcie_config, 0x100 + 0x05, size=1)
    stest.expect_equal(next_function.read(), 0)  # no more PFs


# Test setting BAR to map the device in memory
def test_mapping():
    cmd_reg = du.Register(pci.f0.PF.bank.pcie_config, 0x4, 0x2)  # PCI command register
    bar01_reg = du.Register(pci.f0.PF.bank.pcie_config, 0x10, 0x8)  # PCI BAR01 register
    bar45_reg = du.Register(pci.f0.PF.bank.pcie_config, 0x20, 0x8)  # PCI BAR45 register

    bar01_addr = 0x1000          # 4K aligned
    bar45_addr = 0x200000        # 1M aligned
    bar01_reg.write(bar01_addr)  # Map bank at addr
    bar45_reg.write(bar45_addr)  # Map bank at addr
    cmd_reg.write(2)             # Enable memory access
    stest.expect_equal(dp.mem_space.map[0][1], pci.f0.PF.bank.bar01,
                       "PCI device should have been mapped")

    mem_read = dp.mem_space.iface.memory_space.read
    stest.expect_equal(du.tuple_to_value_le(
            mem_read(None, bar01_addr + 0x10, 4, 0)),
                       0x4711, "expected to read foo register")
    stest.expect_equal(du.tuple_to_value_le(
            mem_read(None, bar45_addr + 0x20, 4, 0)),
                       0x1337, "expected to read bar register")


# Test enabling VF
def test_sriov():
    sriov_base = 0x160
    pfs = [pci.f0.PF.bank.pcie_config, pci.f5.PF.bank.pcie_config]
    total_pfs = len(pfs)

    def enable_sriov_vfs(pfs, num_vfs):
        for pf in pfs:
            num_vfs_reg = du.Register_LE(pf, sriov_base + 0x10, size=2)
            num_vfs_reg.write(num_vfs)

            system_page_size_reg = du.Register_LE(pf, sriov_base + 0x20,
                                                  size=4)
            system_page_size = 64 * 1024
            system_page_size_reg.write(system_page_size >> 12)

            control_reg = du.Register_LE(pf, sriov_base + 0x8,
                                         bitfield=du.Bitfield({
                                             'vf_enable': 0}, bits=16))
            control_reg.vf_enable = 1

    def disable_sriov_vfs(pfs):
        for pf in pfs:
            control_reg = du.Register_LE(pf, sriov_base + 0x8,
                                         bitfield=du.Bitfield({
                                             'vf_enable': 0}, bits=16))
            control_reg.vf_enable = 0

    # Set the value of PF0's ARI Capable Hierarchy field, as it affects all
    # the other PFs, and this field of the other PFs is Read Only Zero
    pf0_control_reg = du.Register_LE(pci.f0.PF.bank.pcie_config, sriov_base + 0x8,
                                     bitfield=du.Bitfield({
                                         'arich': 4}, bits=16))
    pf0_control_reg.arich = 1

    # Enable SR-IOV VFs and check the mappings in the PCIe config space
    before_conf = len(dp.cfg_space.map)
    total_vfs = du.Register_LE(pci.f0.PF.bank.pcie_config, sriov_base + 0xe, size=2).read()
    for num_vfs in [1, total_vfs]:
        enable_sriov_vfs(pfs, num_vfs)
        after_conf = len(dp.cfg_space.attr.map)
        stest.expect_equal(after_conf - before_conf, total_pfs * num_vfs,
                           'VFs mapped in config space')

        # test for overlap (incorrect stride & offset in model)
        offsets = []
        for offset in [offset for (offset, _, _, _, _,
                                   _, _, _, _) in dp.cfg_space.map]:
            stest.expect_true(offset not in offsets, 'Duplicate offset')
            offsets.append(offset)

        # test for correct mapping of port arrays
        if num_vfs > 1:
            (offset, obj, *tail) = dp.cfg_space.map[-1]
            stest.expect_equal(obj, f5.VF[5].bank.pcie_config)

        disable_sriov_vfs(pfs)
        stest.expect_equal(
            len(dp.cfg_space.attr.map), before_conf, 'VFs not disabled')


def test_info_status_commands():
    # Verify that info/status commands have been registered for all
    # classes in this module.
    info_status.check_for_info_status(['sample-pcie-sriov-device'])

    # Run info and status commands. It is difficult to test whether the output
    # is informative, so we just check that the commands complete nicely.
    pci.cli_cmds.info()
    pci.cli_cmds.status()


test_ids()
test_regs()
test_mapping()
test_sriov()
test_info_status_commands()
