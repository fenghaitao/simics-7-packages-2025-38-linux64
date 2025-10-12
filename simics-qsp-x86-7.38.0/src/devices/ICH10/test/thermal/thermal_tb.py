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


# thermal_tb.py
# testbench of thermal sensor module in ICH9

import simics
import stest
import dev_util
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

import sys, os
sys.path.append(os.path.join("..", "common"))
import pcibus

ich_prefix          = 'ich10'

thermal_reg_addr    = 0x80000000

thermal_mapped_addr = 0x880000000

ich9_bus_freq_mhz   = 1333 # FSB frequency

# Period of the thermal sensor in seconds
thermal_sensing_period  = 3 * ich9_bus_freq_mhz * 1000000

class ThermalConst:
    reset_val = {
                    "VID"   : 0x8086,
                    "DID"   : (0x3A32, 0x3a32)[ich_prefix.startswith('ich10')],
                    "CMD"   : 0x0000,
                    "STS"   : 0x0010,
                    "RID"   : (0x00, 0x00)[ich_prefix.startswith('ich10')],
                    "PI"    : 0x00,
                    "SCC"   : 0x80,
                    "BCC"   : 0x11,
                    "CLS"   : 0x00,
                    "LT"    : 0x00,
                    "HTYPE" : 0x00,
                    "BIST"  : 0x00,
                    "TBAR"  : 0x00000004,
                    "TBARH" : 0x00000000,
                    "SVID"  : 0x0000,
                    "SID"   : 0x0000,
                    "CAP_PTR":0x50,
                    "INTLN" : 0x00,
                    "INTPN" : 0x01,
                    "TBARB" : 0x00000004,
                    "TBARBH": 0x00000000,
                    "PID"   : 0x0001,
                    "PC"    : 0x0023,
                    "PCS"   : 0x0000,

                    "TS0E"  : 0x00,
                    "TS0S"  : 0x00,
                    "TS0TTP": 0x00000000,
                    "TS0CO" : 0x00,
                    "TS0PC" : 0x00,
                    "TS0LOCK":0x00,

                    "TS1E"  : 0x00,
                    "TS1S"  : 0x00,
                    "TS1TTP": 0x00000000,
                    "TS1CO" : 0x00,
                    "TS1PC" : 0x00,
                    "TS1LOCK":0x00,
                }

class TestBench:
    def __init__(self, thermal_reg_addr):
        self.thermal_pci_config_addr = thermal_reg_addr
        # Bus clock
        clk = simics.pre_conf_object('bus_clk', 'clock')
        clk.freq_mhz = ich9_bus_freq_mhz
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

        # PCI bus
        self.pci = simics.SIM_create_object('PCIBus', 'pci',
                                            [['memory', self.mem],
                                             ['io', self.io_space],
                                             ['conf', self.conf_space]])

        # Thermal sensor
        thermal = simics.pre_conf_object('thermal', '%s_thermal' % ich_prefix)
        thermal.pci_bus = self.pci
        thermal.queue   = self.bus_clk
        simics.SIM_add_configuration([thermal], None)
        self.thermal = conf.thermal

        self.mem.map += [
                          [thermal_reg_addr, [self.thermal, 'pci_config'], 0xff, 0, 0x100],
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

    def map_thermal_func(self, mapped_addr):
        # Enable the memory space mapping
        self.write_value_le(self.thermal_pci_config_addr + 0x4, 16, 2)
        self.write_value_le(self.thermal_pci_config_addr + 0x10, 64, mapped_addr)

tb = TestBench(thermal_reg_addr)

def expect_string(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%s', expected '%s'" % (info, actual, expected))

def expect_hex(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '0x%x', expected '0x%x'" % (info, actual, expected))

def expect_list(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%r', expected '%r'" % (info, actual, expected))
