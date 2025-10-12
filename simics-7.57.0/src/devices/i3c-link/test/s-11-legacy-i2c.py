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


import pyobj
from simics import SIM_run_command, SIM_set_configuration
from configuration import OBJECT, OBJ
from i3c_dev import bar
from stest import expect_equal

class slave_i2c(pyobj.ConfObject):
    '''Fake I2c slave v2 device class'''
    def _initialize(self, addr = []):
        super()._initialize()
        self.reqs = []
        self.addr = addr

    class i2c_slave_v2(pyobj.Interface):
        def finalize(self):
            if self._up.link:
                SIM_require_object(self._up.link)

        def start(self, addr):
            self._up.reqs.append(['start', addr])

        def read(self):
            self._up.reqs.append(['read',])

        def write(self, val):
            self._up.reqs.append(['write', val])

        def stop(self):
            self._up.reqs.append(['stop'])

        def addresses(self):
            self._up.reqs.append(['addresses'])
            return self._up.addr

    class link(pyobj.SimpleAttribute(None, 'n|o')):
        '''i2c link'''

# setup basic configuration
def setup():
    SIM_run_command('load-module i3c-link')
    SIM_set_configuration([
        OBJECT('default_sync_domain', 'sync_domain', min_latency = 0.1),
        OBJECT('cell', 'cell'),
        OBJECT('clk', 'clock', freq_mhz = 0.001, cell = OBJ('cell')),
        OBJECT('link', 'i3c_link_impl', goal_latency = 0.1),
        OBJECT("ep1", "i3c_link_endpoint",
               link = OBJ("link"), device = OBJ("slave_adapter"), id = 1),
        OBJECT('slave_adapter', 'i2c_to_i3c_adapter',
               queue = OBJ("clk"), i3c_link = OBJ('ep1'), i2c_link_v2 = OBJ('slave')),
        OBJECT('slave', 'slave_i2c', link = OBJ('slave_adapter')),
        OBJECT("ep2", "i3c_link_endpoint",
               link = OBJ("link"), device = OBJ("master"), id = 2),
        OBJECT('master', 'bar', queue = OBJ("clk"), bus = OBJ('ep2'))])

def c():
    SIM_run_command('c 101')

def expect(ls, el):
    expect_equal(ls, el)
    del ls[:]

ACK = 0
NACK = 1

setup()
m_ep = conf.master.bus.iface.i3c_slave
s_ep = conf.slave.link.i3c_link.iface.i3c_master
s = conf.slave.object_data.reqs
m = conf.master.object_data.reqs

# master: start
m_ep.start(0xab)
c()
expect(s, [['start', 0xab]])

# slave: acknowledge
s_ep.acknowledge(ACK)
c()
expect(m, [['ack', 0]])

# master: write (by send with transition bit is 2)
m_ep.write(0xcd)
c()
expect(s, [['write', 0xcd]])

# slave: acknowledge
s_ep.acknowledge(ACK)
c()
expect(m, [['ack', 0]])

# master: stop
m_ep.stop()
c()
expect(s, [['stop']])
