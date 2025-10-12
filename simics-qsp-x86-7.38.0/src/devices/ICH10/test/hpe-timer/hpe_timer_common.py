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


import pyobj
import simics

import stest
import dev_util
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

import sys, os
sys.path.append(os.path.join("..", "common"))

class Test_failure(Exception): pass


MAX32 = 0xFFFFFFFF
MAX32Plus1 = MAX32 + 1
MAX32MASK = MAX32
MAX64 = 0xFFFFFFFFFFFFFFFF
MAX64Plus1 = MAX64 + 1

def expect(got, expected):
    if got != expected:
        raise Test_failure("got %r, expected %r" % (got, expected))
def expect_hex(got, expected):
    if got != expected:
        raise Test_failure("got 0x%x, expected 0x%x" % (got, expected))

def expect_ex(desc, got, expected):
    if got != expected:
        raise Test_failure("%s: got %r, expected %r" % (desc, got, expected))

class MySignal(dev_util.Iface):
    iface = simics.SIGNAL_INTERFACE

    def __init__(self):
        self.level = 0
        self.spikes = 0

    def signal_raise(self, sim_obj):
        self.level += 1

    def signal_lower(self, sim_obj):
        if (self.level == 1):
            self.spikes += 1
        self.level -= 1

    def signal_level(self, sim_obj, level):
        self.level = level

    def get_timer(self):
        try:
            timer = simics.SIM_get_object('hpe_timer')
            return timer
        except simics.SimExc_General:
            return None

    def read_mem(self,addr):
        try:
            mem = simics.SIM_get_object('dev_mem0')
            mem.read()  # not support ?
            return 0
        except simics.SimExc_General:
            return 0

    def get_level(self):
        return self.level

class MySimpleIntr(dev_util.Iface):
    iface = simics.SIMPLE_INTERRUPT_INTERFACE

    def __init__(self):
        self.raised = {}
        self.level = 0
        self.spikes = 0

    def interrupt(self, sim_obj, level):
        raised = self.raised.get(level, 0)
        assert raised == 0
        self.level += 1
        self.spikes += 1
        self.raised[level] = raised + 1

    def interrupt_clear(self, sim_obj, level):
        assert self.raised[level] == 1
        self.level -= 1
        self.raised[level] -= 1

regs = [('GCAP_ID',   0x0),   ('GEN_CONF',  0x10),
        ('GINTR_STA', 0x20),  ('MAIN_CNT',  0xF0),
        ('TIM0_CONF', 0x100), ('TIM0_COMP', 0x108),
        ('TIM1_CONF', 0x120), ('TIM1_COMP', 0x128),
        ('TIM2_CONF', 0x140), ('TIM2_COMP', 0x148),
        ('TIM3_CONF', 0x160), ('TIM3_COMP', 0x168),
        ('TIM4_CONF', 0x180), ('TIM4_COMP', 0x188),
        ('TIM5_CONF', 0x1A0), ('TIM5_COMP', 0x1A8),
        ('TIM6_CONF', 0x1C0), ('TIM6_COMP', 0x1C8),
        ('TIM7_CONF', 0x1E0), ('TIM7_COMP', 0x1E8),
        ]

class ICH9R_HPE_TIMER:
    dev_cls = 'ich10_hpe_timer'

    def get_clock(self):
        try:
            return simics.SIM_get_object('clk1')
        except simics.SimExc_General:
            clk = simics.pre_conf_object('clk1', 'clock')
            clk.freq_mhz = 14.31818
            simics.SIM_add_configuration([clk], None)
            assert conf.clk1
            return conf.clk1

    def __init__(self, endian = 'le', log_level = 1):
        assert endian in ('le', 'be')
        self.endian = endian
        self.intr0 = dev_util.Dev([MySimpleIntr], True, 'intr_8259')
        self.intr1 = simics.SIM_create_object('ich10_test_apic', 'test_apic', [])
        self.intr = [self.intr0, self.intr1]

        self.timer = simics.pre_conf_object('hpe_timer', self.dev_cls)
        self.timer.intc_8259 = self.intr0.obj
        self.timer.intc_apic = self.intr1

        self.timer.log_level = log_level
        # set TIMER property:
        #self.set_timer_properties()
        #ICH9R_HPE_TIMER.get_clock();
        self.timer.queue = self.get_clock()

        simics.SIM_add_configuration([self.timer], None)

        self.timer = simics.SIM_get_object('hpe_timer')

        en = {'le' : 'LE', 'be' : 'BE'}[self.endian]

        self.regs = {}

        for reg in regs:
            (name, addr) = reg
            f = getattr(dev_util, "Register_%s" % en)
            self.regs[name] = f((self.timer, 'regs', addr), 8)

    def adjust_log_level(self, new_level):
        self.timer.log_level = new_level

    def set_timer_properties(self): pass

    def assert_intr_spikes(self, timN, expect):
        if ((self.intr[0].simple_interrupt.spikes != expect)
            and (self.intr[1].regs_spikes_total != expect)):
            raise Test_failure(
                "expected %d edge pulses but got %d/%d in 8259/APIC"
                % (expect, self.intr[0].simple_interrupt.spikes,
                   self.intr[1].regs_spikes_total))

    def is_apic_only_irq(self, timN):
        legacy = (self.read_register("GEN_CONF") & (1 << 1))
        if legacy and timN < 2:
            return False
        irq = (self.read_register("TIM%d_CONF" % timN) >> 9) & 0x1f
        return irq >= 16

    def assert_intr_state(self, timN, exp_apic, exp_pic = None):
        if exp_pic == None:
            if self.is_apic_only_irq(timN):
                exp_pic = 0
            else:
                exp_pic = exp_apic

        if (self.intr[0].simple_interrupt.level == exp_pic
            and self.intr[1].regs_total == exp_apic):
            return
        raise Test_failure(
            "expected %d/%d interrupts but got %d/%d in 8259/APIC"
            % (exp_apic, exp_pic,
               self.intr[0].simple_interrupt.level,
               self.intr[1].regs_total))

    def clear_intr(self):     #clear all existed interrupts
        ori_val = self.read_register('GINTR_STA')
        self.write_register('GINTR_STA', ori_val)


    def _set_bit_value(self, op, bitV, bitOffset):
        if (bitOffset >= 64):
            return op
        if (bitV == 1):  #set to '1'
            op |= (1 << bitOffset)
        else:   #clear to '0'
            mask = (MAX64 ^ ( 1 << bitOffset))
            op &= mask
        return op

    def _set_bitrange_value(self, op, bitsVal, width, lsbIndex):
        new_val = op
        #mask will be '1...1'
        mask = (1 << width) - 1     #  valid bits (width)
        bitsVal = (bitsVal & mask)
        val_0 = bitsVal << lsbIndex
        hole_mask = (mask << lsbIndex)
        hole_mask = (~hole_mask) & MAX64  #hole_mask is like: 11111000001111
        new_val &= hole_mask
        new_val |= val_0
        return new_val


    def set_32bit_mode(self, timN, bSet):  #
        if ((timN >= 0) and (timN < 8)):
            conf_reg = ("TIM%d_CONF" % timN)
            ori_val = self.read_register(conf_reg)
            new_val = ori_val
            new_val = self._set_bit_value(new_val, bSet, 8) ##offs: 8
            self.write_register(conf_reg, new_val)

    def set_timer_intr_conf(self, timN, isEnb, isLevelTrig, isGenPeriod):
        if ((timN >= 0) and (timN < 8)):
            conf_reg = ("TIM%d_CONF" % timN)
            new_val = self.read_register(conf_reg)
            new_val = self._set_bit_value(new_val, isLevelTrig, 1) ##offs: 1
            new_val = self._set_bit_value(new_val, isEnb, 2) ##offs: 2
            new_val = self._set_bit_value(new_val, isGenPeriod, 3) ##offs: 3
            self.write_register(conf_reg, new_val)
            # make sure we have a valid interrupt routing
            if (new_val >> 9) & 0x1f == 0 and isEnb:
                self.set_default_irq_route(timN)

    def set_default_irq_route(self, timN):
        v = [20, 21, 11, 12][timN]
        self.set_timer_rout_conf(timN, v)

    def set_timer_rout_conf(self, timN, irq):
        if ((timN >= 0) and (timN < 8)):
            conf_reg = ("TIM%d_CONF" % timN)
            ori_val = self.read_register(conf_reg)
            width = 5
            lsb = 9
            new_val = self._set_bitrange_value(ori_val, irq, width, lsb)
            self.write_register(conf_reg, new_val)

    def write_register(self,name,value):
        self.regs[name].write(value)

    def read_register(self,name):
        return self.regs[name].read()

    # func: set the positive relative value to current main counter;
    # param:
    # 'cnt_val' --- should greater than 0, and
    # is relative to the current main counter;
    def set_time_count(self, timN, cnt_val):
        if ((timN >= 0) and (timN < 8) and (cnt_val >= 0)):
            compare = ("TIM%d_COMP" % timN)
            old = self.read_register("MAIN_CNT")
            self.write_register(compare, cnt_val + old)

    # set comparator and period for a periodical counter
    def set_comp_and_period(self, timN, comp, period):
        if ((timN >= 0) and (timN < 8)):
            conf = ("TIM%d_CONF" % timN)
            x = self.read_register(conf)
            self.write_register(conf, x | (1 << 6)) # val_set_cnf

            compare = ("TIM%d_COMP" % timN)
            self.write_register(compare, comp)
            self.write_register(compare, period)

    #func: set absolute value to the main counter
    def set_time_countABS(self, timN, cnt_val):
        if ((timN >= 0) and (timN < 8)):
            compare = ("TIM%d_COMP" % timN)
            self.write_register(compare, cnt_val)

    def start_timer(self):
        self.write_register("GEN_CONF", 0x01)

    def stop_timer(self):
        self.write_register("GEN_CONF", 0x0)

    def reset(self, mode = 'HRESET'):
        assert mode in ('HRESET', 'SRESET', 'Reset')
        port = simics.SIM_get_port_interface(self.timer, 'signal', mode)
        port.signal_raise()
        port.signal_lower()
        self.intr[0].simple_interrupt.spikes = 0
        self.intr[1].regs_spikes_total = 0


if __name__ == '__main__':
    timer = ICH9R_HPE_TIMER()
    timer.read_register("GCAP_ID")
    timer.write_register("GEN_CONF", 0xFF)
