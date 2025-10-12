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


from comp import *

class generic_pcie_switch(StandardConnectorComponent):
    """Generic PCIe switch with a configurable number of ports and configurable
    vendor and device IDs"""
    _class_desc = 'generic configurable PCIe switch'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    class basename(StandardConnectorComponent.basename):
        val = 'pcie_switch'

    class port_count(SimpleConfigAttribute(5, 'i')):
        """Number of down ports"""

    class vendor_id(SimpleConfigAttribute(0x8086, 'i')):
        """Vendor ID"""

    class device_id(SimpleConfigAttribute(0x0370, 'i')):
        """Device ID"""

    def add_connectors(self):
        self.add_connector(
            'up', PciBusUpConnector(0, 'up_port', use_upstream=True))
        self.add_slot('down', [self.add_connector(
            None, PciBusDownConnector(0, 'down_bus[%d]' % i))
                               for i in range(self.port_count.val)])

    def add_objects(self):
        # One up-port
        up_port = self.add_pre_obj('up_port', 'generic_pcie_switch_port')
        up_port.is_upstream = True
        up_port.port_num = 0
        up_port.pci_config_vendor_id = self.vendor_id.val
        up_port.pci_config_device_id = self.device_id.val

        # Internal PCIe bus, connecting the up-port to all the down-ports
        vbus_conf = self.add_pre_obj('vbus_conf', 'memory-space')
        vbus_io   = self.add_pre_obj('vbus_io', 'memory-space')
        vbus_mem  = self.add_pre_obj('vbus_mem', 'memory-space')
        vbus      = self.add_pre_obj('vbus', 'pcie-bus')

        vbus_conf.map = []
        vbus_io.map = []
        vbus_mem.map = []

        vbus.conf_space = vbus_conf
        vbus.io_space = vbus_io
        vbus.memory_space = vbus_mem
        vbus.pci_devices = []
        vbus.bridge = up_port
        vbus.upstream_target = up_port

        up_port.secondary_bus = vbus

        # Down ports
        down_port = self.add_pre_obj(
            'down_port[%d]' % self.port_count.val, 'generic_pcie_switch_port')

        for (i, port) in enumerate(down_port):
            port.is_upstream = False
            port.port_num = i
            port.pci_config_vendor_id = self.vendor_id.val
            port.pci_config_device_id = self.device_id.val
            vbus.pci_devices += [[i, 0, port]]

        # PCIe busses for all the down ports
        down_bus_conf = self.add_pre_obj(
            'down_bus_conf[%d]' % self.port_count.val, 'memory-space')
        down_bus_io = self.add_pre_obj(
            'down_bus_io[%d]' % self.port_count.val, 'memory-space')
        down_bus_mem = self.add_pre_obj(
            'down_bus_mem[%d]' % self.port_count.val, 'memory-space')
        down_bus = self.add_pre_obj(
            'down_bus[%d]' % self.port_count.val, 'pcie-bus')

        for s in down_bus_conf + down_bus_io + down_bus_mem:
            s.map = []

        for (port, b, conf, io, mem) in zip(down_port, down_bus, down_bus_conf,
                                            down_bus_io, down_bus_mem):
            b.conf_space = conf
            b.io_space = io
            b.memory_space = mem
            b.pci_devices = []
            b.bridge = port
            b.upstream_target = port

            port.pci_bus = vbus
            port.secondary_bus = b
            port.upstream_target = vbus
