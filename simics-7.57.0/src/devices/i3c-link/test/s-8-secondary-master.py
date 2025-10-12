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


# Test i3c secondary master requests to be current master
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


# slave: ibi request
s_ep.ibi_request()

c()
expect([s, m], [[], ['ibi_request']])

# master: ibi start
m_ep.ibi_start()

c()
expect([s, m], [['ibi_start'], []])

# slave: sends its secondary master address (addr | 0)
snd_addr = 0x01 << 1
s_ep.ibi_address(snd_addr)

c()
expect([s, m], [[], ['ibi_address', snd_addr]])

# master: ibi acks
m_ep.ibi_acknowledge(ACK)

c()
expect([s, m], [['ibi_acknowledge', ACK], []])


# master: start_request for direct read CCC (GETACCMST 0x91)
addr = 0x7e << 1
m_ep.start(addr)

c()
expect([s, m], [['start', addr], []])

# slave: start_response
s_ep.acknowledge(ACK)

c()
expect([s, m], [[], ['ack', 0]])

# master: send direct Common Command Code (GETACCMST 0x91)
direct_ccc = b"%c" % 0x91
m_ep.sdr_write(direct_ccc)

c()
expect([s, m], [['write', direct_ccc], []])

# master: repeat start request to one specific slave
m_ep.start(snd_addr | 1)

c()
expect([s, m], [['start', snd_addr | 1], []])

# slave: start_response
s_ep.acknowledge(ACK)

c()
expect([s, m], [[], ['ack', 0]])

# master: signal ready to read
m_ep.read()

c()
expect([s, m], [['read'], []])

# slave: send data back to master
s_ep.read_response(snd_addr, False)

c()
expect([s, m], [[], ['r_resp', snd_addr, False]])

expect_equal(conf.ep2.main_master, 2)
expect_equal(conf.ep1.main_master, 2)

# master: stop
m_ep.stop()

c()
expect([s, m], [['stop'], []])

expect_equal(conf.ep2.main_master, 1)
expect_equal(conf.ep1.main_master, 1)
