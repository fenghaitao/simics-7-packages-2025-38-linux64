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


import dev_util
import simics
import stest
import random
random.seed("Mercy Now")

dp0, dp1 = [simics.SIM_create_object('pcie-downstream-port', f'dp{i}', [])
            for i in (0, 1)]
dev = simics.SIM_create_object('x58-qpi-arch', 'qpi',
                               [['cfg_space', dp0.port.cfg]])
dp1.transparent_enabled = True
dp0.devices = [dp1.port.downstream]
dp1.devices = [[0, dev]]

bf = dev_util.Bitfield_LE({'address': (39, 20), 'sz': (3, 1), 'enable': 0})
pciexbar = dev_util.Register_LE(dev.bank.f1, 0x50, 8, bf)

with stest.expect_log_mgr(dev.bank.f1, 'spec-viol'):
    pciexbar.sz = 3  # invalid size

for (sz, max_bus) in ((7, 63), (6, 127), (0, 255)):
    length = (max_bus + 1) * 1024 * 1024
    socket_id = random.randint(0, max_bus)
    b = max_bus - socket_id
    df = random.randrange(1 << 5) << 3
    bdf = (b << 8) | df

    # setup size and socket-id, check that arch functions are mapped correctly
    dp1.devices = [[df, dev]]
    dev.socket_id = socket_id
    pciexbar.sz = sz

    # try to access device_id in PCIe cfg space
    for (f, bank) in ((0, dev.bank.f0), (1, dev.bank.f1)):
        exp_val = random.randrange(1 << 16)
        bank.device_id = exp_val
        cfg_addr = ((bdf | f) << 16) + 2
        cfg_buf = dp0.cfg_space.iface.memory_space.read(None, cfg_addr, 2, 0)
        cfg_val = int.from_bytes(cfg_buf, "little")
        stest.expect_equal(cfg_val, exp_val)

    addr = random.randrange(1 << 40) & ~(length - 1)
    pciexbar.write(enable=1, address=addr >> 20)
    exp_map = [[addr, dev.port.mcfg, 0, 0, length, None, socket_id, 0, 0]]
    stest.expect_equal(dp0.mem_space.map, exp_map)

    # try to access device_id in PCIe cfg space via pciexbar in PCIe mem space
    for (f, bank) in ((0, dev.bank.f0), (1, dev.bank.f1)):
        exp_val = random.randrange(1 << 16)
        bank.device_id = exp_val
        # pciexbar has bdf on bits [27:12]
        mem_addr = addr + ((bdf | f) << 12) + 2
        mem_buf = dp0.mem_space.iface.memory_space.read(None, mem_addr, 2, 0)
        mem_val = int.from_bytes(mem_buf, "little")
        stest.expect_equal(mem_val, exp_val)

    # Verify pcie type is converted to cfg when mcfg converts pcie mem to cfg
    final_pcie_type = -1
    def callback(mt, t, address, base, start, size, access, flags, data):
        global final_pcie_type

        final_pcie_type = getattr(t, "pcie_type", -1)
        return True

    t = transaction_t(size=4)
    mt = simics.SIM_new_map_target(dp0.port.mem, None, None)
    simics.SIM_inspect_address_routing(mt, t, addr, callback, None)
    simics.SIM_free_map_target(mt)
    stest.expect_equal(final_pcie_type, simics.PCIE_Type_Cfg)

    # write unaligned address
    with stest.expect_log_mgr(dev.bank.f1, 'spec-viol'):
        pciexbar.address = (addr >> 20) | 1

    pciexbar.enable = 0
