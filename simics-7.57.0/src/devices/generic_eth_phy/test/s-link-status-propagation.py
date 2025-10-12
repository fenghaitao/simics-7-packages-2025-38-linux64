# Test that link status is propagated correctly to mac when
# connecting/disconnecting to a link

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


import contextlib
import stest
import dev_util
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

ep = dev_util.Dev([dev_util.iface("ethernet_common")]).obj
ep2 = dev_util.Dev([dev_util.iface("ethernet_common")]).obj

class Mac(dev_util.Iface):
    iface = simics.IEEE_802_3_MAC_V3_INTERFACE
    def link_status_changed(self, obj, addr, status):
        global calls
        calls.append((addr, status))

mac = dev_util.Dev([Mac]).obj

@contextlib.contextmanager
def call_expectation(exp_calls):
    global calls
    assert calls == []
    yield
    stest.expect_equal(calls, exp_calls)
    calls = []

calls = []
# Create with unconnected link
with call_expectation([(3, IEEE_link_unconnected)]):
    SIM_create_object('generic_eth_phy', None, address=3, mac=mac)

# Create with connected link
with call_expectation([(4, IEEE_link_up)]):
    SIM_create_object('generic_eth_phy', None, [['address', 4], ['mac', mac],
                                                ['link', ep]])

# Restore checkpoint
with call_expectation([]):
    VT_set_restoring_state(True)
    SIM_create_object('generic_eth_phy', None, [['address', 5], ['mac', mac],
                                                ['link', ep]])
    VT_set_restoring_state(False)

# Remaining tests are for hotplugging, reuse the same phy for all tests
phy = SIM_create_object('generic_eth_phy', 'phy',
                        [['address', 7], ['mac', mac]])
calls = []
# basic hotplugging
with call_expectation([(7, IEEE_link_up)]):
    phy.link = ep
with call_expectation([(7, IEEE_link_unconnected)]):
    phy.link = None

# Identity write
with call_expectation([]):
    phy.link = None

phy.link = ep
calls = []
# Change between two endpoints or perform identity write
with call_expectation([]):
    phy.link = ep2
    phy.link = ep2
    phy.link = ep

# Reverse execution
with call_expectation([]):
    VT_set_restoring_state(True)
    phy.link = ep
    VT_set_restoring_state(False)
