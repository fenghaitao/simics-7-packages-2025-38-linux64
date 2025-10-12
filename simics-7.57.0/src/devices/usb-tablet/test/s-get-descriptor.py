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

# Test the get string descriptor request
def str_desc_test(bReq = 0, wVal = 0, size = 0):
    str_desc = [(4, 3, 9, 4),
                (14, 3, 83, 0, 105, 0, 109, 0, 105, 0, 99, 0, 115, 0),
                (36, 3, 83, 0, 105, 0, 109, 0, 105, 0, 99, 0, 115, 0,
                 32, 0,85, 0, 83, 0, 66, 0, 32, 0, 84, 0, 97, 0, 98,
                 0, 108, 0, 101, 0, 116, 0)]

    for ind in range(len(str_desc)):
        str_desc_idx = wVal + ind
        set_transfer_data(bReq = bReq, wVal = str_desc_idx, size = size)
        check_transfer_res(str_desc[ind], str_desc[ind][0], USB_Status_Ack)

# Test the get configuration descriptor request
def conf_desc_test(bReq = 0, wVal = 0, size = 0):
    conf_desc = (0x09, 0x02, 0x22, 0x00, 0x01, 0x01, 0x00, 0xa0, 0x14)
    set_transfer_data(bReq = bReq, wVal = wVal, size = size)
    check_transfer_res(conf_desc, size, USB_Status_Ack)

# Test the get device descriptor request
def dev_desc_test(bReq = 0, wVal = 0, size = 0):
    dev_desc = (0x12, 0x01, 0x10, 0x00, 0x00, 0x00, 0x00, 0x08, 0x27,
                0x06, 0x01, 0x00, 0x00, 0x10, 0x01, 0x02, 0x00, 0x01)
    set_transfer_data(bReq = bReq, wVal = wVal, size = size)
    check_transfer_res(dev_desc, size, USB_Status_Ack)

# Test the get HID report descriptor request
def hid_rep_desc_test(bReq = 0, wVal = 0, size = 0):
    hid_rep_desc = (0x05, 0x01, 0x09, 0x01, 0xa1, 0x01, 0x09, 0x01,
                    0xa1, 0x00, 0x05, 0x09, 0x19, 0x01, 0x29, 0x03,
                    0x15, 0x00, 0x25, 0x01, 0x95, 0x03, 0x75, 0x01,
                    0x81, 0x02, 0x95, 0x01, 0x75, 0x05, 0x81, 0x01,
                    0x05, 0x01, 0x09, 0x30, 0x09, 0x31, 0x15, 0x00,
                    0x26, 0xff, 0x7f, 0x35, 0x00, 0x46, 0xfe, 0x7f,
                    0x75, 0x10, 0x95, 0x02, 0x81, 0x02, 0x05, 0x01,
                    0x09, 0x38, 0x15, 0x81, 0x25, 0x7F, 0x35, 0x00,
                    0x45, 0x00, 0x75, 0x08, 0x95, 0x01, 0x81, 0x02,
                    0xc0, 0xc0)
    set_transfer_data(bReq = bReq, wVal = wVal, size = size)
    check_transfer_res(hid_rep_desc, size, USB_Status_Ack)

# Test answer of non existing debug descriptor request
def debug_desc_test(bReq = 0, wVal = 0, size = 0):
    set_transfer_data(bReq = bReq, wVal = wVal, size = size)
    check_transfer_status(USB_Status_Stall)


def get_desc_test():
    str_desc_test(bReq = 6, wVal = 0b1100000000, size = 50)
    conf_desc_test(bReq = 6, wVal = 0b1000000000, size = 9)
    dev_desc_test(bReq = 6, wVal = 0b100000000, size = 0x12)
    hid_rep_desc_test(bReq = 6, wVal = 0b10001000000000, size = 0x4A)
    debug_desc_test(bReq = 6, wVal = 0b101000000000, size = 0x12)

get_desc_test()
