# © 2013 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from comp import *

class cpci_backplane(StandardConnectorComponent):
    """A sample cPCI backplane."""
    _class_desc = 'cPCI backplane'
    _help_categories = ('PCI',)

    class basename(StandardComponent.basename):
        val = 'cpci_backplane'

    class top_level(StandardConnectorComponent.top_level):
        def _initialize(self):
            self.val = True

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_objects(self):
        # A clock is needed for standalone instantiation
        clock = self.add_pre_obj('clock', 'clock')
        clock.freq_mhz = 1000

        # Backplane PCI bus
        pci_bus = self.add_pre_obj('pci_bus', 'pci-bus')
        pci_mem = self.add_pre_obj('pci_mem', 'memory-space')
        pci_io = self.add_pre_obj('pci_io', 'memory-space')
        pci_conf = self.add_pre_obj('pci_conf', 'memory-space')
        pci_bus.memory_space = pci_mem
        pci_bus.io_space = pci_io
        pci_bus.conf_space = pci_conf
        pci_bus.pci_devices = []  # must initialize or connect will fail
        pci_bus.bridge = []       # ...

    def add_connectors(self):
        # some slots can route interrupts (used by bridges)
        self.add_slot('bridge_slot', [self.add_connector(
                    None, CompactPciBusDownConnector(i, 'pci_bus',
                                                     bridge_supported=True))
                                      for i in range(5)])

        # while others cannot (used by devices)
        self.add_slot('device_slot', [self.add_connector(
                    None, CompactPciBusDownConnector(10 + i, 'pci_bus'))
                               for i in range(5)])

        # for debug purpose only, normal PCI slot
        self.add_connector('pci_slot', PciBusDownConnector(20, 'pci_bus'))
