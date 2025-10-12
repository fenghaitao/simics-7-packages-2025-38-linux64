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


# setup: a non-uniform 16-bit AMD CFI compatible flash on a 16-bit bus
#
# test:
# - various too small and too big accesses with unaligned addresses
#

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("Am29SL160CT", 1, 16)

# autoselect at correct address
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0x90)

expect_hex("manuf. ID  8:",    get8(0), 0x01)
expect_hex("manuf. ID 16:",    get16(0), 0x0001)
expect_hex("manuf. ID 32:",    get32(0), 0x22A40001)
expect_hex("manuf. ID 64:",    get64(0), 0x0000000022A40001)

expect_hex("manuf. ID 16 unaligned:",    get16(1), 0xA400)
expect_hex("manuf. ID 32 unaligned:",    get32(1), 0x0022A400)
expect_hex("manuf. ID 32 unaligned:",    get32(2), 0x000022A4)
expect_hex("manuf. ID 32 unaligned:",    get32(3), 0x00000022)

expect_hex("manuf. ID 64 unaligned:",    get32(1), 0x000000000022A400)
