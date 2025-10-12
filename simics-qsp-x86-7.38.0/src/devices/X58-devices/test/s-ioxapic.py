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


import cli
import simics
import stest
from dev_util import Register_LE
import random
random.seed("Blood Red")


class fake_apic_bus:
    cls = simics.confclass('fake-apic-bus')

    @cls.iface.apic_bus.interrupt
    def interrupt(*args):
        stest.fail("unexpected interrupt")


ab = simics.SIM_create_object('fake-apic-bus', 'ab', [])
dev = simics.SIM_create_object('x58-ioxapic', 'dev', [['ioapic.apic_bus', ab]])
dp = simics.SIM_create_object('pcie-downstream-port', 'dp', [])
dp.devices = [[0, dev]]

cmd = Register_LE(dev.bank.pcie_config, 0x4, 2)
mbar = Register_LE(dev.bank.pcie_config, 0x10)
abar = Register_LE(dev.bank.pcie_config, 0x40, 2)

mbar_addr = random.randrange(1 << 20) << 12
mbar.write(mbar_addr)
cmd.write(2)  # Memory Space enable
stest.expect_equal(
    dp.mem_space.map, [[mbar_addr, dev.ioapic, 0, 0, 1 << 12, None, 0, 8, 0]])
cmd.write(0)  # Memory Space disable
stest.expect_equal(dp.mem_space.map, [])

abar_addr = random.randrange(1 << 12)
abar.write((1 << 15) | abar_addr)  # enable and set address
exp_addr = abar_addr << 8
stest.expect_equal(
    dp.mem_space.map, [[exp_addr, dev.ioapic, 0, 0, 1 << 8, None, 0, 8, 0]])
abar.write(abar_addr)  # disabled
stest.expect_equal(dp.mem_space.map, [])
