# © 2010 Intel Corporation
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
from lpc_tb import *
import stest

route_regs = [(0x3140, 31),
              (0x3144, 29),
              (0x3146, 28),
              (0x3148, 27),
              (0x314c, 26),
              (0x3150, 25)]

route_bf = dev_util.Bitfield_LE({'f3':(14,12),
                                 'f2':(10,8),
                                 'f1':(6,4),
                                 'f0':(2,0)})
pci_bus = tb.lpc.iface.pci_interrupt
for addr, dev in route_regs:
    reg = dev_util.Register_LE(tb.lpc.bank.cs_conf, addr, 2, route_bf)
    for pin in range(4):
        for phys_pin in range(8):
            reg.write(**{"f%d" % pin: phys_pin})
            pci_bus.raise_interrupt(None, dev, pin)
            stest.expect_equal(tb.ioapic.regs_raised[16 + phys_pin], 1)
            pci_bus.lower_interrupt(None, dev, pin)
            stest.expect_equal(tb.ioapic.regs_raised[16 + phys_pin], 0)
