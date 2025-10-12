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
import time

import conf
import stest
from simmod.global_messages.global_messages import (
        Msg_reply, Msg_stop, Msg_barrier, Msg_signal, Global_msg)
import simics
from test_utils import *

latency = 80e-9
freq = 25.0
total_nodes = int(os.environ['TOTAL_NODES'])
node_id = int(os.environ['NODE_ID'])

port_file = stest.scratch_file('i3c-multi-test-cable')

def create_multi_case():
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
    link = simics.pre_conf_object('link', 'i3c_cable_impl')
    dev = simics.pre_conf_object(
            'dev%d' % node_id,
            'i3c_master_device' if node_id == 0 else 'i3c_slave_device')
    ep = simics.pre_conf_object('ep%d' % node_id, 'i3c_cable_endpoint')
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
        top_domain.min_latency = 80e-9
        rss = simics.pre_conf_object('rss', 'remote_sync_server')
        rss.domain = top_domain
        rss.port = 0 # Let OS device port number
        top_conf = [top_domain, rss]
    else:
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
    run_command('log-setup -time-stamp')
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

wb = I3C_RSV_BYTE << 1
rb = wb | 1
dcr = 0x77
addr = 0xa0
if node_id == 0:
    master = Device(conf.dev0)
    master.start(wb)
    master.wait('acknowledge', I3C_ack)
    master.sdr_write(bytes((CCC_ENTDAA,)))
    simics.SIM_continue(1)
    master.start(rb)
    master.wait('acknowledge', I3C_ack)
    master.daa_read()
    master.wait('daa_response', dcr)
    master.write(addr)
    master.wait('acknowledge', I3C_ack)
    master.start(rb)
    master.wait('acknowledge', I3C_noack)
    master.stop()
    simics.SIM_continue(10)
    stop.send()
    saved.send()
else:
    slave = Device(conf.dev1)
    slave.wait('start', wb)
    slave.acknowledge(I3C_ack)
    slave.wait('sdr_write', [CCC_ENTDAA])
    slave.wait('start', rb)
    slave.acknowledge(I3C_ack)
    slave.wait('daa_read', 1)
    slave.daa_response(0, 0, dcr)
    slave.wait('write', addr)
    slave.acknowledge(I3C_ack)
    slave.wait('start', rb)
    slave.acknowledge(I3C_noack)
    slave.wait('stop', 1)
    saved.send()
    SIM_run_command('run')

print('Node %d finished testing' % node_id)
saved.wait()
