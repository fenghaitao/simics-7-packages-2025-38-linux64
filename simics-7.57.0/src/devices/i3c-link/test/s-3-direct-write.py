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


# Test i3c direct write transaction, that is, master communicates
# with slaves one by one
from common import *

# slave - ep1
# master - ep2
setup()

# slave3 - ep3
SIM_set_configuration([
    OBJECT("ep3", "i3c_link_endpoint",
           link = OBJ("link"), device = OBJ("slave3"), id = 3),
    OBJECT('slave3', 'foo', queue = OBJ("clk"))])

s = conf.slave.object_data.reqs
s3 = conf.slave3.object_data.reqs
m = conf.master.object_data.reqs
m_ep = conf.ep2.iface.i3c_slave
s_ep = conf.ep1.iface.i3c_master
s3_ep = conf.ep3.iface.i3c_master

expect([s, s3, m], [[], [], []])

# master: start_request (with broadcast address)
addr = 0x7e << 1
m_ep.start(addr)

c()
expect([s, s3, m], [['start', addr], ['start', addr], []])

# slave: start_response
s_ep.acknowledge(ACK)
s3_ep.acknowledge(ACK)

c()
expect([s, s3, m], [[], [], ['ack', 0]])

# master: send direct Common Command Code, direct CCC ranges 0x80-0xFE
direct_ccc = b"%c" % 0x80
m_ep.sdr_write(direct_ccc)

c()
expect([s, s3, m], [['write', direct_ccc], ['write', direct_ccc], []])

# master: repeat start request to one specific slave
m_ep.start(0x12)

c()
expect([s, s3, m], [['start', 0x12], ['start', 0x12], []])

# slave: start_response
s_ep.acknowledge(ACK)
s3_ep.acknowledge(NACK)

c()
expect([s, s3, m], [[], [], ['ack', 0]])

# master: write_request
data = b"%c" % 0x7f
m_ep.sdr_write(data)

c()
expect([s, s3, m], [['write', data], [], []])

# master: repeat start request to another slave
m_ep.start(0x14)

c()
expect([s, s3, m], [['start', 0x14], ['start', 0x14], []])

# slave: start_response
s_ep.acknowledge(NACK)
s3_ep.acknowledge(ACK)

c()
expect([s, s3, m], [[], [], ['ack', 0]])

# master: write_request
data = b"%c" % 0x7e
m_ep.sdr_write(data)

c()
expect([s, s3, m], [[], ['write', data], []])

# master: stop
m_ep.stop()

c()
expect([s, s3, m], [['stop'], ['stop'], []])
