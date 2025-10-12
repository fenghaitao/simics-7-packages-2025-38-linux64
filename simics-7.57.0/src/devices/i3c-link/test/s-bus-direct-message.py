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

def test_direct_message():
    (bus, devs) = create_bus_testbench(
            ['master'], ['slave0', 'slave1', 'slave2'], log_level = 1)
    master = devs[0]
    slaves = devs[1:]
    slave_addresses = [0x60, 0x62, 0x64]
    bus.known_address = [[slave_addresses[i], i + 1, True] for i in range(3)]
    # Write
    WB = I3C_RSV_BYTE << 1
    multi_devices_wait(slaves, 'start', WB, lambda: master.start(WB))
    master.wait('acknowledge', I3C_ack,
                lambda: [s.acknowledge(I3C_ack) for s in slaves])
    multi_devices_wait(slaves, 'sdr_write', [CCC_SETMWL_D],
                       lambda: master.sdr_write(bytes((CCC_SETMWL_D,))))
    for i in range(len(slaves)):
        addr = slave_addresses[i] << 1
        slaves[i].wait('start', addr, lambda: master.start(addr))
        master.wait('acknowledge', I3C_ack,
                    lambda: slaves[i].acknowledge(I3C_ack))
        data = [0x01, 0x02]
        data_str = bytes(data)
        slaves[i].wait('sdr_write', data, lambda: master.sdr_write(data_str))

    # Read
    multi_devices_wait(slaves, 'start', WB, lambda: master.start(WB))
    master.wait('acknowledge', I3C_ack,
                 lambda: [s.acknowledge(I3C_ack) for s in slaves])
    multi_devices_wait(slaves, 'sdr_write', [CCC_GETMWL_D],
                       lambda: master.sdr_write(bytes((CCC_GETMWL_D,))))
    for i in range(len(slaves)):
        addr = (slave_addresses[i] << 1) | 1
        slaves[i].wait('start', addr, lambda: master.start(addr))
        master.wait('acknowledge', I3C_ack, lambda: slaves[i].acknowledge(I3C_ack))
        data = [0x12, 0x23]
        for n in range(len(data)):
            slaves[i].wait('read', 1, lambda: master.read())
            master.wait('read_response', data[n],
                        lambda: slaves[i].read_response(data[n], n == 1))
    master.stop()

test_direct_message()
