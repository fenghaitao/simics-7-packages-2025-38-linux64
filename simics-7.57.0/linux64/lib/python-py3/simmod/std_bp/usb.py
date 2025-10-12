# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from blueprints import Builder, Namespace
from .state import GFXInputConnectionState, USBConnectionState
from .disks import DiskImage, disk_image

def _usb_string_desc(s) -> bytes:
    ret = (len(s) * 2 + 2, 0x03)
    for c in s:
        ret += (ord(c), 0x00)
    return bytes(ret)


def tablet(bp: Builder, name: Namespace, gfx: GFXInputConnectionState):
    usb = bp.read_state(name, USBConnectionState, allow_local=True)

    # Connect to console
    gfx.abs_pointer = name

    # USB hotplug connector
    usb.device_connector = bp.obj(name.connector, "usb-device-connector",
          device = name,
          aname = "usb_host",
          remote = usb.host_connector,
          connector_name='connector'
    )
    usb.device = bp.obj(name, "usb_tablet",
        usb_host = usb.host,
        descriptor_data = bytes([
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
            0x07, 0x05, 0x81, 0x03, 0x08, 0x00, 0x03]),
        string_descriptor_array = [
            # string lang descriptor
            bytes((0x04, 0x03, 0x09, 0x04)),
            _usb_string_desc("Simics"),
            _usb_string_desc("Simics USB Tablet")],
        hid_report_descriptor_data = bytes((
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
            0xc0, 0xc0)),
    )


def disk(bp: Builder, name: Namespace, usb = None, **kwds):
    usb = bp.read_state(usb or name, USBConnectionState, allow_local=True)
    di = bp.expose_state(name, DiskImage)

    bp.expand(name, "image", disk_image, **kwds)

    size = di.size if di.size else di.resulting_size
    size_in_blk = (size or 0) // 512

    bp.obj(name.disk, "simple-scsi-disk",
        image = di.obj,
        controller = name,
        geometry = [size_in_blk, 1, 1],
    )
    usb.device_connector = bp.obj(name.connector, "usb-device-connector",
          device = name,
          aname = "usb_host",
          remote = usb.host_connector
    )
    usb.device = bp.obj(name, "usb_disk",
        usb_host = usb.host,
        scsi_disk = name.disk,

        descriptor_data = bytes((
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
            0x07, 0x05, 0x01, 0x02, 0x40, 0x00, 0x00)),

        string_descriptor_array = [
            # string lang descriptor
            bytes((0x06, 0x03, 0x09, 0x00, 0x04, 0x00)),
            _usb_string_desc("Simics"),
            _usb_string_desc("USB Disk"),
            _usb_string_desc("200435132207e9526048")],

        device_qualifier_descriptor_data = bytes((
            # device qualifier descriptor
            # size, dev qualify type,  usb 2.0 = 0x2000
            0x0a, 0x06, 0x02, 0x00,
            # class, subclass, protocol, max packet size,
            0x0, 0x0, 0x0, 0,
            # other speed conf, reserved
            0x0, 0x0)),
    )
