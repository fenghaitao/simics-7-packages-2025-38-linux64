# © 2025 Intel Corporation
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
import conf
import stest
import random
random.seed("Dust of the Chase")


class sigtarget:
    cls = simics.confclass('sigtarget')
    cls.attr.pin('i', default=0)
    cls.attr.lvl('i', default=0)
    cls.attr.dev('i', default=0)
    cls.attr.src('o|n', default=None)

    @cls.iface.pci_interrupt.raise_interrupt
    def raise_interrupt(self, src, dev, pin):
        self.set_interrupt(src, dev, pin, 1)

    @cls.iface.pci_interrupt.lower_interrupt
    def lower_interrupt(self, src, dev, pin):
        self.set_interrupt(src, dev, pin, 0)

    def set_interrupt(self, src, dev, pin, lvl):
        self.pin = pin
        self.dev = dev
        self.src = src
        self.lvl = lvl


def check(obj, **attrs):
    for k, v in attrs.items():
        stest.expect_equal(getattr(obj, k), v, f"unexpected '{k}'")


remap_unit = [simics.SIM_create_object('set-memory', f'rm{d}', [])
              for d in (0, 1)]
tgt = simics.SIM_create_object('sigtarget', 'tgt', [])
dev = simics.SIM_create_object('pci_upstream_dispatcher', 'bridge',
                               [['default_remapping_unit', remap_unit[0]],
                                ['gfx_remapping_unit', remap_unit[1]],
                                ['gfx_objs', [conf.sim, tgt]],
                                ['interrupt', tgt]])

remap_unit[0].value = random.randrange(256)
remap_unit[1].value = random.randrange(256)

mt = simics.SIM_new_map_target(dev, None, None)
t = simics.transaction_t(read=True, pcie_type=simics.PCIE_Type_Mem, size=1)
exc = simics.SIM_issue_transaction(mt, t, 0)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)
stest.expect_equal(t.value_le, remap_unit[0].value)

t.initiator = tgt
exc = simics.SIM_issue_transaction(mt, t, 0)
stest.expect_equal(exc, simics.Sim_PE_No_Exception)
stest.expect_equal(t.value_le, remap_unit[1].value)

t.pcie_type = simics.PCIE_Type_Msg
t.initiator = conf.sim
for (msg, pin, lvl) in ((simics.PCIE_Msg_Assert_INTA,   0, 1),
                        (simics.PCIE_Msg_Assert_INTB,   1, 1),
                        (simics.PCIE_Msg_Assert_INTC,   2, 1),
                        (simics.PCIE_Msg_Assert_INTD,   3, 1),
                        (simics.PCIE_Msg_Deassert_INTA, 0, 0),
                        (simics.PCIE_Msg_Deassert_INTB, 1, 0),
                        (simics.PCIE_Msg_Deassert_INTC, 2, 0),
                        (simics.PCIE_Msg_Deassert_INTD, 3, 0),):
    dev = random.randrange(1 << 5)
    t.pcie_msg_type = msg
    t.pcie_requester_id = dev << 3
    exc = simics.SIM_issue_transaction(mt, t, 0)
    stest.expect_equal(exc, simics.Sim_PE_No_Exception)
    check(tgt, pin=pin, lvl=lvl, dev=dev, src=t.initiator)
    tgt.src = None
