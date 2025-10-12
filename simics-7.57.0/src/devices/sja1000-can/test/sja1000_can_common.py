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
import dev_util
import conf
import stest
import simics

class irq_target(pyobj.ConfObject):
    ''' This is a faked irq target'''
    _class_desc = 'fake irq target'
    def _initialize(self):
        super()._initialize()
        self.raised.val = False
        self.irq_cnt.val = 0
    class signal(pyobj.Interface):
        def signal_raise(self):
            self._up.raised.val = True
            self._up.irq_cnt.val += 1
        def signal_lower(self):
            self._up.raised.val = False
            self._up.irq_cnt.val -= 1
    class raised(pyobj.SimpleAttribute(None, 'b')):
        '''signal is raised'''
    class irq_cnt(pyobj.SimpleAttribute(None, 'i')):
        '''irq counter'''


class TestBench:
    def __init__(self, device_num, bus_latency = 0.0, bus_clock = 10):

        # Bus clock
        clk = simics.pre_conf_object('bus_clk', 'clock')
        clk.freq_mhz = bus_clock
        simics.SIM_add_configuration([clk], None)
        self.bus_clk = conf.bus_clk

        # CAN link
        self.link_impl = simics.pre_conf_object('bus_link', 'can_link_impl')
        self.link_impl.goal_latency = bus_latency
        self.devices   = [None] * device_num
        self.irqs = [None] * device_num
        self.mems = [None] * device_num
        self.endpoints = [None] * device_num
        self.next_ep_id = 10
        for i in range(device_num):
            self.devices[i] = simics.pre_conf_object('dev%d' % i, 'sja1000_can')
            self.irqs[i] = simics.pre_conf_object('irq%d' % i, 'irq_target')
            self.mems[i] = simics.pre_conf_object('mems%d' % i, "memory-space")
            self.mems[i].map = [[0x0, [self.devices[i], 'regs'], 0, 0, 128]]
            self.devices[i].irq_target = self.irqs[i]
            self.endpoints[i] = simics.pre_conf_object('ep%d'%i, 'can_endpoint')
            self.devices[i].can_link = self.endpoints[i]
            self.devices[i].queue = self.bus_clk
            self.endpoints[i].link = self.link_impl
            self.endpoints[i].device = self.devices[i]
            self.endpoints[i].id = self.next_ep_id
            self.next_ep_id = self.next_ep_id + 1
        simics.SIM_add_configuration([self.link_impl]
                                     + self.devices
                                     + self.irqs
                                     + self.mems
                                     + self.endpoints,
                                     None)
        self.ep_array = [None] * device_num
        self.dev_array = [None] * device_num

        for i in range(device_num):
            self.ep_array[i] = simics.SIM_get_object('ep%d' % i)
            self.dev_array[i] = simics.SIM_get_object('dev%d' % i)

    def distribute_message(self, sender_num, message):
        self.ep_array[sender_num].iface.can_link.send(message)
