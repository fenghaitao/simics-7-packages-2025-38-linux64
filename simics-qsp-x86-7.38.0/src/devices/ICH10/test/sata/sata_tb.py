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


# sata_tb.py
# testbench of the SATA controller module in ICH9

import simics
import stest
import dev_util
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

import sys, os
sys.path.append(os.path.join("..", "common"))
import pcibus

ich_prefix  = 'ich10'

# SATA modes
IDE_MODE  = 0
AHCI_MODE = 1
RAID_MODE = 2

ahci_mem_base = 0x400000

class intregister(dev_util.Iface):
    """Dummy"""
    iface = 'int_register'

    def __init__(self):
        pass

    def read(self, obj, reg):
        if reg == 0x3100:
            return 0x03243200
        return 0

class TestBench:
    def __init__(self,
                 sata1_pci_config_baseaddr,
                 sata1_bm_baseaddr,
                 sata1_sidp_baseaddr,
                 sata2_pci_config_baseaddr,
                 sata2_bm_baseaddr,
                 sata2_sidp_baseaddr,
                 ahci_base_addr,
                 bus_freq_mhz):
        # base addresses and other constants...
        self.sata1_pci_config_baseaddr = sata1_pci_config_baseaddr
        self.sata1_bm_baseaddr         = sata1_bm_baseaddr
        self.sata1_sidp_baseaddr       = sata1_sidp_baseaddr
        self.sata2_pci_config_baseaddr = sata2_pci_config_baseaddr
        self.sata2_bm_baseaddr         = sata2_bm_baseaddr
        self.sata2_sidp_baseaddr       = sata2_sidp_baseaddr
        self.ahci_base_addr            = ahci_base_addr
        self.bus_freq_mhz              = bus_freq_mhz

        # Bus clock
        clk = simics.pre_conf_object('bus_clk', 'clock')
        clk.freq_mhz = self.bus_freq_mhz
        simics.SIM_add_configuration([clk], None)
        self.bus_clk = conf.bus_clk

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
        mem_size = 0x800000
        ahci_mem = simics.pre_conf_object("ahci_mem", "ram")
        ahci_image = simics.pre_conf_object("ahci_image", "image")
        ahci_mem.image = ahci_image
        ahci_image.size = mem_size
        simics.SIM_add_configuration([ahci_mem, ahci_image], None)
        self.mem.map += [[ahci_mem_base, conf.ahci_mem, 0, 0, mem_size]]

        # PCI bus
        self.pci = simics.SIM_create_object('PCIBus', 'pci',
                                            [['memory', self.mem],
                                             ['io', self.io_space],
                                             ['conf', self.conf_space]])

        # SATA Controller 1 - D31:F2
        sata1 = simics.pre_conf_object('sata1', '%s_sata_f2' % ich_prefix)
        sata1.pci_bus = self.pci
        sata1.queue   = self.bus_clk
        sata1.chipset_config = dev_util.Dev([intregister]).obj
        simics.SIM_add_configuration([sata1], None)
        self.sata1 = conf.sata1
        self.mem.map += [[sata1_pci_config_baseaddr,
                          [self.sata1, 'pci_config'],
                          0xff, 0, 0x100]]

        # SATA Controller 2 - D31:F5
        sata2 = simics.pre_conf_object('sata2', '%s_sata_f5' % ich_prefix)
        sata2.pci_bus = self.pci
        sata2.queue   = self.bus_clk
        sata2.chipset_config = dev_util.Dev([intregister]).obj

        simics.SIM_add_configuration([sata2], None)
        self.sata2 = conf.sata2
        self.mem.map += [[sata2_pci_config_baseaddr,
                          [self.sata2, 'pci_config'],
                          0xff, 0, 0x100]]

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

    # PCI config register access

    def sata1_rd_pci_config(self, offset, bits):
        return self.read_value_le(self.sata1_pci_config_baseaddr + offset, bits)

    def sata1_wr_pci_config(self, offset, bits, value):
        self.write_value_le(self.sata1_pci_config_baseaddr + offset, bits, value)

    def sata2_rd_pci_config(self, offset, bits):
        return self.read_value_le(self.sata2_pci_config_baseaddr + offset, bits)

    def sata2_wr_pci_config(self, offset, bits, value):
        self.write_value_le(self.sata2_pci_config_baseaddr + offset, bits, value)

    # Bus Master IDE I/O Registers

    def sata1_rd_bm_reg(self, offset, bits):
        return self.read_io_le(self.sata1_bm_baseaddr + offset, bits)

    def sata1_wr_bm_reg(self, offset, bits, value):
        self.write_io_le(self.sata1_bm_baseaddr + offset, bits, value)

    def sata2_rd_bm_reg(self, offset, bits):
        return self.read_io_le(self.sata2_bm_baseaddr + offset, bits)

    def sata2_wr_bm_reg(self, offset, bits, value):
        self.write_io_le(self.sata2_bm_baseaddr + offset, bits, value)

    # Serial ATA Index/Data Pair

    def sata1_wr_sidp_index_reg(self, pidx, ridx):
        self.write_io_le(self.sata1_sidp_baseaddr, 32, (pidx << 8) | ridx)

    def sata1_rd_sidp_data_reg(self):
        return self.read_io_le(self.sata1_sidp_baseaddr + 4, 32)

    def sata1_wr_sidp_data_reg(self, value):
        self.write_io_le(self.sata1_sidp_baseaddr + 4, 32, value)

    def sata2_wr_sidp_index_reg(self, pidx, ridx):
        self.write_io_le(self.sata2_sidp_baseaddr, 32, (pidx << 8) | ridx)

    def sata2_rd_sidp_data_reg(self):
        return self.read_io_le(self.sata2_sidp_baseaddr + 4, 32)

    def sata2_wr_sidp_data_reg(self, value):
        self.write_io_le(self.sata2_sidp_baseaddr + 4, 32, value)

    # Serial ATA Superset Registers

    def sata1_rd_sata_reg(self, pidx, ridx):
        self.sata1_wr_sidp_index_reg(pidx, ridx)
        return self.sata1_rd_sidp_data_reg()

    def sata1_wr_sata_reg(self, pidx, ridx, value):
        self.sata1_wr_sidp_index_reg(pidx, ridx)
        self.sata1_wr_sidp_data_reg(value)

    def sata2_rd_sata_reg(self, pidx, ridx):
        self.sata2_wr_sidp_index_reg(pidx, ridx)
        return self.sata2_rd_sidp_data_reg()

    def sata2_wr_sata_reg(self, pidx, ridx, value):
        self.sata2_wr_sidp_index_reg(pidx, ridx)
        self.sata2_wr_sidp_data_reg(value)

    # Mapping

    def sata1_enable_io_space_mapping(self):
        self.sata1_wr_pci_config(0x4, 16, self.sata1_rd_pci_config(0x4, 16) | 0x1)

    def sata1_enable_mem_space_mapping(self):
        self.sata1_wr_pci_config(0x4, 16, self.sata1_rd_pci_config(0x4, 16) | 0x2)

    def sata1_do_bm_mapping(self):
        self.sata1_wr_pci_config(0x20, 32, self.sata1_bm_baseaddr)
        self.sata1_enable_io_space_mapping()

    def sata1_do_sidp_mapping(self):
        self.sata1_wr_pci_config(0x24, 32, self.sata1_sidp_baseaddr)
        self.sata1_enable_io_space_mapping()

    def sata1_do_default_mappings(self):
        self.sata1_do_bm_mapping()
        self.sata1_do_sidp_mapping()

    def sata2_enable_io_space_mapping(self):
        self.sata2_wr_pci_config(0x4, 16, self.sata2_rd_pci_config(0x4, 16) | 0x1)

    def sata2_enable_mem_space_mapping(self):
        self.sata2_wr_pci_config(0x4, 16, self.sata2_rd_pci_config(0x4, 16) | 0x2)

    def sata2_do_default_mappings(self):
        self.sata2_wr_pci_config(0x20, 32, self.sata2_bm_baseaddr)
        self.sata2_wr_pci_config(0x24, 32, self.sata2_sidp_baseaddr)
        self.sata2_enable_io_space_mapping()

    # Operational Mode

    def select_sata_mode(self, mode):
        self.sata1_wr_pci_config(0x90, 16, mode << 6)

    # Access AHCI registers via AIDP
    # make sure BM bank has been mapped already

    def ahci_aidp_rd(self, offset):
        self.sata1_wr_bm_reg(0x10, 32, offset)
        return self.sata1_rd_bm_reg(0x14, 32)

    def ahci_aidp_wr(self, offset, value):
        self.sata1_wr_bm_reg(0x10, 32, offset)
        self.sata1_wr_bm_reg(0x14, 32, value)

    # Map AHCI registers

    def map_ahci_registers(self):
        self.sata1_wr_pci_config(0x24, 32, self.ahci_base_addr)
        self.sata1_enable_mem_space_mapping()

    # Access AHCI registers via mapped ABAR
    # make sure AHCI bank has been mapped already

    def ahci_rd_reg(self, offset):
        return self.read_value_le(self.ahci_base_addr + offset, 32)

    def ahci_wr_reg(self, offset, value):
        self.write_value_le(self.ahci_base_addr + offset, 32, value)

def expect_string(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%s', expected '%s'" % (info, actual, expected))

def expect_hex(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '0x%x', expected '0x%x'" % (info, actual, expected))

def expect_list(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%r', expected '%r'" % (info, actual, expected))

tb = TestBench(sata1_pci_config_baseaddr = 0x10000,
               sata1_bm_baseaddr         = 0x1e0,
               sata1_sidp_baseaddr       = 0x1f0,
               sata2_pci_config_baseaddr = 0x20000,
               sata2_bm_baseaddr         = 0x2e0,
               sata2_sidp_baseaddr       = 0x2f0,
               ahci_base_addr            = 0x80000,
               bus_freq_mhz              = 133)
