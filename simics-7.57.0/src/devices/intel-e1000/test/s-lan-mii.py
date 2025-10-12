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


# s-lan-mii.py
# tests the MII interface in the Gigabit LAN Controller in ICH9

from tb_lan import *
import random

tb.lan.log_level    = 1

mii_read_op         = 2
mii_write_op        = 1

def do_test(phy_addr, reg_addr, op, data):
    tb.lan.ports.HRESET.signal.signal_raise()
    reg_val = IchLanConst.mdic_bf.value(PHYADDR = phy_addr,
                                         REGADDR = reg_addr,
                                         OP = op,
                                         DATA = data
                                        )

    if op == mii_read_op:
        data = random.randint(0, 255)
        tb.mii.read_val = data
    tb.write_value_le(addr_of("MDIC"), bits_of("MDIC"), reg_val)
    if op == mii_read_op:
        reg_val = tb.read_value_le(addr_of("MDIC"), bits_of("MDIC"))
        fields = IchLanConst.mdic_bf.fields(reg_val)
        expect(fields["DATA"], data,
               "data read from reg %d of PHY %d" % (reg_addr, phy_addr))
        expect(tb.mii.read_phy, phy_addr,
               "phy address to read from the MII interface")
        expect(tb.mii.read_reg, reg_addr,
               "register address to read from the PHY")
    else:
        expect(tb.mii.write_val, data,
               "data written to %d reg of %d PHY" % (reg_addr, phy_addr))
        expect(tb.mii.write_phy, phy_addr,
               "phy address to write to the MII interface")
        expect(tb.mii.write_reg, reg_addr,
               "register address to write to the PHY")

for phy in [1, 2]: # 1 for 82566, 2 for 82567
    tb.lan.phy_address = phy
    for reg in range(32):
        for op in [mii_read_op, mii_write_op]:
            do_test(phy, reg, op, 0x0000)
