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

def test_secondary_master():
    (bus, devs) = create_bus_testbench(
            ['master'], ['slave0', 'slave1'] , log_level = 1)
    simics.SIM_create_object('secondary_master',
                             'snd_master', [['bus', conf.bus]])
    conf.snd_master.bus = [conf.bus, 'I3C[3]']
    conf.bus.i3c_devices[3] = conf.snd_master
    master = devs[0]
    slave0 = devs[1]
    slave1 = devs[2]
    snd_master = Device(conf.snd_master)
    bus.i3c_main_master = 0
    snd_addr = 0xa0
    master.start(0xa0)
    master.stop()
    master.wait('ibi_request', 1, lambda: snd_master.ibi_request())
    snd_master.wait('ibi_start', 1, lambda: master.ibi_start())
    master.wait('ibi_address', snd_addr,
                lambda: snd_master.ibi_address(snd_addr))
    snd_master.wait('ibi_acknowledge', I3C_ack,
                    lambda: master.ibi_acknowledge(I3C_ack))
    WB = I3C_RSV_BYTE << 1
    multi_devices_wait([snd_master, slave0, slave1],
                       'start', WB, lambda: master.start(WB))
    master.wait('acknowledge', I3C_ack,
                lambda: [d.acknowledge(I3C_ack) for d in [slave0, slave1, snd_master]])
    multi_devices_wait([snd_master, slave0, slave1],
                       'sdr_write', [CCC_GETACCMST],
                        lambda: master.sdr_write(bytes((CCC_GETACCMST,))))
    snd_addr_with_parity = (snd_addr & 0xfe) | 1 # parity bit
    multi_devices_wait([snd_master, slave0, slave1], 'start', snd_addr | 1,
                       lambda: master.start(snd_addr | 1))
    slave0.acknowledge(I3C_noack)
    slave1.acknowledge(I3C_noack)
    master.wait('acknowledge', I3C_ack,
                lambda: snd_master.acknowledge(I3C_ack))
    snd_master.wait('read', 1, lambda: master.read())
    master.wait('read_response', snd_addr_with_parity,
                lambda: snd_master.read_response(snd_addr_with_parity, False))
    stest.expect_equal(bus.i3c_main_master, 0)
    master.stop()
    stest.expect_equal(bus.i3c_main_master, 3)

test_secondary_master()
