# © 2014 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# s-spi-bank.py
# tests that the SPI bank allows partial register access

from tb_spi import *

def test_partial_access(bar):
    FDATA0_offs = Ich9SpiConst.reg_info["FDATA0"][0]
    tb.write_value_le(bar + FDATA0_offs, 32, 0x11223344)

    v = tb.read_value_le(bar + FDATA0_offs, 32)
    expect_hex(v, 0x11223344, "full access")

    v = tb.read_value_le(bar + FDATA0_offs, 8)
    expect_hex(v, 0x44, "byte access")

    v = tb.read_value_le(bar + FDATA0_offs + 1, 16)
    expect_hex(v, 0x2233, "word access")

    tb.write_value_le(bar + FDATA0_offs + 3, 8, 0xff)
    v = tb.read_value_le(bar + FDATA0_offs, 32)
    expect_hex(v, 0xff223344, "partial write")


tb = TestBench(1, True, False)

test_partial_access(SPIBAR)
test_partial_access(GBEBAR)
