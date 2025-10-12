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
    (bus, devs) = create_bus_testbench(
            ['master'], ['slave'] , log_level = 1)
    bus.known_address = [[0x60, 1, True]]
    master = devs[0]
    slave = devs[1]
    slave_address = 0x60
    master.start(0x02)
    master.stop()

    def start_ibi(ibi, ack):
        master.wait('ibi_request', 1, lambda: slave.ibi_request())
        slave.wait('ibi_start', 1, lambda: master.ibi_start())
        master.wait('ibi_address', ibi, lambda: slave.ibi_address(ibi))
        slave.wait('ibi_acknowledge', ack, lambda: master.ibi_acknowledge(ack))

    # Reject without disable the interrupt
    addr = (slave_address << 1) | 1 # Slave address as IBI
    start_ibi(addr, I3C_noack)
    master.stop()

    # Accept
    start_ibi(addr, I3C_ack)
    slave.wait('read', 1, lambda: master.read())
    slave_byte = 0x56
    master.wait('read_response', slave_byte,
                lambda: slave.read_response(slave_byte, False))
    master.stop()

    # Reject and disable the interrupt
    start_ibi(addr, I3C_noack)
    WB = I3C_RSV_BYTE << 1
    slave.wait('start', WB, lambda: master.start(WB))
    master.wait('acknowledge', I3C_ack, lambda : slave.acknowledge(I3C_ack))
    slave.wait('sdr_write', [CCC_DISE_D],
               lambda: master.sdr_write(bytes((CCC_DISE_D,))))
    addr &= 0xfe
    slave.wait('start', addr, lambda: master.start(addr))
    master.wait('acknowledge', I3C_ack, lambda: slave.acknowledge(I3C_ack))
    data = 0x45
    slave.wait('sdr_write', [data], lambda: master.sdr_write(bytes((data,))))
    master.stop()

test_in_band_interrupt()
