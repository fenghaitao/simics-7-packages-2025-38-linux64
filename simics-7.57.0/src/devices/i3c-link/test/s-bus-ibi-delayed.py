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

def test_in_band_interrupt():
    (bus, devs) = create_bus_testbench(['m'], ['s0', 's1'] , log_level = 1)
    master = devs[0]
    slave0 = devs[1]
    slave1 = devs[2]
    conf.bus.known_address = [[0x50, 1, True], [0x51, 2, True]]

    slave0.wait('start', 0x50 << 1, lambda: master.start(0x50 << 1))
    slave1.ibi_request()
    slave0.acknowledge(I3C_noack)
    master.wait('ibi_request', 1, lambda: master.stop())
    stest.expect_equal(bus.status, 'Wait IBI Start')
    slave1.wait('ibi_start', 1, lambda: master.ibi_start())
    master.wait('ibi_address', 0xee, lambda: slave1.ibi_address(0xee))
    master.stop()
    simics.SIM_continue(1)
    stest.expect_equal(bus.status, 'Idle')

test_in_band_interrupt()
