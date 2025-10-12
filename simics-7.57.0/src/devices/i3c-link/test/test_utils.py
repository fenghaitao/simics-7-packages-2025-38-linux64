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
import comp
import pyobj
import simics
import stest
from connectors import *

class i3c_device(pyobj.ConfObject):
    class bus(pyobj.SimpleAttribute(None, 'o|[os]')): pass

class i3c_slave_device(i3c_device):
    class start(pyobj.SimpleAttribute(0xff, 'i')): pass
    class write(pyobj.SimpleAttribute(0xff, 'i')): pass
    class sdr_write(pyobj.SimpleAttribute([], '[i*]')): pass
    class read(pyobj.SimpleAttribute(0, 'i')): pass
    class daa_read(pyobj.SimpleAttribute(0, 'i')): pass
    class stop(pyobj.SimpleAttribute(0, 'i')): pass
    class ibi_start(pyobj.SimpleAttribute(0, 'i')): pass
    class ibi_acknowledge(pyobj.SimpleAttribute(2, 'i')): pass
    class dcr(pyobj.SimpleAttribute(0, 'i')): pass

    class i3c_slave(pyobj.Interface):
        def start(self, val):
            self._up.start.val = val
        def write(self, val):
            self._up.write.val = val
        def sdr_write(self, buf):
            self._up.sdr_write.val = list(buf)
        def read(self):
            self._up.read.val = 1
        def daa_read(self):
            self._up.daa_read.val = 1
        def stop(self):
            self._up.stop.val = 1
        def ibi_acknowledge(self, ack):
            self._up.ibi_acknowledge.val = ack
        def ibi_start(self):
            self._up.ibi_start.val = 1

class daa_snooper(pyobj.ConfObject):
    class daa_list(pyobj.SimpleAttribute([], '[[ii]*]')): pass
    class i3c_daa_snoop(pyobj.Interface):
        def assigned_address(self, id, bcr, dcr, address):
            data = (id << 16) | (bcr << 8) | dcr
            self._up.daa_list.val.append([data, address])

class i3c_master_device(i3c_device):
    class acknowledge(pyobj.SimpleAttribute(2, 'i')): pass
    class read_response(pyobj.SimpleAttribute(0, 'i')): pass
    class daa_response(pyobj.SimpleAttribute(0, 'i')): pass
    class ibi_request(pyobj.SimpleAttribute(0, 'i')): pass
    class ibi_address(pyobj.SimpleAttribute(0x00, 'i')): pass

    class i3c_master(pyobj.Interface):
        def daa_response(self, uid, bcr, dcr):
            self._up.daa_response.val = (uid << 16) | (bcr << 8) | dcr
        def read_response(self, data, more):
            self._up.read_response.val = data
        def ibi_address(self, addr):
            self._up.ibi_address.val = addr
        def ibi_request(self):
            self._up.ibi_request.val = 1
        def acknowledge(self, ack):
            self._up.acknowledge.val = ack

class secondary_master(i3c_master_device, i3c_slave_device): pass

class i3c_comp(comp.StandardConnectorComponent):
    _class_desc = 'tests a simple I3C component'

    def setup(self):
        if not self.instantiated.val:
            self.add_objects()

    def add_objects(self):
        self.add_pre_obj('dev', self._class_name)
        self.add_connector('i3c', I3CLinkUpConnector('dev', 'bus'))

class i3c_master_comp(i3c_comp):
    _class_name = 'i3c_master_device'

class i3c_slave_comp(i3c_comp):
    _class_name = 'i3c_slave_device'

I3C_ack = 0
I3C_noack = 1
Transition_Low  = 0
Transition_High = 1
Transition_None = 2

I3C_RSV_BYTE = 0x7e
I3C_IBI_BYTE = 0x02

CCC_ENTDAA    = 0x07
CCC_SETMWL_B  = 0x09
CCC_SETMWL_D  = 0x89
CCC_GETMWL_D  = 0x8b
CCC_DISE_D    = 0x81
CCC_GETACCMST = 0x91

class Device:
    def __init__(self, obj):
        self.obj = obj
        if isinstance(obj.bus, list):
            self.bus, self.port = obj.bus
        else:
            self.bus = obj.bus
            self.port = None
        si = simics.SIM_get_port_interface(self.bus, 'i3c_slave', self.port)
        mi = simics.SIM_get_port_interface(self.bus, 'i3c_master', self.port)
        m_funcs = ['acknowledge', 'read_response',
                   'daa_response', 'ibi_request', 'ibi_address']
        s_funcs = ['start', 'ibi_acknowledge', 'write',
                   'sdr_write', 'read', 'daa_read', 'stop', 'ibi_start']
        if mi:
            for n in  m_funcs:
                setattr(self, n, getattr(mi, n))
        if si:
            for n in s_funcs:
                setattr(self, n, getattr(si, n))

    def _check_attr(self, attr, expected):
        if not hasattr(self.obj, attr):
            raise Exception("object %s doesn't have attribute %s"
                             % (self.obj.name, attr))
        if isinstance(expected, list):
            setattr(self.obj, attr, [])
        else:
            setattr(self.obj, attr, ~expected)

    def wait(self, attr, expected, func=None):
        self._check_attr(attr, expected)
        if func:
            func()
        self._wait(attr, expected)

    def _wait(self, attr, expected):
        n = 100000
        while n > 0:
            if getattr(self.obj, attr) == expected:
                return
            simics.SIM_continue(1)
            n -= 1
        raise Exception('timeout: waiting for attribute "%s"' % attr)

def multi_devices_wait(devs, attr, expected, func=None):
    for dev in devs:
        dev._check_attr(attr, expected)
    if func:
        func()
    for dev in devs:
        dev._wait(attr, expected)

def _create_bus_testbench(masters, slaves, snooper, log_level):
    clk = simics.pre_conf_object('clk', 'clock')
    clk.freq_mhz = 25.0
    bus = simics.pre_conf_object('bus', 'i3c_bus')
    bus.queue = clk
    bus.log_level = log_level
    bus.i3c_devices = [None] * 16

    s_devs = [simics.pre_conf_object(n, 'i3c_slave_device') for n in slaves]
    m_devs = [simics.pre_conf_object(n, 'i3c_master_device') for n in masters]
    devs = m_devs + s_devs
    for i in range(len(devs)):
        devs[i].bus = [bus, 'I3C[%d]' % i]
        devs[i].log_level = log_level
        bus.i3c_devices[i] = devs[i]
    names = masters + slaves
    if snooper:
        wire = simics.pre_conf_object('wire', 'i3c_wire')
        snooper_obj = simics.pre_conf_object('snooper', 'daa_snooper')
        wire.i3c_link = [snooper_obj, [bus, 'I3C[%d]' % len(names)]]
        bus.i3c_devices[len(names)] = [wire, 'I3C_PORT[1]']
        devs.extend([wire, snooper_obj])
    simics.SIM_add_configuration([clk, bus] + devs, None)
    return (conf.bus,
            [Device(getattr(conf, names[i])) for i in range(len(names))])

def create_bus_testbench(masters, slaves, log_level=1):
    return _create_bus_testbench(masters, slaves, None, log_level)

def create_bus_testbench_with_snooper(masters, slaves, log_level=1):
    (bus, devs) = _create_bus_testbench(masters, slaves, 'snooper', log_level)
    return (bus, conf.snooper, devs)
