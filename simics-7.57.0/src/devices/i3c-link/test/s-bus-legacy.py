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


import simics
import pyobj
import stest

from test_utils import *

class i2c_slave(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()
        self.m_iface = None

    class master(pyobj.SimpleAttribute(None, 'o')):
        def setter(self, val):
            self.val = val
            self._up.m_iface = val.iface.i2c_master_v2

    class i2c_slave_v2(pyobj.Interface):
        def start(self, address):
            if (address >> 1) == self._up.slave_address.val:
                if address & 1:
                    self._up.status.val = 2
                    self._up.pos = 0
                else:
                    self._up.status.val = 1
                self._up.m_iface.acknowledge(I2C_ack)
            else:
                self._up.status.val = 3
                self._up.m_iface.acknowledge(I2C_noack)
        def read(self):
            if self._up.status.val == 2:
                val = int(self._up.data.val[self._up.pos:self._up.pos + 2], 16)
                self._up.pos += 2
                self._up.m_iface.read_response(val)

        def write(self, value):
            if self._up.status.val == 1:
                self._up.data.val += ('%02x' % value)
                self._up.m_iface.acknowledge(I2C_ack)

        def stop(self):
            self._up.status.val = 0

        def addresses(self):
            return None

    class data(pyobj.SimpleAttribute('', 's')): pass
    class status(pyobj.SimpleAttribute(0, 'i')): pass
    class slave_address(pyobj.SimpleAttribute(0x40, 'i')): pass

slave_addresses = [0x42, 0x43]
invalid_slave = 0x44
slaves_number = len(slave_addresses)
clk = simics.pre_conf_object('clk', 'clock')
clk.freq_mhz = 100.0
i3c = simics.pre_conf_object('i3c', 'i3c_master_device')
bus = simics.pre_conf_object('bus', 'i3c_bus')
bus.queue = clk
slaves = [simics.pre_conf_object('slave%d' % i, 'i2c_slave')
          for i in range(slaves_number)]
adapters = [simics.pre_conf_object('adapter%d' % i, 'i2c_to_i3c_adapter')
            for i in range(slaves_number)]
bus.i3c_devices = [None] * 16
i3c.bus = [bus, 'I3C[0]']
bus.i3c_devices[0] = i3c
for i in range(slaves_number):
    slaves[i].slave_address = slave_addresses[i]
    slaves[i].master = adapters[i]
    adapters[i].i2c_link_v2 = slaves[i]
    adapters[i].i3c_link = [bus, 'I3C[%d]' % (i + 1)]
    bus.i3c_devices[i + 1] = adapters[i]
simics.SIM_add_configuration([bus, clk, i3c] + adapters + slaves, None)

slaves = [conf.slave0, conf.slave1]
for dev in slaves + [conf.i3c, conf.bus, conf.adapter0, conf.adapter1]:
    dev.log_level = 1

master = Device(conf.i3c)

def test_noack():
    master.wait('acknowledge', I3C_noack,
                lambda: master.start(invalid_slave << 1))
    for i in range(slaves_number):
        stest.expect_equal(slaves[i].status, 3)
    master.stop()
    for i in range(slaves_number):
        stest.expect_equal(slaves[i].status, 0)

def test_write():
    conf.bus.known_address = []
    data = [0x12, 0x34, 0x56, 0x78]
    string = ''.join(['%02x' % x for x in data])
    for i in range(slaves_number):
        master.wait('acknowledge', I3C_ack,
                    lambda: master.start(slave_addresses[i] << 1))
        for d in data:
            master.wait('acknowledge', I3C_ack, lambda: master.write(d))
        master.stop()
        stest.expect_equal(slaves[i].data, string)

def test_read():
    strings = ['01234567', '89abcdef']
    conf.bus.known_address = []
    for i in range(slaves_number):
        s = strings[i]
        slaves[i].data = s
        pattern = slave_addresses[i] << 1
        master.wait('acknowledge', I3C_ack, lambda: master.start(pattern))
        master.wait('acknowledge', I3C_ack, lambda: master.start(pattern | 1))
        for j in range(len(s) // 2):
            val = int(s[j * 2 : (j + 1) * 2], 16)
            master.wait('read_response', val, lambda: master.read())
        master.stop()

test_noack()
test_write()
test_read()
