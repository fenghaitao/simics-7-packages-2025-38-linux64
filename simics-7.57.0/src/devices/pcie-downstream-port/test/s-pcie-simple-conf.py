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
import simics
import stest
import random
random.seed("Guantanemera")

board = simics.SIM_create_object('rc_with_eps', 'board', [])
simics.SIM_run_command('instantiate-components')
rc = board.rc
dp = rc.dp

mem = simics.SIM_create_object(
    'set-memory', 'smem', [['value', random.randrange(0x100)]])
downstream_spaces = {simics.PCIE_Type_IO: dp.io_space,
                     simics.PCIE_Type_Mem: dp.mem_space,
                     simics.PCIE_Type_Cfg: dp.cfg_space}
upstream_ifc = dp.iface.pcie_map
upstream_mt = simics.SIM_new_map_target(dp, None, None)
downstream_mt = simics.SIM_new_map_target(dp.port.downstream, None, None)
port_cfg_ifc = dp.iface.pcie_port_control


def map_info(**kwargs):
    # if base + length exceeds (1 << 64) memory-space silently fails to map
    kwargs['length'] = random.randrange((1 << 64) - kwargs['base'])
    return simics.map_info_t(**kwargs)


def bdf(b, df):
    return (b << 8 | df)


# Test that we can access the config space of each EP and that the
# access is made with 'local' address and with device_id atom appended
t = simics.transaction_t(read=True, size=1, pcie_type=simics.PCIE_Type_Cfg)
sec_bus = [0, random.randrange(2, 255), 255]
for sb in sec_bus:
    port_cfg_ifc.set_secondary_bus_number(sb)
    for (df, ep) in dp.devices:
        ep.tx_val = random.randrange(255)

        b = sb
        offset = random.randrange(1 << 16)
        addr = (bdf(b, df) << 16) + offset
        exc = simics.SIM_issue_transaction(downstream_mt, t, addr)
        stest.expect_equal(exc, simics.Sim_PE_No_Exception)
        stest.expect_equal(t.value_le, ep.tx_val)
        stest.expect_equal(ep.tx_addr, offset)
        stest.expect_equal(ep.device_id, bdf(b, df))
        ep.tx_addr = None

        # Test getting our device_id
        device_id = upstream_ifc.get_device_id(ep)
        stest.expect_equal(device_id, bdf(b, df))

        # Test removing our Cfg map (not recommended, but possible)
        devfn = device_id & 0xff
        upstream_ifc.del_map(ep, devfn << 16, simics.PCIE_Type_Cfg)

        b = sb
        offset = random.randrange(1 << 16)
        addr = (bdf(b, df) << 16) + offset
        ep.tx_val = 0
        ep.tx_addr = None
        ep.tx_type = None
        exc = simics.SIM_issue_transaction(downstream_mt, t, addr)
        stest.expect_equal(exc, simics.Sim_PE_No_Exception)
        stest.expect_equal(t.value_le, 0xff)
        stest.expect_equal(ep.tx_addr, None)
        stest.expect_equal(ep.tx_type, None)

        # Restore Cfg map
        nfo = simics.map_info_t(base=devfn << 16, length=1 << 16)
        upstream_ifc.add_map(ep, nfo, simics.PCIE_Type_Cfg)

        # Test that access outside of device cfg space return 0xff
        b = 1
        offset = random.randrange(1 << 16)
        addr = (bdf(b, df) << 16) + offset
        exc = simics.SIM_issue_transaction(downstream_mt, t, addr)
        stest.expect_equal(exc, simics.Sim_PE_No_Exception)
        stest.expect_equal(t.value_le, 0xff)
        stest.expect_equal(ep.tx_addr, None)

        # Test that a device can claim other addresses on the local bus
        b = sb
        offset = random.randrange(1 << 24)
        nfo = simics.map_info_t(base=offset, length=1)
        upstream_ifc.add_map(ep, nfo, simics.PCIE_Type_Cfg)

        addr = (bdf(b, 0) << 16) + offset
        ep.tx_val = random.randrange(255)
        exc = simics.SIM_issue_transaction(downstream_mt, t, addr)
        stest.expect_equal(exc, simics.Sim_PE_No_Exception)
        stest.expect_equal(t.value_le, ep.tx_val)
        stest.expect_equal(ep.tx_addr, 0)
        stest.expect_equal(ep.device_id, addr >> 16)

port_cfg_ifc.set_secondary_bus_number(0)

# Test claiming and accessing some ranges in the downstream space
for (kind, ms) in downstream_spaces.items():
    exp_map = list(ms.map)
    for _ in range(3):
        nfo = map_info(base=random.randrange(1 << 64),
                       start=random.randrange(1 << 64),
                       function=random.randrange(1 << 31),
                       priority=random.randrange(-(1 << 15), 1 << 15))
        upstream_ifc.add_map(mem, nfo, kind)
        addr = nfo.base + random.randrange(nfo.length)

        # Access through shortcut
        val = ms.iface.memory_space.read(None, addr, 1, 0)
        stest.expect_equal(val[0], mem.value)

        # Access through general transaction
        t.pcie_type = kind
        exc = simics.SIM_issue_transaction(downstream_mt, t, addr)
        stest.expect_equal(exc, simics.Sim_PE_No_Exception)
        stest.expect_equal(t.value_le, mem.value)

        exp_map += [[nfo.base, mem, nfo.function, nfo.start, nfo.length, None,
                     nfo.priority, 8, 0]]
        stest.expect_equal(sorted(ms.map), sorted(exp_map))

# Test unclaiming the ranges
for (kind, ms) in downstream_spaces.items():
    f = lambda x: x[1] == mem
    exp_map = sorted(list(filter(f, ms.map)))
    stest.expect_equal(len(exp_map), 3)
    while exp_map:
        map_entry = exp_map.pop(random.randrange(len(exp_map)))
        upstream_ifc.del_map(map_entry[1], map_entry[0], kind)
        got_map = sorted(list(filter(f, ms.map)))
        stest.expect_equal(got_map, exp_map)

# Test sending some messages:
t = simics.transaction_t(pcie_type=simics.PCIE_Type_Msg, size=1)

# Route by ID:
t.pcie_msg_route = simics.PCIE_Msg_Route_ID
for (df, ep) in dp.devices:
    t.pcie_msg_type = random.randrange(0x100)
    offset = random.randrange(1 << 48)
    addr = (bdf(0, df) << 48) + offset
    exc = simics.SIM_issue_transaction(downstream_mt, t, addr)
    stest.expect_equal(exc, simics.Sim_PE_No_Exception)
    stest.expect_equal(ep.tx_addr, offset)
    stest.expect_equal(ep.msg_type, t.pcie_msg_type)
    for (*dontcare, other_ep) in dp.devices:
        if (other_ep != ep):
            stest.expect_different(other_ep.tx_addr, offset)
            stest.expect_different(other_ep.msg_type, t.pcie_msg_type)
    ep.msg_type = None
    ep.tx_addr = None
    ep.msg_type = None

# Add a virtual EP
vep = simics.pre_conf_object('vep', 'fake_pcie_device')
simics.SIM_add_configuration([vep], None)
vep = simics.SIM_get_object(vep.name)
vdf = random.randrange(256)  # find a unique devfn
while vdf in [df for (df, ep) in dp.devices]:
    vdf = random.randrange(256)
dp.iface.pcie_map.add_function(vep, vdf)

# And send a message to it
t.pcie_msg_type = random.randrange(0x100)
offs = random.randrange(1 << 48)
addr = (vdf << 48) + offs
exc = simics.SIM_issue_transaction(downstream_mt, t, addr)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)
stest.expect_equal(vep.tx_addr, offs)
stest.expect_equal(vep.msg_type, t.pcie_msg_type)
for (*dontcare, ep) in dp.devices:
    stest.expect_different(ep.tx_addr, addr)
    stest.expect_different(ep.msg_type, t.pcie_msg_type)
vep.tx_addr = None
vep.msg_type = None

# Disable/enable it
dp.iface.pcie_map.disable_function(vdf)
exc = simics.SIM_issue_transaction(downstream_mt, t, addr)
stest.expect_equal(exc, simics.Sim_PE_IO_Not_Taken)
dp.iface.pcie_map.enable_function(vdf)
exc = simics.SIM_issue_transaction(downstream_mt, t, addr)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)


# Broadcast
t.pcie_msg_route = simics.PCIE_Msg_Route_Broadcast
t.pcie_msg_type = random.randrange(0x100)
exc = simics.SIM_issue_transaction(downstream_mt, t, 0)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)
for (*dontcare, ep) in dp.devices:
    stest.expect_equal(ep.tx_addr, 0)
    stest.expect_equal(ep.msg_type, t.pcie_msg_type)
# Should reach the virtual EP too
stest.expect_equal(vep.tx_addr, 0)
stest.expect_equal(vep.msg_type, t.pcie_msg_type)

# Remove it
dp.iface.pcie_map.del_function(vep, vdf)
t.pcie_msg_route = simics.PCIE_Msg_Route_ID
exc = simics.SIM_issue_transaction(downstream_mt, t, vdf << 48)
stest.expect_equal(exc, simics.Sim_PE_IO_Not_Taken)

# Upstream messages are just forwarded to upstream_target:
t.pcie_msg_route = random.randrange(0x100)
t.pcie_msg_type = random.randrange(0x100)
addr = random.randrange(1 << 64)
exc = simics.SIM_issue_transaction(upstream_mt, t, addr)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)
stest.expect_equal(rc.tx_addr, addr)
stest.expect_equal(rc.msg_type, t.pcie_msg_type)
