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


# setup: 4 uniform 16-bit Intel CFI compatible flash interleaved
# on a 32-bit bus
#
# test:
# - Intel command set for 16-bits on 8-bits bus with interleave
#   and partial accesses
#

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("28F640J3", 4, 32)

# intel identifiers
set32(0, 0x90000090)
expect_hex("manuf. ID:",    get32(0), 0x89ffff89)
expect_hex("device ID:",    get32(8), 0x17ffff17)
expect_hex("lock status:",  get32(16), 0x00ffff00)
expect_hex("outside query", get32(24), 0x00ffff00)
expect_hex("beginning of block 2, manuf. ID:",   get32(0x80000), 0x89ffff89)
expect_hex("beginning of block 2, device ID:",   get32(0x80000+8), 0x17ffff17)
expect_hex("beginning of block 2, lock status:", get32(0x20000+16), 0x00ffff00)

# reset
set32(0, 0xFFFFFFFF)

# CFI
set32(0, 0x00980098)
expect_hex("CFI: signature 1", get32(0x10*8), 0xff51ff51)
expect_hex("CFI: signature 2", get32(0x11*8), 0xff52ff52)
expect_hex("CFI: signature 3", get32(0x12*8), 0xff59ff59)

expect_hex("CFI: extended 1", get32(0x31*8), 0xff50ff50)
expect_hex("CFI: extended 2", get32(0x32*8), 0xff52ff52)
expect_hex("CFI: extended 3", get32(0x33*8), 0xff49ff49)

set32(0, 0xFFFFFFFF)

# program test
set32(0, 0x00400040)
set32(0x10000, 0x12345678)
expect_hex("program 1", get32(0x10000), 0xff80ff80) # status
set32(0x10000, 0x50505050) # clear status register
expect_hex("program 2", get32(0x10000), 0xff34ff78)
expect_hex("program 3", get32(0x0),     0xffffffff)
expect_hex("program 4", get32(0xFFFC),  0xffffffff)
expect_hex("program 5", get32(0x10004), 0xffffffff)

# write buffer - 16 words
set32(0x20200, 0x00E8E800)
set32(0x20200, 0x00030300)

set32(0x20200, 0x01020304)
set32(0x20208, 0x09101112)
set32(0x2020C, 0x13141516)
set32(0x20204, 0x05060708)

set32(0x20200, 0x00D0D000)
set32(0, 0x50505050)

expect_hex("write buffer 1", get32(0x201FC), 0xffffffff)
expect_hex("write buffer 2", get32(0x20200), 0xff0203ff)
expect_hex("write buffer 3", get32(0x20204), 0xff0607ff)
expect_hex("write buffer 4", get32(0x20208), 0xff1011ff)
expect_hex("write buffer 5", get32(0x2020C), 0xff1415ff)
expect_hex("write buffer 6", get32(0x20210), 0xffffffff)

# sector erase
fill(0x7fff0, 0x100010, 0xcc)
set32(0x80000, 0x20000000)
set32(0x80000, 0xD0000000)
set32(0, 0x50000000)

expect_hex("sector erase 1", get32(0x80000), 0xFFcccccc)
expect_hex("sector erase 2", get32(0x7FFFC), 0xcccccccc)
expect_hex("sector erase 3", get32(0xFFFFC), 0xFFcccccc)
expect_hex("sector erase 4", get32(0x100000), 0xcccccccc)
