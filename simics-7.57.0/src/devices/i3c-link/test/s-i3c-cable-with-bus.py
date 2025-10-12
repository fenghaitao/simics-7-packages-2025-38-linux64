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


from test_utils import *

domain = simics.pre_conf_object('domain', 'sync_domain')
cell = simics.pre_conf_object('cell', 'cell')
simics.SIM_add_configuration([cell, domain], None)
(bus, devs) = create_bus_testbench(['master'], [], log_level = 4)
clk = conf.clk
clk.cell = conf.cell
conf.master.queue = clk

cable = simics.pre_conf_object('cable', 'i3c_cable_impl')
ep0 = simics.pre_conf_object('ep0', 'i3c_cable_endpoint')
ep1 = simics.pre_conf_object('ep1', 'i3c_cable_endpoint')
slave = simics.pre_conf_object('slave', 'i3c_slave_device')
for d in [ep0, ep1, cable, slave]:
    d.queue = clk
cable.goal_latency = 1e-5
ep0.link = cable
ep1.link = cable
ep0.device = [bus, 'I3C[1]']
ep1.device = slave
ep0.id = 1
ep1.id = 2
cable.log_level = 4
slave.bus = ep1
simics.SIM_add_configuration([cable, ep0, ep1, slave], None)
bus.i3c_devices[1] = conf.ep0
master = Device(conf.master)
slave = Device(conf.slave)

def test_daa():
    wb = I3C_RSV_BYTE << 1
    rb = wb | 1
    dcr = 0x78
    addr = 0xa0
    slave.wait('start', wb, lambda: master.start(wb))
    master.wait('acknowledge', I3C_ack, lambda: slave.acknowledge(I3C_ack))
    slave.wait('sdr_write', [CCC_ENTDAA],
               lambda: master.sdr_write(bytes((CCC_ENTDAA,))))
    slave.wait('start', rb, lambda: master.start(rb))
    master.wait('acknowledge', I3C_ack, lambda: slave.acknowledge(I3C_ack))
    slave.wait('daa_read', 1, lambda: master.daa_read())
    master.wait('daa_response', dcr, lambda: slave.daa_response(0, 0, dcr))
    slave.wait('write', addr, lambda: master.write(addr))
    master.wait('acknowledge', I3C_ack, lambda: slave.acknowledge(I3C_ack))
    slave.wait('start', rb, lambda: master.start(rb))
    master.wait('acknowledge', I3C_noack, lambda: slave.acknowledge(I3C_noack))
    slave.wait('stop', 1, lambda: master.stop())

run_command('log-setup -time-stamp')
test_daa()
