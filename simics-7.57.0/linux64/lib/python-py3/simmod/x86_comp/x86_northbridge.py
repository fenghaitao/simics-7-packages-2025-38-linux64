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


import simics
from comp import *

class northbridge_x86(StandardConnectorComponent):
    """Base class for x86 northbridge."""
    _do_not_init = object()

    def _initialize(self, pci_bus_class = 'pci-bus'):
        super()._initialize()
        self.pci_bus_class = pci_bus_class

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_northbridge_x86_objects()
        self.add_northbridge_x86_connectors()

    def add_northbridge_x86_connectors(self):
        pci_slots = [None]
        for i in range(1, 32):
            pci_slots.append(self.add_connector(None, PciBusDownConnector(i, 'pci_bus')))
        self.add_slot('pci_slot', pci_slots)

    def add_northbridge_x86_objects(self):
        pci_mem = self.add_pre_obj('pci_mem', 'memory-space')
        pci_conf = self.add_pre_obj('pci_conf', 'memory-space')
        pci_io = self.add_pre_obj('pci_io', 'memory-space')
        pci_mem.map = []
        pci_conf.map = []
        pci_io.map = []
        pci_bus = self.add_pre_obj('pci_bus', self.pci_bus_class)
        pci_bus.memory_space = pci_mem
        pci_bus.conf_space = pci_conf
        pci_bus.io_space = pci_io
        pci_bus.pci_devices = []

class northbridge_agp:
    def add_agp_connectors(self):
        self.add_connector('agp_slot', AgpDownConnector(0, 'agp_bus'))

    def add_agp_objects(self):
        # pci_slot[1] is used by agp
        pci_slot = self.get_slot('pci_slot')
        simics.SIM_delete_object(pci_slot[1])
        pci_slot[1] = None
        self.add_slot('pci_slot', pci_slot)

        agp_conf = self.add_pre_obj('agp_conf', 'memory-space')
        agp_io = self.add_pre_obj('agp_io', 'memory-space')
        agp_io.map = []
        agp_mem = self.add_pre_obj('agp_mem', 'memory-space')
        agp_mem.map = []
        agp_bus = self.add_pre_obj('agp_bus', 'pci-bus')
        agp_bus.conf_space = agp_conf
        agp_bus.io_space = agp_io
        agp_bus.memory_space = agp_mem
        agp_bus.pci_devices = []
        agp = self.get_slot('pci_to_agp')
        agp.pci_bus = self.get_slot('pci_bus')
        agp.secondary_bus = agp_bus
        agp_bus.bridge = agp
        self.get_slot('bridge').agp_bridge = agp
        self.get_slot('pci_bus').pci_devices += [[1, 0, agp]]
