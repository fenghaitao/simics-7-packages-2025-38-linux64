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


# Test IBI process
from common import *

# slave - ep1
# master - ep2
setup()

s = conf.slave.object_data.reqs
m = conf.master.object_data.reqs
m_ep = conf.ep2.iface.i3c_slave
s_ep = conf.ep1.iface.i3c_master

expect([s, m], [[], []])

# Setup main_master by issuing start request with 0x7e
# master: start_request
addr = 0x7e << 1
m_ep.start(addr)

c()
expect([s, m], [['start', addr], []])

# slave: start_response
s_ep.acknowledge(NACK)

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


# master: read slave BCR[2]
m_ep.read()

c()
expect([s, m], [['read'], []])

# slave: send BCR[2] to master
s_ep.read_response(1, False)

c()
expect([s, m], [[], ['r_resp', 1, False]])

# master: read Mandatory Data Byte since BCR[2] is 1
m_ep.read()

c()
expect([s, m], [['read'], []])

# slave: send Mandatory Data Byte to master
s_ep.read_response(0xab, False)

c()
expect([s, m], [[], ['r_resp', 0xab, False]])

# master: stop
m_ep.stop()

c()
expect([s, m], [['stop'], []])


### master responses with ACK, slave send ready to master
# slave: ibi request
s_ep.ibi_request()

c()
expect([s, m], [[], ['ibi_request']])

# master: ibi start
m_ep.ibi_start()

c()
expect([s, m], [['ibi_start'], []])

# slave: sends its IBI address
s_ep.ibi_address(addr)

c()
expect([s, m], [[], ['ibi_address', addr]])

# master: ibi acks
m_ep.ibi_acknowledge(ACK)

c()
expect([s, m], [['ibi_acknowledge', ACK], []])


# master: read BCR[2]
m_ep.read()

c()
expect([s, m], [['read'], []])

# slave: send BCR[2] to master
s_ep.read_response(0, False)

c()
expect([s, m], [[], ['r_resp', 0, False]])

# master: stop since the BCR[2] is 0
m_ep.stop()

c()
expect([s, m], [['stop'], []])


### master responses with NACK
# slave: ibi request
s_ep.ibi_request()

c()
expect([s, m], [[], ['ibi_request']])

# master: ibi start
m_ep.ibi_start()

c()
expect([s, m], [['ibi_start'], []])

# slave: sends its IBI address
s_ep.ibi_address(addr)

c()
expect([s, m], [[], ['ibi_address', addr]])

# master: ibi acks
m_ep.ibi_acknowledge(NACK)

c()
expect([s, m], [['ibi_acknowledge', NACK], []])


# master: issues start to disable ibi
m_ep.start(addr)

c()
expect([s, m], [['start', addr], []])

# master: stop
m_ep.stop()

c()
expect([s, m], [['stop'], []])
