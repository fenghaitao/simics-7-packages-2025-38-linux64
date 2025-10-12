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


import os
import sys

import conf
import stest
from simmod.global_messages.global_messages import (
        Msg_reply, Msg_stop, Msg_barrier, Msg_signal, Global_msg)
import simics
from i3c_dev import foo, bar

latency = 80e-9 # TODO
freq = 25       # TODO
total_nodes = int(os.environ['TOTAL_NODES'])
node_id = int(os.environ['NODE_ID'])


port_file = stest.scratch_file('i3c-multi-test-link')

def create_multi_case():
    print("Node %d" % (node_id))

    class Msg_stop(Global_msg):
        def __init__(self):
            self.init("stop")
        def receive(self, arg):
            SIM_break_simulation(None)

    conf.sim.multithreading = True
    conf_done = Msg_barrier("conf_done", total_nodes)

    cell = simics.pre_conf_object('cell', 'cell')
    clk = simics.pre_conf_object('clk', 'clock')
    clk.freq_mhz = freq
    clk.cell = cell
    link = simics.pre_conf_object('link', 'i3c_link_impl')
    dev = simics.pre_conf_object('dev%d' % node_id,
                                 'bar' if node_id == 0 else 'foo')
    ep = simics.pre_conf_object('ep%d' % node_id, 'i3c_link_endpoint')
    link.log_level = 4
    link.goal_latency = latency
    link.global_id = 'global-link-id'
    dev.queue = clk
    dev.bus = ep
    ep.link = link
    ep.device = dev
    ep.id = node_id + 1
    port = 0
    if node_id == 0:
        # server node_id
        top_domain = simics.pre_conf_object('top_domain','sync_domain')
        top_domain.min_latency = latency
        rss = simics.pre_conf_object('rss', 'remote_sync_server')
        rss.domain = top_domain
        rss.port = 0 # Let OS device port number
        top_conf = [top_domain, rss]
    else:
        port = -1
        # Wait for server to have created RSS and written port number to temporary file
        while True:
            if os.path.isfile(port_file):
                f = open(port_file, "r")
                v = f.read()
                if v.isdigit():
                    port = int(v)
                    break
                time.sleep(1.0)
                f.close()

        top_domain = simics.pre_conf_object('top_domain', 'remote_sync_domain')
        top_domain.server = "localhost:%d" % port
        top_conf = [top_domain]
    local_domain = simics.pre_conf_object('local_domain', 'sync_domain')
    local_domain.sync_domain = top_domain
    local_domain.min_latency = latency
    simics.SIM_add_configuration(
            top_conf + [cell, clk, dev, ep, link, local_domain], None)
    print("Node %d: configured" % node_id)

    if node_id == 0:
        port = conf.rss.port
        f = open(port_file, "a")
        f.write(str(port))
        f.close()

    print("Node %d using port %d" % (node_id, port))

    if node_id == 0:
        conf.rss.finished = None
    else:
        conf.top_domain.finished = None

    start = Msg_signal("start")
    saved = Msg_barrier("saved", total_nodes)
    stop  = Msg_stop()

    conf_done.send()
    if node_id == 0:
        print('Node 0 waiting for configuration completed')
        conf_done.wait()
        start.send()
    else:
        print('Node 1 waiting for start signal')
        start.wait()
    return (saved, stop)

(saved, stop) = create_multi_case()
print('Node %d is ready for i3c transfer' % node_id)

wb = 0x7e << 1
rb = wb | 1
data = 0x12345677
addr = 0xa0

def _wait(dev, msg):
    n = 0
    while True:
        if dev.object_data.reqs == msg:
            dev.object_data.reqs = []
            return
        simics.SIM_continue(1)
        n += 1
        if n > 100000:
            raise Exception('timeout on %s' % dev)

def wait(dev, msg):
    _wait(dev, [msg])

if node_id == 0:
    SIM_run_command('log-level class = i3c_link_endpoint level = 4')
    master = conf.dev0
    conf.ep0.main_master = 1
    m_iface = conf.ep0.iface.i3c_slave
    m_iface.start(wb)
    wait(master, ['ack', 0])
    m_iface.sdr_write(b"%c" % 0x07)
    m_iface.start(rb)
    wait(master, ['ack', 0])
    m_iface.daa_read()
    wait(master, ['daa_response', data >> 16, (data >> 8) & 0xff, data & 0xff])
    m_iface.write(addr)
    wait(master, ['ack', 0])
    m_iface.start(rb)
    wait(master, ['ack', 1])
    m_iface.stop()
    simics.SIM_continue(10)
    stop.send()
    saved.send()
else:
    SIM_run_command('log-level class = i3c_link_endpoint level = 4')
    slave = conf.dev1
    conf.ep1.main_master = 1
    s_iface = conf.ep1.iface.i3c_master
    wait(slave, ['start', wb])
    s_iface.acknowledge(0)
    _wait(slave, [['write', b"%c" % 0x07], ['start', rb]])
    s_iface.acknowledge(0)
    wait(slave, ['daa_read'])
    s_iface.daa_response(data >> 16, (data >> 8) & 0xff, data & 0xff)
    wait(slave, ['daa_address', addr])
    s_iface.acknowledge(0)
    wait(slave, ['start', rb])
    s_iface.acknowledge(1)
    wait(slave, ['stop'])
    saved.send()
    SIM_run_command('run')

print('Node %d finished testing' % node_id)
saved.wait()
