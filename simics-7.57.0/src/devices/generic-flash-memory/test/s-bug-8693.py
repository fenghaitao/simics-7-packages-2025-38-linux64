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
# on a 32-bit bus. We'll try 64-bits accesses
#

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("28F640J3", 4, 32)

# write buffer - 16 words
set32(0x20200, 0xE8E8E8E8)
set32(0x20200, 0x03030303)

set64(0x20200, 0x0101010101010101)
set64(0x20208, 0x0202020202020202)

set32(0x20200, 0xD0D0D0D0)
set32(0, 0x50505050)

expect_hex("write buffer 1", get32(0x201FC), 0xffffffff)
expect_hex("write buffer 2", get32(0x20200), 0x01010101)
expect_hex("write buffer 3", get32(0x20204), 0x01010101)
expect_hex("write buffer 4", get32(0x20208), 0x02020202)
expect_hex("write buffer 5", get32(0x2020C), 0x02020202)
expect_hex("write buffer 6", get32(0x20210), 0xffffffff)
