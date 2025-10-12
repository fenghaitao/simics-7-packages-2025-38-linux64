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


# setup: 8 times 8-bit AMD non-CFI flash on a 64-bit bus
#
# test:
# - AMD command set (autoselect, program, sector erase)
# - interleave
#

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("Am29F040B", 8, 64)

# autoselect at correct address
set64(0x555*8, 0xAAAAAAAAAAAAAAAA)
set64(0x2AA*8, 0x5555555555555555)
set64(0x555*8, 0x9090909090909090)
expect_hex("manuf. ID:",    get64(0), 0x0101010101010101)
expect_hex("device ID:",    get64(1*8), 0xA4A4A4A4A4A4A4A4)
expect_hex("lock status:",  get64(2*8), 0x0)
expect_hex("outside query", get64(3*8), 0x0)
expect_hex("wrap around at 256 bytes", get64(256*8), 0x0101010101010101)
expect_hex("beginning of block 2, manuf. ID:",
           get64(0x10000*8), 0x0101010101010101)
expect_hex("beginning of block 2, device ID:",
           get64(0x10001*8), 0xA4A4A4A4A4A4A4A4)
expect_hex("beginning of block 2, lock status:", get64(0x10002*8), 0x0)

# now set some lock status to test that we are talking to the right block
conf.flash.lock_status = [[0, 0, 0, 0, 0, 0, 0, 0],
                          [1, 0, 0, 0, 0, 0, 0, 1],
                          [1, 0, 1, 0, 1, 0, 1, 0],
                          [0, 0, 1, 0, 0, 1, 0, 0],
                          [1, 1, 1, 1, 1, 1, 1, 1],
                          [1, 1, 1, 1, 0, 1, 1, 1],
                          [0, 0, 0, 0, 0, 1, 0, 0],
                          [1, 1, 0, 0, 0, 0, 1, 1]]

# read all lock status
lock_status_begin = [[], [], [], [], [], [], [], []]
for i in range(8):
    tmp_lock = make_list(get64((0x10000*i + 2)*8), 8)
    for j in range(8):
        lock_status_begin[j].append(tmp_lock[j])

expect("lock status at beginning of blocks",
      lock_status_begin, conf.flash.lock_status)

# read all lock status at wrap-around
lock_status_wrap = [[], [], [], [], [], [], [], []]
for i in range(8):
    tmp_lock = make_list(get64((0x10000*i + 0x102)*8), 8)
    for j in range(8):
        lock_status_wrap[j].append(tmp_lock[j])

expect("lock status at wrap-around of blocks",
      lock_status_wrap, conf.flash.lock_status)

# reset
set64(0, 0xF0F0F0F0F0F0F0F0)

# program test
fill(0, 0x20000*8, 0xcc) # fill test area with C's
set64(0x555*8, 0xAAAAAAAAAAAAAAAA)
set64(0x2AA*8, 0x5555555555555555)
set64(0x555*8, 0xA0A0A0A0A0A0A0A0)
set64(0x10000*8, 0x0102030405060708)
expect_hex("8-byte program 1", get64(0x10000*8), 0x0102030405060708)
expect_hex("8-byte program 2", get64(    0x0  ), 0xcccccccccccccccc)
expect_hex("8-byte program 3", get64( 0xFFFF*8), 0xcccccccccccccccc)
expect_hex("8-byte program 4", get64(0x10001*8), 0xcccccccccccccccc)

# sector erase
fill(0, 0x20100*8, 0xcc) # fill test area with C's
set64(0x555*8, 0xAAAAAAAAAAAAAAAA)
set64(0x2AA*8, 0x5555555555555555)
set64(0x555*8, 0x8080808080808080)
set64(0x555*8, 0xAAAAAAAAAAAAAAAA)
set64(0x2AA*8, 0x5555555555555555)
set64(0x10000*8,  0x3030303030303030)

expect_hex("sector erase 1", get64(0x10000*8), 0xFFFFFFFFFFFFFFFF)
expect_hex("sector erase 2", get64(0xFFFF*8),  0xcccccccccccccccc)
expect_hex("sector erase 3", get64(0x1FFFF*8), 0xFFFFFFFFFFFFFFFF)
expect_hex("sector erase 4", get64(0x20000*8), 0xcccccccccccccccc)
