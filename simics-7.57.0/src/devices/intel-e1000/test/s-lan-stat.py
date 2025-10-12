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


# s-lan-stat.py
# tests the statistics registers in the Gigabit LAN Controller in ICH9

from tb_lan import *
import random

tb.lan.log_level    = 1

mii_read_op         = 2
mii_write_op        = 1

def do_test():
    # Read the statistics registers and it should be cleared
    tb.lan.ports.HRESET.signal.signal_raise()
    for reg in list(IchLanConst.stat_reg_info.keys()):
        tb.read_value_le(addr_of(reg), bits_of(reg))
        reg_val = tb.read_value_le(addr_of(reg), bits_of(reg))
        expect_hex(reg_val, 0x00, "statistics register cleared by reading")

    # Send/receive a few packets and then read the count
do_test()
