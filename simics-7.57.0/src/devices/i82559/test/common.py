# Definitions used by several subtests.
# This includes a simple configuration that includes the device (I82559)
# and an set of fake devices to assist in testing.

# © 2012 Intel Corporation
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
import link_components

# SIMICS-21543
conf.sim.deprecation_level = 0

def create_cable_endpoint(link, dev):
    return link_components.create_generic_endpoint('eth-cable-link-endpoint', link, dev)

import sys, os
sys.path.append(os.path.join("..", "common"))
import dev_util
import stest

main_memory_base  = 0x10000
main_memory_off   = 0x00
main_memory_len   = 0x80000000

nic_pci_config_base    = [0xC000, 0xD000]
nic_pci_config_name    = "pci_config"
nic_pci_config_func    = 255
nic_pci_config_off     = 0
nic_pci_config_len     = 0x100

phy_address0 = 0
phy_address1 = 1
mac_address0 ='00:13:72:EC:91:63'
mac_address1 ='00:14:73:ED:92:64'

nic_csr_base           = [0xE000, 0xF000]
nic_csr_name           = "csr"
nic_csr_func           = 0
nic_csr_off            = 0
nic_csr_len            = 0x40

class Test_state:
    def __init__(self):
        # This is a list recording the sequence of things that happens
        # during a part of the test, so that we can verify both that
        # they happened and in the right order.
        self.seq = []

        # Some memory, so the device has something to read/write
        self.memory = dev_util.Memory()

    def read_mem(self, addr, n): return self.memory.read(addr, n)
    def write_mem(self, addr, bytes): self.memory.write(addr, bytes)

test_state = Test_state()

class PciBus(dev_util.IoMemory, dev_util.PciBus):
    def operation(self, sim_obj, mem_op, map_info):
        return mem_space_if.access(mem_op)

    def add_map(self, sim_obj, dev, space, target, info):
        if space != simics.Sim_Addr_Space_Memory:
            raise Exception("IO memory not implemented!")
        return map_demap_if.add_map(dev, target, info)

    def remove_map(self, sim_obj, dev, space, function):
        if space != simics.Sim_Addr_Space_Memory:
            raise Exception("IO memory not implemented!")
        map_demap_if.remove_map(dev, function)
        return 1

    def get_bus_address(self, sim_obj, dev):
        return 0

    def raise_interrupt(self, sim_obj, dev, pin):
        test_state.seq.append(('raise', dev, pin))

    def lower_interrupt(self, sim_obj, dev, pin):
        test_state.seq.append(('clear', dev, pin))

fake_pci_bus = dev_util.Dev([PciBus])

# Fake DRAM and memory bus to be used by the host processor
fake_host_image = simics.pre_conf_object('host_image', 'image')
fake_host_image.size = main_memory_len
simics.SIM_add_configuration([fake_host_image], None)
fake_host_image = conf.host_image

fake_host_dram = simics.pre_conf_object('host_dram', 'ram')
fake_host_dram.image = fake_host_image
fake_host_dram_if = fake_host_image.iface.image
simics.SIM_add_configuration([fake_host_dram], None)
fake_host_dram = conf.host_dram

def mac_as_list(str) :
    return [int(x,16) for x in str.split(":")]

# EEPROM
ma = mac_as_list(mac_address0)
eeprom0 = simics.pre_conf_object("eeprom0", 'microwire-eeprom')
eeprom0.size  = 1024
eeprom0.width = 16
eeprom0.log_level = 0
eeprom_data0 = (ma[1], ma[0], ma[3], ma[2], ma[5], ma[4], 0,   0,# 0 ~ 3
                0,     0,     0,     0,     0,     0,     0,   0,# 4 ~ 7
                0,     0,     0,     0,     0x41,  0xc0,  0,   0,# 8 ~ b
                0,     0,     0,     0,     0,     0,     0,   0,# c ~ f
                0,     0,     0,     0,     0,     0,     0,   0,
                0,     0,     0,     0,     0,     0,     0,   0,
                0,     0,     0,     0,     0,     0,     0,   0,
                0,     0,     0,     0,     0,     0,     0,   0)
eeprom0.data = eeprom_data0
simics.SIM_add_configuration([eeprom0], None)
eeprom0 = conf.eeprom0

ma = mac_as_list(mac_address1)
eeprom1 = simics.pre_conf_object("eeprom1", 'microwire-eeprom')
eeprom1.size  = 1024
eeprom1.width = 16
eeprom1.log_level = 0
eeprom_data1 = (ma[1], ma[0], ma[3], ma[2], ma[5], ma[4], 0,   0,# 0 ~ 3
                0,     0,     0,     0,     0,     0,     0,   0,# 4 ~ 7
                0,     0,     0,     0,     0x41,  0xc0,  0,   0,# 8 ~ b
                0,     0,     0,     0,     0,     0,     0,   0,# c ~ f
                0,     0,     0,     0,     0,     0,     0,   0,
                0,     0,     0,     0,     0,     0,     0,   0,
                0,     0,     0,     0,     0,     0,     0,   0,
                0,     0,     0,     0,     0,     0,     0,   0)
eeprom1.data = eeprom_data1
simics.SIM_add_configuration([eeprom1], None)
eeprom1 = conf.eeprom1

# Create a clock to queue the events of ethernet-link
clk = simics.pre_conf_object('clk', 'clock')
clk.freq_mhz = 1024
simics.SIM_add_configuration([clk], None)
clk = conf.clk

# the ethernet-link to connect to real network
elink0 = simics.pre_conf_object('elink0', 'eth-cable-link')
elink0.log_level = 0
elink0.goal_latency = 0.001
simics.SIM_add_configuration([elink0], None)
elink0 = conf.elink0

#phy
phy0 = simics.pre_conf_object('phy0', 'mii-transceiver')
phy0.mac = None
phy0.address = phy_address0
phy0.mac_address = mac_address0
phy0.registers = [0] * 32
phy0.registers[0]  = 0x1800
phy0.registers[1]  = 0x7809
phy0.registers[2]  = 0x2a8
phy0.registers[3]  = 0x154
phy0.registers[4]  = 0x5f
phy0.registers[18] = phy0.address
phy0.queue = clk
phy0.log_level = 0
nic0 = simics.pre_conf_object('nic0', 'i82559')
nic0.serial_eeprom = eeprom0
nic0.queue = clk
nic0.mii = phy0
nic0.phy = phy0
nic0.phy_address = phy_address0
nic0.pci_bus = fake_pci_bus.obj
phy0.mac = nic0
ep0 = create_cable_endpoint(elink0, phy0)
phy0.link = ep0
simics.SIM_add_configuration([phy0, ep0, nic0], None)
phy0 = conf.phy0
nic0 = conf.nic0

phy1 = simics.pre_conf_object('phy1', 'mii-transceiver')
phy1.mac = None
phy1.address = phy_address1
phy1.mac_address = mac_address1
phy1.registers = [0] * 32
phy1.registers[0]  = 0x1800
phy1.registers[1]  = 0x7809
phy1.registers[2]  = 0x2a8
phy1.registers[3]  = 0x154
phy1.registers[4]  = 0x5f
phy1.registers[18] = phy1.address
phy1.queue = clk
phy1.log_level = 0
nic1 = simics.pre_conf_object('nic1', 'i82559')
nic1.serial_eeprom = eeprom1
nic1.queue = clk
nic1.mii = phy1
nic1.phy = phy1
nic1.phy_address = phy_address1
nic1.pci_bus = fake_pci_bus.obj
phy1.mac = nic1
ep1 = create_cable_endpoint(elink0, phy1)
phy1.link = ep1
simics.SIM_add_configuration([phy1, ep1, nic1], None)
nic1 = conf.nic1
phy1 = conf.phy1

mem_space = simics.pre_conf_object('mem_space', 'memory-space')
simics.SIM_add_configuration([mem_space], None)
mem_space = conf.mem_space

# Host memory can only see the PCI configuration registers at reset
mem_space.map = [
    [   nic_pci_config_base[0],
        [nic0, "pci_config"] ,
        nic_pci_config_func,
        nic_pci_config_off,
        nic_pci_config_len
    ],
    [   nic_pci_config_base[1],
        [nic1, "pci_config"] ,
        nic_pci_config_func,
        nic_pci_config_off,
        nic_pci_config_len
    ],
    # Host main memory map
    [
        main_memory_base,
        fake_host_dram,
        0,
        main_memory_off,
        main_memory_len
    ]
]
mem_space_if = mem_space.iface.memory_space
map_demap_if = mem_space.iface.map_demap

def mem_write(addr, list_buf):
    return mem_space_if.write(None, addr, tuple(list_buf), 0)

def mem_read(addr, len):
    size = len
    result = []
    while size > 1024 :
        result += list(mem_space_if.read(None, addr, 1024, 0))
        size -= 1024
        addr += 1024
    if size > 0 :
        result += list(mem_space_if.read(None, addr, size, 0))
    result = tuple(result)
    return result
