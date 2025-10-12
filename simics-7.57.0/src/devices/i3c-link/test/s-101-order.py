# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import simics
import common
import stest

class fake_i3c_target_dev:
    cls = simics.confclass('fake-i3c-target')

    def __init__(self):
        self.ack = False

    def connect(self, host):
        self.host_iface = host.iface.i3c_master

    @cls.iface.i3c_slave.start
    def start(self, addr):
        self.host_iface.acknowledge(0 if self.ack else 1)

    @cls.iface.i3c_slave.write
    def write(self, value):
        self.host_iface.acknowledge(0)

    @cls.iface.i3c_slave.sdr_write
    def sdr_write(self, data):
        pass

    @cls.iface.i3c_slave.read
    def read(self):
        pass

    @cls.iface.i3c_slave.daa_read
    def daa_read(self):
        pass

    @cls.iface.i3c_slave.stop
    def stop(self):
        pass

    @cls.iface.i3c_slave.ibi_start
    def ibi_start(self):
        pass

    @cls.iface.i3c_slave.ibi_acknowledge
    def ibi_acknowledge(self, ack):
        pass


class fake_i3c_controller_dev:
    cls = simics.confclass('fake-i3c-controller')

    def __init__(self):
        self.wait_ack = False

    def connect(self, tgt):
        self.tgt_iface = tgt.iface.i3c_slave

    def start(self, addr):
        self.wait_ack = True
        self.tgt_iface.start(addr)

    def sdr_write(self, val):
        self.tgt_iface.sdr_write(val.to_bytes(4, byteorder='little'))

    def stop(self):
        self.tgt_iface.stop()

    @cls.iface.i3c_master.acknowledge
    def acknowledge(self, ack):
        stest.expect_true(self.wait_ack)
        self.wait_ack = False

    @cls.iface.i3c_master.read_response
    def read_response(self, data, more):
        pass

    @cls.iface.i3c_master.daa_response
    def daa_response(self, id, bcr, dcr):
        pass

    @cls.iface.i3c_master.ibi_request
    def ibi_request(self):
        pass

    @cls.iface.i3c_master.ibi_address
    def ibi_address(self, addr):
        pass


# Here we test that host can send messages to targets
# with latency 0 and has a sorting key higher than the targets.
# Thus there is a possibility that liblink will reorder the messages
# and the targets can bypass the messages from host in the queue.

simics.SIM_run_command('load-module i3c-link')
sync = simics.pre_conf_object(None, 'sync_domain', min_latency=1e-11)
cell = simics.pre_conf_object(None, 'cell')
clock = simics.pre_conf_object('clock', 'clock', cell=cell, freq_mhz=10)
link = simics.pre_conf_object("link", 'i3c_link_impl', goal_latency=0.0)
host = simics.pre_conf_object(None, 'fake-i3c-controller', queue=clock)
ep_host = simics.pre_conf_object("ep_host", 'i3c_link_endpoint', link=link,
                                 device=host, id=1, sorting_key=[True, 100])

eps = []
tgts = []
for i in range(3):
    tgt = simics.pre_conf_object(None, 'fake-i3c-target', queue=clock)
    tgts.append(tgt)
    eps.append(simics.pre_conf_object(f"ep_tgt{i}", 'i3c_link_endpoint', link=link,
                                 device=tgt, id=i+2, queue=clock, sorting_key=[True, i + 1]))
conf_list = [host, sync, cell, clock, ep_host, link]
simics.SIM_add_configuration(conf_list + eps + tgts, None)

host = simics.SIM_get_object(host.name).object_data
host.connect(simics.SIM_get_object(ep_host.name))

# simics.SIM_get_object(ep_host.name).cli_cmds.log_level(level=4)
for i in range(3):
    ep = simics.SIM_get_object(eps[i].name)
    ep.cli_cmds.log_level(level=4)
    tgt_dev = simics.SIM_get_object(tgts[i].name).object_data
    tgt_dev.connect(ep)
    if i == 0:
        tgt_dev.ack = True

common.c()
host.start(0xa1)
stest.expect_true(host.wait_ack)
common.c()
stest.expect_false(host.wait_ack)
host.sdr_write(100)
host.stop()
host.start(0xa1)
stest.expect_true(host.wait_ack)
common.c()
stest.expect_false(host.wait_ack)
host.stop()
