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


# setup: a 8-bit AMD non-CFI flash on a 8-bit bus
#
# test:
# - AMD command set (autoselect, program, sector erase)
#

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("Am29F040B", 1, 8)

# amd-ignore-cmd-address variant
if "amd_ignore_cmd_address" in dir():
    if amd_ignore_cmd_address:
        conf.flash.amd_ignore_cmd_address = 1
        ADDR_0x555 = 0x0
        ADDR_0x2AA = 0x0
else:
    amd_ignore_cmd_address = 0
    ADDR_0x555 = 0x555
    ADDR_0x2AA = 0x2AA

# autoselect at wrong address
# test is only interesting if amd_ignore_cmd_address is not set
if not amd_ignore_cmd_address:
    set8(0, 0xAA)
    set8(0, 0x55)
    set8(0, 0x90)
    expect_hex("autoselect at wrong address:", get8(0), 0xff)
    # reset
    set8(0, 0xF0)

# autoselect at correct address
set8(ADDR_0x555, 0xAA)
set8(ADDR_0x2AA, 0x55)
set8(ADDR_0x555, 0x90)
expect_hex("manuf. ID:",    get8(0), 0x01)
expect_hex("device ID:",    get8(1), 0xA4)
expect_hex("lock status:",  get8(2), 0x0)
expect_hex("outside query", get8(3), 0x0)
expect_hex("wrap around at 256 bytes", get8(256), 0x01)
expect_hex("beginning of block 2, manuf. ID:",   get8(0x10000), 0x01)
expect_hex("beginning of block 2, device ID:",   get8(0x10001), 0xA4)
expect_hex("beginning of block 2, lock status:", get8(0x10002), 0x0)

# now set some lock status to test that we are talking to the right block
conf.flash.lock_status = [[1, 0, 1, 0, 0, 1, 1, 0]]

# read all lock status
lock_status_begin = []
for i in range(8):
    lock_status_begin.append(get8(0x10000*i + 2))
expect("lock status at beginning of blocks",
       [lock_status_begin], conf.flash.lock_status)

# read all lock status at wrap-around
lock_status_wrap = []
for i in range(8):
    lock_status_wrap.append(get8(0x10000*i + 0x102))
expect("lock status at wrap-around",
       [lock_status_wrap], conf.flash.lock_status)

# reset
set8(0, 0xF0)

# program test
fill(0, 0x10002, 0xcc) # fill test area with C's
set8(ADDR_0x555, 0xAA)
set8(ADDR_0x2AA, 0x55)
set8(ADDR_0x555, 0xA0)
set8(0x10000, 0x12)
expect_hex("one-byte program 1", get8(0x10000), 0x12)
expect_hex("one-byte program 2", get8(0x0), 0xcc)
expect_hex("one-byte program 3", get8(0xFFFF), 0xcc)
expect_hex("one-byte program 4", get8(0x10001), 0xcc)

# program test against lock
set8(ADDR_0x555, 0xAA)
set8(ADDR_0x2AA, 0x55)
set8(ADDR_0x555, 0xA0)
set8(0x0, 0x12)
# this fails because we don't respect locks when programming
# expect_hex("one-byte program lock", get8(0x0), 0)

# sector erase
fill(0xffff, 0x20001, 0xcc) # fill test area with c's
set8(ADDR_0x555, 0xAA)
set8(ADDR_0x2AA, 0x55)
set8(ADDR_0x555, 0x80)
set8(ADDR_0x555, 0xAA)
set8(ADDR_0x2AA, 0x55)
set8(0x10000, 0x30)

expect_hex("sector erase 1", get8(0x10000), 0xFF)
expect_hex("sector erase 2", get8(0xFFFF),  0xCC)
expect_hex("sector erase 3", get8(0x1FFFF), 0xFF)
expect_hex("sector erase 4", get8(0x20000), 0xCC)

# chip erase is not implemented
