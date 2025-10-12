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


import pyobj
import simics
import stest
import dev_util
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

ich_prefix      = 'ich10'

lpc_counter_cnt = 3
lpc_timer_mhz       = 1000. / 838.

class TimerOutSignal(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()

        self.level = 0

    class signal(pyobj.Interface):
        def signal_raise(self):
            self._up.level = 1
        def signal_lower(self):
            self._up.level = 0

    class level(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.level
        def setter(self, val):
            self._up.level = val

class TestBench:
    def __init__(self):

        # Bus clock
        clk = simics.pre_conf_object('lpc_timer_clk', 'clock')
        clk.freq_mhz = lpc_timer_mhz
        simics.SIM_add_configuration([clk], None)
        self.timer_clk = conf.lpc_timer_clk

        # Memory-space
        self.io_space = simics.SIM_create_object('memory-space', 'io_space', [])

        # Initialize memory
        self.memory = dev_util.Memory()

        # Timer
        self.timer = simics.SIM_create_object('%s_timer' % ich_prefix, 'timer',
                                              [['queue', self.timer_clk]])

        # Timer output signals
        self.signal = []
        for i in range(lpc_counter_cnt):
            self.signal.append(
                simics.SIM_create_object('TimerOutSignal', 'sig%d' % i, []))

        self.io_space.map += [[0x040, self.timer, 0, 0, 4],
                              [0x050, self.timer, 0, 0, 4]]
        self.timer.output = self.signal

    # IO space operation methods
    def read_io(self, addr, size):
        return self.io_space.iface.memory_space.read(None, addr, size, 0)

    def write_io(self, addr, bytes):
        self.io_space.iface.memory_space.write(None, addr, bytes, 0)

    def read_io_le(self, addr, bits):
        return dev_util.tuple_to_value_le(self.read_io(addr, bits // 8))

    def write_io_le(self, addr, bits, value):
        self.write_io(addr, dev_util.value_to_tuple_le(value, bits // 8))

tb = TestBench()

def expect_string(actual, expected, info):
    if actual != expected:
        raise Exception(
            "%s: got '%s', expected '%s'" % (info, actual, expected))

def expect_hex(actual, expected, info):
    if actual != expected:
        raise Exception(
            "%s: got '0x%x', expected '0x%x'" % (info, actual, expected))

def expect_list(actual, expected, info):
    if actual != expected:
        raise Exception(
            "%s: got '%r', expected '%r'" % (info, actual, expected))

def expect(actual, expected, info):
    if actual != expected:
        raise Exception(
            "%s: got '%d', expected '%d'" % (info, actual, expected))
