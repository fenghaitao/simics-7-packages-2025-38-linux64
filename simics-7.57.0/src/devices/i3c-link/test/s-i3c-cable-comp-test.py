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

def comp_test():
    for m in ['clock', 'i3c-link']:
        simics.SIM_load_module(m)

    for cmd in ['create-cell-and-clocks-comp cc0 freq_mhz = 25',
                'create-i3c-master-comp i3c_cmp0',
                'create-i3c-slave-comp i3c_cmp1',
                'create-i3c-cable cable0']:
        run_command(cmd)

    stest.expect_equal(conf.cable0.connector_count, 0)
    run_command('connect cable0.device0 i3c_cmp0.i3c')
    stest.expect_equal(conf.cable0.connector_count, 1)
    run_command('connect cable0.device1 i3c_cmp1.i3c')
    stest.expect_equal(conf.cable0.connector_count, 2)
    if getattr(conf.cable0, 'device2', None):
        raise Exception("component shouldn't have connector 'device2'")
    run_command('disconnect cable0.device1 i3c_cmp1.i3c')
    stest.expect_equal(conf.cable0.connector_count, 1)
    run_command('connect cable0.device1 i3c_cmp1.i3c')
    run_command('instantiate-components')
    conf.cable0.link.goal_latency = 80e-9

    master = Device(conf.i3c_cmp0.dev)
    slave = Device(conf.i3c_cmp1.dev)

    # IBI
    addr = 0xa2

    master.wait('ibi_request', 1, lambda: slave.ibi_request())
    slave.wait('ibi_start', 1, lambda: master.ibi_start())
    master.wait('ibi_address', addr, lambda: slave.ibi_address(addr))
    slave.wait('ibi_acknowledge', I3C_ack,
               lambda: master.ibi_acknowledge(I3C_ack))

    WB = I3C_RSV_BYTE << 1
    slave.wait('start', WB, lambda: master.start(WB))
    master.wait('acknowledge', I3C_ack, lambda: slave.acknowledge(I3C_ack))
    master.stop()

comp_test()
