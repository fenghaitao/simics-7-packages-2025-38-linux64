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


from common import *
from stest import expect_equal

def get_coor_hid(x_coor = 0, y_coor = 0):
    x_hid = x_coor >> 1
    y_hid = y_coor >> 1
    x_low  = x_hid & 0xFF
    x_high = x_hid >> 8
    y_low  = y_hid & 0xFF
    y_high = y_hid >> 8
    return [x_low, x_high, y_low, y_high]

def check_mouse_coor(x_coor = 0, y_coor = 0):
    hid_coor = get_coor_hid(x_coor, y_coor)
    for ind, item in enumerate(hid_coor, start = 1):
        expect_equal(test_device.tablet_hid_data[ind], hid_coor[ind - 1])

def set_mouse_coor(x_coor = 0, y_coor = 0):
    mouse_coor = abs_pointer_state_t(x = x_coor, y = y_coor)
    tablet.iface.abs_pointer.set_state(mouse_coor)

# Test the HID data when the mouse move
def hid_data_test(ep_num = 0, usb_type = 0, bmReq = 0, bReq = 0,
                  x_coor = 0, y_coor = 0):
    set_mouse_coor(x_coor, y_coor)
    set_transfer_data(ep_num = ep_num, usb_type = usb_type,
                      bmReq = bmReq, bReq = bReq)
    check_mouse_coor(x_coor, y_coor)

def mouse_mov_test():
    # Move the mouse cursor diagonally
    for ind in range(5):
        mouse_coor = [10000 * (ind + 1), 10000 * (ind + 1)]
        hid_data_test(bmReq = 0b100000, bReq = 1,
                      x_coor = mouse_coor[0], y_coor = mouse_coor[1])
        hid_data_test(ep_num = 1, usb_type = USB_Type_Bulk,
                      x_coor = mouse_coor[0], y_coor = mouse_coor[1])

    # Move the mouse cursor to the corners
    for ind in range(4):
        mouse_coor = [(ind >> 1) * 0xffff, (ind & 0b01) * 0xffff]
        hid_data_test(bmReq = 0b100000, bReq = 1,
                      x_coor = mouse_coor[0], y_coor = mouse_coor[1])
        hid_data_test(ep_num = 1, usb_type = USB_Type_Bulk,
                      x_coor = mouse_coor[0], y_coor = mouse_coor[1])

mouse_mov_test()
