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
import dev_util
from stest import expect_equal

# fake i3c slave device
class foo(pyobj.ConfObject):
    '''i3c slave device'''
    def _initialize(self):
        super()._initialize()
        self.reqs = []

    class bus(pyobj.SimpleAttribute(None, 'n|o')):
        '''i3c bus'''

    class i3c_slave(pyobj.Interface):
        def start(self, addr):
            self._up.reqs.append(['start', addr])

        # slave write() called when it receives daa address
        def write(self, addr):
            self._up.reqs.append(['daa_address', addr])

        def sdr_write(self, data):
            self._up.reqs.append(['write', data])

        def read(self):
            self._up.reqs.append(['read'])

        def daa_read(self):
            self._up.reqs.append(['daa_read'])

        def stop(self):
            self._up.reqs.append(['stop'])

        def ibi_start(self):
            self._up.reqs.append(['ibi_start'])

        def ibi_acknowledge(self, ack):
            self._up.reqs.append(['ibi_acknowledge', ack])

# slave - ep1
# slave2 - ep2
# master - ep3
def setup():
    SIM_run_command('load-module i3c-link')
    SIM_run_command('load-module sample-i3c-devices')
    SIM_set_configuration([
        OBJECT('default_sync_domain', 'sync_domain', min_latency = 0.1),
        OBJECT('cell', 'cell'),
        OBJECT('clk', 'clock', freq_mhz = 0.001, cell = OBJ('cell')),
        OBJECT('link', 'i3c_link_impl', goal_latency = 0.1),
        OBJECT("ep1", "i3c_link_endpoint",
               link = OBJ("link"), device = OBJ("slave"), id = 1),
        OBJECT('slave', 'foo',
               bus = OBJ("ep1"), queue = OBJ("clk")),
        OBJECT("ep2", "i3c_link_endpoint",
               link = OBJ("link"), device = OBJ("slave2"), id = 2),
        OBJECT('slave2', 'foo',
               bus = OBJ("ep2"), queue = OBJ("clk")),
        OBJECT("ep3", "i3c_link_endpoint",
               link = OBJ("link"), device = OBJ("master"), id = 3),
        OBJECT('master', 'sample_i3c_master',
               bus = OBJ("ep3"), queue = OBJ("clk"))])

def expect(a, b):
    assert len(a) == len(b)
    for i in range(len(a)):
        if b[i] != []:
            expect_equal(a[i], [b[i]])
            del a[i][:]
        else:
            expect_equal(a[i], b[i])

def c():
    SIM_run_command('c 101')

setup()
s = conf.slave.object_data.reqs
s2 = conf.slave2.object_data.reqs
s_iface = conf.slave.bus.iface.i3c_master
s2_iface = conf.slave2.bus.iface.i3c_master

conf.ep1.log_level = 4
conf.ep2.log_level = 4
conf.ep3.log_level = 4

# write to master registers
reg_start_addr = dev_util.Register_LE(conf.master.bank.b, 0, 1)
reg_ccc = dev_util.Register_LE(conf.master.bank.b, 1, 1)
reg_slave_addr = dev_util.Register_LE(conf.master.bank.b, 2, 1)
reg_slave_addr_another = dev_util.Register_LE(conf.master.bank.b, 3, 1)
reg_write_value = dev_util.Register_LE(conf.master.bank.b, 6, 2)
reg_assigned_addr = dev_util.Register_LE(conf.master.bank.b, 16, 1)
reg_trigger_start = dev_util.Register_LE(conf.master.bank.b, 17, 1)

def test_read():
    # normal slave address (with R/W = 1)
    s_addr = 0xab
    read_value = 0x1234
    reg_start_addr.write(s_addr)
    reg_trigger_start.write(1)

    c()
    expect([s, s2], [['start', s_addr], ['start', s_addr]])

    s_iface.acknowledge(0)
    s2_iface.acknowledge(1)
    c()
    # ack received, master issues read request to current slave
    c()
    expect([s, s2], [['read'], []])

    s_iface.read_response((read_value & 0xff00) >> 8, True)
    c()
    # master received data with more data afterwards, issues read again
    c()
    expect([s, s2], [['read'], []])

    s_iface.read_response(read_value & 0xff, False)
    c()
    # master received data with no more data afterwards, issues stop
    c()
    expect([s, s2], [['stop'], ['stop']])
    expect_equal(conf.master.b_read_value, 0x1234)
    conf.master.b_read_value = 0

def test_write():
    # normal slave address (with R/W = 0)
    s_addr = 0xba
    write_value = 0x1234
    reg_start_addr.write(s_addr)
    reg_write_value.write(write_value)
    reg_trigger_start.write(1)

    c()
    expect([s, s2], [['start', s_addr], ['start', s_addr]])

    s_iface.acknowledge(0)
    s2_iface.acknowledge(1)
    c()
    # ack received, master issues write request to current slave
    # write operation does not need response. master issue stop.
    c()
    expect_equal(s, [['write', b"%c%c"
                      % ((write_value & 0xff00) >> 8, write_value & 0xff)],
                     ['stop']])
    del s[:]
    expect_equal(s2, [['stop']])
    del s2[:]

def test_broadcast():
    b_addr = 0x7e << 1
    b_ccc = 0x70
    write_value = 0x1234
    reg_start_addr.write(b_addr)
    reg_ccc.write(b_ccc)
    reg_write_value.write(write_value)
    reg_trigger_start.write(1)

    c()
    expect([s, s2], [['start', b_addr], ['start', b_addr]])

    s_iface.acknowledge(0)
    s2_iface.acknowledge(0)
    c()
    # ack received
    # master sends broadcast ccc (0x00 - 0x7f)
    # master issues write operation
    # master issues stop
    c()
    expect_equal(s, [['write', b"%c" % b_ccc],
                     ['write', b"%c%c" % ((write_value & 0xff00) >> 8,
                                          write_value & 0xff)],
                     ['stop']])
    expect_equal(s2, [['write', b"%c" % b_ccc],
                      ['write', b"%c%c" % ((write_value & 0xff00) >> 8,
                                           write_value & 0xff)],
                      ['stop']])
    del s[:]
    del s2[:]

def test_direct_read():
    b_addr = 0x7e << 1
    d_ccc = 0x90
    s_addr = 0xab
    s2_addr = 0xbb
    read_value = 0x1234
    reg_start_addr.write(b_addr)
    reg_ccc.write(d_ccc)
    reg_slave_addr.write(s_addr)
    reg_slave_addr_another.write(s2_addr)
    reg_trigger_start.write(1)

    c()
    expect([s, s2], [['start', b_addr], ['start', b_addr]])

    s_iface.acknowledge(0)
    s2_iface.acknowledge(0)
    c()
    # ack received
    # master sends direct ccc (0x80 - 0xfe)
    # master repeat start with slave address | read
    c()
    expect_equal(s, [['write', b"%c" % d_ccc], ['start', s_addr]])
    expect_equal(s2, [['write', b"%c" % d_ccc], ['start', s_addr]])
    del s[:]
    del s2[:]

    s_iface.acknowledge(0)
    s2_iface.acknowledge(1)
    c()
    # ack received, master issues read request to current slave
    c()
    expect([s, s2], [['read'], []])

    s_iface.read_response((read_value & 0xff00) >> 8, False)
    c()
    # master received data with no more data afterwards, repeat start
    # to read from another slave
    c()
    expect([s, s2], [['start', s2_addr], ['start', s2_addr]])

    s_iface.acknowledge(1)
    s2_iface.acknowledge(0)
    c()
    # ack received, master issues read request to current slave
    c()
    expect([s, s2], [[], ['read']])

    s2_iface.read_response(read_value &0xff, False)
    c()
    # master received data with no more data afterwards, repeat start
    # or issue stop
    c()
    expect([s, s2], [['stop'], ['stop']])
    expect_equal(conf.master.b_read_value, 0x1234)
    conf.master.b_read_value = 0

def test_direct_write():
    b_addr = 0x7e << 1
    d_ccc = 0x90
    s_addr = 0xba
    s2_addr = 0xaa
    write_value = 0x1234
    reg_start_addr.write(b_addr)
    reg_ccc.write(d_ccc)
    reg_slave_addr.write(s_addr)
    reg_slave_addr_another.write(s2_addr)
    reg_write_value.write(write_value)
    reg_trigger_start.write(1)

    c()
    expect([s, s2], [['start', b_addr], ['start', b_addr]])

    s_iface.acknowledge(0)
    s2_iface.acknowledge(0)
    c()
    # ack received
    # master sends direct ccc (0x80 - 0xfe)
    # master repeat start with slave address | write
    c()
    expect_equal(s, [['write', b"%c" % d_ccc], ['start', s_addr]])
    expect_equal(s2, [['write', b"%c" % d_ccc], ['start', s_addr]])
    del s[:]
    del s2[:]

    s_iface.acknowledge(0)
    s2_iface.acknowledge(1)
    c()
    # ack received, master issues write request to current slave
    # write operation does not expect response
    # master issues repeat start to write to another slave
    c()
    expect_equal(s, [['write', b"%c" % ((write_value & 0xff00) >> 8)],
                     ['start', s2_addr]])
    expect([s2], [['start', s2_addr]])
    del s[:]
    del s2[:]

    s_iface.acknowledge(1)
    s2_iface.acknowledge(0)
    c()
    # ack received, master issues write request to current slave
    # write operation does not expect response
    # master issues repeat start to write to another slave, or issues stop
    c()
    expect_equal(s2, [['write', b"%c" % (write_value & 0xff)], ['stop']])
    expect_equal(s, [['stop']])
    del s2[:]
    del s[:]

def test_daa():
    b_addr = 0x7e << 1
    entdaa_ccc = 0x07
    assigned_addr = 0xaa
    id = 0xdeadbeaf
    bcr = 0xff  # Note that bcr[2] is 1
    dcr = 0xee
    id_another = 0x1deadbeef
    reg_start_addr.write(b_addr)
    reg_ccc.write(entdaa_ccc)
    reg_assigned_addr.write(assigned_addr)
    reg_trigger_start.write(1)

    c()
    expect([s, s2], [['start', b_addr], ['start', b_addr]])

    s_iface.acknowledge(0)
    s2_iface.acknowledge(0)
    c()
    # ack received
    # master sends ENTDAA CCC 0x07
    # master repeat start with 0x7e | 1
    c()
    expect_equal(s,  [['write', b"%c" % entdaa_ccc], ['start', 0x7e << 1 | 1]])
    expect_equal(s2, [['write', b"%c" % entdaa_ccc], ['start', 0x7e << 1 | 1]])
    del s[:]
    del s2[:]

    s_iface.acknowledge(0)
    s2_iface.acknowledge(0)
    c()
    # ack received
    # master issues read to request daa data
    c()
    expect([s, s2], [['daa_read'], ['daa_read']])

    s_iface.daa_response(id, bcr, dcr)
    s2_iface.daa_response(id_another, bcr, dcr)
    c()
    # master received the winner daa data, and send daa address
    # the fake address is 0xaa
    c()
    expect([s, s2], [['daa_address', assigned_addr], []])

    s_iface.acknowledge(0)
    s2_iface.acknowledge(1)
    c()
    # ack received
    # master repeat start with 0x7e | 1 to continue the daa process
    c()
    expect([s, s2], [['start', 0x7e << 1 | 1], ['start', 0x7e << 1 | 1]])

    s_iface.acknowledge(1)
    s2_iface.acknowledge(1)
    c()
    # nack received, master issue stop
    c()
    expect([s, s2], [['stop'], ['stop']])

def test_hot_join():
    # hot-join address is 0x04
    s_iface.ibi_request()
    c()

    # master receives ibi request, issues ibi start
    c()
    expect([s, s2], [['ibi_start'], []])

    s_iface.ibi_address(0x04)
    c()

    # master receives ibi hot-join address, issues ack
    c()
    expect([s, s2], [['ibi_acknowledge', 0], []])

    # master enter into daa process
    test_daa()

def test_ibi():
    read_value = 0xef

    # ibi address is slave_addr | 1
    s_iface.ibi_request()
    c()

    # master receives ibi request, issues ibi start
    c()
    expect([s, s2], [['ibi_start'], []])

    s_iface.ibi_address(0x12 << 1 | 1)
    c()

    # master receives ibi address, acks
    # master check its BCR[2] as 1, issues read to request slave data
    c()
    expect_equal(s, [['ibi_acknowledge', 0], ['read']])
    del s[:]
    expect_equal(s2, [])


    s_iface.read_response(read_value, False)
    c()

    # master received slave data, issue stop
    c()
    expect([s, s2], [['stop'], ['stop']])
    expect_equal(conf.master.b_read_value, read_value)
    conf.master.b_read_value = 0

def test_secondary_master():
    # secondary master address is slave_addr | 0
    s_iface.ibi_request()
    c()

    # master receives ibi request, issues ibi start
    c()
    expect([s, s2], [['ibi_start'], []])

    s_iface.ibi_address(0x12 << 1)
    c()

    # master receives ibi secondary mastere address, acks
    c()
    expect([s, s2], [['ibi_acknowledge', 0], []])

    # master enter into direct read process
    test_direct_read()

test_read()
test_write()
test_broadcast()
test_direct_read()
test_direct_write()
test_daa()
test_hot_join()
test_ibi()
test_secondary_master()
print("test s-master passed.")
