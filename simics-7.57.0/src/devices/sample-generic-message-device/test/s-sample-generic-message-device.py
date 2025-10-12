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


import stest
import pyobj
import cli

DEVICE_NUMBER = 2

class obj: pass

def setup_test_bench():
    tb = obj()
    tb.devs = [None] * DEVICE_NUMBER
    clk = simics.pre_conf_object('clk', 'clock')
    clk.attr.freq_mhz = 1.0
    SIM_add_configuration([clk], None)
    link_impl = simics.pre_conf_object('link_impl', 'gml_link_impl')
    link_impl.attr.queue = clk
    link_impl.attr.goal_latency = 1e-6
    SIM_add_configuration([link_impl], None)
    for idx in range(DEVICE_NUMBER):
        dev = simics.pre_conf_object('dev_%d' % idx,
                                     'sample_generic_message_device')
        ep = simics.pre_conf_object('ep_%d' % idx, 'gml_link_endpoint')
        ep.attr.id = 1 + idx
        ep.attr.link = link_impl
        ep.attr.queue = clk
        ep.attr.device = dev
        dev.attr.queue = clk
        dev.attr.link = ep
        dev.attr.address = 0x100 + idx
        dev.attr.dest_address = 0x100 + (DEVICE_NUMBER - 1 - idx)
        dev.attr.length = 8
        dev.attr.send_value = 0x50 + idx
        dev.attr.delay = 10          # 10 us
        dev.attr.frame_delay = 2000  # 2 us
        SIM_add_configuration([dev, ep], None)
        tb.devs[idx] = simics.SIM_get_object("dev_%d" % idx)
    return tb

def test_start():
    cli.run_command("log-level 4")
    cli.run_command("c 20")

tb = setup_test_bench()
test_start()

# check the results
for idx in range(DEVICE_NUMBER):
    stest.expect_equal(tb.devs[idx].attr.received_value,
                       0x50 + (DEVICE_NUMBER - 1 - idx),
                       "received data incorrect")

print("All tests passed.")
