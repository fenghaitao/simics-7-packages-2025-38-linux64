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


import conf
import dev_util
import pyobj
import simics
import stest

class i3c_master_device(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()

    class i3c_master(pyobj.Interface):
        def ibi_request(self):
            self._up.ibi_request.val = 1

        def ibi_address(self, addr):
            self._up.ibi_address.val = addr

        def acknowledge(self, ack):
            self._up.acknowledge.val = ack

        def read_response(self, data, more):
            self._up.read_response.val = data

        def daa_response(self, id, bcr, dcr):
            self._up.daa_response.val = (id << 16) | (bcr << 8) | dcr

    class ibi_request(pyobj.SimpleAttribute(0xff, 'i')): pass
    class ibi_address(pyobj.SimpleAttribute(0xff, 'i')): pass
    class acknowledge(pyobj.SimpleAttribute(2, 'i')): pass
    class stop(pyobj.SimpleAttribute(2, 'i')): pass
    class read_response(pyobj.SimpleAttribute(2, 'i')): pass
    class daa_response(pyobj.SimpleAttribute(2, 'i')): pass

I3C_ack = 0
I3C_noack = 1

I3C_RSV_BYTE = 0x7e
I3C_IBI_BYTE = 0x02

CCC_ENTDAA    = 0x07
CCC_SETMWL_B  = 0x09
CCC_SETMWL_D  = 0x89
CCC_GETMWL_D  = 0x8b
CCC_DISE_D    = 0x81
CCC_GETACCMST = 0x91

class Testbench:
    def __init__(self):
        clk = simics.pre_conf_object('clk', 'clock')
        master = simics.pre_conf_object('master', 'i3c_master_device')
        slave = simics.pre_conf_object('slave', 'sample-i3c-target')
        clk.attr.freq_mhz = 25.0
        slave.attr.queue = clk
        slave.attr.bus = master
        slave.attr.log_level = 4
        simics.SIM_add_configuration([clk, master, slave], None)
        self.master = conf.master
        self.slave = conf.slave

    def reset(self):
        self.slave.attr.static_address = 0xff
        self.slave.attr.dynamic_address = 0xff
        self.slave.attr.i3c_status = 0
        self.slave.attr.command = 0xff
        self.slave.attr.ibi = 0xff

    def issue(self, name, *args):
        getattr(conf.slave.iface.i3c_slave, name)(*args)

    def action_then_wait(self, action, result):
        if result:
            name, expected = result
            if not hasattr(self.master.attr, name):
                raise Exception('invalid attribute name')
            setattr(self.master.attr, name, 2)
        if action:
            self.issue(*action)
        if not result:
            return
        n = 0
        while n < 10000:
            if getattr(self.master.attr, name) == expected:
                return
            simics.SIM_continue(1)
            n += 1
        raise Exception('timeout when action_then_waiting for ' + name)


def test_i2c_transaction(tb):
    addr = 0x60
    data = [i * 2 for i in range(8)]
    wb = addr << 1
    rb = wb | 1
    tb.reset()
    tb.slave.attr.static_address = addr
    tb.action_then_wait(('start', 0xa0), ('acknowledge', I3C_noack))
    tb.action_then_wait(('start', wb), ('acknowledge', I3C_ack))
    for d in data:
        tb.action_then_wait(('write', d), ('acknowledge', I3C_ack))
    tb.action_then_wait(('start', rb), ('acknowledge', I3C_ack))
    for i in range(len(data)):
        tb.action_then_wait(('read',), ('read_response', data[i]))
    tb.issue('stop')
    simics.SIM_continue(10)

def test_i3c_transaction(b):
    addr = 0x60
    data = [i * 2 for i in range(8)]
    wb = addr << 1
    rb = wb | 1
    tb.reset()
    tb.slave.attr.dynamic_address = addr
    tb.action_then_wait(('start', wb), ('acknowledge', I3C_ack))
    tb.issue('sdr_write', bytes(data))
    tb.action_then_wait(('start', rb), ('acknowledge', I3C_ack))
    for i in range(len(data)):
        tb.action_then_wait(('read',), ('read_response', data[i]))
    tb.issue('stop')
    simics.SIM_continue(10)

def test_daa(tb):
    tb.reset()
    rsv_byte = 0x7e
    wb = rsv_byte << 1
    addr = 0x30
    rb = wb | 1
    tb.slave.provisional_id = 0x123456
    tb.action_then_wait(('start', wb), ('acknowledge', I3C_ack))
    tb.issue('sdr_write', bytes((CCC_ENTDAA,)))
    tb.action_then_wait(('start', rb), ('acknowledge', I3C_ack))
    tb.issue('daa_read')
    simics.SIM_continue(1)
    stest.expect_equal(tb.master.daa_response >> 16, tb.slave.provisional_id)
    tb.action_then_wait(('write', addr << 1), ('acknowledge', I3C_ack))
    tb.action_then_wait(('start', rb), ('acknowledge', I3C_noack))
    tb.issue('stop')
    simics.SIM_continue(1)

def test_ibi(tb):
    tb.reset()
    addr = 0x60
    ibi = (addr << 1) | 1
    tb.slave.attr.dynamic_address = 0x60
    tb.slave.attr.ibi = ibi
    stest.expect_equal(tb.master.ibi_request, 1)
    tb.issue('ibi_start')
    stest.expect_equal(tb.master.ibi_address, ibi)
    tb.issue('ibi_acknowledge', I3C_ack)
    for i in range(8):
        tb.slave.attr.read_value = 0x45 + i
        tb.action_then_wait(('read',), ('read_response', 0x45 + i))
    tb.issue('stop')

tb = Testbench()
test_i2c_transaction(tb)
test_i3c_transaction(tb)
test_daa(tb)
test_ibi(tb)
