# Test MII registers

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


import stest
import dev_util
from configuration import *
from common import control_bf, MiiRegister

classname = "generic_eth_phy"

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

ep = dev_util.Dev([dev_util.iface("ethernet_common")])
dummy_mac = dev_util.Dev([Ieee_802_3_mac_v3])

def soft_reset(obj):
    MiiRegister(obj, 0, control_bf).write(reset = 1)

def create_phy(extra_attrs = []):
    return SIM_create_object(classname, None,
                             extra_attrs + [['mac', dummy_mac.obj]])

# Test that control/status registers are set to checkpointed values if
# any, otherwise to configurable default values. Test also that a
# reset restores the configurable default value.
def test_configurable_defaults(classname, addr,
                               init_value, reset_value, mask,
                               extra_attrs):
    zeros = {1: 4}.get(addr, 0)
    obj = create_phy(extra_attrs)
    reg = MiiRegister(obj, addr)
    stest.expect_equal(reg.read() & mask, init_value & mask & ~zeros)
    # make sure it's not already at the reset value
    # avoid to trriger restart auto-negotiation before auto-negotiation enabled
    if addr == 0:
        obj.registers[addr] = 0xfdff & ~reset_value
    else:
        obj.registers[addr] = 0xffff & ~reset_value
    soft_reset(obj)
    stest.expect_equal(reg.read() & mask, reset_value & mask & ~zeros)

for (attr, addr,
     default_reset, mask) in [("control", 0, 0, 0xffff),
                              ("status", 1, 0xff08, 0xffdf),
                              (("phy_id", 2, 0), 2, 0, 0xffff),
                              ("an_advertisement", 4, 0x03e1, 0xbfff),
                              ("an_link_partner_base_page_ability",
                               5, 0, 0xffff),
                              ("an_expansion", 6, 0, 0x7f),
                              ("an_next_page_transmit", 7, 0, 0xffff),
                              ("an_link_partner_received_next_page",
                               8, 0, 0xffff),
                              ("ms_control", 9, 0, 0x3c00),
                              ("ms_status", 10, 0, 0xf0ff),
                              ("pse_control", 11, 0, 0xffff),
                              ("pse_status", 12, 0, 0xffff),
                              ("mmd_access_control", 13, 0, 0xffff),
                              ("mmd_access_addr_data", 14, 0, 0xffff),
                              ("ext_status", 15, 0xf000, 0xffff)] + [
                              (("vendor_specific", 16, i),
                               i + 16, 0, 0xffff)
                              for i in [0, 15]]:
    test_configurable_defaults(classname, addr,
                               default_reset, default_reset, mask, [])
    for value in [0x3333, 0xcccc]:
        if isinstance(attr, str):
            attribute_init = ["mii_regs_" + attr, value]
        else:
            name, length, index = attr
            attribute_init = ["mii_regs_" + name, [value if i == index else 0
                                                   for i in range(length)]]
        test_configurable_defaults(classname, addr, value, default_reset, mask,
                                   [attribute_init])
        test_configurable_defaults(classname, addr, value, value, mask,
                                   [["register_defaults",
                                     [value if i == addr else None
                                      for i in range(32)]]])
        test_configurable_defaults(
            classname, addr, value, (value + 1), mask,
            [attribute_init,
             ["register_defaults", [value + 1 if i == addr
                                    else None
                                    for i in range(32)]]])
        test_configurable_defaults(classname, addr, value, default_reset, mask,
                                   [["registers", [value if i == addr else 0
                                                   for i in range(32)]]])

# Test reset values of indexed registers
phy = create_phy()
stest.expect_equal(phy.registers[2:4], [0, 0])
stest.expect_equal(phy.registers[16:32], [0] * 16)

# test the phy_id attribute
phy = create_phy([["phy_id", 0x12345678]])
stest.expect_equal(phy.register_defaults[2:4], [0x1234, 0x5678])
stest.expect_equal(phy.registers[2:4], [0x1234, 0x5678])
with stest.expect_log_mgr(log_type = "error"):
    create_phy([["phy_id", 0], ["register_defaults", [0] * 32]])

# react to autonegotiation enable
phy = create_phy()
control = MiiRegister(phy, 0, control_bf)
status = MiiRegister(phy, 1, dev_util.Bitfield_LE({"an_complete": 5,
                                                   "an_ability": 3,
                                                   "link_status": 2}))
stest.expect_equal(status.an_ability, 1)
stest.expect_equal(status.an_complete, 0)
control.an_enable = 1
stest.expect_equal(status.an_complete, 1)

# invalid accesses
phy = create_phy()
for access in [lambda x: x.read(), lambda x: x.write()]:
    # out-of-range
    with stest.expect_log_mgr(log_type = "spec-viol"):
        access(MiiRegister(phy, 32))
