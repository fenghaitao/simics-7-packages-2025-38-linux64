# © 2023 Intel Corporation
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
import stest

class DummyPCIeDevice(pyobj.ConfObject):
    class hot_reset_received(pyobj.SimpleAttribute(False, 'b')):
        '''Have we seen a call to hot_reset?'''

    class pcie_device(pyobj.Interface):
        def hot_reset(self):
            self._up.hot_reset_received.val = True
        def connected(self, port , devid):
            pass
        def disconnected(self, port, devid):
            pass

uut=SIM_create_object('x58-pcie-port', 'uut',[["port_index", 1],["link_width", 1]])
devs = [ SIM_create_object('DummyPCIeDevice',f'dev{i}') for i in range(5) ]
uut.downstream_port.devices = devs

stest.expect_true(all(devs[i].hot_reset_received == False for i in range(len(devs))))
uut.iface.pcie_device.hot_reset()
stest.expect_true(all(devs[i].hot_reset_received == True for i in range(len(devs))))
