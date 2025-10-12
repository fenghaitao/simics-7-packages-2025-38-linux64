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


import simics
from comp import *
import flash_memory

simics.SIM_load_module("pci-comp")
from simmod.pci_comp.pci_comp import x86_bios_old_comp

class i82571EB_v2_comp(x86_bios_old_comp):
    """PCIe i82571EB Ethernet controller."""
    _class_desc = "a PCIe Ethernet controller"
    _help_categories = ()
    _no_new_command = object()

    def setup(self):
        x86_bios_old_comp.setup(self)
        if not self.instantiated.val:
            self.add_i82571eb_objects()
        self.add_i82571eb_connectors()

    def get_pci_device(self):
        return self.get_slot('mac[0]')

    class mac_address0(SimpleConfigAttribute("", 's', simics.Sim_Attr_Required)):
        """MAC address 0 for LAN A."""
        attrattr = simics.Sim_Attr_Optional
        attrtype = "s"
        def _initialize(self):
            self.val = '20:20:20:20:30:30'
        def getter(self):
            return self.val
        def setter(self, val):
            self.val = val

    class mac_address1(SimpleConfigAttribute("", 's', simics.Sim_Attr_Required)):
        """MAC address 1 for LAN B."""
        attrattr = simics.Sim_Attr_Optional
        attrtype = "s"
        def _initialize(self):
            self.val = '20:20:20:20:30:31'
        def getter(self):
            return self.val
        def setter(self, val):
            self.val = val

    def add_i82571eb_connectors(self):
        self.add_slot('eth', [self.add_connector('', EthernetLinkDownConnector('phy[0]')),
                              self.add_connector('', EthernetLinkDownConnector('phy[1]'))])
        self.add_connector('pci_bus', PciBusUpMultiFunctionConnector([[0, 'mac[0]'], [1, 'mac[1]']]))

    def add_i82571eb_objects(self):
        mac = self.add_pre_obj('mac[2]', 'i82571EB_v2')
        phy = self.add_pre_obj('phy[2]', 'generic_eth_phy')

        spi_image = self.add_pre_obj('spi_image[2]', 'image')
        spi_flash = self.add_pre_obj('spi_flash_obj[2]', 'M25Pxx')
        spi = self.add_pre_obj('spi[2]', 'e1000_spi')

        for i in range(len(mac)):
            mac[i].lan_identifier = i
            mac[i].phy = phy[i]
            mac[i].mii = phy[i]
            mac[i].phy_address = 1
            mac[i].flash = [spi[i], "gbe_regs"]
            mac[i].flash_func = 1
            # e1000e driver in ubuntu seems to need this
            # in order to allocate an irq (we don't have msi yet)
            mac[i].pci_config_interrupt_pin = i + 1

            phy[i].mac  = mac[i]
            phy[i].registers = [0, 0, 0x02A8, 0x0380] + [0] * 28
            phy[i].address = 1
            phy[i].mii_regs_vendor_specific = [0, 0x8200, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

            spi_image[i].size = 1 << 21
            spi_flash[i].mem_block = spi_image[i]
            spi_flash[i].sector_number = (1 << 21) >> 16
            spi_flash[i].sector_size = 1 << 16

            spi[i].spi_slave = spi_flash[i]
            spi_flash[i].spi_master = spi[i]

        mac[0].mac_address = self.mac_address0.val
        mac[1].mac_address = self.mac_address1.val
        if self.bios.val:
            self.add_prom_objects()
