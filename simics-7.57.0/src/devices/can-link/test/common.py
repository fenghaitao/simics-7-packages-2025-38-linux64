# © 2011 Intel Corporation
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
import dev_util
import conf
import stest
from device import *
# we want stacktraces if a command fails
def cmd(x):
    try:
        return run_command(x)
    except CliError as msg:
        raise Exception("Failed running '%s': %s" % (x, msg))

def cmd_expect_fail(x):
    try:
        run_command(x)
    except CliError:
        return
    raise Exception("command %s should fail but did not" % x)

def expect_can_frame(actual, expected):
    stest.expect_equal(actual.extended,
                       expected.extended,
                       "extended does not match")
    stest.expect_equal(actual.identifier,
                       expected.identifier,
                       "identifier does not match")
    stest.expect_equal(actual.rtr,
                       expected.rtr,
                       "rtp does not match")
    stest.expect_equal(actual.data_length,
                       expected.data_length,
                       "data_length does not match")
    stest.expect_equal(actual.crc,
                       expected.crc,
                       "crc does not match")
    stest.expect_equal(actual.data,
                       expected.data,
                       "data does not match")

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
        self.endpoints = [None] * device_num
        self.next_ep_id = 10
        for i in range(device_num):
            self.devices[i]        = simics.pre_conf_object('dev%d' % i,
                                                            'can_controller')
            self.endpoints[i]      = simics.pre_conf_object('ep%d' % i,
                                                            'can_endpoint')
            self.devices[i].link = self.endpoints[i]
            self.devices[i].queue        = self.bus_clk
            self.endpoints[i].link       = self.link_impl
            self.endpoints[i].device     = self.devices[i]
            self.endpoints[i].id         = self.next_ep_id
            self.next_ep_id              = self.next_ep_id + 1
        simics.SIM_add_configuration([self.link_impl]
                                     + self.devices
                                     + self.endpoints,
                                     None)
        self.ep_array = [None] * device_num
        self.dev_array = [None] * device_num
        for i in range(device_num):
            self.ep_array [i] = simics.SIM_get_object('ep%d' % i)
            self.dev_array [i] = simics.SIM_get_object('dev%d' % i)

    def distribute_message(self, sender_num, message):
        self.ep_array[sender_num].iface.can_link.send(message)


def create_info_status_simple():
    clk          = simics.pre_conf_object('clk', 'clock')
    clk.freq_mhz = 10.0
    simics.SIM_add_configuration([clk], None)

    link = simics.pre_conf_object('link', 'can_link_impl')
    dev  = simics.pre_conf_object('dev', 'can_controller')
    ep   = simics.pre_conf_object('ep', 'can_endpoint')

    link.goal_latency = 0.0
    dev.link  = ep
    dev.queue         = conf.clk
    ep.link           = link
    ep.device         = dev
    ep.id             = 1

    simics.SIM_add_configuration([ep, dev, link], None)
    return conf.ep, conf.link
