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


import stest
import dev_util
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

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

# Since the mac attribute is required, we have to create a dummy mock
# object. Test will fail if any frame comes in during the test.
class Ieee_802_3_mac_v3(dev_util.Iface):
    iface = "ieee_802_3_mac_v3"
    def tx_bandwidth_available(self, sim_obj, addr):
        stest.fail("tx_bandwidth_available call unexpected")
    def receive_frame(self, sim_obj, addr, frame, crc_ok):
        stest.fail("receive_frame call unexpected")
    def link_status_changed(self, sim_obj, phy, status):
        pass

dummy_mac = dev_util.Dev([Ieee_802_3_mac_v3])

phy = SIM_create_object('dm9161', 'phy', mac=dummy_mac.obj)

control_bf = dev_util.Bitfield_LE({"reset": 15, "an_enable": 12})
control = MiiRegister(phy, 0, control_bf)
status_bf = dev_util.Bitfield_LE({"an_complete": 5})
status = MiiRegister(phy, 1, status_bf)

def soft_reset(obj):
    control.write(reset = 1)

stest.expect_equal(control.an_enable, 1)
stest.expect_equal(status.an_complete, 1)

phy.mii_regs_control = 0
phy.mii_regs_status = 0

stest.expect_equal(control.an_enable, 0)
stest.expect_equal(status.an_complete, 0)

print('foo')
soft_reset(phy)

stest.expect_equal(control.an_enable, 1)
stest.expect_equal(status.an_complete, 1)
