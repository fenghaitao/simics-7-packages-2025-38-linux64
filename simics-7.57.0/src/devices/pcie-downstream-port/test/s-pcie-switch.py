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


import pcie_downstream_port_common
import random
import simics
import stest

random.seed("Povel Ramel")
board = simics.SIM_create_object('rc_with_switch', 'board', [])
simics.SIM_run_command('instantiate-components')
rc = board.root_complex
sw = board.switch

# SW sets the secondary bus number of the Root Port
rc_sec_num = random.randrange(1, 256)
rc_sub_num = rc_sec_num + 1 + len(sw.dp.devices)
rc_control = rc.dp.iface.pcie_port_control
rc_control.set_secondary_bus_number(rc_sec_num)
# SW should now be able to write to the Cfg-space of the Switch
# upstream port
t = simics.transaction_t(read=True, size=1)
cfg_mt = simics.SIM_new_map_target(rc.dp.port.cfg, None, None)
b = rc_sec_num
d = 0
f = 0
base = (b << 8 | d << 3 | f) << 16
offs = random.randrange(1 << 16)
addr = base + offs
exp_addr = offs
sw.tx_val = random.randrange(255)
exc = simics.SIM_issue_transaction(cfg_mt, t, addr)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)
stest.expect_equal(sw.tx_addr, exp_addr)
stest.expect_equal(t.value_le, sw.tx_val)

# Software configures the secondary and subordinate bus number in the
# Switch Upstream Port which reacts by claiming/mapping the config
# space bounded by sec and sub bus number in the cfg-space of the root
# port
sw_sec_num = rc_sec_num + 1
sw_sub_num = rc_sub_num
tgt = sw.dp.port.cfg
base = sw_sec_num << 24
limit = (sw_sub_num + 1) << 24
size = limit - base
nfo = simics.map_info_t(base=base, start=base, length=size)
sw_control = sw.dp.iface.pcie_port_control
sw_control.set_secondary_bus_number(sw_sec_num)
rc.dp.iface.pcie_map.add_map(tgt, nfo, simics.PCIE_Type_Cfg)

# We should now be able to reach the config-space of the
# switch-internal devices, i.e. the virtual PCI-PCI bridges
t = simics.transaction_t(read=True, size=1)
cfg_mt = simics.SIM_new_map_target(rc.dp.port.cfg, None, None)
for (d, f, iep) in sw.dp.devices:
    iep.tx_val = random.randrange(255)
    b = sw_sec_num
    base = (b << 8 | d << 3 | f) << 16
    offs = random.randrange(1 << 16)
    addr = base + offs
    exp_addr = offs
    exc = simics.SIM_issue_transaction(cfg_mt, t, addr)
    stest.expect_equal(exc, simics.Sim_PE_No_Exception)
    stest.expect_equal(iep.tx_addr, exp_addr)
    stest.expect_equal(t.value_le, iep.tx_val)

# Since we can reach the switch-internal devices, SW can configure the
# sec and (sub) bus numbers of the virtual PCI-PCI bridges in the
# switch. The bridges react by claiming/mapping the config spaces of
# bounded by these numbers
b = sw_sec_num
for (_, _, iep) in sw.dp.devices:
    b += 1
    tgt = iep.dp.port.cfg
    base = b << 24
    size = 1 << 24
    nfo = simics.map_info_t(base=base, start=base, length=size)
    iep.dp.iface.pcie_port_control.set_secondary_bus_number(b)
    sw.dp.iface.pcie_map.add_map(tgt, nfo, simics.PCIE_Type_Cfg)

# We should now be able to reach the config-space of the EP's
# connected to the switch
b = sw_sec_num
for (_, _, iep) in sw.dp.devices:
    b += 1
    for (d, f, ep) in iep.dp.devices:
        bdf = (b << 8) | (d << 3) | f
        base = bdf << 16
        offs = random.randrange(1 << 16)
        addr = base + offs
        ep.tx_val = random.randrange(255)
        exp_addr = offs
        exc = simics.SIM_issue_transaction(cfg_mt, t, addr)
        stest.expect_equal(exc, simics.Sim_PE_No_Exception)
        stest.expect_equal(ep.tx_addr, exp_addr)
        stest.expect_equal(ep.device_id, bdf)
        stest.expect_equal(t.value_le, ep.tx_val)

# Now that we can configure the EP's we can map some BARs.
mem_mt = simics.SIM_new_map_target(rc.dp.port.mem, None, None)
for (_, _, iep) in sw.dp.devices:
    p = iep.dp
    for (d, f, ep) in p.devices:
        # SW Configures the BAR in the EP, model reacts by add_map to
        # the Switch
        nfo = simics.map_info_t()
        nfo.base = random.randrange(1 << 64)
        nfo.length = random.randrange((1 << 64) - nfo.base)
        ep_up_ifc = p.iface.pcie_map
        ep_up_ifc.add_map(ep, nfo, simics.PCIE_Type_Mem)

        # SW Configures Memory Base and Limit in the Switch Virtual
        # PCI-PCI bridge which reacts by claiming/mapping the range
        # to dp.port.mem in the upstream memory space
        bridge_tgt = p.port.mem
        bridge_up_ifc = rc.dp.iface.pcie_map
        nfo.start = nfo.base  # global address
        bridge_up_ifc.add_map(bridge_tgt, nfo, simics.PCIE_Type_Mem)

        # We should now be able to reach the mapped bar from the RC
        # downstream port memory space
        ep.tx_val = random.randrange(255)
        offset = random.randrange(nfo.length)
        addr = nfo.base + offset
        exc = simics.SIM_issue_transaction(mem_mt, t, addr)
        stest.expect_equal(exc, simics.Sim_PE_No_Exception)
        stest.expect_equal(ep.tx_addr, offset)
        stest.expect_equal(t.value_le, ep.tx_val)

        # Remove all mappings
        ep_up_ifc.del_map(ep, nfo.base, simics.PCIE_Type_Mem)
        bridge_up_ifc.del_map(bridge_tgt, nfo.base, simics.PCIE_Type_Mem)
