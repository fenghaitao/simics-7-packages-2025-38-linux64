# © 2018 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

# Virtutech specific extensions to dev_util. Mostly stuff that may be
# convenient, but is still rough, and not something we want to commit to.
from dev_util import *
from dev_util import (SimpleInterrupt, SerialDevice,
                      SerialPeripheralInterfaceSlave, Signal, MultiLevelSignal,
                      FrequencyListener, SimpleDispatcher, I2cDevice, I2cBus,
                      I2cLink, Mii, MiiManagement, Microwire, Ieee_802_3_mac,
                      Ieee_802_3_phy, IoMemory, PciBus, PciBridge, PciExpress,
                      Translate, MemorySpace, FirewireDevice,
                      FirewireBus, CacheControl, MapDemap, StepQueue,
                      CycleQueue, Ppc, Sata, wrap_register_init)

class DebugOutput:
    def __init__(self):
        import os
        from cli import pr
        if os.environ.get("V", "") == "1":
            self.out = pr
        else:
            self.out = self.drop

    def drop(self, arg):
        pass

    def write(self, arg):
        self.out(arg)

class StdBitfields:
    def __init__(self):
        self.pci_config = {}

std_bitfields = StdBitfields()

# PCI configuration space bitfields
std_bitfields.pci_config['command'] = Bitfield_LE({'id'  : 10,
                                                   'fb'  : 9,
                                                   'se'  : 8,
                                                   'wc'  : 7,
                                                   'pe'  : 6,
                                                   'vga' : 5,
                                                   'mwi' : 4,
                                                   'sc'  : 3,
                                                   'm'   : 2,
                                                   'mem' : 1,
                                                   'io'  : 0})
std_bitfields.pci_config['status'] = Bitfield_LE({'dpe' : 15,
                                                  'ssa' : 14,
                                                  'rma' : 13,
                                                  'rta' : 12,
                                                  'sta' : 11,
                                                  'ds'  : (9, 10),
                                                  'pe'  : 8,
                                                  'fbb' : 7,
                                                  'mhz' : 5,
                                                  'c'   : 4,
                                                  'ins' : 3})
std_bitfields.pci_config['header_type'] = Bitfield_LE({'mf'   : 7,
                                                       'type' : (6, 0)})
