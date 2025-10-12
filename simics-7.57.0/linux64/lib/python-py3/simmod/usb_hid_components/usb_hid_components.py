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

class AbsMouseDownConnector(StandardConnector):
    '''The AbsMouseDownConnector class handles abs-mouse down
    connections. The first argument to the init method is the
    device which wants to receive coordinates from console.'''

    type = 'abs-mouse'
    direction = simics.Sim_Connector_Direction_Down
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, dev):
        self.dev = dev

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.dev)]

    def connect(self, cmp, cnt, attr):
        pass

    def disconnect(self, cmp, cnt):
        pass

class MouseDownConnector(StandardConnector):
    '''The MouseDownConnector class handles mouse down
    connections. The first argument to the init method is the
    device which wants to receive coordinates from console.'''

    type = 'mouse'
    direction = simics.Sim_Connector_Direction_Down
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, dev):
        self.dev = dev

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.dev)]

    def connect(self, cmp, cnt, attr):
        pass

    def disconnect(self, cmp, cnt):
        pass

class KeyboardDownConnector(StandardConnector):
    '''The KeyboardDownConnector class handles keyboard down
    connections. The first argument to the init method is the
    device which wants to receive keys from console.'''

    type = 'keyboard'
    direction = simics.Sim_Connector_Direction_Down
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, dev):
        self.dev = dev

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.dev)]

    def connect(self, cmp, cnt, attr):
        pass

    def disconnect(self, cmp, cnt):
        pass

class usb_generic:
    def string_desc(self, str):
        ret = (len(str) * 2 + 2, 0x03)
        for c in str:
            ret += (ord(c), 0x00)
        return ret

class usb_mouse_comp(StandardConnectorComponent, usb_generic):
    """The USB Mouse component class. Encapsulated usb-mouse device in
    \'usb_device\' slot."""
    _class_desc = "a USB mouse"
    _help_categories = ()

    def setup(self):
        StandardComponent.setup(self)
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_objects(self):
        # add usb-mouse
        usb_device = self.add_pre_obj('usb_device', 'usb_mouse')
        usb_device.descriptor_data = ( # -------- Device Descriptor --------
                                         18, # bLength - in bytes
                                          1, # bDescriptorType - 1 means device descriptor
                                 0x00, 0x01, # bcdUSB two bytes - Revision of USB protocol 1.00
                                          0, # bDeviceClass - 0 means see following interface descriptors
                                          0, # bDeviceSubClass - 0 means see following interface descriptors
                                          0, # bDeviceProtocol - 0 means see following interface descriptors
                                         64, # bMaxPacketSize should be (8, 16, 32 or 64)
                                 0x86, 0x80, # idVendor (lower than higher byte)
                                 0xE0, 0xBE, # idProduct (lower than higher byte)
                                 0x00, 0x01, # bcdDevice two bytes - 1.00
                                          1, # iManufacturer
                                          2, # iProduct
                                          3, # iSerialNumber
                                          1, # bNumConfigurations
                                       # -------- Configuration Descriptor - general device info --------
                                          9, # bLength - in bytes
                                          2, # bDescriptorType - 2 means Configuration Descriptor
                                   34,    0, # wTotalLength (lower than higher byte) - total length
                                               #  of Configuration Descriptor = 9 + 9 + 9 + 7
                                          1, # bNumInterfaces
                                          1, # bConfigurationValue
                                          0, # iConfiguration
                                       0xa0, # bmAttributes
                                         50, # MaxPower = 50 * 2mA = 100 mA
                                       # -------- Configuration Descriptor - PrimaryInterfaceDescriptor --------
                                          9, # bLength
                                          4, # bDescriptorType - 4 means PrimaryInterfaceDescriptor
                                          0, # bInterfaceNumber
                                          0, # bAlternateSetting
                                          1, # bNumEndpoints (excluding EP0)
                                          3, # bInterfaceClass    - HID
                                          1, # bInterfaceSubClass - Boot interface subclass
                                          2, # bInterfaceProtocol - Mouse protocol
                                          0, # iInterface
                                       # -------- Configuration Descriptor - HID descriptor --------
                                          9, # bLength
                                       0x21, # bDescriptorType - HID descriptor type
                                 0x11, 0x01, # bcdHID - version of Device Class Definition for HID 1.11
                                          0, # bCountryCode
                                          1, # bNumDescriptors
                                       0x22, # bDescriptorType   - Report descriptor type
                                   52,    0, # wDescriptorLength - Length of report descriptor (sometimes ignored)
                                       # -------- Configuration Descriptor - Endpoint 1 Descriptor --------
                                          7, # bLength
                                          5, # bDescriptorType - 5 means Endpoint Descriptor
                                       0x81, # bEndpointAddress - Endpoint number 1 - direction IN
                                       0x03, # bmAttributes - Interrupt endpoint
                                       8, 0, # wMaxPacketSize
                                         10  # bInterval - Poll every 10 ms
                                       )
        usb_device.string_descriptor_array = [(4, 3, 9, 4), # language Descriptor (string index0)
                                      self.string_desc("Intel"),
                                      self.string_desc("Simics USB Mouse"),
                                      self.string_desc("0123456789")]
        usb_device.hid_report_descriptor_data = (
                                                 0x5,  0x1, # Usage Page (Generic Desktop)
                                                 0x9,  0x2, # Usage (Mouse)
                                                0xa1,  0x1, # Collection (Application)
                                                 0x9,  0x1, # Usage (Pointer)
                                                0xa1,  0x0, # Collection (Physical)
                                                0x95,  0x5, # Report Count (5)
                                                0x75,  0x1, # Report Size (1)
                                                 0x5,  0x9, # Usage Page (Buttons)
                                                0x19,  0x1, # Usage Minimum (1)
                                                0x29,  0x5, # Usage Maximum (5)
                                                0x15,  0x0, # Logical Minimum (0)
                                                0x25,  0x1, # Logical Maximum (1)
                                                0x81,  0x2, # Input (Data, Variable, Absolute)
                                                0x95,  0x1, # Report Count (1)
                                                0x75,  0x3, # Report Size (3)
                                                0x81,  0x1, # Input (Constant)
                                                0x75,  0x8, # Report Size (8)
                                                0x95,  0x3, # Report Count (3)
                                                 0x5,  0x1, # Usage Page (Generic Desktop)
                                                 0x9, 0x30, # Usage (X)
                                                 0x9, 0x31, # Usage (Y)
                                                 0x9, 0x38, # Usage (Wheel)
                                                0x15, 0x81, # Logical Minimum (-127)
                                                0x25, 0x7f, # Logical Maximum (127)
                                                0x81,  0x6, # Input (Data, Variable, Relative)
                                                0xc0, #  // End Collection
                                                0xc0  #  // End Collection
                                               )
        usb_device.device_qualifier_descriptor_data = (
            0x0a, # bLength - in bytes
            0x06, # bDescriptorType
            0x02, 0x00, # bcdUSB two bytes - usb 2.0 = 0x2000
            0x0, # bDeviceClass - 0 means see following interface descriptors
            0x0, # bDeviceSubClass - 0 means see following interface descriptors
            0x0, # bDeviceProtocol - 0 means see following interface descriptors
            0,   # bMaxPacketSize
            0x0, # other speed conf
            0x0  # reserved
        )

    def add_connectors(self):
        # device ports
        self.add_connector('connector_usb_host', UsbPortUpConnector('usb_device'))
        self.add_connector('connector_abs_mouse', AbsMouseDownConnector('usb_device'))
        self.add_connector('connector_mouse', MouseDownConnector('usb_device'))


# -------- USB KEYBOARD --------
class usb_keyboard_comp(StandardConnectorComponent, usb_generic):
    """The USB Keyboard component class. Encapsulated usb-keyboard device in
    \'usb_device\' slot."""
    _class_desc = "a USB keyboard"
    _help_categories = ()

    def setup(self):
        StandardComponent.setup(self)
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_objects(self):
        # add usb-keyboard
        usb_device = self.add_pre_obj('usb_device', 'usb_keyboard')
        usb_device.descriptor_data = ( # -------- Device Descriptor --------
                                         18, # bLength - in bytes
                                          1, # bDescriptorType - 1 means device descriptor
                                 0x00, 0x01, # bcdUSB two bytes - Revision of USB protocol 1.00
                                          0, # bDeviceClass - 0 means see following interface descriptors
                                          0, # bDeviceSubClass - 0 means see following interface descriptors
                                          0, # bDeviceProtocol - 0 means see following interface descriptors
                                         64, # bMaxPacketSize should be (8, 16, 32 or 64)
                                 0x86, 0x80, # idVendor (lower than higher byte)
                                 0xE0, 0xBE, # idProduct (lower than higher byte)
                                 0x00, 0x01, # bcdDevice two bytes - 1.00
                                          1, # iManufacturer
                                          2, # iProduct
                                          3, # iSerialNumber
                                          1, # bNumConfigurations
                                       # -------- Configuration Descriptor - general device info --------
                                          9, # bLength - in bytes
                                          2, # bDescriptorType - 2 means Configuration Descriptor
                                   34,    0, # wTotalLength (lower than higher byte) - total length
                                               #  of Configuration Descriptor = 9 + 9 + 9 + 7
                                          1, # bNumInterfaces
                                          1, # bConfigurationValue
                                          0, # iConfiguration
                                       0xa0, # bmAttributes
                                         50, # MaxPower = 50 * 2mA = 100 mA
                                       # -------- Configuration Descriptor - PrimaryInterfaceDescriptor --------
                                          9, # bLength
                                          4, # bDescriptorType - 4 means PrimaryInterfaceDescriptor
                                          0, # bInterfaceNumber
                                          0, # bAlternateSetting
                                          1, # bNumEndpoints (excluding EP0)
                                          3, # bInterfaceClass    - HID
                                          1, # bInterfaceSubClass - Boot interface subclass
                                          1, # bInterfaceProtocol - Keyboard protocol
                                          0, # iInterface
                                       # -------- Configuration Descriptor - HID descriptor --------
                                          9, # bLength
                                       0x21, # bDescriptorType - HID descriptor type
                                 0x11, 0x01, # bcdHID - version of Device Class Definition for HID 1.11
                                          0, # bCountryCode
                                          1, # bNumDescriptors
                                       0x22, # bDescriptorType   - Report descriptor type
                                   63,    0, # wDescriptorLength - Length of report descriptor (sometimes ignored)
                                       # -------- Configuration Descriptor - Endpoint 1 Descriptor --------
                                          7, # bLength
                                          5, # bDescriptorType - 5 means Endpoint Descriptor
                                       0x81, # bEndpointAddress - Endpoint number 1 - direction IN
                                       0x03, # bmAttributes - Interrupt endpoint
                                       8, 0, # wMaxPacketSize
                                         10  # bInterval - Poll every 10 ms
                                       )
        usb_device.string_descriptor_array = [(4, 3, 9, 4), # language Descriptor (string index0)
                                      self.string_desc("Intel"),
                                      self.string_desc("Simics USB Keyboard"),
                                      self.string_desc("0123456789")]
        usb_device.hid_report_descriptor_data = (
                                                0x05, 0x01, # USAGE_PAGE (Generic Desktop)
                                                0x09, 0x06, # USAGE (Keyboard)
                                                0xA1, 0x01, # COLLECTION (Application)
                                                0x05, 0x07, # USAGE_PAGE (Key Codes)
                                                0x19, 0xE0, # USAGE_MINIMUM (Keyboard LeftControl)
                                                0x29, 0xE7, # USAGE_MAXIMUM (Keyboard Right GUI)
                                                0x15, 0x00, # LOGICAL_MINIMUM (0)
                                                0x25, 0x01, # LOGICAL_MAXIMUM (1)
                                                0x75, 0x01, # REPORT_SIZE (1)
                                                0x95, 0x08, # REPORT_COUNT (8)
                                                0x81, 0x02, # INPUT (Data,Var,Abs)
                                                0x95, 0x01, # REPORT_COUNT (1)
                                                0x75, 0x08, # REPORT_SIZE (8)
                                                0x81, 0x03, # INPUT (Cnst,Var,Abs)
                                                0x95, 0x05, # REPORT_COUNT (5)
                                                0x75, 0x01, # REPORT_SIZE (1)
                                                0x05, 0x08, # USAGE_PAGE (LEDs)
                                                0x19, 0x01, # USAGE_MINIMUM (Num Lock)
                                                0x29, 0x05, # USAGE_MAXIMUM (Kana)
                                                0x91, 0x02, # OUTPUT (Data,Var,Abs)
                                                0x95, 0x01, # REPORT_COUNT (1)
                                                0x75, 0x03, # REPORT_SIZE (3)
                                                0x91, 0x03, # OUTPUT (Cnst,Var,Abs)
                                                0x95, 0x06, # REPORT_COUNT (6)
                                                0x75, 0x08, # REPORT_SIZE (8)
                                                0x15, 0x00, # LOGICAL_MINIMUM (0)
                                                0x25, 0xff, # LOGICAL_MAXIMUM (255)
                                                0x05, 0x07, # USAGE_PAGE (Keyboard)
                                                0x19, 0x00, # USAGE_MINIMUM (0)
                                                0x29, 0xff, # USAGE_MAXIMUM (255)
                                                0x81, 0x00, # INPUT (Data,Ary,Abs)
                                                0xC0        # END_COLLECTION
                                               )
        usb_device.tr_table = [0 for i in range(256)]
        usb_device.tr_table[28:28+26] = [0x04+i for i in range(26)] # alphabet
        usb_device.tr_table[18]       = 0x27 # 0
        usb_device.tr_table[19:19+9]  = [0x1e+i for i in range(9)] # 1-9
        usb_device.tr_table[67]       = 0x28 # Return
        usb_device.tr_table[1]        = 0x29 # Esc
        usb_device.tr_table[68]       = 0x2a # Backspace
        usb_device.tr_table[66]       = 0x2b # Tab
        usb_device.tr_table[61]       = 0x2c # Space
        usb_device.tr_table[64]       = 0x2d # -
        usb_device.tr_table[58]       = 0x2e # =
        usb_device.tr_table[62]       = 0x2f # [
        usb_device.tr_table[63]       = 0x30 # ]
        usb_device.tr_table[60]       = 0x31 # \
        usb_device.tr_table[57]       = 0x33 # ;
        usb_device.tr_table[54]       = 0x34 # '
        usb_device.tr_table[65]       = 0x35 # `
        usb_device.tr_table[55]       = 0x36 # ,
        usb_device.tr_table[56]       = 0x37 # .
        usb_device.tr_table[59]       = 0x38 # /
        usb_device.tr_table[71]       = 0xe1 # Left SHIFT
        usb_device.tr_table[72]       = 0xe5 # Right SHIFT
        usb_device.tr_table[86]       = 0x52 # Key up
        usb_device.tr_table[87]       = 0x51 # Key down
        usb_device.tr_table[88]       = 0x50 # Key left
        usb_device.tr_table[89]       = 0x4f # Key right
        usb_device.tr_table[2:2+12]  = [0x3a+i for i in range(12)] # F1-F12
        usb_device.tr_table[101]      = 0x48 # Pause
        usb_device.tr_table[80]       = 0x49 # Insert
        usb_device.tr_table[81]       = 0x4A # Home
        usb_device.tr_table[82]       = 0x4B # PgUp
        usb_device.tr_table[83]       = 0x4C # Delete
        usb_device.tr_table[84]       = 0x4D # End
        usb_device.tr_table[85]       = 0x4E # PgDn
        usb_device.tr_table[69]       = 0xE0 # Left CTRL
        usb_device.tr_table[70]       = 0xE4 # Right CTRL
        usb_device.tr_table[73]       = 0xE2 # Left ALT
        usb_device.tr_table[74]       = 0xE6 # Right ALT
        usb_device.tr_table[17]       = 0x39 # CAPS_LOCK
        usb_device.tr_table[16]       = 0x53 # NUM_LOCK
        usb_device.tr_table[15]       = 0x47 # SCROLL_LOCK
        usb_device.tr_table[14]       = 0x46 # PRNT_SCRN
        usb_device.tr_table[75]       = 0x54 # keypad /
        usb_device.tr_table[76]       = 0x55 # keypad *
        usb_device.tr_table[77]       = 0x56 # keypad -
        usb_device.tr_table[78]       = 0x57 # keypad +
        usb_device.tr_table[79]       = 0x58 # keypad enter
        usb_device.tr_table[96]       = 0x59 # keypad 1
        usb_device.tr_table[97]       = 0x5A # keypad 2
        usb_device.tr_table[98]       = 0x5B # keypad 3
        usb_device.tr_table[93]       = 0x5C # keypad 4
        usb_device.tr_table[94]       = 0x5D # keypad 5
        usb_device.tr_table[95]       = 0x5E # keypad 6
        usb_device.tr_table[90]       = 0x5F # keypad 7
        usb_device.tr_table[91]       = 0x60 # keypad 8
        usb_device.tr_table[92]       = 0x61 # keypad 9
        usb_device.tr_table[99]       = 0x62 # keypad 0
        usb_device.tr_table[100]      = 0x63 # keypad .

    def add_connectors(self):
        # device ports
        self.add_connector('connector_usb_host', UsbPortUpConnector('usb_device'))
        self.add_connector('connector_keyboard', KeyboardDownConnector('usb_device'))

# -------- USB HIGH SPEED KEYBOARD --------
class usb_hs_keyboard_comp(StandardConnectorComponent, usb_generic):
    """The High Speed USB Keyboard component class. Encapsulated usb-hs-keyboard
    device in \'usb_device\' slot."""
    _class_desc = "high speed USB keyboard"
    _help_categories = ()

    def setup(self):
        StandardComponent.setup(self)
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_objects(self):
        # add usb-keyboard
        usb_device = self.add_pre_obj('usb_device', 'usb_hs_keyboard')
        usb_device.descriptor_data = ( # -------- Device Descriptor --------
                                         18, # bLength - in bytes
                                          1, # bDescriptorType - 1 means device descriptor
                                 0x00, 0x02, # bcdUSB two bytes - Revision of USB protocol 2.00
                                          0, # bDeviceClass - 0 means see following interface descriptors
                                          0, # bDeviceSubClass - 0 means see following interface descriptors
                                          0, # bDeviceProtocol - 0 means see following interface descriptors
                                         64, # bMaxPacketSize should be (8, 16, 32 or 64)
                                 0x86, 0x80, # idVendor (lower than higher byte)
                                 0xE0, 0xBE, # idProduct (lower than higher byte)
                                 0x00, 0x01, # bcdDevice two bytes - 1.00
                                          1, # iManufacturer
                                          2, # iProduct
                                          3, # iSerialNumber
                                          1, # bNumConfigurations
                                       # -------- Configuration Descriptor - general device info --------
                                          9, # bLength - in bytes
                                          2, # bDescriptorType - 2 means Configuration Descriptor
                                   34,    0, # wTotalLength (lower than higher byte) - total length
                                               #  of Configuration Descriptor = 9 + 9 + 9 + 7
                                          1, # bNumInterfaces
                                          1, # bConfigurationValue
                                          0, # iConfiguration
                                       0xa0, # bmAttributes
                                         50, # MaxPower = 50 * 2mA = 100 mA
                                       # -------- Configuration Descriptor - PrimaryInterfaceDescriptor --------
                                          9, # bLength
                                          4, # bDescriptorType - 4 means PrimaryInterfaceDescriptor
                                          0, # bInterfaceNumber
                                          0, # bAlternateSetting
                                          1, # bNumEndpoints (excluding EP0)
                                          3, # bInterfaceClass    - HID
                                          1, # bInterfaceSubClass - Boot interface subclass
                                          1, # bInterfaceProtocol - Keyboard protocol
                                          0, # iInterface
                                       # -------- Configuration Descriptor - HID descriptor --------
                                          9, # bLength
                                       0x21, # bDescriptorType - HID descriptor type
                                 0x11, 0x01, # bcdHID - version of Device Class Definition for HID 1.11
                                          0, # bCountryCode
                                          1, # bNumDescriptors
                                       0x22, # bDescriptorType   - Report descriptor type
                                   63,    0, # wDescriptorLength - Length of report descriptor (sometimes ignored)
                                       # -------- Configuration Descriptor - Endpoint 1 Descriptor --------
                                          7, # bLength
                                          5, # bDescriptorType - 5 means Endpoint Descriptor
                                       0x81, # bEndpointAddress - Endpoint number 1 - direction IN
                                       0x03, # bmAttributes - Interrupt endpoint
                                       8, 0, # wMaxPacketSize
                                         10  # bInterval - Poll every 10 ms
                                       )
        usb_device.string_descriptor_array = [(4, 3, 9, 4), # language Descriptor (string index0)
                                      self.string_desc("Intel"),
                                      self.string_desc("Simics High Speed USB Keyboard"),
                                      self.string_desc("0123456789")]
        usb_device.hid_report_descriptor_data = (
                                                0x05, 0x01, # USAGE_PAGE (Generic Desktop)
                                                0x09, 0x06, # USAGE (Keyboard)
                                                0xA1, 0x01, # COLLECTION (Application)
                                                0x05, 0x07, # USAGE_PAGE (Key Codes)
                                                0x19, 0xE0, # USAGE_MINIMUM (Keyboard LeftControl)
                                                0x29, 0xE7, # USAGE_MAXIMUM (Keyboard Right GUI)
                                                0x15, 0x00, # LOGICAL_MINIMUM (0)
                                                0x25, 0x01, # LOGICAL_MAXIMUM (1)
                                                0x75, 0x01, # REPORT_SIZE (1)
                                                0x95, 0x08, # REPORT_COUNT (8)
                                                0x81, 0x02, # INPUT (Data,Var,Abs)
                                                0x95, 0x01, # REPORT_COUNT (1)
                                                0x75, 0x08, # REPORT_SIZE (8)
                                                0x81, 0x03, # INPUT (Cnst,Var,Abs)
                                                0x95, 0x05, # REPORT_COUNT (5)
                                                0x75, 0x01, # REPORT_SIZE (1)
                                                0x05, 0x08, # USAGE_PAGE (LEDs)
                                                0x19, 0x01, # USAGE_MINIMUM (Num Lock)
                                                0x29, 0x05, # USAGE_MAXIMUM (Kana)
                                                0x91, 0x02, # OUTPUT (Data,Var,Abs)
                                                0x95, 0x01, # REPORT_COUNT (1)
                                                0x75, 0x03, # REPORT_SIZE (3)
                                                0x91, 0x03, # OUTPUT (Cnst,Var,Abs)
                                                0x95, 0x06, # REPORT_COUNT (6)
                                                0x75, 0x08, # REPORT_SIZE (8)
                                                0x15, 0x00, # LOGICAL_MINIMUM (0)
                                                0x25, 0xff, # LOGICAL_MAXIMUM (255)
                                                0x05, 0x07, # USAGE_PAGE (Keyboard)
                                                0x19, 0x00, # USAGE_MINIMUM (0)
                                                0x29, 0xff, # USAGE_MAXIMUM (255)
                                                0x81, 0x00, # INPUT (Data,Ary,Abs)
                                                0xC0        # END_COLLECTION
                                               )
        usb_device.device_qualifier_descriptor_data = (
            0x0a, # bLength - in bytes
            0x06, # bDescriptorType
            0x02, 0x00, # bcdUSB two bytes - usb 2.0 = 0x2000
            0x0, # bDeviceClass - 0 means see following interface descriptors
            0x0, # bDeviceSubClass - 0 means see following interface descriptors
            0x0, # bDeviceProtocol - 0 means see following interface descriptors
            0,   # bMaxPacketSize
            0x0, # other speed conf
            0x0  # reserved
        )
        usb_device.tr_table = [0 for i in range(256)]
        usb_device.tr_table[28:28+26] = [0x04+i for i in range(26)] # alphabet
        usb_device.tr_table[18]       = 0x27 # 0
        usb_device.tr_table[19:19+9]  = [0x1e+i for i in range(9)] # 1-9
        usb_device.tr_table[67]       = 0x28 # Return
        usb_device.tr_table[1]        = 0x29 # Esc
        usb_device.tr_table[68]       = 0x2a # Backspace
        usb_device.tr_table[66]       = 0x2b # Tab
        usb_device.tr_table[61]       = 0x2c # Space
        usb_device.tr_table[64]       = 0x2d # -
        usb_device.tr_table[58]       = 0x2e # =
        usb_device.tr_table[62]       = 0x2f # [
        usb_device.tr_table[63]       = 0x30 # ]
        usb_device.tr_table[60]       = 0x31 # \
        usb_device.tr_table[57]       = 0x33 # ;
        usb_device.tr_table[54]       = 0x34 # '
        usb_device.tr_table[65]       = 0x35 # `
        usb_device.tr_table[55]       = 0x36 # ,
        usb_device.tr_table[56]       = 0x37 # .
        usb_device.tr_table[59]       = 0x38 # /
        usb_device.tr_table[71]       = 0xe1 # Left SHIFT
        usb_device.tr_table[72]       = 0xe5 # Right SHIFT
        usb_device.tr_table[86]       = 0x52 # Key up
        usb_device.tr_table[87]       = 0x51 # Key down
        usb_device.tr_table[88]       = 0x50 # Key left
        usb_device.tr_table[89]       = 0x4f # Key right
        usb_device.tr_table[2:2+12]  = [0x3a+i for i in range(12)] # F1-F12
        usb_device.tr_table[101]      = 0x48 # Pause
        usb_device.tr_table[80]       = 0x49 # Insert
        usb_device.tr_table[81]       = 0x4A # Home
        usb_device.tr_table[82]       = 0x4B # PgUp
        usb_device.tr_table[83]       = 0x4C # Delete
        usb_device.tr_table[84]       = 0x4D # End
        usb_device.tr_table[85]       = 0x4E # PgDn
        usb_device.tr_table[69]       = 0xE0 # Left CTRL
        usb_device.tr_table[70]       = 0xE4 # Right CTRL
        usb_device.tr_table[73]       = 0xE2 # Left ALT
        usb_device.tr_table[74]       = 0xE6 # Right ALT
        usb_device.tr_table[17]       = 0x39 # CAPS_LOCK
        usb_device.tr_table[16]       = 0x53 # NUM_LOCK
        usb_device.tr_table[15]       = 0x47 # SCROLL_LOCK
        usb_device.tr_table[14]       = 0x46 # PRNT_SCRN
        usb_device.tr_table[75]       = 0x54 # keypad /
        usb_device.tr_table[76]       = 0x55 # keypad *
        usb_device.tr_table[77]       = 0x56 # keypad -
        usb_device.tr_table[78]       = 0x57 # keypad +
        usb_device.tr_table[79]       = 0x58 # keypad enter
        usb_device.tr_table[96]       = 0x59 # keypad 1
        usb_device.tr_table[97]       = 0x5A # keypad 2
        usb_device.tr_table[98]       = 0x5B # keypad 3
        usb_device.tr_table[93]       = 0x5C # keypad 4
        usb_device.tr_table[94]       = 0x5D # keypad 5
        usb_device.tr_table[95]       = 0x5E # keypad 6
        usb_device.tr_table[90]       = 0x5F # keypad 7
        usb_device.tr_table[91]       = 0x60 # keypad 8
        usb_device.tr_table[92]       = 0x61 # keypad 9
        usb_device.tr_table[99]       = 0x62 # keypad 0
        usb_device.tr_table[100]      = 0x63 # keypad .

    def add_connectors(self):
        # device ports
        self.add_connector('connector_usb_host', UsbPortUpConnector('usb_device'))
        self.add_connector('connector_keyboard', KeyboardDownConnector('usb_device'))
