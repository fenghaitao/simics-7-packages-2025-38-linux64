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


# setup: a uniform 16-bit Intel CFI compatible flash on a 8-bit bus
#
# test:
# - Intel command set for 16-bits on 8-bits bus
#

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("28F640J3", 1, 8)

# intel identifiers
set8(0x0*2, 0x90)
expect_hex("manuf. ID:",    get8(0*2), 0x89)
expect_hex("device ID:",    get8(1*2), 0x17)
expect_hex("lock status:",  get8(2*2), 0x0)
expect_hex("outside query", get8(3*2), 0x0)
expect_hex("beginning of block 2, manuf. ID:",   get8(0x20000), 0x89)
expect_hex("beginning of block 2, device ID:",   get8(0x20000+1*2), 0x17)
expect_hex("beginning of block 2, lock status:", get8(0x20000+2*2), 0x0)

# now set some lock status to test that we are talking to the right block
conf.flash.lock_status = [[1, 0, 1, 1, 0, 0, 1, 1,
                           1, 0, 0, 0, 1, 1, 1, 1,
                           0, 0, 0, 0, 1, 1, 1, 1,
                           1, 0, 0, 0, 0, 0, 1, 1,
                           1, 1, 1, 1, 0, 0, 0, 0,
                           0, 0, 1, 1, 1, 1, 1, 1,
                           1, 0, 0, 0, 0, 0, 0, 0,
                           1, 1, 1, 1, 1, 1, 1, 1]]

# read all lock status
lock_status_begin = []
for i in range(64):
    lock_status_begin.append(get8(0x20000*i + 2*2))
expect("lock status at beginning of blocks",
      [lock_status_begin], conf.flash.lock_status)

# reset
set8(0, 0xFF)

# CFI
set8(0, 0x98)
expect_hex("CFI: signature 1", get8(0x10*2), 0x51)
expect_hex("CFI: signature 2", get8(0x11*2), 0x52)
expect_hex("CFI: signature 3", get8(0x12*2), 0x59)

expect_hex("CFI: extended 1", get8(0x31*2), 0x50)
expect_hex("CFI: extended 2", get8(0x32*2), 0x52)
expect_hex("CFI: extended 3", get8(0x33*2), 0x49)

set8(0, 0xFF)

# program test
fill(0, 0x10010, 0xcc)
set8(0, 0x40)
set8(0x10000, 0x34)
expect_hex("one-byte program 1", get8(0x10000), 0x80) # status
set8(0x10000, 0x50) # clear status register
expect_hex("one-byte program 1", get8(0x10000), 0x34)
expect_hex("one-byte program 2", get8(0x0), 0xcc)
expect_hex("one-byte program 3", get8(0xFFFF), 0xcc)
expect_hex("one-byte program 4", get8(0x10001), 0xcc)

# write buffer - 16 bytes
set8(0x20200, 0xE8)
set8(0x20200, 15)

set8(0x20200, 0x01)
set8(0x20201, 0x04)
set8(0x20202, 0x05)
set8(0x20203, 0x07)
set8(0x20204, 0x09)
set8(0x20205, 0x11)
set8(0x20206, 0x13)
set8(0x20207, 0x15)
set8(0x20208, 0x17)
set8(0x20209, 0x19)
set8(0x2020A, 0x21)
set8(0x2020B, 0x23)
set8(0x2020C, 0x25)
set8(0x2020D, 0x27)
set8(0x2020E, 0x29)
set8(0x2020F, 0x31)

set8(0x20200, 0xD0)
set8(0, 0x50)

expect_hex("write buffer 1", get8(0x201FF), 0xff)
expect_hex("write buffer 2", get8(0x20200), 0x01)
expect_hex("write buffer 3", get8(0x20201), 0x04)
expect_hex("write buffer 4", get8(0x20202), 0x05)
expect_hex("write buffer 5", get8(0x20203), 0x07)
expect_hex("write buffer 6", get8(0x20204), 0x09)
expect_hex("write buffer 7", get8(0x20205), 0x11)
expect_hex("write buffer 8", get8(0x20206), 0x13)
expect_hex("write buffer 9", get8(0x20207), 0x15)
expect_hex("write buffer 10", get8(0x20208), 0x17)
expect_hex("write buffer 11", get8(0x20209), 0x19)
expect_hex("write buffer 12", get8(0x2020A), 0x21)
expect_hex("write buffer 13", get8(0x2020B), 0x23)
expect_hex("write buffer 14", get8(0x2020C), 0x25)
expect_hex("write buffer 15", get8(0x2020D), 0x27)
expect_hex("write buffer 16", get8(0x2020E), 0x29)
expect_hex("write buffer 17", get8(0x2020F), 0x31)
expect_hex("write buffer 18", get8(0x20210), 0xff)

# sector erase
fill(0x5fff0, 0x80010, 0xcc)
set8(0x60000, 0x20)
set8(0x60000, 0xD0)
set8(0, 0x50)

expect_hex("sector erase 1", get8(0x60000), 0xFF)
expect_hex("sector erase 2", get8(0x5FFFF), 0xcc)
expect_hex("sector erase 3", get8(0x7FFFF), 0xFF)
expect_hex("sector erase 4", get8(0x80000), 0xcc)
