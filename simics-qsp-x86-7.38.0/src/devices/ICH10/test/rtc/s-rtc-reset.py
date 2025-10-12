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


# s-rtc-reset.py
# test the reset state of the real-time clock in the LPC bridge in the ICH9 chip

from rtc_tb import *

def test_reset(with_alias):
    for i in range(rtc_reg_cnt):
        tb.write_io_le(rtc_io_index, 8, i)
        read_val = tb.read_io_le(rtc_io_data, 8)
        exp_val = 0x00
        if i == 11:
            exp_val = 0x06
        elif i == 13:
            exp_val = 0x80
        expect_hex(read_val, exp_val, "default value of register %d" % i)

        if with_alias:
            tb.write_io_le(rtc_io_index_alias, 8, i)
            read_val = tb.read_io_le(rtc_io_data_alias, 8)
            expect_hex(read_val, exp_val, "default value of register %d" % i)

    tb.enable_rtc(0)
    tb.set_rtc([0, 0, 0, 0, 0, 0, 0])

test_reset(1)
