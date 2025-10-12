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


import os
import simics
from comp import (
    StandardComponent, StandardConnectorComponent,
    CompException,
    ConfigAttribute, SimpleConfigAttribute, mac_as_list
)
from component_utils import get_highest_2exp
import connectors
import systempanel
import systempanel.widgets as w
from deprecation import DEPRECATED

def byte_swap(tpl):
    return sum(zip(tpl[1::2], tpl[::2]), ())

class x86_bios_comp(StandardConnectorComponent):
    _do_not_init = object()

    class bios(SimpleConfigAttribute(None, 's|n')):
        '''The x86 BIOS file to use.'''
        def setter(self, val):
            if self._up.obj.configured:
                return simics.Sim_Set_Illegal_Value
            self.val = val

    class component(StandardConnectorComponent.component):
        def pre_instantiate(self):
            file_name = self._up.bios.val
            if not file_name:
                return True
            if not simics.SIM_lookup_file(file_name):
                print('Could not find BIOS file ' + file_name)
                return False
            size = os.stat(simics.SIM_lookup_file(file_name)).st_size
            map_size = get_highest_2exp(size - 1) << 1
            self._up.get_slot('prom_image').size = map_size
            self._up.get_pci_device().expansion_rom = [self._up.get_slot('prom'),
                                                       map_size, 0]
            self._up.get_slot('prom_image').files = [[file_name, 'ro', 0, size]]
            return True

    def add_prom_objects(self):
        prom_image = self.add_pre_obj('prom_image', 'image')
        prom = self.add_pre_obj('prom', 'rom')
        prom.image = prom_image

# for old pci device which separates expansion_rom assignment to two attributes
class x86_bios_old_comp(x86_bios_comp):
    _do_not_init = object()

    class component(StandardConnectorComponent.component):
        def pre_instantiate(self):
            file_name = self._up.bios.val
            if not file_name:
                return True
            if not simics.SIM_lookup_file(file_name):
                print('Could not find BIOS file ' + file_name)
                return False
            size = os.stat(simics.SIM_lookup_file(file_name)).st_size
            map_size = get_highest_2exp(size - 1) << 1
            self._up.get_slot('prom_image').size = map_size
            self._up.get_pci_device().expansion_rom = self._up.get_slot('prom')
            self._up.get_pci_device().expansion_rom_size = map_size
            self._up.get_slot('prom_image').files = [[file_name, 'ro', 0, size]]
            return True

class pci_dec21140(StandardConnectorComponent):
    '''The pci-dec21140a component represents a DEC21140A PCI based
    fast Ethernet adapter'''
    _class_desc = 'a PCI-based fast Ethernet adapter'
    _help_categories = ('PCI', 'Networking')

    class basename(StandardConnectorComponent.basename):
        val = 'eth_adapter'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    class mac_address(ConfigAttribute):
        """The MAC address of the Ethernet adapter."""
        attrattr = simics.Sim_Attr_Required
        attrtype = 's'
        def _initialize(self):
            self.val = ""
        def getter(self):
            return self.val
        def setter(self, val):
            if len(mac_as_list(val)) != 6:
                return simics.Sim_Set_Illegal_Value
            self.val = val

    class bios(SimpleConfigAttribute(None, 's|n')):
        'The x86 BIOS file to use.'

    def add_objects(self):
        dec = self.add_pre_obj('dec', "DEC21140A-dml")

        eeprom = self.add_pre_obj('eeprom', "microwire-eeprom")
        self.add_component('system_panel', 'pci_dec21140_panel', [])
        mac_a = mac_as_list(self.mac_address.val)
        eeprom_data = byte_swap((
                0x0e, 0x11, 0xb0, 0xbb, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x18, 0x3f, 0x01, 0x04,
                mac_a[0], mac_a[1], mac_a[2],
                mac_a[3], mac_a[4], mac_a[5],
                0x1e, 0x00, 0x00, 0x00, 0x00, 0x00,

                0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,

                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,

                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00))
        # The last two bytes should be the CRC, but we ignore it here
        if self.bios.val:
            prom_image = self.add_pre_obj('prom_image', 'image')
            prom = self.add_pre_obj('prom', 'rom')
            prom.image = prom_image
            dec.expansion_rom = prom

        eeprom.data = eeprom_data
        eeprom.width = 16
        eeprom.size = 1024

        phy = self.add_pre_obj('phy', "generic_eth_phy")
        phy.mac = dec

        mii = self.add_pre_obj('mii', "mii-management-bus")

        dec.phy = phy
        dec.serial_eeprom = eeprom
        dec.mii_bus = mii
        mii.devices = [[phy, 0]]

        phy.link_led = self.get_slot('system_panel.link')
        phy.tx_led = self.get_slot('system_panel.tx')
        phy.rx_led = self.get_slot('system_panel.rx')

    def add_connectors(self):
        self.add_connector(
            'pci_bus', connectors.PciBusUpConnector(
                0, 'dec', hotpluggable = False, required = True))
        self.add_connector(
            'ethernet', connectors.EthernetLinkDownConnector('phy'))

    class component(StandardComponent.component):
        def pre_instantiate(self):
            self._up.pre_instantiate_dec21140a()
            return True

    def pre_instantiate_dec21140a(self):
        if self.bios.val:
            bios_file = simics.SIM_lookup_file(self.bios.val)
            if not bios_file:
                raise CompException(
                    'Could not find BIOS file %s' % self.bios.val)
            biossize = os.stat(bios_file).st_size
            map_size = get_highest_2exp(biossize - 1) << 1
            self.get_slot("prom_image").size = map_size
            self.get_slot("prom_image").files = [[self.bios.val, 'ro', 0, biossize]]
            self.get_slot("dec").expansion_rom_size = map_size

class pci_dec21140_panel(systempanel.SystemPanel):
    """System panel for a DEC21140 PCI network card."""
    _class_desc = "a PCI network card system panel"
    default_layout = w.LabeledBox('', w.Grid(columns=2, contents=[
                w.Led('link'), w.Label("Link"),
                w.Led('tx'), w.Label("Tx"),
                w.Led('rx'), w.Label("Rx")]))

    objects = default_layout.objects()

def MacAddressAttribute(val = []):
    class PCA(ConfigAttribute):
        attrtype = 's'
        attrattr = simics.Sim_Attr_Required
        valid = val
        def _initialize(self):
            self.val = None
        def getter(self):
            return self.val
        def setter(self, val):
            if self._up.obj.configured:
                return simics.Sim_Set_Illegal_Value
            if len(mac_as_list(val)) != 6:
                return simics.Sim_Set_Illegal_Value
            self.val = val
    return PCA

class pci_bcm5703c_comp(x86_bios_comp):
    '''The "pci_bcm5703c_comp" component represents a Broadcom 5703C PCI based
gigabit Ethernet adapter.'''
    _class_desc = 'a PCI-based Gb eth adapter'
    _help_categories = ('PCI', 'Networking')

    class basename(x86_bios_comp.basename):
        val = 'eth_adapter'

    class mac_address(MacAddressAttribute()):
        '''The MAC address of the Ethernet adapter.'''
        pass

    def get_pci_device(self):
        return self.get_slot('bge')

    def setup(self):
        x86_bios_comp.setup(self)
        if not self.instantiated.val:
            self.add_objects()
        self.add_connector('pci_bus', connectors.PciBusUpConnector(
            0, 'bge', hotpluggable = False, required = True))
        self.add_connector('eth', connectors.EthernetLinkDownConnector('bge'))

    def add_objects(self):
        bge = self.add_pre_obj('bge', 'BCM5703C')
        bge.mac_address = self.mac_address.val
        if self.bios.val:
            self.add_prom_objects()

class pci_bcm5704c_comp(x86_bios_comp):
    '''The "pci_bcm5704c_comp" component represents a Broadcom 5704C PCI based
dual-port gigabit Ethernet adapter.'''
    _class_desc = 'a PCI-based dual-port Gb eth adapter'
    _help_categories = ('PCI', 'Networking')

    class basename(x86_bios_comp.basename):
        val = 'eth_adapter'

    class mac_address0(MacAddressAttribute()):
        '''The MAC address of the first Ethernet adapter.'''
        pass

    class mac_address1(MacAddressAttribute()):
        '''The MAC address of the second Ethernet adapter.'''
        pass

    def get_pci_device(self):
        return self.get_slot('bge[0]')

    def setup(self):
        x86_bios_comp.setup(self)
        if not self.instantiated.val:
            self.add_objects()
        self.add_slot(
            'eth',
            [self.add_connector(
                None, connectors.EthernetLinkDownConnector('bge[%d]' % (i,)))
             for i in range(2)])
        self.add_connector('pci_bus',
                connectors.PciBusUpMultiFunctionConnector(
                        [(0, 'bge[0]'), (1, 'bge[1]')]))

    def add_objects(self):
        bge = self.add_pre_obj('bge[2]', 'BCM5704C')
        for i in range(2):
            bge[i].mac_address = getattr(self, 'mac_address%d' % (i,)).val
            bge[i].is_mac1 = [0, 1][i]
            bge[i].other_bcm = bge[1 - i]
        if self.bios.val:
            self.add_prom_objects()

class pci_am79c973_comp(x86_bios_old_comp):
    '''The "pci_am79c973_comp" component represents a AM79C973 PCI based
Ethernet adapter.'''
    _class_desc = 'an AM79C973 PCI-based Ethernet adapter'
    _help_categories = ('PCI', 'Networking')

    class basename(x86_bios_old_comp.basename):
        val = 'eth_adapter'

    class mac_address(MacAddressAttribute()):
        '''The MAC address of the Ethernet adapter.'''
        pass

    def get_pci_device(self):
        return self.get_slot('lance')

    def setup(self):
        x86_bios_old_comp.setup(self)
        if not self.instantiated.val:
            self.add_objects()
        self.add_connector('eth', connectors.EthernetLinkDownConnector('phy'))
        self.add_connector('pci_bus', connectors.PciBusUpConnector(
            0, 'lance', hotpluggable = False, required = True))

    def add_objects(self):
        phy = self.add_pre_obj('phy', 'mii-transceiver')
        lance = self.add_pre_obj('lance', 'AM79C973')
        phy.mac = lance
        lance.phy = phy
        aprom = [0] * 16
        aprom[0:6] = mac_as_list(self.mac_address.val)
        aprom[14:16] = [0x57, 0x57]
        lance.ioreg_aprom = aprom
        if self.bios.val:
            self.add_prom_objects()

class VgaPciBusUpConnector(connectors.PciBusUpConnector):
    def __init__(self, vga, cls, maps, extra_vga_maps=False):
        connectors.PciBusUpConnector.__init__(
                self, 0, vga, hotpluggable = False, required = True)
        self.cls = cls
        self.vga = vga
        self.maps = maps

    def check(self, cmp, cnt, attr):
        (_, pci_bus) = attr
        if isinstance(pci_bus, simics.conf_object_t):
            # See bug 20806
            print('The "%s" component only supports connecting to %s ' % (
                    self.cls, 'a non-instantiated PCI bus'))
            return False
        return True

    def connect(self, cmp, cnt, attr):
        (_, pci_bus) = attr
        vga = cmp.get_slot(self.vga)
        vga.pci_bus = pci_bus
        vga.memory_space = pci_bus.memory_space
        if not hasattr(pci_bus.memory_space, 'map'):
            pci_bus.memory_space.map = []
        if not hasattr(pci_bus.io_space, 'map'):
            pci_bus.io_space.map = []
        for (base, obj, func, ofs, len) in self.maps:
            pci_bus.memory_space.map += [
                    [base, cmp.get_slot(obj), func, ofs, len]]

class vga_bios_comp(StandardConnectorComponent):
    _do_not_init = object()

    class basename(StandardConnectorComponent.basename):
        val = 'gfx_adapter'

    class bios(SimpleConfigAttribute(
            'seavgabios-simics-x58-ich10-1.11-20180508.bin', 's')):
        '''The VGA BIOS file to use (empty string if no VGA BIOS is needed)'''
        def setter(self, val):
            if self._up.obj.configured:
                return simics.Sim_Set_Illegal_Value
            self.val = val

    class component(StandardConnectorComponent.component):
        def post_instantiate(self):
            self._up.load_file_into_image()
            vga = self._up.get_slot('vga')
            vga_pspace = self._up.get_slot('vga_pspace')

            io_spaces = []
            if getattr(vga.pci_bus, "upstream_target", False):
                io_spaces += [vga.pci_bus.io_space]

            try:
                cur_bus = vga.pci_bus
                # Ugly work around for SB pcie ports
                while True:
                    bus = getattr(cur_bus.bridge, "pci_bus", False)
                    if cur_bus == bus:
                        break
                    cur_bus = bus

                io_spaces += [cur_bus.io_space]
            except Exception:
                pass

            for io_space in set(io_spaces):
                io_space.map += [[0x1ce, vga_pspace, 0, 0x1ce, 4]]
                io_space.map += [[0x3b0, vga_pspace, 0, 0x3b0, 0x30]]

            top_component = vga.component.top_component
            if top_component and top_component.cpu_list:
                b = top_component.cpu_list[0].system
                if hasattr(vga, "system"):
                    vga.system = b

    def setup(self):
        super().setup()
        vga_sub_obj = getattr(self, 'gfx_sub_obj', None)
        self.add_connector('console',
                           connectors.GfxDownConnector('vga',
                                                       'console',
                                                       sub_obj = vga_sub_obj))

    def load_file_into_image(self, target_image=None):
        # Load the bios into the ROM area, so that checkpoints not depend
        # on the BIOS file being available all time.
        if not self.bios.val:
            return
        biospath = (simics.SIM_lookup_file(self.bios.val)
                    or simics.SIM_lookup_file('%simics%/targets/common/images/'
                                              + self.bios.val))
        with open(biospath, "rb") as f:
            data = f.read()
        if target_image:
            image = target_image
        else:
            image = self.get_slot('prom_image')
        image.iface.image.set(0, data)

    def add_vga_objects(self, vram_size):
        vga = self.add_pre_obj('vga', self._vga_class )
        vram_image = self.add_pre_obj('vram_image', 'image')
        vram_image.size = vram_size
        vga.image = vram_image
        vga.lfb_size = vram_size

        if self.bios.val:
            biospath = (simics.SIM_lookup_file(self.bios.val)
                        or simics.SIM_lookup_file('%simics%/targets/common/images/'
                                                  + self.bios.val))
            if not biospath:
                raise CompException('Could not find video BIOS file ' +
                                    self.bios.val)
            biossize = os.stat(biospath).st_size
            map_size = get_highest_2exp(biossize - 1) << 1

            prom_img = self.add_pre_obj('prom_image', 'image', size = map_size)
            prom = self.add_pre_obj('prom', 'rom', image = prom_img)
            vga.expansion_rom = [prom, map_size, 0]

        # special port-space to work-around 16-bit access to 1-byte port
        self.vga_pspace = self.add_pre_obj('vga_pspace', 'port-space')
        self.vga_pspace.map = []
        self.vga_pspace.map += [[0x1ce, vga, 3, 0, 2]]
        self.vga_pspace.map += [[0x1cf, vga, 3, 1, 2]]
        self.vga_pspace.map += [[0x1d0, vga, 3, 1, 2]] # GOP driver uses port 0x1d0 instead of 0x1cf
        self.vga_pspace.map += [[0x3b0 + i, vga, 0, 0x3b0 + i, 1] for i in range(0x30)] # IO_VGA

        return vga

    def get_option_rom_size(self):
        if not self.has_slot('prom_image'):
            return False
        return self.get_slot('prom_image').size

class pci_vga_comp(vga_bios_comp):
    '''The "pci_vga_comp" component represents a PCI based VGA compatible
graphics adapter.'''
    _class_desc = 'a PCI-based VGA graphics adapter'
    _help_categories = ('PCI', 'Graphics')
    _vga_class = 'vga_pci'

    def setup(self):
        vga_bios_comp.setup(self)
        if not self.instantiated.val:
            self.add_objects()
        self.add_connector('pci_bus',
                           VgaPciBusUpConnector(
                                   'vga', 'pci_vga_comp',
                                   [[0x0000a0000, 'vga', 1, 0, 0x20000]]))

    def add_objects(self):
        self.add_vga_objects(256 * 1024)

class pci_accel_vga_comp(vga_bios_comp):
    '''The "pci_accel_vga_comp" component represents a PCI based VGA
compatible graphics adapter.'''
    _class_desc = 'a PCI-based graphics adapter'
    _help_categories = ('PCI', 'Graphics')
    _vga_class = 'accel-vga'

    class bochs_workaround(SimpleConfigAttribute(False, 'b', simics.Sim_Attr_Optional)):
        """When true, activating workaround for bochs driver bug
           which is present, for instance, in RHEL 7.1"""

    class vram_size_mb(SimpleConfigAttribute(16, 'i', simics.Sim_Attr_Optional)):
        """Video RAM volume (MB)"""

    def setup(self):
        DEPRECATED(simics.SIM_VERSION_8,
                   "The component pci_accel_vga_comp has been deprecated.",
                   "Please use the class pci_accel_vga_v2_comp instead.")
        vga_bios_comp.setup(self)
        if not self.instantiated.val:
            self.add_objects()
        maps = [[0x000a0000, 'dmap_space', 0, 0, 0x20000]]
        prom_size = self.get_option_rom_size()
        if prom_size:
            maps.append([0x000c0000, 'prom', 0, 0, prom_size])

        self.add_connector('pci_bus',
                           VgaPciBusUpConnector(
                               'vga', 'pci_accel_vga_comp',
                               maps))

    def add_objects(self):
        vga = self.add_vga_objects(self.vram_size_mb.val * 1024 * 1024)
        vga.bochs_wrkrnd_enab = self.bochs_workaround.val
        dmap_space = self.add_pre_obj('dmap_space', 'memory-space')
        dmap_ram = self.add_pre_obj('dmap_ram', 'ram')
        dmap_ram.image = vga.image
        vga.direct_map_space = dmap_space
        vga.direct_map_ram = dmap_ram
        dmap_space.default_target = [vga, 1, 0, None]
        vga.lfb_uses_bar = True


class pci_accel_vga_v2_comp(vga_bios_comp):
    '''The "pci_accel_vga_v2_comp" component represents a PCI based VGA
compatible graphics adapter.'''
    _class_desc = 'a PCI-based graphics adapter'
    _help_categories = ('PCI', 'Graphics')
    _vga_class = 'accel_vga_v2'

    class bochs_workaround(SimpleConfigAttribute(False, 'b', simics.Sim_Attr_Optional)):
        """When true, activating workaround for bochs driver bug
           which is present, for instance, in RHEL 7.1"""

    class vram_size_mb(SimpleConfigAttribute(16, 'i', simics.Sim_Attr_Optional)):
        """Video RAM volume (MB)"""

    def setup(self):
        self.gfx_sub_obj = 'vga_engine'
        vga_bios_comp.setup(self)
        if not self.instantiated.val:
            self.add_objects()
        maps = [[0x000a0000, 'dmap_space', 0, 0, 0x20000]]
        if self.bios.val:
            maps.append([0x000c0000,
                         'vga.bank.pcie_config.expansion.rom',
                         0,
                         0,
                         self.get_slot('vga').expansion_rom_size])

        self.add_connector('pci_bus',
                           VgaPciBusUpConnector(
                               'vga', 'pci_accel_vga_v2_comp',
                               maps))

    def add_objects(self):
        bios = self.bios.val
        self.bios.val = None  # clear to disable related code in base class
        vga = self.add_vga_objects(self.vram_size_mb.val * 1024 * 1024)
        self.bios.val = bios  # restore the bios attribute value now

        # now let's do our own bios handling
        if self.bios.val:
            biospath = (simics.SIM_lookup_file(self.bios.val)
                        or simics.SIM_lookup_file('%simics%/targets/common/images/'
                                                  + self.bios.val))
            if not biospath:
                raise CompException('Could not find video BIOS file ' +
                                    self.bios.val)
            biossize = os.stat(biospath).st_size
            map_size = get_highest_2exp(biossize - 1) << 1
            vga.expansion_rom_size = map_size
        else:
            vga.expansion_rom_size = 1024  # just to satisfy the required attr
        vga.bochs_wrkrnd_enab = self.bochs_workaround.val
        dmap_space = self.add_pre_obj('dmap_space', 'memory-space')
        dmap_ram = self.add_pre_obj('dmap_ram', 'ram')
        dmap_ram.image = vga.image
        vga.direct_map_space = dmap_space
        vga.video_ram = dmap_ram
        dmap_space.default_target = [vga.port.video_mem, 0, 0, None]
        self.get_slot('vga_pspace').map = []
        self.get_slot('vga_pspace').map += [[0x1ce, vga.bank.vbe_io, 0, 0, 2]]
        self.get_slot('vga_pspace').map += [[0x1cf, vga.bank.vbe_io, 0, 2, 2]]
        self.get_slot('vga_pspace').map += [[0x1d0, vga.bank.vbe_io, 0, 2, 2]] # GOP driver uses port 0x1d0 instead of 0x1cf
        self.get_slot('vga_pspace').map += [[0x3b0 + i, vga.vga_io, 0, 0x3b0 + i, 1] for i in range(0x30)] # IO_VGA

    def load_file_into_image(self):
        vga_bios_comp.load_file_into_image(self,
            self.get_slot('vga').bank.pcie_config.expansion.image)

class intel_ethernet_comp(x86_bios_comp):
    _do_not_init = object()

    class basename(x86_bios_comp.basename):
        val = 'eth_adapter'

    class mac_address(MacAddressAttribute()):
        '''The MAC address of the Ethernet adapter.'''
        pass

    def calculate_csum(self, data):
        # After adding the 16-bit words 0x00 to 0x3F, the sum should be
        # 0xBABA after masking off the carry bits.
        sum = 0
        for i, x in enumerate(data):
            if i&1: sum += x
            else:   sum += x << 8
        sum = 0xbaba - sum
        return ((sum & 0xff00) >> 8, sum & 0xff)

    def setup(self):
        x86_bios_comp.setup(self)
        if not self.instantiated.val:
            self.add_objects()

class IntelEthernetLinkDownConnector(connectors.StandardConnector):
    type = 'ethernet-link'
    direction = simics.Sim_Connector_Direction_Down
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, mac, phy):
        self.mac = mac
        self.phy = phy

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.mac)]

    def check(self, cmp, cnt, attr):
        if isinstance(attr[0], list):
            print('%s only supports new Ethernet links' % cmp.obj.name)
            return False
        return True

    def connect(self, cmp, cnt, attr):
        link = attr[0]
        cmp.get_slot(self.mac).link = link
        phy = cmp.get_slot(self.phy)
        phy.link_up = 1
        phy.full_duplex = 1

    def disconnect(self, cmp, cnt):
        cmp.get_slot(self.mac).link = None
        phy = cmp.get_slot(self.phy)
        phy.link_up = 0
        phy.full_duplex = 0

class pci_i82543gc_comp(intel_ethernet_comp):
    '''The "pci_i82543gc_comp" component represents the PCI-based Intel® 82543
Gigabit Ethernet Controller.'''
    _class_desc = 'an Ethernet controller'
    _help_categories = ('PCI', 'Networking')

    def setup(self):
        intel_ethernet_comp.setup(self)
        self.add_connector('pci_bus', connectors.PciBusUpConnector(
            0, 'mac', hotpluggable = False, required = True))
        self.add_connector('eth', IntelEthernetLinkDownConnector('mac', 'phy'))

    def get_pci_device(self):
        return self.get_slot('mac')

    def add_objects(self):
        mac = self.add_pre_obj('mac', 'i82543')
        mac.STATUS = 0
        eeprom = self.add_pre_obj('eth_eeprom', 'microwire-eeprom')
        eeprom.width = 16
        eeprom.size = 1024
        ma = mac_as_list(self.mac_address.val)
        eeprom_data = (ma[1], ma[0], ma[3], ma[2], ma[5], ma[4], 0, 0,
                       0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                          0,    0,    0,    0, 0x44, 0x08, 0x80, 0x86,
                       0x80, 0x86, 0x10, 0x79, 0x80, 0x86,    0,    0,
                       0x00, 0x00, 0x10, 0x08,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0,    0,    0,

                       0x00, 0x00, 0x78, 0x63, 0x28, 0x0c, 0x00, 0xc8,
                          0,    0,    0,    0,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0)
        eeprom.data = eeprom_data + self.calculate_csum(eeprom_data)
        mac.eeprom = eeprom

        phy = self.add_pre_obj('phy', 'eth-transceiver')
        # define M88E1011_I_PHY_ID  0x01410C20
        # define M88E1000_E_PHY_ID  0x01410C50 <- etherboot expect this
        # define M88E1000_I_PHY_ID  0x01410C30
        phy.phyidr1 = 0x0141
        phy.phyidr2 = 0x0c50
        phy.registers = [0] * 32
        phy.registers[1] = 0x794d
        phy.registers[17] = 0x0400 # link up
        phy.speed = 1000
        mac.tx_bandwidth = 1000000000
        mac.phy_device = phy
        if self.bios.val:
            self.add_prom_objects()

class pci_i82546bg_comp(intel_ethernet_comp):
    '''The "pci_i82546bg_comp" component represents an Intel® 82546 Gigabit
Ethernet Controller.'''
    _class_desc = 'gigabit Ethernet controller'
    _help_categories = ('PCI', 'Networking')

    class mac_address(intel_ethernet_comp.mac_address):
        '''The MAC address of the first Ethernet adapter. The last bit
is toggled to get the address for the second interface.'''
        pass

    def setup(self):
        intel_ethernet_comp.setup(self)
        self.add_connector('pci_bus',
                           connectors.PciBusUpMultiFunctionConnector(
                               [(0, 'mac[0]'), (1,'mac[1]')],
                               hotpluggable = False, required = True))
        self.add_slot('eth',
                      [self.add_connector(None, IntelEthernetLinkDownConnector(
                            'mac[%d]' % i, 'phy[%d]' % i))
                       for i in range(2)])

    def get_pci_device(self):
        return self.get_slot('mac[0]')

    def add_objects(self):
        ma = mac_as_list(self.mac_address.val)
        eeprom_data = (ma[1], ma[0], ma[3], ma[2], ma[5], ma[4], 0, 0,
                       0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                          0,    0,    0,    0, 0x44, 0x08, 0x80, 0x86,
                       0x80, 0x86, 0x10, 0x79, 0x80, 0x86,    0,    0,
                       0x00, 0x00, 0x10, 0x08,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0,    0,    0,

                       0x00, 0x00, 0x78, 0x63, 0x28, 0x0c, 0x00, 0xc8,
                          0,    0,    0,    0,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0,    0,    0,
                          0,    0,    0,    0,    0,    0)
        eeprom = self.add_pre_obj('eeprom', 'microwire-eeprom')
        eeprom.width = 16
        eeprom.size = 1024
        eeprom.data = eeprom_data + self.calculate_csum(eeprom_data)
        phy = self.add_pre_obj('phy[2]', 'eth-transceiver')
        for i in range(len(phy)):
            # define M88E1011_I_PHY_ID  0x01410C20
            phy[i].phyidr1 = 0x0141
            phy[i].phyidr2 = 0x0c20
            phy[i].registers = [0] * 32
            phy[i].registers[1] = 0x794d
            phy[i].registers[17] = 0x0400
            phy[i].speed = 1000

        mac = self.add_pre_obj('mac[2]', 'i82546')
        for i in range(len(mac)):
            mac[i].STATUS = 0 if i == 0 else 4
            mac[i].eeprom = eeprom
            mac[i].phy_device = phy[i]
            mac[i].tx_bandwidth = 1000000000

        if self.bios.val:
            self.add_prom_objects()

class pci_i82559_comp(intel_ethernet_comp):
    '''An Ethernet device with Intel® 82559 Fast Ethernet Controller.'''
    _class_desc = 'fast Ethernet controller'
    _help_categories = ('PCI', 'Networking')

    def get_pci_device(self):
        return self.get_slot('eepro')

    class component(x86_bios_comp.component):
        def pre_instantiate(self):
            if not x86_bios_comp.component.pre_instantiate(self):
                return False
            # The i82559 device uses two attribute for the expansion_rom
            if self._up.bios.val:
                mac = self._up.get_slot('eepro')
                size = os.stat(simics.SIM_lookup_file(self._up.bios.val)).st_size
                map_size = get_highest_2exp(size - 1) << 1
                mac.expansion_rom = self._up.get_slot('prom')
                mac.expansion_rom_size = map_size
            return True

    def add_objects(self):
        ma = mac_as_list(self.mac_address.val)
        eeprom_data = (ma[1], ma[0], ma[3], ma[2], ma[5], ma[4], 0,   0x03,# 0 ~ 3
                       0,     0,     0x1,   0x2,   0x47,  0x1,   0,   0,# 4 ~ 7
                       0,     0,     0,     0,     0x41,  0xc0,  0,   0,# 8 ~ b
                       0,     0,     0,     0,     0,     0,     0,   0,# c ~ f
                       0,     0,     0,     0,     0,     0,     0,   0,
                       0,     0,     0,     0,     0,     0,     0,   0,
                       0,     0,     0,     0,     0,     0,     0,   0,
                       0,     0,     0,     0,     0,     0,     0,   0,
                       ) + (0,) * 62
        eeprom = self.add_pre_obj('eeprom', 'microwire-eeprom')
        eeprom.width = 16
        eeprom.size = 1024
        eeprom.data = eeprom_data + self.calculate_csum(eeprom_data)
        phy = self.add_pre_obj('phy', 'mii-transceiver')
        phy.mac_address = self.mac_address.val
        phy.registers = [0] * 32
        phy.registers[0] = 0x1800
        phy.registers[1] = 0x7809
        phy.registers[2] = 0x02a8
        phy.registers[3] = 0x0154
        phy.registers[4] = 0x005f
        phy.registers[18] = 1
        mac = self.add_pre_obj('eepro', 'i82559')
        mac.serial_eeprom = eeprom
        mac.mii = phy
        mac.phy = phy
        mac.phy_address = 1
        phy.mac = mac
        if self.bios.val:
            self.add_prom_objects()
        self.add_connector('pci_bus', connectors.PciBusUpConnector(
            0, 'eepro', hotpluggable = False, required = True))
        self.add_connector('eth', connectors.EthernetLinkDownConnector('phy'))

class pci_i21152_comp(StandardConnectorComponent):
    '''The "pci_i21152_comp" component represents an Intel® 21152 Transparent
PCI-to-PCI Bridge.'''
    _class_desc = 'transparent PCI-to-PCI bridge'
    _help_categories = ('PCI',)

    class basename(StandardConnectorComponent.basename):
        val = 'pci_bridge'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connector('pci_bus', connectors.PciBusUpConnector(
                0, 'bridge', hotpluggable = False, required = True))
        self.add_slot('pci_slot',
                     [self.add_connector(None,
                         connectors.PciBusDownConnector(i, 'pcibus',
                                                        hotpluggable = False))
                      for i in range(24)])

    def add_objects(self):
        bridge = self.add_pre_obj('bridge', 'i21152')
        io = self.add_pre_obj('pciio', 'memory-space')
        cfg = self.add_pre_obj('pcicfg', 'memory-space')
        mem = self.add_pre_obj('pcimem', 'memory-space')
        bus = self.add_pre_obj('pcibus', 'pci-bus')
        bus.bridge = bridge
        bus.io_space = io
        bus.conf_space = cfg
        bus.memory_space = mem
        bus.pci_devices = []
        bridge.secondary_bus = bus
        mem.map = []

class PcmciaDownConnector(connectors.StandardConnector):
    type = 'pcmcia-slot'
    direction = simics.Sim_Connector_Direction_Down
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, dev, slot):
        self.dev = dev
        self.slot = slot

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.dev), self.slot]

    def connect(self, cmp, cnt, attr):
        attr_space, cmn_space, io_space = attr
        setattr(cmp.get_slot(self.dev), 'slot%d_spaces' % (self.slot,),
                [attr_space, cmn_space, io_space])

    def disconnect(self, cmp, cnt):
        setattr(cmp.get_slot(self.dev), 'slot%d_spaces' % (self.slot,), None)

class pci_pd6729_comp(StandardConnectorComponent):
    '''The "pci_pd6729_comp" component represents a Cirrus Logic PD6729
PCI-to-PCMCIA (PC-Card) Controller with two slots.'''
    _class_desc = 'two-slot PCI-to-PCMCIA controller'
    _help_categories = ('PCI',)

    class basename(StandardConnectorComponent.basename):
        val = 'pcmcia_bridge'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connector('pci_bus', connectors.PciBusUpConnector(
                0, 'pcmcia', hotpluggable = False, required = True))
        self.add_slot(
                'pcmcia',
                [self.add_connector(None,
                                    PcmciaDownConnector('pcmcia', i))
                 for i in range(2)])

    def add_objects(self):
        self.add_pre_obj('pcmcia', 'CL-PD6729')

class SimpleFcLoopDownConnector(connectors.StandardConnector):
    type = 'simple-fc-loop'
    direction = simics.Sim_Connector_Direction_Down
    required = False
    hotpluggable = False
    multi = True

    def __init__(self, device, use_loops):
        self.device = device
        self.use_loops = use_loops

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.device)]

    def check(self, cmp, cnt, attr):
        info = attr[0]
        if info >= 127:
            print('Illegal loop ID 0x%x' % (info,))
            return False
        use_loops = getattr(cmp.get_slot(self.device), self.use_loops)
        if info in use_loops:
            print('Loop ID 0x%x already in use.' % (info,))
            return False
        setattr(cmp.get_slot(self.device), self.use_loops, use_loops + [info])
        return True

    def connect(self, cmp, cnt, attr):
        pass

    def disconnect(self, cmp, cnt):
        pass

class pci_dec21xx_comp(x86_bios_comp):
    _do_not_init = object()

    class basename(x86_bios_comp.basename):
        val = 'eth_adapter'

    class mac_address(MacAddressAttribute()):
        '''The MAC address of the Ethernet adapter.'''
        pass

    def get_pci_device(self):
        return self.get_slot('dec')

    def setup(self):
        x86_bios_comp.setup(self)
        if not self.instantiated.val:
            self.add_objects()
        self.add_connector('pci_bus', connectors.PciBusUpConnector(
                0, 'dec', required = True, hotpluggable = False))
        self.add_connector('eth', connectors.EthernetLinkDownConnector('dec'))

    def add_objects(self):
        dec = self.add_pre_obj('dec', self._conf_class)
        dec.mac_address = self.mac_address.val
        dec.srom_address_width = 8
        if self.bios.val:
            self.add_prom_objects()

class pci_dec21041_comp(pci_dec21xx_comp):
    '''The "pci_dec21041_comp" component represents an Intel DEC21041 PCI
based fast Ethernet adapter.'''
    _class_desc = 'a PCI-based fast Ethernet adapter'
    _help_categories = ('PCI', 'Networking')
    _conf_class = 'DEC21041'

class pci_dec21143_comp(pci_dec21xx_comp):
    '''The "pci_dec21143_comp" component represents an Intel DEC21143 PCI
based fast Ethernet adapter.'''
    _class_desc = 'a PCI-based fast Ethernet adapter'
    _help_categories = ('PCI', 'Networking')
    _conf_class = 'DEC21143'

class pci_dec21140a_comp(pci_dec21xx_comp):
    '''The pci_dec21140a_comp component represents a DEC21140A PCI based
    fast Ethernet adapter'''
    _class_desc = 'a PCI-based fast Ethernet adapter'
    _help_categories = ('PCI', 'Networking')
    _conf_class = 'DEC21140A'
