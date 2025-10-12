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


# setup: a non-uniform 16-bit AMD CFI compatible flash on a 8-bit bus
#
# test:
# - AMD command set for 16-bits on 8-bits bus (all + unlock bypass)
# - non-uniform sectors (lock info, erase)
# - CFI
#

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("Am29SL160CT", 1, 8)

# autoselect at correct address
set8(0x555*2, 0xAA)
set8(0x2AA*2, 0x55)
set8(0x555*2, 0x90)
expect_hex("manuf. ID:",    get8(0*2), 0x01)
expect_hex("device ID:",    get8(1*2), 0xA4)
expect_hex("lock status:",  get8(2*2), 0x0)
expect_hex("outside query", get8(3*2), 0x0)
expect_hex("wrap around at 256 bytes", get8(256*2), 0x01)
expect_hex("beginning of block 2, manuf. ID:",   get8(0x10000), 0x01)
expect_hex("beginning of block 2, device ID:",   get8(0x10000+1*2), 0xA4)
expect_hex("beginning of block 2, lock status:", get8(0x10000+2*2), 0x0)

# now set some lock status to test that we are talking to the right block
conf.flash.lock_status = [[1, 0, 1, 1, 0, 0, 1, 1,
                           1, 0, 0, 0, 1, 1, 1, 1,
                           0, 0, 0, 0, 1, 1, 1, 1,
                           1, 0, 0, 0, 0, 0, 1, 1,
                           1, 1, 1, 1, 0, 0, 0]]

# read all lock status
lock_status_begin = []
for i in range(31):
    lock_status_begin.append(get8(0x10000*i + 2*2))
for i in range(8):
    lock_status_begin.append(get8(0x1F0000 + 0x2000*i + 2*2))
expect("lock status at beginning of blocks",
      [lock_status_begin], conf.flash.lock_status)

# reset
set8(0, 0xF0)

# CFI
set8(0x55*2, 0x98)
expect_hex("CFI: signature 1", get8(0x10*2), 0x51)
expect_hex("CFI: signature 2", get8(0x11*2), 0x52)
expect_hex("CFI: signature 3", get8(0x12*2), 0x59)

expect_hex("CFI: extended 1", get8(0x40*2), 0x50)
expect_hex("CFI: extended 2", get8(0x41*2), 0x52)
expect_hex("CFI: extended 3", get8(0x42*2), 0x49)

set8(0, 0xF0)

# program test
fill(0, 0x10002, 0xcc)
set8(0x555*2, 0xAA)
set8(0x2AA*2, 0x55)
set8(0x555*2, 0xA0)
set8(0x10000, 0x12)
expect_hex("one-byte program 1", get8(0x10000), 0x12)
expect_hex("one-byte program 2", get8(0x0), 0xcc)
expect_hex("one-byte program 3", get8(0xFFFF), 0xcc)
expect_hex("one-byte program 4", get8(0x10001), 0xcc)

# unlock bypass/program
fill(0x1fff, 0x40020, 0xcc)

set8(0x555*2, 0xAA)
set8(0x2AA*2, 0x55)
set8(0x555*2, 0x20)

set8(0, 0xA0)
set8(0x20000, 0xAB)
set8(0, 0xA0)
set8(0x20001, 0x53)
set8(0, 0xA0)
set8(0x30010, 0x87)
set8(0, 0xA0)
set8(0x40011, 0x13)

# unlock bypass/reset
set8(0, 0x90)
set8(0, 0)

expect_hex("unlock bypass program 1", get8(0x1FFFF), 0xcc)
expect_hex("unlock bypass program 2", get8(0x20000), 0xAB)
expect_hex("unlock bypass program 3", get8(0x20001), 0x53)
expect_hex("unlock bypass program 4", get8(0x20002), 0xcc)
expect_hex("unlock bypass program 5", get8(0x3000F), 0xcc)
expect_hex("unlock bypass program 6", get8(0x30010), 0x87)
expect_hex("unlock bypass program 7", get8(0x30011), 0xcc)
expect_hex("unlock bypass program 8", get8(0x40010), 0xcc)
expect_hex("unlock bypass program 9", get8(0x40011), 0x13)
expect_hex("unlock bypass program 10", get8(0x40012), 0xcc)

# sector erase
fill(0xffff, 0x20001, 0xcc)
set8(0x555*2, 0xAA)
set8(0x2AA*2, 0x55)
set8(0x555*2, 0x80)
set8(0x555*2, 0xAA)
set8(0x2AA*2, 0x55)
set8(0x10000, 0x30)

expect_hex("sector erase 1", get8(0x10000), 0xFF)
expect_hex("sector erase 2", get8(0xFFFF),  0xcc)
expect_hex("sector erase 3", get8(0x1FFFF), 0xFF)
expect_hex("sector erase 4", get8(0x20000), 0xcc)

# sector erase (a smaller sector)
fill(0x1f7ff0, 0x1fa010, 0xcc) # fill test area with known pattern
set8(0x555*2, 0xAA)
set8(0x2AA*2, 0x55)
set8(0x555*2, 0x80)
set8(0x555*2, 0xAA)
set8(0x2AA*2, 0x55)
set8(0x1F8000, 0x30)

expect_hex("sector erase 5", get8(0x1F8000), 0xFF)
expect_hex("sector erase 6", get8(0x1F7FFF), 0xcc)
expect_hex("sector erase 7", get8(0x1F9FFF), 0xFF)
expect_hex("sector erase 8", get8(0x1FA000), 0xcc)
