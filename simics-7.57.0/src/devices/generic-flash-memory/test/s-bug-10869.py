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


# setup: a single Spansion S29GL256N
# test: autoselect for device-id
#

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("S29GL256N", 1, 16)

# autoselect mode
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0x90)
expect_hex("device id 1", get16(0x01 * 2), 0x227E)
expect_hex("device id 2", get16(0x0E * 2), 0x2222)
expect_hex("device id 3", get16(0x0F * 2), 0x2201)
