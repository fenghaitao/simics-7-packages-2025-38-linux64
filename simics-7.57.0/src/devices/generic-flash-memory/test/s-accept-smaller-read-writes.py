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
# - accept_smaller_reads/writes attributes
#

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("Am29F040B", 8, 64)

# autoselect at correct address
set16(0x555*8+3, 0xAAAA)
set16(0x2AA*8+3, 0x5555)
set16(0x555*8+3, 0x9090)
expect_hex("manuf. ID:",    get64(0),   0xffffff0101ffffff)
expect_hex("device ID:",    get16(1*8+3), 0xA4A4)
expect_hex("lock status:",  get64(2*8), 0xffffff0000ffffff)
expect_hex("outside query", get64(3*8), 0xffffff0000ffffff)
expect_hex("wrap around at 256 bytes", get64(256*8), 0xffffff0101ffffff)
expect_hex("beginning of block 2, manuf. ID:",
           get16(0x10000*8+3), 0x0101)
expect_hex("beginning of block 2, device ID:",
           get64(0x10001*8), 0xffffffA4A4ffffff)
expect_hex("beginning of block 2, lock status:", get16(0x10002*8+3), 0x0000)

# try some corner cases
set64(0x0, 0xF0F0F0F0F0F0F0F0)

# single byte access at byte 0
set8(0x555*8, 0xAA)
set8(0x2AA*8, 0x55)
set8(0x555*8, 0x90)
expect_hex("manuf. ID 2:",    get64(0), 0xffffffffffffff01)

set64(0x0, 0xF0F0F0F0F0F0F0F0)

# single byte access at byte 7
set8(0x555*8+7, 0xAA)
set8(0x2AA*8+7, 0x55)
set8(0x555*8+7, 0x90)
expect_hex("manuf. ID 3:",    get64(0), 0x01ffffffffffffff)

set64(0x0, 0xF0F0F0F0F0F0F0F0)

# 4 byte access at byte 0
set32(0x555*8, 0xAAAAAAAA)
set32(0x2AA*8, 0x55555555)
set32(0x555*8, 0x90909090)
expect_hex("manuf. ID 4:",    get64(0), 0xffffffff01010101)

set64(0x0, 0xF0F0F0F0F0F0F0F0)

# 4 byte access at byte 3
set32(0x555*8, 0xAAAAAAAA)
set32(0x2AA*8, 0x55555555)
set32(0x555*8, 0x90909090)
expect_hex("manuf. ID 5:",    get32(3), 0xffffff01)
