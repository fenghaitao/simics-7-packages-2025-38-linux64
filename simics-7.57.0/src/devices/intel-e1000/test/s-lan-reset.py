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


# s-lan-reset.py
# tests the reset status of Gigabit LAN Controller in ICH9

from tb_lan import *
stest.untrap_log("unimpl")
stest.untrap_log("spec-viol")

def do_test():
    tb.lan.ports.HRESET.signal.signal_raise()
    for reg_name in IchLanConst.reg_names:
        off = offset_of(reg_name)
        size = size_of(reg_name)
        def_val = default_of(reg_name)
        reg_val = tb.read_value_le(ICH9_LAN_REG_BASE + off, size * 8)
        expect_hex(reg_val, def_val, "default value of register %s" % reg_name)

do_test()
