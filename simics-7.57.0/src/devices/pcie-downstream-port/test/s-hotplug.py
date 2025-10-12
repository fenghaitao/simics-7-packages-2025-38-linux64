# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import pyobj
import simics
import stest
import pcie_downstream_port_common as common

PD_NOT_PRESENT = 0
PD_PRESENT = 1

class dummy_up(pyobj.ConfObject):
    class hotplug_pc_state(pyobj.SimpleAttribute(None, 'i|n')): pass
    class hotplug_pc_count(pyobj.SimpleAttribute(0, 'i')): pass

    class pcie_map(pyobj.Interface):
        def add_map(self, map_obj, nfo, pcie_type):
            pass
        def del_map(self, map_obj, base, pcie_type):
            pass
        def add_function(self, map_obj, bdf):
            pass
        def del_function(self, map_obj, bdf):
            pass
        def enable_function(self, bdf):
            pass
        def disable_function(self, bdf):
            pass
        def get_device_id(self, dev):
            return 0
    class transaction(pyobj.Interface):
        def issue(self, t, addr):
            stest.fail("transaction not expected to be called")
    class pcie_hotplug_events(pyobj.Interface):
        def presence_change(self, state):
            print("Presence changed", state)
            self._top.hotplug_pc_state.val = state
            self._top.hotplug_pc_count.val += 1
        def power_fault(self, obj):
            stest.fail("unexpected call")
        def attention_button_pressed(self):
            stest.fail("unexpected call")
        def mrl_sensor(self, state):
            stest.fail("unexpected call")
        def data_link_layer(self, is_active):
            stest.fail("unexpected call")

class dummy_ep(pyobj.ConfObject):
    class ut(pyobj.SimpleAttribute(None, 'o|n')): pass

    class transaction(pyobj.Interface):
        def issue(self, *args):
            stest.fail("transaction not expected to be called")


    class pcie_device(pyobj.Interface):
        def hot_reset(self):
            pass

        def connected(self, ut, devid):
            self._top.ut.setter(ut)
            ut.iface.pcie_map.add_function(self._top.obj, devid)

        def disconnected(self, ut, devid):
            ut.iface.pcie_map.del_function(self._top.obj, devid)
            self._top.ut.setter(None)


# Shall support cold-plugged state and not only hot-plugging
# Test instantiation state no device connected
up = simics.pre_conf_object('up', 'dummy_up')
dp = simics.pre_conf_object('dp', 'pcie-downstream-port')
ep = simics.pre_conf_object('ep', 'dummy_ep')

dp.upstream_target = up
simics.SIM_add_configuration([dp, up, ep], None)

up = simics.SIM_get_object(up.name)
dp = simics.SIM_get_object(dp.name)
ep = simics.SIM_get_object(ep.name)
stest.expect_equal(up.hotplug_pc_state, None)
dp.devices = [[0, ep]]
stest.expect_equal(up.hotplug_pc_state, PD_PRESENT)
simics.SIM_delete_objects([up, dp, ep])

# Test instantiation state one device connected
up = simics.pre_conf_object('up', 'dummy_up')
dp = simics.pre_conf_object('dp', 'pcie-downstream-port')
ep = simics.pre_conf_object('ep', 'dummy_ep')

dp.upstream_target = up
dp.devices = [[0, ep]]
simics.SIM_add_configuration([dp, up, ep], None)

up = simics.SIM_get_object(up.name)
dp = simics.SIM_get_object(dp.name)
ep = simics.SIM_get_object(ep.name)
stest.expect_equal(up.hotplug_pc_state, PD_PRESENT)
simics.SIM_delete_objects([up, dp, ep])

# Test instantiation state one legacy device connected
up = simics.pre_conf_object('up', 'dummy_up')
dp = simics.pre_conf_object('dp', 'pcie-downstream-port-legacy')
ep = simics.pre_conf_object('ep', 'dummy_ep')
leg_ep = simics.pre_conf_object('leg_ep', 'fake_legacy_ep')

dp.pci_devices = [[0, 0, leg_ep]]
dp.upstream_target = up
simics.SIM_add_configuration([dp, ep, up, leg_ep], None)
up = simics.SIM_get_object(up.name)
dp = simics.SIM_get_object(dp.name)
ep = simics.SIM_get_object(ep.name)
leg_ep = simics.SIM_get_object(leg_ep.name)

stest.expect_equal(up.hotplug_pc_state, PD_PRESENT)

# Test hot plug during run time
up.hotplug_pc_state = None
dp.devices = [[1 << 3, ep]]
stest.expect_equal(up.hotplug_pc_state, PD_PRESENT)
up.hotplug_pc_state = None
dp.pci_devices = []
stest.expect_equal(up.hotplug_pc_state, PD_PRESENT)
dp.devices = []
stest.expect_equal(up.hotplug_pc_state, PD_NOT_PRESENT)
simics.SIM_delete_objects([up, dp, ep, leg_ep])


# Test instantiation state one legacy device and one new ep connected
up = simics.pre_conf_object('up', 'dummy_up')
dp = simics.pre_conf_object('dp', 'pcie-downstream-port-legacy')
ep = simics.pre_conf_object('ep', 'dummy_ep')
leg_ep = simics.pre_conf_object('leg_ep', 'fake_legacy_ep')
dp.pci_devices = [[0, 0, leg_ep]]
dp.devices = [[1, 0, ep]]
dp.upstream_target = up
simics.SIM_add_configuration([dp, ep, up, leg_ep], None)

up = simics.SIM_get_object(up.name)
dp = simics.SIM_get_object(dp.name)
ep = simics.SIM_get_object(ep.name)
leg_ep = simics.SIM_get_object(leg_ep.name)
stest.expect_equal(up.hotplug_pc_state, PD_PRESENT)
stest.expect_equal(up.hotplug_pc_count, 1)
