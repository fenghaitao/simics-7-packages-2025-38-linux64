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

class i82583V_v2_comp(x86_bios_old_comp):
    """PCIe i82583V Ethernet Controller."""
    _class_desc = "a PCIe Ethernet controller"
    _help_categories = ()
    _no_new_command = object()

    def setup(self):
        x86_bios_old_comp.setup(self)
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def get_pci_device(self):
        return self.get_slot('mac')

    class mac_address(SimpleConfigAttribute("", 's', simics.Sim_Attr_Required)):
        """MAC address."""
        attrattr = simics.Sim_Attr_Optional
        attrtype = "s"
        def _initialize(self):
            self.val = '20:20:20:20:30:30'
        def getter(self):
            return self.val
        def setter(self, val):
            self.val = val

    class eeprom_file(SimpleConfigAttribute('', 's', simics.Sim_Attr_Optional)):
        """The eeprom image file."""
        def lookup(self):
            if self.val:
                file = simics.SIM_lookup_file(self.val)
                if not file:
                    print('lookup of eeprom file %s failed' % self.val)
                    return ''
                return file
            return self.val

    def add_connectors(self):
        self.add_connector('eth', EthernetLinkDownConnector('phy'))
        self.add_connector('pci_bus', PciBusUpMultiFunctionConnector([[0, 'mac']]))

    def add_objects(self):
        mac = self.add_pre_obj('mac', 'i82583V_v2')
        phy = self.add_pre_obj('phy', 'generic_eth_phy')

        spi_image = self.add_pre_obj('nvm_image', 'image')
        spi_flash = self.add_pre_obj('spi_flash', 'M25Pxx')
        spi = self.add_pre_obj('spi', 'e1000_spi')

        mac.phy = phy
        mac.mii = phy
        mac.phy_address = 0
        mac.flash = [spi, "gbe_regs"]
        mac.flash_func = 1

        eeprom_file = self.eeprom_file.lookup()
        if eeprom_file:
            file = open(eeprom_file, mode='r')
            nvm = [None]*64
            for i in range(64):
                nvm[i] = int(file.read(1),16) << 12 | int(file.read(1),16) << 8 | int(file.read(1),16) << 4 | int(file.read(1),16)
            file.close()
            mac.nvm = nvm

        phy.mac = mac
        # PHY identifier
        phy.registers = [0, 0, 0x0141, 0x0cb1] + [0] * 28
        phy.address = 0
        phy.mii_regs_vendor_specific = [0, 0x8200, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

        spi_image.size = 1 << 21
        spi_flash.mem_block = spi_image
        spi_flash.sector_number = (1 << 21) >> 16
        spi_flash.sector_size = 1 << 16

        spi.spi_slave = spi_flash
        spi_flash.spi_master = spi

        if (eeprom_file):
            file = open(eeprom_file, mode='r')
            mac_address = file.read(2) + ':' + file.read(2) + ':' + file.read(2) + ':' +file.read(2) + ':' + file.read(2) + ':' + file.read(2)
            file.close()
            mac.mac_address = mac_address
        else:
            mac.mac_address = self.mac_address.val
        if self.bios.val:
            self.add_prom_objects()
