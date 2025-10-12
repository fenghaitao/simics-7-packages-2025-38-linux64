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


import simics
from comp import *
import flash_memory

simics.SIM_load_module("pci-comp")
from simmod.pci_comp.pci_comp import x86_bios_old_comp

class i210_comp(x86_bios_old_comp):
    """PCIe i210 Ethernet Controller."""
    _class_desc = "a PCIe Ethernet controller"
    _help_categories = ()

    def setup(self):
        x86_bios_old_comp.setup(self)
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def get_pci_device(self):
        return self.get_slot('mac')

    class mac_address(SimpleConfigAttribute('20:20:20:20:30:30', 's', simics.Sim_Attr_Optional)):
        """MAC address, default 20:20:20:20:30:30"""

    class phy_id(SimpleConfigAttribute(0x01410C00, 'i', simics.Sim_Attr_Optional)):
        """PHY ID value, default 0x01410C00 (i210 Linux 4.3)"""

    def add_connectors(self):
        self.add_slot('eth', [self.add_connector('', EthernetLinkDownConnector('phy'))])
        self.add_connector('pci_bus', PciBusUpMultiFunctionConnector([[0, 'mac']]))

    def add_objects(self):
        mac = self.add_pre_obj('mac', 'i210')
        phy = self.add_pre_obj('phy', 'generic_eth_phy')

        spi_image = self.add_pre_obj('nvm_image', 'image')
        spi_flash = self.add_pre_obj('spi_flash', 'M25Pxx')
        spi = self.add_pre_obj('spi', 'e1000_spi')

        mac.phy = phy
        mac.mii = phy
        mac.phy_address = 0
        mac.flash = [spi, "gbe_regs"]
        mac.flash_func = 1

        phy.mac = mac
        phy.address = 0
        phy.phy_id = self.phy_id.val
        phy.mii_regs_vendor_specific = [0, 0x8200, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

        spi_image.size = 1 << 21
        spi_flash.mem_block = spi_image
        spi_flash.sector_number = (1 << 21) >> 16
        spi_flash.sector_size = 1 << 16

        spi.spi_slave = spi_flash
        spi_flash.spi_master = spi

        mac.mac_address = self.mac_address.val
        if self.bios.val:
            self.add_prom_objects()
