# © 2019 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import conf
import pyobj
import simics
from dev_util import Register_LE
import random

class TB: pass

class sig_target(pyobj.ConfObject):
    class state(pyobj.SimpleAttribute(False, 'b')): pass
    class signal(pyobj.Interface):
        def signal_raise(self):
            self._top.state.val = True
        def signal_lower(self):
            self._top.state.val = False
    class irq(pyobj.Port):
        class signal(pyobj.Interface):
            def signal_raise(self):
                self._top.state.val = True
            def signal_lower(self):
                self._top.state.val = False

class fake_hart(pyobj.ConfObject):
    class riscv_state(pyobj.SimpleAttribute(False, 'b')): pass
    class riscv_int_id(pyobj.SimpleAttribute(False, 'i')): pass
    class riscv_int_level(pyobj.SimpleAttribute(False, 'i')): pass
    class riscv_int_vector(pyobj.SimpleAttribute(False, 'i')): pass
    class MTIP(pyobj.PortObject):
        class state(pyobj.SimpleAttribute(False, 'b')): pass
        class signal(pyobj.Interface):
            def signal_raise(self):
                self._up.state.val = True
            def signal_lower(self):
                self._up.state.val = False
    class MSIP(pyobj.PortObject):
        class state(pyobj.SimpleAttribute(False, 'b')): pass
        class signal(pyobj.Interface):
            def signal_raise(self):
                self._up.state.val = True
            def signal_lower(self):
                self._up.state.val = False
    class MEIP(pyobj.PortObject):
        class state(pyobj.SimpleAttribute(False, 'b')): pass
        class signal(pyobj.Interface):
            def signal_raise(self):
                self._up.state.val = True
            def signal_lower(self):
                self._up.state.val = False
    class SEIP(pyobj.PortObject):
        class state(pyobj.SimpleAttribute(False, 'b')): pass
        class signal(pyobj.Interface):
            def signal_raise(self):
                self._up.state.val = True
            def signal_lower(self):
                self._up.state.val = False
    class riscv_clic_interrupt(pyobj.Interface):
        def set_active_interrupt(self, id, level, vector, cpumode):
            self._top.riscv_state.val = True
            self._top.riscv_int_id.val = id
            self._top.riscv_int_level.val = level
            self._top.riscv_int_vector.val = vector
        def clear_interrupt(self):
            self._top.riscv_state.val = False

def create_tb(num_harts=3, hart_freq_mhz = 1.0, freq_mhz=1.0):
    harts = [simics.pre_conf_object('hart%d' % d, 'fake_hart')
             for d in range(num_harts)]
    clock = simics.pre_conf_object('clock', 'clock', freq_mhz = hart_freq_mhz)

    clint = simics.pre_conf_object('clint', 'riscv-clint')
    clint.queue = clock
    clint.freq_mhz = freq_mhz
    clint.hart = harts

    plic = simics.pre_conf_object('plic', 'riscv-plic')
    tgt = [simics.pre_conf_object('tgt%d' % d, 'sig_target')
            for d in range(num_harts)]
    plic.hart = harts

    objects = harts + tgt + [clock, clint, plic]
    simics.SIM_add_configuration(objects, None)

    tb = TB()
    tb.harts = [TB() for h in range(num_harts)]
    for h in range(num_harts):
        tb.harts[h].obj = simics.SIM_get_object(harts[h].name)

    tb.clint = TB()
    tb.clint.obj = conf.clint
    Reg = lambda a, sz = 8: Register_LE(conf.clint.bank.regs, a, sz)
    tb.clint.msip = [Reg(i * 4, 4) for i in range(num_harts)]
    tb.clint.mtimecmp = [Reg(0x4000 + i * 8) for i in range(num_harts)]
    tb.clint.mtime = Reg(0xbff8)

    tb.plic = TB()
    tb.plic.obj = simics.SIM_get_object(plic.name)
    Reg = lambda a: Register_LE(tb.plic.obj.bank.regs, a)
    tb.plic.priority = [Reg(0 + i * 4) for i in range(1024)]
    tb.plic.pending = [Reg(0x1000 + i * 4) for i in range(32)]
    def get_ctx(x):
        regs = TB()
        regs.index = x
        regs.enable = [Reg(0x2000 + x * 0x80 + i * 4) for i in range(32)]
        regs.threshold = Reg(0x200000 + x * 0x1000)
        regs.claim =     Reg(0x200004 + x * 0x1000)
        return regs
    tb.plic.context = lambda x: get_ctx(x)

    return tb
