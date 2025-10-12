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

def test_broadcast_write():
    (bus, devs) = create_bus_testbench(['m'], ['s0', 's1', 's2'], log_level=1)
    master = devs[0]
    slaves = devs[1:]
    wb = I3C_RSV_BYTE << 1
    multi_devices_wait(slaves, 'start', wb, lambda: master.start(wb))
    master.wait('acknowledge', I3C_ack,
                lambda: [slave.acknowledge(I3C_ack) for slave in slaves])
    data = [0x01, 0x02]
    raw_data = bytes([CCC_SETMWL_B] + data)
    multi_devices_wait(slaves, 'sdr_write', [CCC_SETMWL_B] + data,
                       lambda: master.sdr_write(raw_data))
    master.stop()

test_broadcast_write()
