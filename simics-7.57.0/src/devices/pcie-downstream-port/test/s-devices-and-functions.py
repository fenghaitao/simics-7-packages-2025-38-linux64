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
import random
random.seed("Montgomery")


class dummy_device(pyobj.ConfObject):
    class connected_calls(pyobj.SimpleAttribute(list, '[[oi]*]')):
        pass

    class disconnected_calls(pyobj.SimpleAttribute(list, '[[oi]*]')):
        pass

    class hot_reset_calls(pyobj.SimpleAttribute(0, 'i')):
        pass

    class transaction(pyobj.Interface):
        def operation(self, *args):
            stest.fail("transaction not expected to be called")

    class foo(pyobj.PortObject):
        class transaction(pyobj.Interface):
            def operation(self, *args):
                stest.fail("transaction not expected to be called")

    class pcie_device(pyobj.Interface):
        def hot_reset(self):
            self._top.hot_reset_calls.val += 1

        def connected(self, dp, did):
            self._top.connected_calls.val.append([dp, did])

        def disconnected(self, dp, did):
            self._top.disconnected_calls.val.append([dp, did])


dp = simics.pre_conf_object('dp', 'pcie-downstream-port')
ep = simics.pre_conf_object('ep', 'dummy_device')
did = random.randrange(1, 256)
dp.devices = [[did, ep]]
simics.SIM_add_configuration([dp, ep], None)

dp = simics.SIM_get_object(dp.name)
ep = simics.SIM_get_object(ep.name)

# devices are connected as part of instantiation
stest.expect_equal(ep.connected_calls, [[dp, did]])
stest.expect_equal(ep.disconnected_calls, [])

# devices are disconnected when removed after instantiation
dp.devices = []
stest.expect_equal(ep.connected_calls, [[dp, did]])
stest.expect_equal(ep.disconnected_calls, [[dp, did]])

# devices are connected when added after instantiation
dp.devices = [[did, ep]]
stest.expect_equal(ep.connected_calls, [[dp, did], [dp, did]])
stest.expect_equal(ep.disconnected_calls, [[dp, did]])

ep.connected_calls = []
ep.disconnected_calls = []
cp = stest.scratch_file('checkpoint.cp')
simics.SIM_write_configuration_to_file(cp, 0)

# devices -are- connected as part of loading a checkpoint
simics.SIM_delete_objects([dp, ep])
simics.SIM_read_configuration(cp)
ep = simics.SIM_get_object('ep')
dp = simics.SIM_get_object('dp')
stest.expect_equal(dp.devices, [[did, ep]])
stest.expect_equal(ep.connected_calls, [[dp, did]])
stest.expect_equal(ep.disconnected_calls, [])

# Bad values for 'devices' are not accepted
ep2 = simics.SIM_create_object('dummy_device', 'another_ep', [])
bad_values = ([[0x10000, ep]],        # too big device id
              [[32, 0, ep]],          # too big device id
              [[0, 9, ep]],           # too big function id
              [[0, ep], [1, ep]],     # duplicate object
              [[42, ep], [42, ep2]],  # duplicate device id
              )
for bv in bad_values:
    with stest.expect_exception_mgr(simics.SimExc_IllegalValue):
        before = dp.devices
        dp.devices = bv
        stest.expect_equal(dp.devices, before)

# devices are hot_reset
dp.iface.pcie_port_control.hot_reset()
stest.expect_equal(ep.hot_reset_calls, 1)

# functions are also hot_reset, if they implement pcie_device
dp.iface.pcie_map.add_function(ep2, 123)
dp.iface.pcie_map.add_function(ep2.port.foo, 231)
dp.iface.pcie_port_control.hot_reset()
stest.expect_equal(ep.hot_reset_calls, 2)
stest.expect_equal(ep2.hot_reset_calls, 1)


def check_maps(dp, eps):
    # Config-space is mapped at 23:16
    cfg = [[did << 16, obj, 0, 0, 1 << 16, None, 0, 0, 0]
           for (obj, did) in eps]
    # Message-space is mapped at 53:48
    msg = [[did << 48, obj, 0, 0, 1 << 48, None, 0, 0, 0]
           for (obj, did) in eps]
    stest.expect_equal(sorted(dp.cfg_space.map), cfg)
    stest.expect_equal(sorted(dp.msg_space.map), msg)


# functions are mapped
check_maps(dp, [(ep2, 123), (ep2.port.foo, 231)])

# but not if disabled
dp.iface.pcie_map.disable_function(231)
check_maps(dp, [(ep2, 123)])

# but they can get their device_id
for (obj, did) in [(ep2, 123), (ep2.port.foo, 231)]:
    stest.expect_equal(dp.iface.pcie_map.get_device_id(obj), did)

# and can be enabled
dp.iface.pcie_map.enable_function(231)
check_maps(dp, [(ep2, 123), (ep2.port.foo, 231)])

# and removed
dp.iface.pcie_map.del_function(ep2, 123)
check_maps(dp, [(ep2.port.foo, 231)])

# functions can be disabled preventively
dp.iface.pcie_map.disable_function(123)
dp.iface.pcie_map.add_function(ep2, 123)
check_maps(dp, [(ep2.port.foo, 231)])

# and enabled preventively too
dp.iface.pcie_map.del_function(ep2, 123)
dp.iface.pcie_map.enable_function(123)

# so when it's added again it's not disabled any more
dp.iface.pcie_map.add_function(ep2, 123)
check_maps(dp, [(ep2, 123), (ep2.port.foo, 231)])

# bad object causes error log
with stest.expect_log_mgr(dp, regex="map target"):
    dp.iface.pcie_map.add_function(ep2.port, 456)

# duplicate id causes error log
dp.iface.pcie_map.del_function(ep2.port.foo, 231)
with stest.expect_log_mgr(dp, regex="duplicate"):
    dp.iface.pcie_map.add_function(ep2.port.foo, 123)
