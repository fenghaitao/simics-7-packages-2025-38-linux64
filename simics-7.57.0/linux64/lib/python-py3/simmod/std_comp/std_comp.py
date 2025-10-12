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
import systempanel
from systempanel.widgets import (Column, Grid, Label, LabeledBox, Led,
                                 NumberInput, NumberOutput, ToggleButton)
import cli
import component_utils
from simicsutils.host import is_windows

from comp import *
from deprecation import DEPRECATED
import pyobj

# The first CD has id 1 and the first disk id 2 (for backward compatibility
# reasons) then simply assign new numbers
ide_serial_number = 3
vt_first_cdrom = 1
vt_first_disk = 1
def vt_serial_number(type=''):
    global ide_serial_number
    global vt_first_cdrom
    global vt_first_disk
    if type == 'cdrom' and vt_first_cdrom:
        serial_number = 1
        vt_first_cdrom = 0
    elif type == 'disk' and vt_first_disk:
        serial_number = 2
        vt_first_disk = 0
    else:
        serial_number = ide_serial_number
        ide_serial_number += 1
    return " VT%05d" % serial_number

# Standard CIS for an PCMCIA Flash/IDE disk

ide_cis = (
    0x01, 0x03, 0xd9, 0x01, 0xff, 0x1c, 0x04, 0x03, 0xd9, 0x01, 0xff, 0x18,
    0x02, 0xdf, 0x01, 0x20, 0x04, 0x01, 0x4e, 0x00, 0x02, 0x15, 0x2b, 0x04,
    0x01, 0x56, 0x69, 0x6b, 0x69, 0x6e, 0x67, 0x20, 0x41, 0x54, 0x41, 0x20,
    0x46, 0x6c, 0x61, 0x73, 0x68, 0x20, 0x43, 0x61, 0x72, 0x64, 0x20, 0x20,
    0x20, 0x20, 0x00, 0x53, 0x54, 0x4f, 0x52, 0x4d, 0x20, 0x20, 0x00, 0x53,
    0x54, 0x42, 0x4d, 0x30, 0x00, 0xff, 0x21, 0x02, 0x04, 0x01, 0x22, 0x02,
    0x01, 0x01, 0x22, 0x03, 0x02, 0x04, 0x5f, 0x1a, 0x05, 0x01, 0x03, 0x00,
    0x02, 0x0f, 0x1b, 0x0b, 0xc0, 0x40, 0xa1, 0x27, 0x55, 0x4d, 0x5d, 0x75,
    0x08, 0x00, 0x21, 0x1b, 0x06, 0x00, 0x01, 0x21, 0xb5, 0x1e, 0x4d, 0x1b,
    0x0d, 0xc1, 0x41, 0x99, 0x27, 0x55, 0x4d, 0x5d, 0x75, 0x64, 0xf0, 0xff,
    0xff, 0x21, 0x1b, 0x06, 0x01, 0x01, 0x21, 0xb5, 0x1e, 0x4d, 0x1b, 0x12,
    0xc2, 0x41, 0x99, 0x27, 0x55, 0x4d, 0x5d, 0x75, 0xea, 0x61, 0xf0, 0x01,
    0x07, 0xf6, 0x03, 0x01, 0xee, 0x21, 0x1b, 0x06, 0x02, 0x01, 0x21, 0xb5,
    0x1e, 0x4d, 0x1b, 0x12, 0xc3, 0x41, 0x99, 0x27, 0x55, 0x4d, 0x5d, 0x75,
    0xea, 0x61, 0x70, 0x01, 0x07, 0x76, 0x03, 0x01, 0xee, 0x21, 0x1b, 0x06,
    0x03, 0x01, 0x21, 0xb5, 0x1e, 0x4d, 0x14)

### dummy_comp
class dummy_comp(StandardComponent):
    '''Dummy component used for configurations that are not component based.'''
    _class_desc = 'deprecated machine component'
    _do_not_init = object()

    class basename(StandardComponent.basename):
        val = 'no_comp'

    class top_component(StandardComponent.top_component):
        def getter(self):
            return self._up.obj

    class cpu_list(StandardComponent.cpu_list):
        def getter(self):
            return []

# return an attribute that can only be set before the component
# has been configured
def PreConfigAttribute(init, type, attr, val = []):
    class PCA(ConfigAttribute):
        attrtype = type
        attrattr = attr
        valid = val
        def _initialize(self):
            self.val = init
        def getter(self):
            return self.val
        def setter(self, val):
            if self._up.obj.configured:
                return simics.Sim_Set_Illegal_Value
            self.val = val
    return PCA


# base class for disk components


class disk_components(StandardConnectorComponent):
    _do_not_init = object()

    class component_icon(StandardConnectorComponent.component_icon):
        val = 'harddisk.png'

    class component(StandardConnectorComponent.component):
        def pre_instantiate(self):
            if not self._up.file.val and self._up.size.val == 0:
                print("Either file or size attribute must be set")
                return False
            if self._up.file.val and not simics.SIM_lookup_file(self._up.file.val):
                print("Could not find disk file: %s" % self._up.file.val)
                return False
            return True

    class size(PreConfigAttribute(0, 'i', simics.Sim_Attr_Optional)):
        '''The size of the disk in bytes.'''
        valid = [4096]

    class file(PreConfigAttribute(
            None, 's|n', simics.Sim_Attr_Optional)):
        '''File with disk contents for the full disk. Either a raw file or
        a virtual disk file in craff, DMG, or VHDX format.'''
        pass

    class disk_component(pyobj.Interface):
        def size(self):
            return self._up.size.val

    def create_disk_image(self, name):
        valid_path = False
        if self.file.val:
            real_path = simics.SIM_lookup_file(self.file.val)
            if real_path:
                valid_path = True
                if self.size.val == 0:
                    # Only use size from file if no disk size is set, allowing
                    # users to skip the end of the file or have a larger disk
                    # than the current file size.
                    self.size.val = simics.VT_logical_file_size(real_path)
                elif self.size.val < simics.VT_logical_file_size(real_path):
                    simics.SIM_log_info(
                        1, self.obj, 0,
                        "WARNING: explicitly specified disk size is smaller"
                        " than the size required by the disk image.")
        if self.size.val == 0:
            simics.SIM_log_info(1, self.obj, 0,
                         "WARNING: neither file nor size attribute"
                         " has been set, create disk with default"
                         " size (4096 bytes)")
        image = self.add_pre_obj(name, 'image')
        if valid_path:
            image.files = [[self.file.val, 'ro', 0, 0, 0]]
        image.size = self.size.val
        return image

### IDE Disk


class ide_disk_comp(disk_components):
    '''The "ide_disk_comp" component represents an IDE disk. Disk data is
    stored in the hd_image subobject.'''
    #first_ide_disk = 1
    _class_desc = 'an IDE disk drive'
    _do_not_init = object()
    _help_categories = ('Disks',)

    class basename(disk_components.basename):
        val = 'ide_disk'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connector('ide_slot', IdeSlotUpConnector('disk'))

    def add_objects(self):
        hd_image = self.create_disk_image('hd_image')
        geometry = [min(self.size.val // (16 * 63 * 512), 16383), 16, 63]
        hd = self.add_pre_obj('disk', 'ide-disk')
        hd.image = hd_image
        hd.disk_sectors = self.size.val // 512
        hd.disk_cylinders = geometry[0]
        hd.disk_heads = geometry[1]
        hd.disk_sectors_per_track = geometry[2]
        hd.serial_number = vt_serial_number(type='disk')


### IDE CD-ROM


class ide_cdrom_comp(StandardConnectorComponent):
    '''The "ide_cdrom_comp" component represents an IDE ATAPI CD-ROM.'''
    _class_desc = 'an IDE ATAPI CD-ROM drive'
    _do_not_init = object()
    _help_categories = ('Disks',)

    class basename(StandardConnectorComponent.basename):
        val = 'ide_cdrom'

    class component_icon(StandardConnectorComponent.component_icon):
        val = 'cdrom.png'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connector('ide_slot', IdeSlotUpConnector('cd'))

    def add_objects(self):
        cd = self.add_pre_obj('cd', 'ide-cdrom')
        cd.serial_number = vt_serial_number(type='cdrom')

### PCMCIA Flash Disk

# list of "small" known disk ageometries
known_geometries = {  94080: ( 735,  4, 32),
                     125440: ( 490,  8, 32),  # SDCFJ-64-388
                     250880: ( 980,  8, 32),  # SDCFJ-128-388
                     251904: ( 984,  8, 32),  #
                     501760: ( 980, 16, 32),  # SDCFJ-256-388
                    1000944: ( 993, 16, 63),  # SDCFJ-512-388
                    2064384: (2048, 16, 63),  # SDCFJ-1024-388
                    3931200: (3900, 16, 63)
}

class pcmcia_flash_disk_comp(disk_components):
    '''The "pcmcia_flash_disk_comp" component represents a PCMCIA flash disk. Disk data is
    stored in the hd_image subobject.'''
    _class_desc = 'a PCMCIA flash disk'
    _do_not_init = object()

    class basename(disk_components.basename):
        val = 'flash_disk'

    class component_icon(disk_components.component_icon):
        val = 'removable-card.png'

    class component_connector(pyobj.Interface):
        def get_check_data(self, cnt):
            return []

        def get_connect_data(self, cnt):
            return [self._up.get_slot('pcmcia_attr_space'),
                    self._up.get_slot('pcmcia_common_space'),
                    self._up.get_slot('pcmcia_io_space')
                    ]

        def check(self, cnt, attr):
            return True

        def connect(self, cnt, attr):
            (bridge, slot_id) = attr
            self._up.get_slot('pcmcia_ide').irq_dev = bridge
            self._up.get_slot('pcmcia_ide').irq_level = slot_id

        def disconnect(self, cnt):
            self._up.get_slot('pcmcia_ide').irq_dev = None

    class component(disk_components.component):
        def post_instantiate(self):
            attr_space = self._up.get_slot('pcmcia_attr_space')
            for i in range(len(ide_cis)):
                attr_space.iface.memory_space.write(None, i * 2,
                                                    (ide_cis[i], ), 1)
            # Fake some attribute space register
            attr_space.iface.memory_space.write(None, 0x204, (0x2e, ), 1)

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()

    def add_objects(self):
        hd_image = self.create_disk_image('hd_image')
        sects = self.size.val // 512
        if sects >= 16 * 63 * 16363:
            geometry = [16683, 16, 63]
        else:
            if sects in known_geometries:
                geometry = known_geometries[sects]
            else:
                s = sects // (16 * 63)
                if s * 16 * 63 != sects:
                    simics.SIM_log_info(
                        1, self.obj, 0,
                        'No exact disk geometry calculated, set manually')
                geometry = [s, 16, 63]
        hd = self.add_pre_obj('disk', 'ide-disk')
        hd.image = hd_image
        hd.disk_sectors = sects
        hd.disk_cylinders = geometry[0]
        hd.disk_heads = geometry[1]
        hd.disk_sectors_per_track = geometry[2]
        hd.serial_number = vt_serial_number(type='pcmcia')
        ide = self.add_pre_obj('pcmcia_ide', 'ide')
        ide.lba_mode = 1
        ide.primary = 1
        ide.interrupt_delay = 0.000001
        ide.master = hd
        ide.irq_level = 0
        cis_image = self.add_pre_obj('cis_image', 'image')
        cis_image.size = 0x300
        cis = self.add_pre_obj('cis', 'rom')
        cis.image = cis_image
        attr_space = self.add_pre_obj('pcmcia_attr_space', 'memory-space')
        attr_space.map = [[0x0, cis, 0, 0, 0x208]]

        # "True IDE-mode" mappings are not supported

        cmn_space = self.add_pre_obj('pcmcia_common_space', 'memory-space')
        io_space = self.add_pre_obj('pcmcia_io_space', 'memory-space')
        io_ide_map = [[0x0, ide, 0, 0x0, 8],
                      [0x8, ide, 0, 0x0, 2],
                      [0xd, ide, 0, 0x1, 1],
                      [0xe, ide, 0, 0x8, 1]]
        mem_ide_map = [[0x0, ide, 0, 0x0, 8],
                       [0x8, ide, 0, 0x0, 2],
                       [0xd, ide, 0, 0x1, 1],
                       [0xe, ide, 0, 0x8, 1]]
        for i in range(0x400, 0x800, 2):
            mem_ide_map.append([i, ide, 0, 0x0, 2])
        cmn_space.map = mem_ide_map
        io_space.map = io_ide_map
        StandardComponent.add_connector(
            self, 'pcmcia_slot', 'pcmcia-slot', True, False, False,
            simics.Sim_Connector_Direction_Up)

etg_mac_idx = 0

### SATA disk

class sata_disk_comp(disk_components):
    """The "sata_disk" component represents a Serial ATA Disk. Disk data is
    stored in the hd_image subobject."""
    _class_desc = "a SATA disk drive"
    _do_not_init = object()
    _help_categories = ("Disks", )

    class basename(StandardConnectorComponent.basename):
        val = 'sata_disk'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connector('sata_slot', SataSlotUpConnector('sata'))

    def add_objects(self):
        hd_image = self.create_disk_image('hd_image')
        sata = self.add_pre_obj('sata', 'sata')
        geometry = [min(self.size.val // (16 * 63 * 512), 16383), 16, 63]
        hd = self.add_pre_obj('hd', 'ide-disk')
        hd.image = hd_image
        hd.disk_sectors = self.size.val // 512
        hd.disk_cylinders = geometry[0]
        hd.disk_heads = geometry[1]
        hd.disk_sectors_per_track = geometry[2]
        hd.serial_number = vt_serial_number(type='disk')
        sata.master = hd

# SATA cdrom

class sata_cdrom_comp(StandardConnectorComponent):
    """The "sata_cdrom" component represents an Serial ATA CD-ROM."""
    _class_desc = "a SATA CD-ROM"
    _do_not_init = object()
    _help_categories = ("Disks",)

    class basename(StandardConnectorComponent.basename):
        val = 'sata_cdrom'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connector('sata_slot', SataSlotUpConnector('sata'))

    def add_objects(self):
        sata = self.add_pre_obj('sata', 'sata')
        cd = self.add_pre_obj('cd', 'ide-cdrom')
        cd.serial_number = vt_serial_number(type='cdrom')
        sata.master = cd

### Service node
simics.SIM_load_module('service-node')

### Ethernet traffic generator component

class etg_panel_comp(systempanel.SystemPanel):
    """The Ethernet Generator System Panel."""
    _class_desc = "an ETG system panel"
    _do_not_init = object()
    default_layout = Column([
        Grid(columns=2, contents=[
                Led('enabled'), Label('Enabled')]),
        LabeledBox("Counters", Grid(columns=2, contents=[
                Label("Packets left to send"), NumberOutput('pkt_left'),
                Label("Packets sent"), NumberOutput('pkt_sent'),
                Label("Packets received"), NumberOutput('pkt_recv'),
                Label("CRC errors"), NumberOutput('crc_errs'),
                ])),
        LabeledBox("Parameters", Grid(columns=2, contents=[
                Label("Packet rate"), NumberInput('pkt_rate'),
                Label("Packet size"), NumberInput('pkt_size'),
                Label("Packets to send"), NumberInput('start_count'),
                ])),
        ToggleButton('start', label='Start'),
        ])
    objects = default_layout.objects()

class etg_comp(StandardConnectorComponent):
    """The "etg_comp" component represents an Ethernet traffic generator."""
    _class_desc = 'an Ethernet traffic generator'
    _do_not_init = object()
    _help_categories = ('Networking',)

    panel_class = 'etg_panel_comp'

    class component_icon(StandardConnectorComponent.component_icon):
        def _initialize(self):
            self.val = 'service-node.png'

    class basename(StandardConnectorComponent.basename):
        val = 'etg'

    class mac_address(ConfigAttribute):
        """The MAC address of the traffic generator."""
        attrattr = simics.Sim_Attr_Optional
        attrtype = 's'
        def _initialize(self):
            self.val = ""
        def getter(self):
            return self.val
        def setter(self, val):
            if len(mac_as_list(val)) != 6:
                return simics.Sim_Set_Illegal_Value
            self.val = val

    class ip(SimpleConfigAttribute("", 's', simics.Sim_Attr_Required)):
        """IP address of the traffic generator."""

    class netmask(SimpleConfigAttribute("", 's', simics.Sim_Attr_Required)):
        """IP netmask of the traffic generator."""

    class dst_ip(SimpleConfigAttribute("", 's', simics.Sim_Attr_Required)):
        """Destination IP address for generated traffic."""

    class gateway_ip(SimpleConfigAttribute("", 's', simics.Sim_Attr_Optional)):
        """Gateway for non-local traffic."""

    class pps(SimpleConfigAttribute(10, 'i', simics.Sim_Attr_Optional)):
        """Traffic rate in packets per second."""

    class packet_size(SimpleConfigAttribute(142, 'i', simics.Sim_Attr_Optional)):
        """Packet size."""

    class port(SimpleConfigAttribute(-1, 'i', simics.Sim_Attr_Optional)):
        """Port."""

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_objects(self):
        # Create the ETG device
        etg = self.add_pre_obj('etg', 'etg')
        if self.mac_address.val != "":
            etg.mac_address = self.mac_address.val
        else:
            global etg_mac_idx
            self.mac_address.val = "10:10:10:10:30:%02x" % etg_mac_idx
            etg.mac_address = self.mac_address.val
            etg_mac_idx += 1
        etg.ip = self.ip.val
        etg.netmask = self.netmask.val
        etg.dst_ip = self.dst_ip.val
        etg.pps = self.pps.val
        etg.packet_size = self.packet_size.val
        if self.port.val != -1:
            etg.port = self.port.val
        if self.gateway_ip.val != "":
            etg.gateway = self.gateway_ip.val

        # Define a panel for the ETG
        self.add_component('system_panel', self.panel_class, [])
        self.get_slot('system_panel.pkt_rate').number_state = etg.pps
        self.get_slot('system_panel.pkt_size').number_state = etg.packet_size
        self.get_slot('system_panel.start_count').number_state = 0 #inf

        # Inputs using existing attributes (authority)
        self.get_slot('system_panel.start_count').authority = [etg,
                                                               "start_count"]

        # Inputs using (new) uint64_state interface
        # NOTE: authority could have been used for the following inputs as
        # well, as etg attributes exist, instead of adding new interface ports.
        # Using uint64_state interface is just to demo different ways of using
        # the System Panel
        self.get_slot('system_panel.pkt_rate').target = [etg, "pps"]
        self.get_slot('system_panel.pkt_size').target = [etg, "packet_size"]
        self.get_slot('system_panel.start').target = [etg, "start"]

        # Outputs (pushed)
        etg.led_enabled_target = self.get_slot('system_panel.enabled')
        etg.countdown_target = self.get_slot('system_panel.pkt_left')
        etg.crc_errors_target = self.get_slot('system_panel.crc_errs')

        # Outputs (polled, using authority)
        self.get_slot('system_panel.pkt_sent').authority = [etg,
                                                            "total_tx_packets"]
        self.get_slot('system_panel.pkt_recv').authority = [etg,
                                                            "total_rx_packets"]

    def add_connectors(self):
        self.add_connector('ethernet',
                           EthernetLinkDownConnector('etg'))

### MMC/SD card

class mmc_card_comp(StandardConnectorComponent):
    """The mmc_card_comp component represents an MMC/SD/SDHC/SDIO card."""
    _class_desc = 'a MMC/SD card'
    _do_not_init = object()

    class basename(StandardConnectorComponent.basename):
        val = 'mmc_card'

    class type(SimpleConfigAttribute('mmc', 's')):
        """Card type ('mmc', 'sd', 'sdhc' or 'sdio'). Note that the card type
        will be adjusted by the model to handle large card sizes (i.e. card type
        will be forced to 'sdhc' if you create an 8 GB 'mmc' card)."""

        def _initialize(self):
            self.val = 0 # MMC

        def getter(self):
            val_enc = (self._up.get_slot('card').card_type
                       if self._up.instantiated.val else self.val)
            return ('mmc', 'sd', 'sdhc', 'sdio')[val_enc]

        def setter(self, val):
            if val not in ['mmc', 'sd', 'sdhc', 'sdio']:
                simics.SIM_attribute_error(
                    'card type must be one of "mmc", "sd", "sdhc" or "sdio"')
                return simics.Sim_Set_Illegal_Value
            self.val = {'mmc'  : 0,
                        'sd'   : 1,
                        'sdhc' : 2,
                        'sdio' : 3}[val]
            return simics.Sim_Set_Ok

    class size(SimpleConfigAttribute(0, 'i', attr = simics.Sim_Attr_Required)):
        """Card size, in bytes"""
        valid = [4096]

    class file(SimpleConfigAttribute(None, 's|n')):
        """File with disk contents for the full disk. Either a raw file or
        a virtual disk file in craff, DMG, or VHDX format"""

    class disk_component(pyobj.Interface):
        def size(self):
            return self._up.size.val

    class component(StandardConnectorComponent.component):
        def pre_instantiate(self):
            if self._up.file.val and not simics.SIM_lookup_file(self._up.file.val):
                print('could not find disk file', self._up.file.val)
                return False
            return True

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_connectors(self):
        self.add_connector('mmc_controller', MMCUpConnector('card'))

    def add_objects(self):
        # Backing image
        image = self.add_pre_obj('image', 'image')
        image.size = self.size.val
        if self.file.val:
            image.files = [[self.file.val, 'ro', 0, 0]]

        # Card
        card = self.add_pre_obj('card', 'generic-mmc-card')
        card.size = self.size.val
        card.flash_image = image
        card.card_type = self.type.val
