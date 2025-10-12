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


# tb_apic.py
# testbench of APIC interrupt controller in ICH9

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

apic_bank_base = 0x0
apic_bank_size = 0x1000

apic_ind_addr   = apic_bank_base + 0x00
apic_dat_addr   = apic_bank_base + 0x10

apic_int_cnt    = 24

apic_client_bank_base   = 0x1000
apic_client_bank_size   = 0x1000

class ApicConst:
    reset_val = {
                    "ID"    : 0x00000000,
                    "VER"   : 0x00170011,
                    "REDIR" : 0x0000000000010000,
                }

    redir_low_bf = dev_util.Bitfield_LE({
                    "IM"        : 16,
                    "TRIG_MODE" : 15,
                    "R_IRR"     : 14,
                    "INT_POL"   : 13,
                    "DELIV_S"   : 12,
                    "DEST_MODE" : 11,
                    "DELIV_MODE": (10, 8),
                    "INT_VEC"   : (7, 0)
                   })

    redir_high_bf = dev_util.Bitfield_LE({
                        "DEST_MODE" : (31, 24)
                    })

class ApicBus(pyobj.ConfObject):
    '''A pseudo object with apic_bus interface to test APIC'''
    def _initialize(self):
        super()._initialize()
        self.last_paras = {}

    class apic_bus(pyobj.Interface):
        def interrupt(self, dest_mode, delivery_mode,
                            level_assert, trigger_mode, vector, destination):
            self._up.last_paras['dest-mode'] = dest_mode
            self._up.last_paras['deliv-mode'] = delivery_mode
            self._up.last_paras['level'] = level_assert
            self._up.last_paras['trig-mode'] = trigger_mode
            self._up.last_paras['vect'] = vector
            self._up.last_paras['dest'] = destination
            return simics.Apic_Bus_Accepted

    class current_interrupt(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'D'
        def getter(self):
            return self._up.last_paras

        def setter(self, val):
            self._up.last_paras = val

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

        # Pseudo APIC bus
        apic_bus = simics.pre_conf_object('apic_bus', 'ApicBus')
        simics.SIM_add_configuration([apic_bus], None)
        self.apic_bus = conf.apic_bus

        # Intel APIC
        apic = simics.pre_conf_object('apic', 'io-apic')
        apic.apic_bus = self.apic_bus
        simics.SIM_add_configuration([apic], None)
        self.apic = conf.apic

        # Pseudo APIC client
        apic_client = simics.pre_conf_object('apic_client', 'ich10_test_apic_client')
        apic_client.apic = self.apic
        simics.SIM_add_configuration([apic_client], None)
        self.apic_client = conf.apic_client

        self.mem.map += [
                          [main_ram_base,  self.main_ram, 0, 0, main_ram_size],
                          [apic_bank_base, self.apic, 0, 0, apic_bank_size],
                          [apic_client_bank_base, [self.apic_client, "io_func"], 0, 0, apic_client_bank_size],
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

    def read_apic_reg(self, index, bits):
        self.write_value_le(apic_ind_addr, 8, index)
        value = self.read_value_le(apic_dat_addr, 32)
        if bits == 64:
            self.write_value_le(apic_ind_addr, 8, index + 1)
            high = self.read_value_le(apic_dat_addr, 32)
            value = (high << 32) + value
        return value

    def enable_intr(self, intr_no, yes_or_no):
        self.write_value_le(apic_ind_addr, 8, 0x10 + intr_no * 2)
        value = self.read_value_le(apic_dat_addr, 32)
        if yes_or_no == "yes":
            value = value & ~(1 << 16)
        else:
            value = value | (1 << 16)
        self.write_value_le(apic_ind_addr, 8, 0x10 + intr_no * 2)
        self.write_value_le(apic_dat_addr, 32, value)

    def set_intr_paras(self, intr_no, vector, dest_mode, dest, deliv_mode, trig_mode):
        self.write_value_le(apic_ind_addr, 8, 0x10 + intr_no * 2)
        val = self.read_value_le(apic_dat_addr, 32)
        fields = ApicConst.redir_low_bf.fields(val)
        val = ApicConst.redir_low_bf.value(
                        IM = fields['IM'],
                        R_IRR = fields['R_IRR'],
                        INT_POL = fields['INT_POL'],
                        DELIV_S = fields['DELIV_S'],
                        TRIG_MODE = trig_mode,
                        DELIV_MODE = deliv_mode,
                        DEST_MODE = dest_mode,
                        INT_VEC = vector)
        self.write_value_le(apic_ind_addr, 8, 0x10 + intr_no * 2)
        self.write_value_le(apic_dat_addr, 32, val)
        # Write the high 32-bit half
        self.write_value_le(apic_ind_addr, 8, 0x10 + intr_no * 2 + 1)
        self.write_value_le(apic_dat_addr, 32, dest << 24)

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

def expect_dict(actual, expected, info):
    if actual != expected:
        raise Exception("%s: " % info, "got ", actual, ", expected ", expected)

def expect(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%d', expected '%d'" % (info, actual, expected))

def examine_intr_paras(intr_no, test_vec, test_dest, test_dest_mode, test_deliv_mode):
    paras = tb.apic_bus.current_interrupt
    expect(paras['vect'], test_vec,
           "testing vector of the interrupt %d" % intr_no)
    expect(paras['dest'], test_dest,
           "testing destination of the interrupt %d" % intr_no)
    expect(paras['dest-mode'], test_dest_mode,
           "testing destination mode of the interrupt %d" % intr_no)
    expect(paras['deliv-mode'], test_deliv_mode,
           "testing delivery mode of the interrupt %d" % intr_no)
