# © 2025 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import stest
import simics
from common import *

# Test master HDR read transaction

# slave - ep1
# master - ep2
setup()

link = simics.SIM_get_object("link")

stest.expect_equal(link.num_hdr_devs, 1, "Number of HDR devices should be 1")

s = conf.slave.object_data.reqs
m = conf.master.object_data.reqs
m_ep = conf.ep2.iface.i3c_slave
s_ep = conf.ep1.iface.i3c_master

m_h_ep = conf.ep2.iface.i3c_hdr_slave
s_h_ep = conf.ep1.iface.i3c_hdr_master

expect([s, m], [[], []])

# master: start_request broadcast
m_ep.start(0x7e << 1)

c()
expect([s, m], [['start', 0x7e << 1], []])

# slave: start_response
s_ep.acknowledge(ACK)

c()
expect([s, m], [[], ['ack', ACK]])

# Master: Enter HDR
m_ep.sdr_write(bytes([0x20]))
c()
expect([s, m], [['write', b"%c" % 0x20], []])

# Master send command code
m_h_ep.hdr_write(bytes([0x11 << 1, 1 << 7 | 0x63]))  # 0x11 is the HDR command code, 0x63 cmd]))
c()
expect([s, m], [['hdr_write', bytes([0x11 << 1, 1 << 7 | 0x63])], []])

s_h_ep.hdr_acknowledge(ACK)
c()
expect([s, m], [[], ['hdr_ack', ACK]])

# master: read_request
m_h_ep.hdr_read(10)

c()
expect([s, m], [['hdr_read', 10], []])

s_h_ep.hdr_read_response(
    bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a]),
    True)

c()
expect([s, m], [[], ['hdr_r_resp', bytes([0x01, 0x02, 0x03, 0x04, 0x05,
                                          0x06, 0x07, 0x08, 0x09, 0x0a]),
                        True]])
m_h_ep.hdr_exit()
c()
expect([s, m], [['hdr_exit'], []])

m_ep.stop()
c()
expect([s, m], [['stop'], []])
