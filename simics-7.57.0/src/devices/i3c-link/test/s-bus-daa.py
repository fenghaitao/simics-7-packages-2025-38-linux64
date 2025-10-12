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

def daa_candidate(slaves):
    candidate = None
    dcr = 0xff
    for s in slaves:
        if s.obj.dcr < dcr and s.obj.write == 0xff:
            candidate = s
            dcr = s.obj.dcr
    return candidate

def daa_ack(slave):
    return I3C_ack if slave.obj.write == 0xff else I3C_noack

def test_dynamic_address_assigning():
    (bus, snooper, devs) = create_bus_testbench_with_snooper(
            ['m'], ['s0', 's1', 's2'], log_level=1)
    mapping = {0xa1: 0xa0, 0xa0: 0xa2, 0xa2: 0xa4}
    master = devs[0]
    slaves = devs[1:]
    mapping_keys = sorted(list(mapping.keys()))
    for i in range(len(slaves)):
        slaves[i].obj.dcr = mapping_keys[i]
    WB = I3C_RSV_BYTE << 1
    RB = WB | 1
    multi_devices_wait(slaves, 'start', WB, lambda: master.start(WB))
    master.wait('acknowledge', I3C_ack,
                lambda: [s.acknowledge(I3C_ack) for s in slaves])
    multi_devices_wait(slaves, 'sdr_write', [CCC_ENTDAA],
                       lambda: master.sdr_write(bytes((CCC_ENTDAA,))))
    for i in range(len(slaves)):
        candidate = daa_candidate(slaves)
        multi_devices_wait(slaves, 'start', RB, lambda: master.start(RB))
        master.wait('acknowledge', I3C_ack,
                    lambda: [s.acknowledge(daa_ack(s)) for s in slaves])
        unassigned_slaves = [s for s in slaves if s.obj.write == 0xff]
        multi_devices_wait(unassigned_slaves, 'daa_read', 1,
                           lambda: master.daa_read())
        master.wait('daa_response', candidate.obj.dcr,
                    lambda: [s.daa_response(0, 0, s.obj.dcr) for s in unassigned_slaves])
        addr = mapping[candidate.obj.dcr]
        candidate.wait('write', addr, lambda: master.write(addr))
        master.wait('acknowledge', I3C_ack, lambda: candidate.acknowledge(I3C_ack))
    multi_devices_wait(slaves, 'start', RB, lambda: master.start(RB))
    master.wait('acknowledge', I3C_noack,
                lambda: [s.acknowledge(I3C_noack) for s in slaves])
    master.stop()
    expected = [[k, mapping[k] >> 1] for k in mapping_keys]
    stest.expect_equal(expected, snooper.daa_list)

test_dynamic_address_assigning()
