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


# tb_8259.py
# testbench of 8259A interrupt controller in ICH9

import pyobj
import simics
import stest
import dev_util
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

sys_timer_mhz   = 14.18

main_ram_base   = 0x80000000
main_ram_size   = 0x100000

i8259_bank_base = 0x0
i8259_bank_size = 0x1000

class I8259Const:
    reset_val = {
                    "VID"   : 0x8086,
                    "DID"   : 0x2916,
                    "CMD"   : 0x0000,
                    "STS"   : 0x0280,
                    "RID"   : 0x02,
                    "PI"    : 0x00,
                    "SCC"   : 0x05,
                    "BCC"   : 0x0C,
                    "BAR0"  : 0x00000004,
                    "BAR1"  : 0x00000000,
                    "BASE"  : 0x00000001,
                    "SVID"  : 0x0000,
                    "SID"   : 0x0000,
                    "INTLN" : 0x00,
                    "INTPN" : 0x02,
                    "HOSTC" : 0x00,
                }

class InterruptAck(pyobj.ConfObject):
    '''A pseudo object with interrupt_ack interface to test 8259A'''
    def _initialize(self):
        super()._initialize()
        self.cur_intr = []
        self.last_intc = None

    class interrupt_ack(pyobj.Interface):
        def raise_interrupt(self, ack_fn, intc):
            self.last_intc = intc
            # Acknowledge the interrupt to the controller
            # and get and remember the interrupt vector
            if ack_fn and self._up.auto_ack.val:
                iv = ack_fn(intc)
                self._up.cur_intr.append(iv)
            self._up.irq_raised.val = True

        def lower_interrupt(self, ack_fn):
            self._up.irq_raised.val = False

    class current_interrupt(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = '[i*]'
        def getter(self):
            return self._up.cur_intr

        def setter(self, val):
            self._up.cur_intr = val

    class auto_ack(pyobj.SimpleAttribute(True, 'b')):
        """Directly ack the interrupt"""

    class irq_raised(pyobj.SimpleAttribute(False, 'b')):
        """Is the interrupt raised"""


class TestBench:
    def __init__(self):
        # Bus clock
        clk = simics.pre_conf_object('sys_timer_clk', 'clock')
        clk.freq_mhz = sys_timer_mhz
        simics.SIM_add_configuration([clk], None)
        self.sys_clk = conf.sys_timer_clk

        # Main memory and its image
        img = simics.pre_conf_object('main_img', 'image')
        img.size = main_ram_size
        main_ram = simics.pre_conf_object('main_ram', 'ram')
        main_ram.image = img
        simics.SIM_add_configuration([img, main_ram], None)
        self.main_ram_image = conf.main_img
        self.main_ram = conf.main_ram

        # Memory-space
        mem = simics.pre_conf_object('mem', 'memory-space')
        simics.SIM_add_configuration([mem], None)
        self.mem = conf.mem
        self.mem_iface = self.mem.iface.memory_space

        # Pseudo interrupt ack device
        iack = simics.pre_conf_object('iack', 'InterruptAck')
        simics.SIM_add_configuration([iack], None)
        self.iack = conf.iack

        # Intel 8259A
        i8259 = simics.pre_conf_object('i8259', 'i8259x2')
        i8259.irq_dev = self.iack
        i8259.queue = self.sys_clk
        simics.SIM_add_configuration([i8259], None)
        self.i8259 = conf.i8259

        self.mem.map += [
                          [main_ram_base,  self.main_ram, 0, 0, main_ram_size],
                          [i8259_bank_base, self.i8259, 0, 0, i8259_bank_size],
                        ]

    # Memory operation methods
    def read_mem(self, addr, size):
        return self.mem_iface.read(None, addr, size, 0)

    def write_mem(self, addr, bytes):
        self.mem_iface.write(None, addr, bytes, 0)

    def read_value_le(self, addr, bits):
        return dev_util.tuple_to_value_le(self.read_mem(addr, bits // 8))

    def write_value_le(self, addr, bits, value):
        self.write_mem(addr, dev_util.value_to_tuple_le(value, bits // 8))

    def init_i8259(self):
        # Write the initialization command words to 8259
        for i in range(2):
            addr_a = 0x20 + i * 0x80
            addr_b = addr_a + 1
            icw1 = 0x11 # D4 = 1, IC4 = 1, SNGL = 0
            if i == 0:
                icw2 = 0x08
                icw3 = 0x04
            else:
                icw2 = 0x70
                icw3 = 0x02
            icw4 = 0x01 # IA = 1, AEOI = 0, BUF = 0, SFNM = 0
            self.write_value_le(addr_a, 8, icw1)
            self.write_value_le(addr_b, 8, icw2)
            self.write_value_le(addr_b, 8, icw3)
            self.write_value_le(addr_b, 8, icw4)

        # Write the operation command words to 8259
        for i in range(2):
            addr_a = 0x21 + i * 0x80
            addr_b = addr_a - 1
            ocw1 = 0xFF
            ocw2 = 0xC7 # Set the priority to default setting
            ocw3 = 0x08
            self.write_value_le(addr_a, 8, ocw1)
            self.write_value_le(addr_b, 8, ocw2)
            self.write_value_le(addr_b, 8, ocw3)

    def enable_interrupt(self, intr_no, to_enable):
        m_addr_odd = 0x21
        s_addr_odd = 0xA1
        if intr_no > 7:
            m_enable_intr = 2
            s_enable_intr = intr_no - 8
        else:
            m_enable_intr = intr_no

        # Enable or disable the master interrupt
        reg_val = tb.read_value_le(m_addr_odd, 8)
        if to_enable:
            reg_val = reg_val & ~(1 << m_enable_intr)
        else:
            reg_val = reg_val | (1 << m_enable_intr)
        tb.write_value_le(m_addr_odd, 8, reg_val)

        # Enable the slave interrupt if needed
        if intr_no > 7:
            reg_val = tb.read_value_le(s_addr_odd, 8)
            if to_enable:
                reg_val = reg_val & ~(1 << s_enable_intr)
            else:
                reg_val = reg_val | (1 << s_enable_intr)
            tb.write_value_le(s_addr_odd, 8, reg_val)

    def read_irr_isr(self, irr_or_isr, master_or_slave):
        if irr_or_isr == "irr":
            write_val = 0xA
        elif irr_or_isr == "isr":
            write_val = 0xB
        else:
            print("Please give 'irr' or 'isr' in the 'irr_or_isr' parameter")

        if master_or_slave == "master":
            addr = 0x20
        elif master_or_slave == "slave":
            addr = 0xA0
        else:
            print("Please give 'master' or 'slave' in the 'master_or_slave' parameter")
            assert 0
        self.write_value_le(addr, 8, write_val)
        reg_val = self.read_value_le(addr, 8)
        return reg_val

    def clear_interrupt(self, intr_no):
        # Write a EOI command to OCW2 to clear the interrupt
        if intr_no < 8:
            self.write_value_le(0x20, 8, 0x20)
        else:
            self.write_value_le(0xA0, 8, 0x20)
            self.write_value_le(0x20, 8, 0x20)

    def set_trig_mode(self, intr_no, trig_mode):
        if intr_no < 8:
            reg_addr = 0x4d0
            bit_no = intr_no
        else:
            reg_addr = 0x4d1
            bit_no = intr_no - 8
        reg_val = self.read_value_le(reg_addr, 8)
        if trig_mode == "level":
            reg_val = reg_val | (1 << bit_no)
        else:
            reg_val = reg_val & ~(1 << bit_no)
        self.write_value_le(reg_addr, 8, reg_val)

    def irq_no_to_vector(self, intr_no):
        if intr_no < 8:
            return 0x08 + intr_no
        elif intr_no < 16:
            return 0x70 + intr_no - 8

tb = TestBench()

def expect_string(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%s', expected '%s'" % (info, actual, expected))

def expect_hex(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '0x%x', expected '0x%x'" % (info, actual, expected))

def expect_list(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%r', expected '%r'" % (info, actual, expected))

def expect(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%d', expected '%d'" % (info, actual, expected))
