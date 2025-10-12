# Test that link status is propagated correctly to mac when
# restart Auto-Negotiation process

# © 2015 Intel Corporation
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
    def _initialize(self):
        super()._initialize()
        self.link_status_changed_calls = []
    class ieee_802_3_mac_v3(pyobj.Interface):
        def link_status_changed(self, phy, status):
            SIM_log_info(2, self._up.obj, 0,
                "link_status_changed(): phy=%d, status=%s" %
                (phy, ('unconnected', 'down', 'up')[status]))
            self._up.link_status_changed_calls.append((phy, status))

class EthernetCommon(pyobj.ConfObject):
    def __init__(self):
        super().__init__()
        self.frames = []
    class ethernet_common(pyobj.Interface):
        def frame(self, sim_obj, frame, crc_status):
            self.frames.append((frame, crc_status))

simics.SIM_set_configuration([
        OBJECT("ep", "EthernetCommon"),
        OBJECT("mac", "Mac"),
        OBJECT("phy", "generic_eth_phy", address = 1, mac = OBJ("mac"))
    ])

mac = SIM_object_data(conf.mac)
phy = conf.phy
ep = SIM_object_data(conf.ep)
link_down = simics.IEEE_link_down
link_up = simics.IEEE_link_up

control = MiiRegister(phy, 0, control_bf)
status = MiiRegister(phy, 1, dev_util.Bitfield_LE({"an_complete": 5,
                                                   "an_ability": 3,
                                                   "link_status": 2}))

stest.expect_equal(status.an_ability, 1)
stest.expect_equal(status.an_complete, 0)

# Restart Auto-Negotiation before it be enabled
logstr = "Attempt to enable auto-negotiation which is not available"
stest.expect_log(control.write, [0x200], log_type = 'spec-viol', msg = logstr)

# Enable Auto-Negotiation
control.an_enable = 1
stest.expect_equal(status.an_complete, 1)
# Link down because there is no link connecting
stest.expect_equal(status.link_status, 0)

# Restart Auto-Negotiation
mac.link_status_changed_calls = [] # Clear link status changed record
control.restart_an = 1
stest.expect_equal(status.an_complete, 1)
# No link status change because the link status is down
stest.expect_equal(status.link_status, 0)
stest.expect_equal(mac.link_status_changed_calls, [])

# Disable Auto-Negotiation
control.an_enable = 0
# Link connected
phy.link = ep.obj
mac.link_status_changed_calls = [] # Clear link status changed record
# Enable Auto-Negotiation
control.an_enable = 1
stest.expect_equal(status.an_complete, 1)
# Check the link status after enable Auto-Negotiation of phy 1
stest.expect_equal(mac.link_status_changed_calls, [])

control.restart_an = 1
stest.expect_equal(status.an_complete, 1)
# Check the link status up -> down -> up after restart Auto-Negotiation of phy 1
stest.expect_equal(mac.link_status_changed_calls, [(1, link_down), (1, link_up)])
