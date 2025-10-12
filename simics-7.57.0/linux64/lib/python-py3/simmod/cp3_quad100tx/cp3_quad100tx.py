# © 2011 Intel Corporation
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
import simics
import component_utils

class cp3_quad100tx(StandardConnectorComponent):
    """The cp3-quad100tx component class."""
    _class_desc = "cp3-quad100tx component"
    _help_categories = ('PCI', 'Networking')

    def setup(self):
        StandardConnectorComponent.setup(self)
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    class top_level(StandardConnectorComponent.top_level):
        def _initialize(self):
            self.val = False

    class mac_addr1(SimpleConfigAttribute(None, 's', simics.Sim_Attr_Required)):
        """The MAC address of eth1"""

    class mac_addr2(SimpleConfigAttribute(None, 's', simics.Sim_Attr_Required)):
        """The MAC address of eth2"""

    class mac_addr3(SimpleConfigAttribute(None, 's', simics.Sim_Attr_Required)):
        """The MAC address of eth3"""

    class mac_addr4(SimpleConfigAttribute(None, 's', simics.Sim_Attr_Required)):
        """The MAC address of eth4"""

    def add_connectors(self):
        self.add_connector('pci', PciBusUpConnector(0, 'bridge'))
        self.add_connector('eth1', EthernetLinkDownConnector('phy[0]'))
        self.add_connector('eth2', EthernetLinkDownConnector('phy[1]'))
        self.add_connector('eth3', EthernetLinkDownConnector('phy[2]'))
        self.add_connector('eth4', EthernetLinkDownConnector('phy[3]'))

    def calculate_csum(self, data):
        # After adding the 16-bit words 0x00 to 0x3F, the sum should be
        # 0xBABA after masking off the carry bits.
        sum = 0
        for i, x in enumerate(data):
            if i&1: sum += x
            else:   sum += x << 8
        sum = 0xbaba - sum
        return ((sum & 0xff00) >> 8, sum & 0xff)

    def add_objects(self):
        mac_addrs = [
            self.mac_addr1.val,
            self.mac_addr2.val,
            self.mac_addr3.val,
            self.mac_addr4.val,
            ]
        mal = list(map(mac_as_list, mac_addrs))

        # eeprom
        eeprom = self.add_pre_obj("eeprom[4]", 'microwire-eeprom')
        for i in range(4):
            eeprom[i].size  = 1024 # 64 16-bit words
            eeprom[i].width = 16
            ma = mal[i]
            eeprom_data = (
                ma[1], ma[0], ma[3], ma[2], ma[5], ma[4], 0,   0x03,# 0 ~ 3
                0,     0,     0x1,   0x2,   0x47,  0x1,   0,   0,# 4 ~ 7
                0,     0,     0,     0,     0x41,  0xc0,  0,   0,# 8 ~ b
                0,     0,     0,     0,     0,     0,     0,   0,# c ~ f
                0,     0,     0,     0,     0,     0,     0,   0,
                0,     0,     0,     0,     0,     0,     0,   0,
                0,     0,     0,     0,     0,     0,     0,   0,
                0,     0,     0,     0,     0,     0,     0,   0
            ) + (0,) * 62
            eeprom_data = eeprom_data + self.calculate_csum(eeprom_data)
            assert self.calculate_csum(eeprom_data) == (0, 0)
            eeprom[i].data = eeprom_data

        # phy1
        phy = self.add_pre_obj('phy[4]', 'mii-transceiver')
        for i in range(4):
            phy[i].mac = None
            phy[i].registers = [0] * 32
            phy[i].registers[0]  = 0x1800
            phy[i].registers[1]  = 0x7809
            phy[i].registers[2]  = 0x2a8
            phy[i].registers[3]  = 0x154
            phy[i].registers[4]  = 0x5f
            phy[i].registers[18] = 1

        # i82559
        mac = self.add_pre_obj('mac[4]', 'i82559')
        for i in range(4):
            # morph the 82559 into an 82559ER
            mac[i].pci_config_device_id = 0x1209

            # 82559 has vendor-mutable ID configs
            # massage them to look like a RAMIX device
            mac[i].pci_config_subsystem_vendor_id = 0x140b
            mac[i].pci_config_subsystem_id = 0x0009
            mac[i].pci_config_header_type = 0

            mac[i].pci_config_interrupt_pin = 1
            mac[i].serial_eeprom = eeprom[i]
            mac[i].mii = phy[i]
            mac[i].phy = phy[i]
            mac[i].phy_address = (i + 1)
            phy[i].mac = mac[i]

        # i21152 PCI bridge and bus
        bridge = self.add_pre_obj("bridge", "i21154")

        pci_bus = self.add_pre_obj('pci_bus', 'pci-bus')
        pci_space_io = self.add_pre_obj('pci_io', 'memory-space')
        pci_space_conf = self.add_pre_obj('pci_conf', 'memory-space')
        pci_space_mem = self.add_pre_obj('pci_mem', 'memory-space')
        pci_bus.io_space = pci_space_io
        pci_bus.conf_space = pci_space_conf
        pci_bus.memory_space = pci_space_mem
        bridge.secondary_bus = pci_bus
        pci_bus.bridge = bridge
        pci_bus.pci_devices = [ ]
        pci_bus.pci_devices += [ [ 0, 0, mac[0] ] ]
        pci_bus.pci_devices += [ [ 1, 0, mac[1] ] ]
        pci_bus.pci_devices += [ [ 2, 0, mac[2] ] ]
        pci_bus.pci_devices += [ [ 3, 0, mac[3] ] ]

        for i in range(4):
            mac[i].pci_bus = pci_bus
