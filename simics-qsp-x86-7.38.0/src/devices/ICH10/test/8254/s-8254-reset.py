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


# s-8254-reset.py
# test the reset state of the 8254 timer in the LPC bridge in the ICH9 chip

from timer_tb import *

def test_reset(with_alias):
    read_val = tb.read_io_le(0x40, 8)
    expect_hex(read_val, 0x0,
               "counter 0 interval time status byte format register")
    if with_alias:
        read_val2 = tb.read_io_le(0x50, 8)
        expect_hex(
            read_val2, read_val,
            "alias of counter 0 interval time status byte format register")

    read_val = tb.read_io_le(0x41, 8)
    expect_hex(read_val, 0x0,
               "counter 1 interval time status byte format register")
    if with_alias:
        read_val2 = tb.read_io_le(0x51, 8)
        expect_hex(
            read_val2, read_val,
            "alias of counter 1 interval time status byte format register")

    read_val = tb.read_io_le(0x42, 8)
    expect_hex(read_val, 0x0,
               "counter 2 interval time status byte format register")
    if with_alias:
        read_val2 = tb.read_io_le(0x52, 8)
        expect_hex(
            read_val2, read_val,
            "alias of counter 0 interval time status byte format register")

    initial_cnt = 0xFF

    ctrl_val = 0x16 # counter 0, LSB, mode 3
    if with_alias:
        tb.write_io_le(0x53, 8, ctrl_val)
    else:
        tb.write_io_le(0x43, 8, ctrl_val)
    read_val = tb.read_io_le(0x43, 8)
    expect_hex(read_val, 0x0, "write-only timer control word register")
    if with_alias:
        read_val2 = tb.read_io_le(0x53, 8)
        expect_hex(read_val2, read_val,
            "the value of the alias of timer control word register")
    if with_alias:
        tb.write_io_le(0x40, 8, initial_cnt)
    else:
        tb.write_io_le(0x50, 8, initial_cnt)
    read_val = tb.read_io_le(0x40, 8)
    expect_hex(read_val, initial_cnt, "counter 0 initial count value")
    if with_alias:
        read_val2 = tb.read_io_le(0x50, 8)
        expect_hex(read_val2, read_val,
                   "value of alias of counter 0 initial count")


    ctrl_val = 0x56 # counter 1, LSB, mode 3
    if with_alias:
        tb.write_io_le(0x53, 8, ctrl_val)
    else:
        tb.write_io_le(0x43, 8, ctrl_val)
    if with_alias:
        tb.write_io_le(0x41, 8, initial_cnt)
    else:
        tb.write_io_le(0x51, 8, initial_cnt)
    read_val = tb.read_io_le(0x41, 8)
    expect_hex(read_val, initial_cnt, "counter 1 initial count value")
    if with_alias:
        read_val2 = tb.read_io_le(0x51, 8)
        expect_hex(read_val2, read_val,
                   "value of alias of counter 1 initial count")

    ctrl_val = 0x96 # counter 2, LSB, mode 3
    if with_alias:
        tb.write_io_le(0x53, 8, ctrl_val)
    else:
        tb.write_io_le(0x43, 8, ctrl_val)
    if with_alias:
        tb.write_io_le(0x42, 8, initial_cnt)
    else:
        tb.write_io_le(0x52, 8, initial_cnt)
    read_val = tb.read_io_le(0x42, 8)
    expect_hex(read_val, initial_cnt, "counter 2 initial count value")
    if with_alias:
        read_val2 = tb.read_io_le(0x52, 8)
        expect_hex(read_val2, read_val,
                   "value of alias of counter 2 initial count")

test_reset(1)
