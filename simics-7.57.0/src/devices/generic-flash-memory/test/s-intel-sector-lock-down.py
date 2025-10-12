# © 2012 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Test the Intel Sector Lock Down, Bug 19345

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("28F320C3T", 2, 32)

# write buffer - 16 words
set32(0x0, 0x80)
print("Chip Mode: %s" % conf.flash.chip_mode)
set32(0x0, 0x900090)
print("Chip Mode: %s" % conf.flash.chip_mode)
expect_hex("read 0:", get32(0), 0x890089)
expect_hex("read 1:", get32(4), 0x88c488c4)
expect_hex("read 2:", get32(8), 0x10001)
set32(0x0, 0x600060)
print("Chip Mode: %s" % conf.flash.chip_mode)
set32(0x0, 0x2f002f)
set32(0x0, 0x700070)
print("Chip Mode: %s" % conf.flash.chip_mode)
print("status 0: 0x%x" % get32(0))
set32(0x0, 0x900090)
print("Chip Mode: %s" % conf.flash.chip_mode)
expect_hex("read 8:", get32(8), 0x30003)
set32(0x0, 0x700070)
print("Chip Mode: %s" % conf.flash.chip_mode)
print("status 0: 0x%x" % get32(0))
