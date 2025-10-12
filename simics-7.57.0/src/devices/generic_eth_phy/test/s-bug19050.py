# Test that link status is propagated correctly to mac when
# connecting/disconnecting to a cable (bug 19050)

# © 2013 Intel Corporation
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
from configuration import OBJECT, OBJ

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

simics.SIM_set_configuration([
        OBJECT('default_sync_domain', 'sync_domain', min_latency = 0.000001),
        OBJECT("cell", "cell"),
        OBJECT("clk", "clock", freq_mhz=10, cell=OBJ("cell")),
        OBJECT("cable", "eth-cable-link", goal_latency = 0.00001),
        OBJECT("ep1", "eth-cable-link-endpoint", link = OBJ("cable"),
               device = OBJ("phy1"), id = 1),
        OBJECT("ep2", "eth-cable-link-endpoint", link = OBJ("cable"),
               device = OBJ("phy2"), id = 2),
        OBJECT("mac1", "Mac"),
        OBJECT("phy1", "generic_eth_phy", queue=OBJ("clk"),
               address = 1, mac = OBJ("mac1"), link = OBJ("ep1")),
        OBJECT("mac2", "Mac"),
        OBJECT("phy2", "generic_eth_phy", queue=OBJ("clk"),
               address = 2, mac = OBJ("mac2"), link = OBJ("ep2")),
    ])

mac1 = SIM_object_data(conf.mac1)
mac2 = SIM_object_data(conf.mac2)
phy1 = conf.phy1
phy2 = conf.phy2

conf.mac1.log_level = 2
conf.mac2.log_level = 2
phy1.log_level = 2
phy2.log_level = 2

# helper routines
def get_mac_link_status_changed_calls(mac):
    return mac.link_status_changed_calls

def clear_mac_link_status_changed_calls(mac):
    mac.link_status_changed_calls = []

def check_mac_link_status_changed_calls(mac, expect):
    stest.expect_equal(get_mac_link_status_changed_calls(mac), expect)

def get_phy_link_status_bit(phy):
    return (phy.mii_regs_status >> 2) & 1

def clear_phy_link_status_bit(phy):
    phy.mii_regs_status &= ~2

def check_phy_link_status_bit(phy, expect):
    stest.expect_equal(get_phy_link_status_bit(phy), expect)

# make sure things are clear before connection established
check_phy_link_status_bit(phy1, 0)
check_phy_link_status_bit(phy2, 0)
check_mac_link_status_changed_calls(mac1, [])
check_mac_link_status_changed_calls(mac2, [])

## wait until hand-shaking process complete and connection setup
timeout = 1000
while (timeout > 0):
    timeout -= 1
    if get_phy_link_status_bit(phy1):
        break
    simics.SIM_continue(1)
else:
    stest.fail('timeout: connection not setup')

# check connection status
check_phy_link_status_bit(phy1, 1)
check_phy_link_status_bit(phy2, 1)
check_mac_link_status_changed_calls(mac1, [(1, IEEE_link_up)])
check_mac_link_status_changed_calls(mac2, [(2, IEEE_link_up)])

clear_mac_link_status_changed_calls(mac1)
clear_mac_link_status_changed_calls(mac2)

# idling some cycles
simics.SIM_continue(100)

# disconnect phy1 from the cable
phy1.link = None
SIM_delete_objects([conf.ep1])

# phy1/mac1 link status updated immediately
check_phy_link_status_bit(phy1, 0)
check_mac_link_status_changed_calls(mac1, [(1, IEEE_link_unconnected)])

## wait until phy2/mac2 link status being updated
timeout = 1000
while (timeout > 0):
    timeout -= 1
    if get_phy_link_status_bit(phy2) == 0:
        break
    simics.SIM_continue(1)
else:
    stest.fail('timeout: connection not setup')

check_phy_link_status_bit(phy2, 0)
check_mac_link_status_changed_calls(mac2, [(2, IEEE_link_unconnected)])
