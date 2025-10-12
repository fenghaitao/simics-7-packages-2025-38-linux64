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

from simmod.std_comp.std_comp import disk_components

def usb_string_desc(str):
    ret = (len(str) * 2 + 2, 0x03)
    for c in str:
        ret += (ord(c), 0x00)
    return ret

def setup_pre_conf_usb_disk(usb_disk):
    usb_disk.descriptor_data = (
            # device descriptor
            0x12, 0x01, 0x00, 0x02, 0x00, 0x00, 0x00, 0x40, 0x11,
            0x47, 0x34, 0x12, 0x1e, 0x00, 0x01, 0x02, 0x03, 0x01,
            # configuration descriptor
            0x09, 0x02, 0x20, 0x00, 0x01, 0x01, 0x00, 0xc0, 0x10,
            # interface descriptor
            0x09, 0x04, 0x00, 0x00, 0x02, 0x08, 0x06, 0x50, 0x00,
            # endpoint descriptor (bulk-in)
            0x07, 0x05, 0x82, 0x02, 0x40, 0x00, 0x00,
            # endpoint descriptor (bulk-out)
            0x07, 0x05, 0x01, 0x02, 0x40, 0x00, 0x00)

    usb_disk.string_descriptor_array = [
            # string lang descriptor
            (0x06, 0x03, 0x09, 0x00, 0x04, 0x00),
            usb_string_desc("Simics"),
            usb_string_desc("USB Disk"),
            usb_string_desc("200435132207e9526048")]

    usb_disk.device_qualifier_descriptor_data = (
            # device qualifier descriptor
            # size, dev qualify type,  usb 2.0 = 0x2000
             0x0a,              0x06,        0x02, 0x00,
            # class, subclass, protocol, max packet size,
             0x0,         0x0,      0x0,            0,
            # other speed conf, reserved
             0x0,                    0x0)

def setup_pre_conf_usb_tablet(usb_device):
    usb_device.descriptor_data = (
        # device descriptors
        0x12, 0x01, 0x10, 0x00, 0x00, 0x00, 0x00, 0x08, 0x27,
        0x06, 0x01, 0x00, 0x00, 0x10, 0x01, 0x02, 0x00, 0x01,
        # configuration descriptor
        0x09, 0x02, 0x22, 0x00, 0x01, 0x01, 0x00, 0xa0, 0x14,
        # interface descriptor
        0x09, 0x04, 0x00, 0x00, 0x01, 0x03, 0x01, 0x02, 0x00,
        # HID descriptor
        0x09, 0x21, 0x01, 0x00, 0x00, 0x01, 0x22, 0x4a, 0x00,
        # endpoint descriptor
        0x07, 0x05, 0x81, 0x03, 0x08, 0x00, 0x03)
    usb_device.string_descriptor_array = [
        # string lang descriptor
        (0x04, 0x03, 0x09, 0x04),
        usb_string_desc("Simics"),
        usb_string_desc("Simics USB Tablet")]
    usb_device.hid_report_descriptor_data = (
        # HID report descriptor
        0x05, 0x01, 0x09, 0x01, 0xa1, 0x01, 0x09, 0x01,
        0xa1, 0x00, 0x05, 0x09, 0x19, 0x01, 0x29, 0x03,
        0x15, 0x00, 0x25, 0x01, 0x95, 0x03, 0x75, 0x01,
        0x81, 0x02, 0x95, 0x01, 0x75, 0x05, 0x81, 0x01,
        0x05, 0x01, 0x09, 0x30, 0x09, 0x31, 0x15, 0x00,
        0x26, 0xff, 0x7f, 0x35, 0x00, 0x46, 0xfe, 0x7f,
        0x75, 0x10, 0x95, 0x02, 0x81, 0x02, 0x05, 0x01,
        0x09, 0x38, 0x15, 0x81, 0x25, 0x7F, 0x35, 0x00,
        0x45, 0x00, 0x75, 0x08, 0x95, 0x01, 0x81, 0x02,
        0xc0, 0xc0)

class myUsbPortUpConnector(UsbPortUpConnector):
    def __init__(self, usb, connected_fun, disconnected_fun):
        UsbPortUpConnector.__init__(self, usb)
        self.connected_fun = connected_fun
        self.disconnected_fun = disconnected_fun

    def connect(self, cmp, cnt, attr):
        (usb_host,) = attr
        cmp.get_slot(self.usb).usb_host = usb_host
        self.connected_fun()

    def disconnect(self, cmp, cnt):
        cmp.get_slot(self.usb).usb_host = None
        self.disconnected_fun()

class UsbDeviceComponent(StandardConnectorComponent):
    _do_not_init = object()

    def add_usb_connector(self, device):
        self.add_connector('usb_host', UsbPortUpConnector(device))

class usb_disk_comp(UsbDeviceComponent, disk_components):
    '''The "usb_disk_comp" component represents a USB SCSI disk. Disk data is
    stored in the usb_scsi_disk_image subobject.'''
    _class_desc = 'a USB SCSI disk'
    _do_not_init = object()
    _help_categories = ('USB',)

    class basename(UsbDeviceComponent.basename):
        val = 'usb_disk'

    class component_icon(disk_components.component_icon):
        pass

    class component(disk_components.component):
        def pre_instantiate(self):
            if not super().pre_instantiate():
                return False
            self._up.scsi_disk.geometry = [self._up.size.val // 512, 1, 1]
            return True

    def setup(self):
        UsbDeviceComponent.setup(self)
        if not self.instantiated.val:
            self.add_objects()
        self.add_usb_connector('usb_disk')

    def add_objects(self):
        scsi_disk_image = self.create_disk_image('usb_scsi_disk_image')
        self.scsi_disk = self.add_pre_obj('usb_scsi_disk', 'simple-scsi-disk')
        usb_disk = self.add_pre_obj('usb_disk', 'usb_disk')
        self.scsi_disk.image = scsi_disk_image
        self.scsi_disk.controller = usb_disk
        usb_disk.scsi_disk = self.scsi_disk
        setup_pre_conf_usb_disk(usb_disk)

# we have to use the ugly class name to avoid conflict with
# the device usb_tablet and component usb-tablet-comp
class usb_tablet_component(UsbDeviceComponent):
    '''The "usb_tablet_component" component represents a USB tablet device.'''
    _class_desc = 'a USB tablet'
    _do_not_init = object()
    _help_categories = ('USB',)

    class basename(UsbDeviceComponent.basename):
        val = 'usb_tablet_comp'

    class component_icon(UsbDeviceComponent.component_icon):
        val = 'tablet.png'

    def setup(self):
        UsbDeviceComponent.setup(self)
        if not self.instantiated.val:
            self.add_objects()
        self.add_usb_connector('usb_tablet')
        self.add_connector('abs_mouse', AbsMouseDownConnector('usb_tablet'))

    def add_objects(self):
        usb_device = self.add_pre_obj('usb_tablet', 'usb_tablet')
        setup_pre_conf_usb_tablet(usb_device)
