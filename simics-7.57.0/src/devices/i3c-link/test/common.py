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


from simics import SIM_run_command, SIM_set_configuration
from configuration import OBJECT, OBJ
from stest import expect_equal
from i3c_dev import foo, bar

# setup basic configuration
def setup(extra_slave=False):
    SIM_run_command('load-module i3c-link')
    v = [
        OBJECT('default_sync_domain', 'sync_domain', min_latency = 0.1),
        OBJECT('cell', 'cell'),
        OBJECT('clk', 'clock', freq_mhz = 0.001, cell = OBJ('cell')),
        OBJECT('link', 'i3c_link_impl', goal_latency = 0.1),
        OBJECT("ep1", "i3c_link_endpoint",
               link = OBJ("link"), device = OBJ("slave"), id = 1),
        OBJECT('slave', 'foo', queue = OBJ("clk")),
        OBJECT("ep2", "i3c_link_endpoint",
               link = OBJ("link"), device = OBJ("master"), id = 2),
        OBJECT('master', 'bar', queue = OBJ("clk"))]
    if extra_slave:
        v += [OBJECT("ep3", "i3c_link_endpoint",
                link = OBJ("link"), device = OBJ("slave2"), id = 3),
                OBJECT('slave2', 'foo', queue = OBJ("clk"))]
    SIM_set_configuration(v)

def setup_no_slaves():
    SIM_run_command('load-module i3c-link')
    SIM_set_configuration([
        OBJECT('default_sync_domain', 'sync_domain', min_latency = 0.1),
        OBJECT('cell', 'cell'),
        OBJECT('clk', 'clock', freq_mhz = 0.001, cell = OBJ('cell')),
        OBJECT('link', 'i3c_link_impl', goal_latency = 0.1),
        OBJECT("ep1", "i3c_link_endpoint",
               link = OBJ("link"), device = OBJ("master"), id = 2),
        OBJECT('master', 'bar', queue = OBJ("clk"))])

# helper functions
def expect(a, b):
    assert len(a) == len(b)
    for i in range(len(a)):
        if b[i] != []:
            expect_equal(a[i], [b[i]], f"idx: {i}")
            del a[i][:]
        else:
            expect_equal(a[i], b[i], f"idx: {i}")

def c():
    SIM_run_command('c 101')

ACK = 0
NACK = 1
