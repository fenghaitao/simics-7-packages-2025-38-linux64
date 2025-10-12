# © 2023 Intel Corporation
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
import stest
import legacy_upstream_pcie_adapter_common

import dev_util


PCIE_Vendor_Defined_Type_0 = 0x7e

PCIE_Type_Mem = 1
Sim_Addr_Space_Memory = 2


def test_config(ep1, up):
    ep1.pcie_config.iface.memory_space.write(None, 0, (0x12, 0x34), False)

    # Read the bytes using the legacy pci-bus
    bytes = up.conf_space.iface.memory_space.read(
        None, up.secondary_bus_number << 20, 2, False)
    stest.expect_equal(bytes, (0x12, 0x34))


def test_upstream_maps(adapter, up, ep1):
    nfo = simics.map_info_t(base=0xf00000, length=0x100)
    adapter.impl.port.downstream.iface.pcie_map.add_map(ep1.bar_mapped, nfo,
                                                        PCIE_Type_Mem)
    stest.expect_equal(up.mem_space.map[0][0], 0xf00000)
    stest.expect_equal(up.mem_space.map[0][1], ep1.bar_mapped_bank_map)


def test_mem(ep1, up):
    ep1.bar_mapped.iface.memory_space.write(None, 0, (0x56, 0x78), False)
    bytes = up.mem_space.iface.memory_space.read(None, 0xf00000, 2, False)
    stest.expect_equal(bytes, (0x56, 0x78))


def test_msg(adapter, up):
    msg = "hello"
    msg = [byte for byte in msg.encode()]
    adapter.impl.port.downstream.downstream_port.port.broadcast.log_level = 2
    with stest.expect_log_mgr(log_type="info", regex="Message broadcast"):
        adapter.iface.pci_express.send_message(up, PCIE_Vendor_Defined_Type_0,
                                               msg)
    adapter.impl.port.downstream.downstream_port.port.broadcast.log_level = 1


def test_upstream_req(adapter, up, ep1):
    mt = simics.SIM_new_map_target(adapter.impl.port.downstream, None, None)
    t = simics.transaction_t(read=True, size=4, data=bytes(4),
                             pcie_type=PCIE_Type_Mem, initiator=ep1, pcie_requester_id=0x201)
    simics.SIM_issue_transaction(mt, t, 0x1337)
    stest.expect_equal(up.upstream_request_space, Sim_Addr_Space_Memory)
    stest.expect_equal(up.upstream_request_size, 4)
    stest.expect_equal(up.upstream_request_address, 0x1337)
    stest.expect_equal(up.upstream_rid, 0x201)


def test_reset(ep1, up):
    stest.expect_equal(ep1.has_been_reset, False)
    up.iface.pci_bus.bus_reset()
    stest.expect_equal(ep1.has_been_reset, True)
    ep1.has_been_reset = False


def test_multi_function_ep():
    adapter = legacy_upstream_pcie_adapter_common.create_legacy_upstream_pcie_adapter(
        "adapter1")
    up = legacy_upstream_pcie_adapter_common.create_fake_legacy_upstream("up1")
    mf_ep = simics.SIM_create_object("test-pcie-mf-endpoint", "mf_ep")
    adapter.pci_bus = up
    up.pci_devices = [[0, 0, adapter, 1]]
    adapter.devices = [[0, 0, mf_ep]]

    f0 = dev_util.bank_regs(mf_ep.bank.f[0])
    f1 = dev_util.bank_regs(mf_ep.bank.f[1])
    f0.vendor_id.get_set_reg.write(0x1337)
    f1.vendor_id.get_set_reg.write(0x1234)

    bytes = up.conf_space.iface.memory_space.read(
        None, up.secondary_bus_number << 20, 2, False)
    stest.expect_equal(bytes, (0x37, 0x13))
    bytes = up.conf_space.iface.memory_space.read(
        None, (up.secondary_bus_number << 20) | (1 << 12), 2, False)
    stest.expect_equal(bytes, (0x34, 0x12))


def test_rp():
    adapter = legacy_upstream_pcie_adapter_common.create_legacy_upstream_pcie_adapter(
        "adapter2")
    up = legacy_upstream_pcie_adapter_common.create_fake_legacy_upstream("up2")
    rp = simics.SIM_create_object("test-pcie-root-port", "rp")
    adapter.pci_bus = up
    up.pci_devices = [[0, 0, adapter, 1]]
    adapter.devices = [[0, 0, rp]]

    pcie_config = dev_util.bank_regs(rp.bank.pcie_config)
    pcie_config.secondary_bus_number.write(1)
    pcie_config.subordinate_bus_number.write(3)
    # Now re-write to ensure no duplicate maps occur
    pcie_config.subordinate_bus_number.write(4)

    stest.expect_equal(
        up.conf_space.map[0],
        [1048576, adapter, 255, 0x100000, 0x1000000, None, 0, 0, 0])
    stest.expect_equal(len(up.conf_space.map), 1)


def main():
    adapter = legacy_upstream_pcie_adapter_common.create_legacy_upstream_pcie_adapter(
        "adapter")
    ep1 = legacy_upstream_pcie_adapter_common.create_fake_pcie_ep("ep1")
    up = legacy_upstream_pcie_adapter_common.create_fake_legacy_upstream("up")

    adapter.pci_bus = up
    up.pci_devices = [[0, 0, adapter, 1]]
    with stest.expect_log_mgr(log_type="error", regex="The adapter only"):
        with stest.expect_exception_mgr(simics.SimExc_IllegalValue):
            adapter.devices = [[1, 0, ep1]]
    adapter.devices = [[0, 0, ep1]]

    test_config(ep1, up)
    test_upstream_maps(adapter, up, ep1)
    test_mem(ep1, up)
    test_msg(adapter, up)
    test_upstream_req(adapter, up, ep1)
    test_reset(ep1, up)
    test_multi_function_ep()
    test_rp()


main()
