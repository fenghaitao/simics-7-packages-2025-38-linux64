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


# Test that intel P30 flashes have a 64 byte write buffer (bug 14453)

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("28F640P30T", 2, 32)

# write buffer - 32 words
set32(0x20200, 0xE800E8)
set32(0x20200, 0x1f001f)

for i in range(32):
    set32(0x20200 + 4 * i, i + (i << 16))

set32(0x20200, 0xD000D0)
set32(0, 0x500050)

expect_hex("write buffer -1", get32(0x201FC), 0xffffffff)
for i in range(32):
    expect_hex("write buffer %d" % (i), get32(0x20200 + i * 4), i + (i << 16))
expect_hex("write buffer 33", get32(0x20200 + 33 *4), 0xffffffff)
