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

def test_known_address():
    (bus, devs) = create_bus_testbench(['m'], ['s0', 's1', 's2'], log_level=1)
    master = devs[0]
    slave_address = [0x50, 0x51, 0x52]
    bus.known_address = [[slave_address[i], i + 1, True] for i in range(3)]
    for i in range(3):
        for dev in devs[1:]:
            dev.obj.start = 0xff
            dev.obj.stop = 0
        start = slave_address[i] << 1
        master.start(slave_address[i] << 1)
        for dev in devs[1:]:
            stest.expect_equal(dev.obj.start,
                               start if dev == devs[i+1] else 0xff)
        master.stop()
        for dev in devs[1:]:
            stest.expect_equal(dev.obj.stop,
                               1 if dev == devs[i + 1] else 0)
    for dev in devs[1:]:
        dev.obj.start = 0xff
    master.start(0x53 << 1)
    for dev in devs[1:]:
        stest.expect_equal(dev.obj.start, 0x53 << 1)

test_known_address()
