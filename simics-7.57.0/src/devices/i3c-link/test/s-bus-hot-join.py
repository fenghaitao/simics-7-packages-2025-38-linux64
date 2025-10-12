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

def test_hot_join():
    (bus, devs) = create_bus_testbench(['master'], ['slave'], log_level = 1)
    master = devs[0]
    slave = devs[1]
    slave_address = 0x64
    ibi = I3C_IBI_BYTE << 1
    master.start(slave_address << 1)
    master.stop()
    master.wait('ibi_request', 1, lambda: slave.ibi_request())
    slave.wait('ibi_start', 1, lambda: master.ibi_start())
    master.wait('ibi_address', ibi, lambda: slave.ibi_address(ibi))
    slave.wait('ibi_acknowledge', I3C_ack,
               lambda: master.ibi_acknowledge(I3C_ack))
    addr = I3C_RSV_BYTE << 1
    slave.wait('start', addr, lambda: master.start(addr))
    master.wait('acknowledge', I3C_ack, lambda: slave.acknowledge(I3C_ack))
    slave.wait('sdr_write', [CCC_ENTDAA],
               lambda: master.sdr_write(bytes((CCC_ENTDAA,))))
    slave.wait('start', addr | 1, lambda: master.start(addr | 1))
    master.wait('acknowledge', I3C_ack, lambda: slave.acknowledge(I3C_ack))
    slave.wait('daa_read', 1, lambda: master.daa_read())
    dcr = 0x78
    slave.obj.dcr = dcr
    master.wait('daa_response', dcr, lambda: slave.daa_response(0, 0, dcr))
    slave.wait('write', slave_address << 1,
               lambda: master.write(slave_address << 1))
    master.wait('acknowledge', I3C_ack, lambda: slave.acknowledge(I3C_ack))
    master.stop()

test_hot_join()
