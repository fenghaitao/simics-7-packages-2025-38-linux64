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


from pcie_downstream_port_common import check
import cli
import simics
import stest
import random
random.seed("Atlantis")


class dummy:
    cls = simics.confclass('dummy')
    cls.attr.addr('i|n', default=None)
    cls.attr.value('i|n', default=None)

    @cls.iface.pcie_device.hot_reset
    def hot_reset(self):
        pass

    @cls.iface.pcie_device.connected
    def connected(self, ut, devid):
        ut.iface.pcie_map.add_function(self.obj, devid)

    @cls.iface.pcie_device.disconnected
    def disconnected(self, ut, devid):
        ut.iface.pcie_map.del_function(self.obj, devid)

    @cls.iface.transaction.issue
    def issue(self, t, addr):
        self.addr = addr
        if simics.SIM_transaction_is_read(t):
            t.value_le = self.value
        else:
            self.value = t.value_le
        return simics.Sim_PE_No_Exception


def bdf_to_addr(bdf, kind):
    if kind == simics.PCIE_Type_Cfg:
        return bdf << 16
    elif kind == simics.PCIE_Type_Msg:
        return bdf << 48
    else:
        return addr


dp0, dp1 = [simics.SIM_create_object('pcie-downstream-port', f'dp{i}', [])
            for i in (0, 1)]
devs = [simics.SIM_create_object('dummy', f'dev{i}', [])
        for i in range(8)]

dp1.transparent_enabled = True
dp1.devices = [[random.randrange(256), d] for d in devs]
dp0.devices = [dp1.port.downstream]

ppci = dp1.iface.pcie_port_control
mt = simics.SIM_new_map_target(dp0.port.downstream, None, None)
for (df, dev) in dp1.devices:
    bus = random.randrange(1, 256)
    ppci.set_secondary_bus_number(bus)
    bdf = (bus << 8) | df
    for kind in (simics.PCIE_Type_Cfg, simics.PCIE_Type_Msg):
        offset = random.randrange(1 << 16)
        addr = bdf_to_addr(bdf, kind) + offset
        value = random.randrange(1 << 32)
        t = simics.transaction_t(write=True, size=4, value_le=value)
        t.pcie_msg_route = simics.PCIE_Msg_Route_ID
        t.pcie_type = kind
        exc = simics.SIM_issue_transaction(mt, t, addr)
        if kind == simics.PCIE_Type_Msg:
            cli.run_command(f'{dp0.name}.msg_space.map')
            cli.run_command(f'{dp1.name}.msg_space.map')
            cli.run_command(f'probe-address obj={dp0.name}.msg_space {addr}')
        stest.expect_equal(exc, simics.Sim_PE_No_Exception)
        check(dev, addr=offset, value=value)
