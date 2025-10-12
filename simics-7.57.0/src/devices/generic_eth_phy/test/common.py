# © 2011 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import dev_util
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

control_bf = dev_util.Bitfield_LE({"reset": 15, "loopback": 14,
                                   "an_enable": 12, "restart_an": 9})

class MiiRegister(dev_util.AbstractRegister):
    tuple_based = False

    def __init__(self, dev, regnum, fields = None, phy_addr = 0):
        dev_util.AbstractRegister.__init__(self, size=2, bitfield=fields,
                                           little_endian=True)
        self.dev = dev
        self.phy_addr = phy_addr
        self.regnum = regnum

    def raw_read(self):
        return self.dev.iface.mii_management.read_register(
            self.phy_addr, self.regnum)

    def raw_write(self, value):
        self.dev.iface.mii_management.write_register(
            self.phy_addr, self.regnum, value)
