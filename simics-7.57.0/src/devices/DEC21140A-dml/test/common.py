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


# Definitions used by several subtests.
# This includes a simple configuration that includes the device (DEC21140A)
# and an set of fake devices to assist in testing.

import simics
import conf
import dev_util

# SIMICS-21543
conf.sim.deprecation_level = 0

class Struct:
    def __init__(self, **kws):
        for (k, v) in list(kws.items()):
            setattr(self, k, v)

# This class encapsulates the test state.
# It records the changes in the environment done by the device.
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

def create_config():
    test_state = Test_state()

    # This class records events on the ieee_802_3_phy_v2 interface
    class Phy(dev_util.Ieee_802_3_phy_v2):
        def send_frame(self, sim_obj, buf, replace_crc):
            test_state.seq.append(('send_frame', tuple(buf), replace_crc))
            return 0

        def check_tx_bandwidth(self, sim_obj):
            return 1

    class PciBus(dev_util.IoMemory, dev_util.PciBus):
        def operation(self, sim_obj, mem_op, map_info):
            if simics.SIM_mem_op_is_read(mem_op):
                bytes = test_state.read_mem(
                    simics.SIM_get_mem_op_physical_address(mem_op),
                    simics.SIM_get_mem_op_size(mem_op))
                simics.SIM_set_mem_op_value_buf(mem_op, tuple(bytes))
            else:
                bytes = simics.SIM_get_mem_op_value_buf(mem_op)
                test_state.write_mem(
                    simics.SIM_get_mem_op_physical_address(mem_op), bytes)
            return simics.Sim_PE_No_Exception

        def add_map(self, sim_obj, dev, space, target, info):
            test_state.seq.append(('add_map', dev, space, target,
                                   info.base, info.start, info.length))
            return 0

        def remove_map(self, sim_obj, dev, space, function):
            return 0

        def get_bus_address(self, sim_obj, dev):
            return 0

        def raise_interrupt(self, sim_obj, dev, pin):
            test_state.seq.append(('raise', dev, pin))

        def lower_interrupt(self, sim_obj, dev, pin):
            test_state.seq.append(('clear', dev, pin))

    # Fake objects, to provide the device with a test environment
    fake_mii = dev_util.Dev([dev_util.MiiManagement])
    fake_eeprom = dev_util.Dev([dev_util.Microwire])
    fake_phy = dev_util.Dev([Phy])
    fake_pci_bus = dev_util.Dev([PciBus])

    # Create a test configuration using the classes we have defined.
    # Note that none of the tests here need to advance time, so the
    # configuration does not include a clock at all.

    eth = simics.pre_conf_object('eth', 'DEC21140A-dml')
    eth.mii_bus = fake_mii.obj
    eth.serial_eeprom = fake_eeprom.obj
    eth.phy = fake_phy.obj
    eth.pci_bus = fake_pci_bus.obj

    simics.SIM_add_configuration([eth], None)
    return (conf.eth, test_state)

def dec_regs(eth):
    # DEC registers
    return Struct(
        cfid = dev_util.Register_LE(eth.bank.pci_config, 0x00),
        cfcs = dev_util.Register_LE(
            eth.bank.pci_config,
            0x04,
            bitfield = dev_util.Bitfield_LE({'id'  : 10,
                                             'fb'  : 9,
                                             'se'  : 8,
                                             'wc'  : 7,
                                             'pe'  : 6,
                                             'vga' : 5,
                                             'mwi' : 4,
                                             'sc'  : 3,
                                             'm'   : 2,
                                             'mem' : 1,
                                             'io'  : 0})),
        cfrv = dev_util.Register_LE(eth.bank.pci_config, 0x08),
        cflt = dev_util.Register_LE(eth.bank.pci_config, 0x0c),
        cbma = dev_util.Register_LE(eth.bank.pci_config, 0x14),
        cfit = dev_util.Register_LE(eth.bank.pci_config, 0x3c)
        )

# Descriptor layouts
Receive_desc = {'rdes0' : (0, 4, dev_util.Bitfield_LE({'own'  : 31,
                                                       'ff'   : 30,
                                                       'fl'   : (29, 16),
                                                       'es'   : 15,
                                                       'de'   : 14,
                                                       'dt'   : (13, 12),
                                                       'rf'   : 11,
                                                       'mf'   : 10,
                                                       'fs'   : 9,
                                                       'ls'   : 8,
                                                       'tl'   : 7,
                                                       'cs'   : 6,
                                                       'ft'   : 5,
                                                       'rw'   : 4,
                                                       're'   : 3,
                                                       'db'   : 2,
                                                       'ce'   : 1,
                                                       'zero' : 0})),
                'rdes1' : (4, 4, dev_util.Bitfield_LE({'rer'  : 25,
                                                       'rch'  : 24,
                                                       'rbs2' : (21, 11),
                                                       'rbs1' : (10, 0)})),
                'buf_addr1' : (8, 4),
                'buf_addr2' : (12, 4)}

Transmit_desc = {'tdes0' : (0, 4, dev_util.Bitfield_LE({'own' : 31,
                                                        'es'  : 15,
                                                        'to'  : 14,
                                                        'lo'  : 11,
                                                        'nc'  : 10,
                                                        'lc'  : 9,
                                                        'ec'  : 8,
                                                        'hf'  : 7,
                                                        'cc'  : (6, 3),
                                                        'lf'  : 2,
                                                        'uf'  : 1,
                                                        'de'  : 0})),
                 'tdes1' : (4, 4, dev_util.Bitfield_LE({'ic'   : 31,
                                                        'ls'   : 30,
                                                        'fs'   : 29,
                                                        'ft1'  : 28,
                                                        'set'  : 27,
                                                        'ac'   : 26,
                                                        'ter'  : 25,
                                                        'tch'  : 24,
                                                        'dpd'  : 23,
                                                        'ft0'  : 22,
                                                        'tbs2' : (21, 11),
                                                        'tbs1' : (10, 0)})),
                 'buf_addr1' : (8, 4),
                 'buf_addr2' : (12, 4)}
