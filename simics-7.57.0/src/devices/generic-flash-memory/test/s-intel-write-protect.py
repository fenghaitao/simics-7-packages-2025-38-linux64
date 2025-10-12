# © 2025 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("28F640P30T", 2, 32)

print("write protect set")
conf.flash.wp = True
expect("Failed to set WP", conf.flash.wp, True)
conf.flash.port.wp.iface.signal.signal_lower()
expect("Failed to clear WP", conf.flash.wp, False)
conf.flash.port.wp.iface.signal.signal_raise()
expect("Failed to set WP", conf.flash.wp, True)

check = list()

# write buffer - 32 words
set32(0x20200, 0xE800E8)
set32(0x20200, 0x1f001f)

for i in range(32):
    set32(0x20200 + 4 * i, i + (i << 16))
    check.append(i + (i << 16))

set32(0x20200, 0xD000D0)
set32(0, 0x500050)

for i in range(32):
    expect_hex("write buffer %d" % (i), get32(0x20200 + i * 4), 0xffffffff)

print("write protect off")
conf.flash.wp = False
expect("Failed to clear WP", conf.flash.wp, False)

# write buffer - 32 words
set32(0x20200, 0xE800E8)
set32(0x20200, 0x1f001f)

for i in range(32):
    set32(0x20200 + 4 * i, i + (i << 16))

set32(0x20200, 0xD000D0)
set32(0, 0x500050)

for i in range(32):
    expect_hex("write buffer %d" % (i), check[i], i + (i << 16))
