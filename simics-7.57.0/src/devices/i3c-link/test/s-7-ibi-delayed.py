# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Test IBI process
from common import *

# slave - ep1
# master - ep2
setup(extra_slave=True)

s = conf.slave.object_data.reqs
s2 = conf.slave2.object_data.reqs
m = conf.master.object_data.reqs
m_ep = conf.ep2.iface.i3c_slave
s_ep = conf.ep1.iface.i3c_master
s2_ep = conf.ep3.iface.i3c_master

conf.ep1.log_level = 4
conf.ep2.log_level = 4
conf.ep3.log_level = 4

expect([s, s2, m], [[], [], []])

# Setup main_master by issuing start request with 0x7e
# master: start_request
addr = 0x7e << 1
m_ep.start(addr)

c()
expect([s, m], [['start', addr], []])

# slave: start_response
s_ep.acknowledge(NACK)
s2_ep.acknowledge(NACK)

c()
expect([s, m], [[], ['ack', 1]])

# master: stop
m_ep.stop()

c()
expect([s, m], [['stop'], []])


### master responses with ACK, slave send Mandatory Data Byte to master
# slave: ibi request
s_ep.ibi_request()

c()
expect([s, m], [[], ['ibi_request']])

# master: ibi start
m_ep.ibi_start()

c()
expect([s, m], [['ibi_start'], []])

# slave: sends its IBI address
addr = 0x01 << 1 | 1
s_ep.ibi_address(addr)

c()
expect([s, m], [[], ['ibi_address', addr]])

# master: ibi acks
m_ep.ibi_acknowledge(ACK)

c()
expect([s, m], [['ibi_acknowledge', ACK], []])

m_ep.stop()
c()
expect([s, m], [['stop'], []])

s2.clear()

addr = 0x50 << 1

s_ep.ibi_request()
m_ep.start(addr)

c()
expect([s, s2, m], [['start', addr], ['start', addr], ['ibi_request']])

s_ep.acknowledge(NACK)
s2_ep.acknowledge(ACK)

c()
expect([s, s2, m], [[], [], ['ack', ACK]])

m_ep.stop()

c()
expect([s, s2, m], [['stop'], ['stop'], []])

s2_ep.ibi_request()

c()
expect([s, s2, m], [[], [], ['ibi_request']])

m_ep.ibi_start()

c()
expect([s, s2, m], [['ibi_start'], ['ibi_start'], []])

s2_ep.ibi_address(0x1)
s_ep.ibi_address(0x2)

c()
expect([s, s2, m], [[], [], ['ibi_address', 0x1]])
m_ep.ibi_acknowledge(ACK)

c()
expect([s, s2, m], [[], ['ibi_acknowledge', ACK], []])

m_ep.stop()

c()
expect([s, s2, m], [['stop'], ['stop'], []])

s_ep.ibi_request()
s2_ep.ibi_request()
c()
expect([s, s2], [[], []])
expect(m, ['ibi_request', 'ibi_request'])
m.clear()

m_ep.ibi_start()
c()
expect([s, s2, m], [['ibi_start'], ['ibi_start'], []])
s2_ep.ibi_address(0x2)
s_ep.ibi_address(0x1)
c()
expect([s, s2, m], [[], [], ['ibi_address', 0x1]])
m_ep.ibi_acknowledge(ACK)
c()
expect([s, s2, m], [['ibi_acknowledge', ACK], [], []])
m_ep.stop()

c()
expect([s, s2, m], [['stop'], ['stop'], []])
