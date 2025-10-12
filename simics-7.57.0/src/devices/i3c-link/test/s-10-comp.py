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


from i3c_dev import i3c_master_dev_comp, i3c_slave_dev_comp
import stest

ACK = 0
NACK = 1

# Test connecting i3c_master_dev_comp and i3c_slave_dev_comp directly
SIM_load_module('clock')
run_command('create-cell-and-clocks-comp cc')
run_command('create-i3c-master-dev-comp m0')
run_command('create-i3c-slave-dev-comp s0')

run_command('connect m0.link_conn s0.link_conn')
run_command('instantiate-components')

start_addr = 0x7e << 1
conf.m0.master.bus.iface.i3c_slave.start(start_addr)
run_command('c 100')
stest.expect_equal(conf.s0.slave.object_data.reqs, [['start', start_addr]])

conf.s0.slave.bus.iface.i3c_master.acknowledge(ACK)
run_command('c 100')
stest.expect_equal(conf.m0.master.object_data.reqs, [['ack', 0]])


# Test connecting i3c_master_dev_comp and i3c_slave_dev_comp by i3c_link
run_command('create-i3c-simple-master-dev-comp m1')
run_command('create-i3c-slave-dev-comp s1')
SIM_load_module('i3c-link')
run_command('create-i3c-link link')

run_command('connect link.device0 m1.link_conn')
run_command('connect link.device1 s1.link_conn')
run_command('instantiate-components')

conf.m1.master.bus.iface.i3c_slave.start(start_addr)
run_command('c 100')
stest.expect_equal(conf.s1.slave.object_data.reqs, [['start', start_addr]])

conf.s1.slave.bus.iface.i3c_master.acknowledge(ACK)
run_command('c 100')
stest.expect_equal(conf.m1.master.object_data.reqs, [['ack', 0]])
