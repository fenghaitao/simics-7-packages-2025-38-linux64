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


# setup: 2 uniform 16-bit Intel CFI compatible flash interleaved
# on a 32-bit bus, with big-endian setup
#
# test:
# - our assumptions about big-endian mode
#

from stest import expect_true

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("28F640J3", 2, 32, big_endian = 1)

# all set and expect functions take little-endian values as input

# make sure the flash is configured as big-endian
expect_true(conf.flash.big_endian == 1)

#
# intel identifiers, flash 2, then flash 1
#

# written on bus as 00 90 00 00, swapped as 00 00 90 00 -> activate flash 2
set32(0, 0x00009000)
# flash 1 returns 0xffff, flash 2 returns 0x0089 => ff ff 89 00, swapped as 00 89 ff ff
expect_hex("manuf. ID:",    get32(0), 0xffff8900)
# reset
set32(0, 0xFFFFFFFF)

# written on bus 00 00 00 90, swapped as 90 00 00 00 -> activate flash 1
set32(0, 0x90000000)
# flash 1 returns 0x0089, flash 2 returns 0xffff => 89 00 ff ff, swapped as ff ff 00 89
expect_hex("manuf. ID:",    get32(0), 0x8900ffff)
# reset
set32(0, 0xFFFFFFFF)

#
# program test, flash 2, then flash 1, then both
#

# written on bus as 00 40 00 00, swapped as 00 00 40 00 -> activate flash 2
set32(0, 0x00004000)
# written on bus as 21 20 00 00, swapped as 00 00 20 21 -> write to flash 2, so
# the new content should be 00 00 20 21, visible from cpu as 21 20 00 00
set32(0x10000, 0x00002021)

set32(0x10000, 0x00005000) # clear status register
# we expect to see exactly what we programmed in, since the endianness
# conversion is invisible for the cpu
expect_hex("program 1", get32(0x10000), 0xffff2021)

# written on bus as 00 00 00 40, swapped as 40 00 00 00 -> activate flash 1
set32(0, 0x40000000)
# written on bus as 00 00 11 10, swapped as 10 11 00 00 -> write to flash 1, so
# the new content should be 10 11 20 21, visible from cpu as 21 20 11 10
set32(0x10000, 0x10110000)
set32(0x10000, 0x50000000) # clear status register
# we expect to see exactly what we programmed in, since the endianness
# conversion is invisible for the cpu
expect_hex("program 2", get32(0x10000), 0x10112021)

set32(0, 0x40004000)
set32(0x10000, 0x12132223)
set32(0x10000, 0x50005000) # clear status register
expect_hex("program 3", get32(0x10000), 0x12132223)


#
# write-buffer test, flash 2, then flash 1, then both
#

# flash 2
set32(0x20200, 0x0000E800)
set32(0x20200, 0x00000300)

set32(0x20200, 0x00002122)
set32(0x20204, 0x00002324)
set32(0x20208, 0x00002526)
set32(0x2020C, 0x00002728)

set32(0x20200, 0x0000D000)
set32(0, 0x00005000)

expect_hex("write buffer 1a", get32(0x20200), 0xffff2122)
expect_hex("write buffer 1b", get32(0x20204), 0xffff2324)
expect_hex("write buffer 1c", get32(0x20208), 0xffff2526)
expect_hex("write buffer 1d", get32(0x2020C), 0xffff2728)

# flash 1
set32(0x20200, 0xE8000000)
set32(0x20200, 0x03000000)

set32(0x20200, 0x11120000)
set32(0x20204, 0x13140000)
set32(0x20208, 0x15160000)
set32(0x2020C, 0x17180000)

set32(0x20200, 0xD0000000)
set32(0, 0x50000000)

expect_hex("write buffer 2a", get32(0x20200), 0x11122122)
expect_hex("write buffer 2b", get32(0x20204), 0x13142324)
expect_hex("write buffer 2c", get32(0x20208), 0x15162526)
expect_hex("write buffer 2d", get32(0x2020C), 0x17182728)
