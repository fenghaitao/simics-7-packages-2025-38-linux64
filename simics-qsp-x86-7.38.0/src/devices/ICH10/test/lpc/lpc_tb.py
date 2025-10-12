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


# lpc_tb.py
# testbench of Low Pin Controller devices in ICH10

import pyobj
import simics
import stest
import dev_util
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

import sys, os
sys.path.append(os.path.join("..", "common"))
import pcibus

lpc_main_ram_size=0x100000
lpc_sram_size   = 0x100
lpc_counter_cnt = 3
lpc_ext_dev_cnt = 4

lpc_io_addr     = 0x00000000
lpc_fixed_io_len= 0x100
lpc_reg_addr    = 0x80000000
lpc_dev_io_base = [0x8100, 0x8200, 0x8300, 0x8400]
lpc_main_mem_base=0x100000
lpc_mapped_addr = 0x00080000
lpc_timer_mhz       = 1000. / 838.

spi_flash_rom_size  = 0x100000 # M25P80
spi_flash_sector_cnt    = 16
spi_flash_sector_size   = 0x10000 # 64K

class TimerOutSignal(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()

        self.level = 0

    class signal(pyobj.Interface):
        def signal_raise(self):
            self._up.level = 1
        def signal_lower(self):
            self._up.level = 0

    class level(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.level
        def setter(self, val):
            self._up.level = val

class LpcConst:
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

import pyobj
class PCI_Bridge(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()

    class pci_bridge(pyobj.Interface):
        def system_error(self):
            pass
        def raise_interrupt(self, bus, dev, pin):
            pass
        def lower_interrupt(self, bus, dev, pin):
            pass

class TestBench:
    def __init__(self, lpc_reg_addr):
        self.lpc_pci_config_addr = lpc_reg_addr

        # Bus clock
        clk = simics.pre_conf_object('lpc_timer_clk', 'clock')
        clk.freq_mhz = lpc_timer_mhz
        simics.SIM_add_configuration([clk], None)
        self.timer_clk = conf.lpc_timer_clk

        # Image and ram
        img = simics.pre_conf_object('img', 'image')
        img.size = lpc_sram_size
        sram = simics.pre_conf_object('sram', 'ram')
        sram.image = img
        simics.SIM_add_configuration([img, sram], None)
        self.sram_image = conf.img
        self.sram = conf.sram

        # Main memory and its image
        img = simics.pre_conf_object('main_img', 'image')
        img.size = lpc_main_ram_size
        main_ram = simics.pre_conf_object('main_ram', 'ram')
        main_ram.image = img
        simics.SIM_add_configuration([img, main_ram], None)
        self.main_ram_image = conf.main_img
        self.main_ram = conf.main_ram

        # Memory-space
        self.mem = simics.pre_conf_object('mem', 'memory-space')
        simics.SIM_add_configuration([self.mem], None)
        self.mem = conf.mem
        self.mem_iface = self.mem.iface.memory_space

        self.io_space = simics.SIM_create_object('memory-space', 'io_space', [])
        self.conf_space = simics.SIM_create_object('memory-space',
                                                   'conf_space', [])

        # Initialize memory
        self.memory = dev_util.Memory()

        # PCI bus
        self.bridge = simics.SIM_create_object('PCI_Bridge', 'bridge', [])
        self.pci = simics.SIM_create_object('pci-bus', 'pci',
                                            [['memory_space', self.mem],
                                             ['io_space', self.io_space],
                                             ['conf_space', self.conf_space],
                                             ['bridge', self.bridge]])

        # Interrupt controller
        self.intc_py = dev_util.Dev([dev_util.SimpleInterrupt])
        self.intc_state = self.intc_py.simple_interrupt.raised
        self.intc = self.intc_py.obj

        # APIC Interrupt controller
        self.ioapic = simics.SIM_create_object('ich10_test_apic', 'ioapic', [])

        # LPC Bus
        self.lpc_io = simics.SIM_create_object('memory-space', 'lpc_io', [])
        self.lpc_mem = simics.SIM_create_object('memory-space', 'lpc_mem', [])

        # LPC memory target devices
        lpc_ram = simics.pre_conf_object('lpc_ram', 'ram')
        lpc_img = simics.pre_conf_object('lpc_img', 'image')
        lpc_img.size = 0x10000 #64KB
        lpc_ram.image = lpc_img
        simics.SIM_add_configuration([lpc_img, lpc_ram], None)
        self.lpc_mem.map = [[0x0, conf.lpc_ram, 0, 0, 0x10000]]

        # LPC bridge
        lpc = simics.pre_conf_object('lpc', 'ich10_lpc')
        lpc.ich10_corporate = True  # enable ICH10D
        lpc.pci_bus    = self.pci
        lpc.queue      = self.timer_clk
        lpc.lpc_io     = self.lpc_io
        lpc.lpc_memory = self.lpc_mem
        lpc.ioapic     = self.ioapic
        lpc.cpus       = []

        # SPI and SPI flash
        spi = simics.pre_conf_object('spi', 'ich10_spi')
        spi_flash_img = simics.pre_conf_object('spi_flash_img', 'image')
        spi_flash_img.size = spi_flash_rom_size
        spi_flash = simics.pre_conf_object('spi_flash', 'M25Pxx')
        spi_flash.mem_block = spi_flash_img
        spi_flash.sector_size   = spi_flash_sector_size
        spi_flash.spi_master = spi
        spi_flash.sector_number = spi_flash_sector_cnt
        lpc.flash = [spi, "spi_regs"]
        spi.spi_slave = spi_flash

        # parameters for serial ports
        lpc.coma_level = 3
        lpc.comb_level = 4
        lpc.coma_pirq = self.intc
        lpc.comb_pirq = self.intc
        lpc.serial_port = [None] * 4
        simics.SIM_add_configuration([lpc, spi, spi_flash, spi_flash_img], None)
        self.lpc = conf.lpc

        # NS16550
        self.coms = []
        for i in range(4):
            self.coms.append(
                simics.SIM_create_object('NS16550', 'com%d' % (i + 1),
                                         [['queue', self.timer_clk]]))

        self.lpc.serial_port = self.coms
        self.coms[0].irq_dev = [self.lpc, 'com1_in']
        self.coms[1].irq_dev = [self.lpc, 'com2_in']
        self.coms[2].irq_dev = [self.lpc, 'com3_in']
        self.coms[3].irq_dev = [self.lpc, 'com4_in']

        self.conf_space.map += \
            [[lpc_reg_addr, [self.lpc, 'pci_config'], 0xff, 0, 0x100]]

        self.io_space.map += \
            [[lpc_io_addr,  [self.lpc, 'fixed_io'],   0xff, 0, lpc_fixed_io_len]]

        self.mem.map += \
            [[lpc_main_mem_base,  self.main_ram, 0x0, 0, lpc_main_ram_size]]

        self.lpc_func_mapped_addr = 0
        self.lpc_sram_mapped_addr = 0

        # Four testing LPC devices
        self.lpc_dev = []
        for i in range(lpc_ext_dev_cnt):
            lpc_dev = simics.pre_conf_object('lpc_dev%d' % i,
                                             'ich10_test_lpc_device')
            simics.SIM_add_configuration([lpc_dev], None)
            self.lpc_dev.append(simics.SIM_get_object("lpc_dev%d" % i))

    # Memory operation methods
    def read_mem(self, addr, size):
        return self.mem_iface.read(None, addr, size, 0)

    def write_mem(self, addr, bytes):
        self.mem_iface.write(None, addr, bytes, 0)

    def read_value_le(self, addr, bits):
        return dev_util.tuple_to_value_le(self.read_mem(addr, bits // 8))

    def write_value_le(self, addr, bits, value):
        self.write_mem(addr, dev_util.value_to_tuple_le(value, bits // 8))

    # IO space operation methods
    def read_io(self, addr, size):
        return self.io_space.iface.memory_space.read(None, addr, size, 0)

    def write_io(self, addr, bytes):
        self.io_space.iface.memory_space.write(None, addr, bytes, 0)

    def read_io_le(self, addr, bits):
        return dev_util.tuple_to_value_le(self.read_io(addr, bits // 8))

    def write_io_le(self, addr, bits, value):
        self.write_io(addr, dev_util.value_to_tuple_le(value, bits // 8))

    # Config space operation methods
    def read_conf(self, addr, size):
        return self.conf_space.iface.memory_space.read(None, addr, size, 0)

    def write_conf(self, addr, bytes):
        self.conf_space.iface.memory_space.write(None, addr, bytes, 0)

    def read_conf_le(self, addr, bits):
        return dev_util.tuple_to_value_le(self.read_conf(addr, bits // 8))

    def write_conf_le(self, addr, bits, value):
        self.write_conf(addr, dev_util.value_to_tuple_le(value, bits // 8))

    def map_lpc_func(self, mapped_addr):
        # Enable the io space mapping
        reg_val = self.read_conf_le(self.lpc_pci_config_addr + 0x4, 16)
        reg_val = reg_val | 0x1
        self.write_conf_le(self.lpc_pci_config_addr + 0x4, 16, reg_val)
        self.write_conf_le(self.lpc_pci_config_addr + 0x20, 32, mapped_addr)
        self.lpc_func_mapped_addr = mapped_addr

    def map_lpc_sram(self, mapped_addr):
        # Enable the memory space mapping
        reg_val = self.read_conf_le(self.lpc_pci_config_addr + 0x4, 16)
        reg_val = reg_val | 0x2
        self.write_conf_le(self.lpc_pci_config_addr + 0x4, 16, reg_val)
        self.write_conf_le(self.lpc_pci_config_addr + 0x10, 64, mapped_addr)
        self.lpc_sram_mapped_addr = mapped_addr

    def set_rtc(self, time_list):
        [sec, min, hour, dow, dom, mon, year] = time_list
        # Inhibit the update cycle temporarily
        self.write_io_le(rtc_io_index, 8, 0xB)
        orig_regb = self.read_io_le(rtc_io_data, 8)
        self.write_io_le(rtc_io_index, 8, 0xB)
        self.write_io_le(rtc_io_data, 8, orig_regb | 0x80)

        val_list = [sec, min, hour]
        for i in range(len(val_list)):
            self.write_io_le(rtc_io_index, 8, 2 * i)
            self.write_io_le(rtc_io_data, 8, val_list[i])

        val_list = [dow, dom, mon, year]
        for i in range(len(val_list)):
            self.write_io_le(rtc_io_index, 8, 6 + i)
            self.write_io_le(rtc_io_data, 8, val_list[i])
        # Restore the original register B
        self.write_io_le(rtc_io_index, 8, 0xB)
        self.write_io_le(rtc_io_data, 8, orig_regb)

    def get_rtc(self):
        self.write_io_le(rtc_io_index, 8, 0)
        sec = self.read_io_le(rtc_io_data, 8)

        self.write_io_le(rtc_io_index, 8, 2)
        min = self.read_io_le(rtc_io_data, 8)

        self.write_io_le(rtc_io_index, 8, 4)
        hour = self.read_io_le(rtc_io_data, 8)

        self.write_io_le(rtc_io_index, 8, 6)
        dow = self.read_io_le(rtc_io_data, 8)

        self.write_io_le(rtc_io_index, 8, 7)
        dom = self.read_io_le(rtc_io_data, 8)

        self.write_io_le(rtc_io_index, 8, 8)
        mon = self.read_io_le(rtc_io_data, 8)

        self.write_io_le(rtc_io_index, 8, 9)
        year = self.read_io_le(rtc_io_data, 8)

        list_val = [sec, min, hour, dow, dom, mon, year]
        #self.write_value_le(rtc_io_index, 8, 0xB)
        #regb_val = self.read_value_le(rtc_io_data, 8)
        #if ((regb_val >> 2) & 0x1) == 0:
        #    bcd_to_binary(list_val)

        return list_val

    def enable_rtc(self, to_enable):
        # Select the divider chain select
        self.write_io_le(rtc_io_index, 8, 0xA)
        self.write_io_le(rtc_io_data, 8, 0x20)

        self.write_io_le(rtc_io_index, 8, 0xB)
        orig_regb = self.read_io_le(rtc_io_data, 8)
        if to_enable:
            new_origb = orig_regb & 0x7F
        else:
            new_origb = orig_regb | 0x80
        self.write_io_le(rtc_io_index, 8, 0xB)
        self.write_io_le(rtc_io_data, 8, new_origb)


tb = TestBench(lpc_reg_addr)

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
