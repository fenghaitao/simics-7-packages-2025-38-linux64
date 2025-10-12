# Test that reset and an_enable bits can be written in one shot

# © 2017 Intel Corporation
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
import pyobj
from configuration import *
from common import control_bf, MiiRegister

# Faked MAC
class Mac(pyobj.ConfObject):
    '''Fake Mac'''
    class ieee_802_3_mac_v3(pyobj.Interface):
        def link_status_changed(self, phy, status):
            pass

simics.SIM_set_configuration([
        OBJECT("mac", "Mac"),
        OBJECT("phy", "generic_eth_phy", address = 1, mac = OBJ("mac"))
    ])

phy = conf.phy
control = MiiRegister(phy, 0, control_bf)
status = MiiRegister(phy, 1, dev_util.Bitfield_LE({"an_complete": 5,
                                                   "an_ability": 3}))

# Default value
stest.expect_equal(status.an_ability, 1)
stest.expect_equal(status.an_complete, 0)


# Set an_enable bit hard reset value to 1 for below tests
phy.register_defaults[0] = 0x1000

# Write reset and an_enable bits in one shot
control.write(0x9000)
stest.expect_equal(control.an_enable, 1)
stest.expect_equal(status.an_complete, 1)

# Restart Auto-Negotiation.
control.restart_an = 1
stest.expect_equal(status.an_complete, 1)


# Set an_enable bit hard reset value to 0 for below tests
phy.register_defaults[0] = 0x0

# Write reset and an_enable bits in one shot
control.write(0x9000)
stest.expect_equal(control.an_enable, 0)
stest.expect_equal(status.an_complete, 0)

# Restart Auto-Negotiation.
logstr = "Attempt to enable auto-negotiation which is not available"
stest.expect_log(control.write, [0x200], log_type = 'spec-viol', msg = logstr)
stest.expect_equal(status.an_complete, 0)
