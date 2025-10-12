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


# smbus_tb_decl.py
# declarations of testbench of SMBus controller module in ICH9

import simics
import stest
import dev_util
import conf
import cli

# SIMICS-21543
conf.sim.deprecation_level = 0

import sys, os
sys.path.append(os.path.join("..", "common"))

from pcibus import *

ich_prefix        = 'ich10'

smbus_sram_size   = 0x100
smbus_slave_addr  = 0x44

smbus_reg_addr    = 0x80000000

smbus_mapped_addr = 0x00008000

ich9_bus_freq_mhz   = 1333 # FSB frequency

quick_slave_addr                = 0x40
quick_slave_addr_mask           = 0xFFFFFFFE
byte_slave_addr                 = 0x42
byte_slave_addr_mask            = 0xFFFFFFFE
byte_data_slave_addr            = 0x44
byte_data_slave_addr_mask       = 0xFFFFFFFE
word_data_slave_addr            = 0x46
word_data_slave_addr_mask       = 0xFFFFFFFE
process_call_slave_addr         = 0x48
process_call_slave_addr_mask    = 0xFFFFFFFE
block_slave_addr                = 0x4A
block_slave_addr_mask           = 0xFFFFFFFE
block_process_slave_addr        = 0x4C
block_process_slave_addr_mask   = 0xFFFFFFFE

class SmbusConst:
    reset_val = {
                    "VID"   : 0x8086,
                    "DID"   : (0x2930, 0x3A30)[ich_prefix.startswith('ich10')],
                    "CMD"   : 0x0000,
                    "STS"   : 0x0280,
                    "RID"   : 0x00,
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

                    # Function registers
                    "HST_STS"   : 0x00,
                    "HST_CNT"   : 0x00,
                    "HST_CMD"   : 0x00,
                    "XMIT_SLVA" : 0x00,
                    "HST_D0"    : 0x00,
                    "HST_D1"    : 0x00,
                    "HOST_BLK_DB":0x00,
                    "PEC"       : 0x00,
                    "RCV_SLVA"  : 0x44,
                    "SLV_DATA"  : 0x0000,
                    "AUX_STS"   : 0x00,
                    "AUX_CTL"   : 0x00,
                    "SMLINK_PIN_CTL"    : 0x00,
                    "SMBUS_PIN_CTL"     : 0x00,
                    "SLV_STS"           : 0x00,
                    "SLV_CMD"           : 0x00,
                    "NOTIFY_DADDR"      : 0x00,
                    "NOTIFY_DLOW"       : 0x00,
                    "NOTIFY_DHIGH"      : 0x00,
                }

    cmd = {
            "quick"         : 0x0,
            "byte"          : 0x1,
            "byte-data"     : 0x2,
            "word-data"     : 0x3,
            "process-call"  : 0x4,
            "block"         : 0x5,
            "i2c-read"      : 0x6,
            "block-process" : 0x7,
          }

    smb_write = 0
    smb_read  = 1

from smbus_slave import *
from comp import *


# It is much simpler to just use components with connectors when working
# with the i2c_link_v2. Hence we use trivial wrapper components for the
# smbus controller and the smbus slaves.
class smbus_wrapper_comp(StandardConnectorComponent):
    """N/A"""
    _class_desc = "N/A"

    def setup(self):
        super().setup()
        self.add_connector('sm_bus_mst',
                           I2cLinkDownConnector('device.port.master_side'))
        self.add_connector('sm_bus_sl',
                           I2cLinkDownConnector('device.port.slave_side'))

class slave_wrapper_comp(StandardConnectorComponent):
    """N/A"""
    _class_desc = "N/A"

    def setup(self):
        super().setup()
        self.add_connector('sm_bus',
                           I2cLinkDownConnector('device'))

def insert_dev_into_comp(comp, device):
    '''Insert given device into given component in a slot named "device"'''
    comp.iface.component.add_slot('device')
    comp.iface.component.set_slot_value('device', device)

def connect_to_i2c_v2_link(link, tgt_comp, tgt_conn):
    i2c_conn0 = link.cli_cmds.get_available_connector(type='i2c-link')
    cli.global_cmds.connect(
        cnt0=i2c_conn0,
        cnt1=getattr(tgt_comp,tgt_conn))

class TestBench:
    def __init__(self, smbus_reg_addr, i2c_v2=False):
        self.smbus_pci_config_addr = smbus_reg_addr
        # Bus clock
        clk = simics.pre_conf_object('bus_clk', 'clock')
        clk.freq_mhz = ich9_bus_freq_mhz
        simics.SIM_add_configuration([clk], None)
        self.bus_clk = conf.bus_clk

        # Image and ram
        img = simics.pre_conf_object('img', 'image')
        img.size = smbus_sram_size
        img.queue = self.bus_clk
        simics.SIM_add_configuration([img], None)
        self.sram_image = conf.img

        # Memory-space
        self.mem = simics.pre_conf_object('mem', 'memory-space')
        self.mem.queue = self.bus_clk
        simics.SIM_add_configuration([self.mem], None)
        self.mem = conf.mem
        self.mem_iface = self.mem.iface.memory_space
        self.io_space = simics.SIM_create_object('memory-space', 'io_space', [])
        self.io_space.queue = self.bus_clk
        self.conf_space = simics.SIM_create_object('memory-space',
                                                   'conf_space', [])

        # Initialize memory
        self.memory = dev_util.Memory()

        # PCI bus
        self.pci = simics.SIM_create_object('fake_upstream_target', 'pci')
        self.pci.object_data.mem_obj = self.mem
        self.pci.object_data.io_obj = self.io_space
        self.pci.object_data.conf_obj = self.conf_space

        # SMBus host controller
        smbus = simics.pre_conf_object('smbus', '%s_smbus%s' % (ich_prefix,
                                        '_i2c_v2' if i2c_v2 else ''))
        smbus.upstream_target = self.pci
        smbus.queue   = self.bus_clk
        smbus.sram_image = self.sram_image
        if i2c_v2:
            self.i2c_link = simics.SIM_create_object('i2c_link_v2', 'i2c_link')
            self.smbus_comp = simics.SIM_create_object('smbus_wrapper_comp',
                                                  'smbus_comp')
            insert_dev_into_comp(self.smbus_comp, smbus)
            connect_to_i2c_v2_link(self.i2c_link, self.smbus_comp, 'sm_bus_mst')
            connect_to_i2c_v2_link(self.i2c_link, self.smbus_comp, 'sm_bus_sl')
            cli.global_cmds.instantiate_components()
            self.smbus = self.smbus_comp.device
            self.i2c_link.immediate_delivery = True
        else:
            self.i2c_link = simics.SIM_create_object('i2c_link', 'i2c_link', [])
            smbus.smbus   = self.i2c_link
            simics.SIM_add_configuration([smbus], None)
            self.smbus = conf.smbus

        self.mem.map += [
                          [smbus_reg_addr, self.smbus.bank.pcie_config, 0xff, 0, 0x100],
                        ]

        self.slaves = {}
        self.smbus_func_mapped_addr = 0
        self.smbus_sram_mapped_addr = 0


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

    def map_smbus_func(self, mapped_addr):
        # Enable the io space mapping
        reg_val = self.read_value_le(self.smbus_pci_config_addr + 0x4, 16)
        reg_val = reg_val | 0x1
        self.write_value_le(self.smbus_pci_config_addr + 0x4, 16, reg_val)
        self.write_value_le(self.smbus_pci_config_addr + 0x20, 32, mapped_addr)
        self.smbus_func_mapped_addr = mapped_addr

    def map_smbus_sram(self, mapped_addr):
        # Enable the memory space mapping
        reg_val = self.read_value_le(self.smbus_pci_config_addr + 0x4, 16)
        reg_val = reg_val | 0x2
        self.write_value_le(self.smbus_pci_config_addr + 0x4, 16, reg_val)
        self.write_value_le(self.smbus_pci_config_addr + 0x10, 64, mapped_addr)
        self.smbus_sram_mapped_addr = mapped_addr

    def construct_slave(self, slave_class, slave_addr, slave_addr_mask,
                        i2c_v2=False):
        # SMBus slave device
        name = "slave%d" % slave_addr
        slave = simics.pre_conf_object(name, slave_class)
        slave.addr = slave_addr
        slave.addr_mask = slave_addr_mask
        if i2c_v2:
            slave_comp = simics.SIM_create_object('slave_wrapper_comp',f'{name}_comp')
            insert_dev_into_comp(slave_comp, slave)
            connect_to_i2c_v2_link(self.i2c_link, slave_comp, 'sm_bus')
            cli.global_cmds.instantiate_components()
            slaveobj = slave_comp.device
        else:
            slave.smbus = self.i2c_link
            simics.SIM_add_configuration([slave], None)
            slaveobj = simics.SIM_get_object('slave%d' % slave_addr)
            slaveobj.register = slaveobj

        self.slaves[slave_addr] = slaveobj

    def enable_smbus_host(self, to_enable):
        reg_val = self.read_value_le(self.smbus_pci_config_addr + 0x40, 8)
        if to_enable:
            reg_val = reg_val | 0x1
        else:
            reg_val = reg_val & ~0x1
        self.write_value_le(self.smbus_pci_config_addr + 0x40, 8, reg_val)

    def configure_transfer_paras(self, slave, read_or_write, cmd_para, d0, d1):
        self.write_io_le(self.smbus_func_mapped_addr + 0x3, 8, cmd_para)
        reg_val = slave + read_or_write
        self.write_io_le(self.smbus_func_mapped_addr + 0x4, 8, reg_val)
        self.write_io_le(self.smbus_func_mapped_addr + 0x5, 8, d0)
        self.write_io_le(self.smbus_func_mapped_addr + 0x6, 8, d1)

    def configure_block_paras(self, slave, read_or_write,
                              cmd_code, byte_cnt, block_data):
        self.write_io_le(self.smbus_func_mapped_addr + 0x3, 8, cmd_code)
        reg_val = slave + read_or_write
        self.write_io_le(self.smbus_func_mapped_addr + 0x4, 8, reg_val)
        # Enable the 32-byte block buffer
        self.write_io_le(self.smbus_func_mapped_addr + 0xD, 8, 0x2)

        # Write the bytes to the 32-byte buffer
        if read_or_write == SmbusConst.smb_write:
            self.write_io_le(self.smbus_func_mapped_addr + 0x5, 8, byte_cnt)
            # Clear the internal index pointer
            self.read_io_le(self.smbus_func_mapped_addr + 0x2, 8)
            for i in range(byte_cnt):
                self.write_io_le(self.smbus_func_mapped_addr + 0x7,
                                    8, block_data[i])

    def read_block_data(self):
        byte_cnt = self.read_io_le(self.smbus_func_mapped_addr + 0x5, 8)
        block_data = []
        reg_val = self.read_io_le(self.smbus_func_mapped_addr + 0xD, 8)
        if ((reg_val >> 1) & 0x1) == 0:
            print("32-byte buffer is disabled in the SMBus host controller")
            return (byte_cnt, block_data)

        # Clear the internal index pointer
        self.read_io_le(self.smbus_func_mapped_addr + 0x2, 8)
        for i in range(byte_cnt):
            byte = self.read_io_le(self.smbus_func_mapped_addr + 0x7, 8)
            block_data.append(byte)
        return (byte_cnt, block_data)

    def start_smb_cmd(self, cmd):
        reg_val = self.read_io_le(self.smbus_func_mapped_addr + 0x2, 8)
        reg_val = reg_val & ~(0x7 << 2)
        reg_val = reg_val | (cmd << 2)
        reg_val = reg_val | (0x1 << 6)
        self.write_io_le(self.smbus_func_mapped_addr + 0x2, 8, reg_val)

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
