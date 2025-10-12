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


# Test new slave hot-join process
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

# slave: sends its hot-join address
addr = 0x02 << 1
s_ep.ibi_address(addr)

c()
expect([s, m], [[], ['ibi_address', addr]])

# master: ibi acks
m_ep.ibi_acknowledge(ACK)

c()
expect([s, m], [['ibi_acknowledge', ACK], []])

# master: send CCC (either disable hot-join or start DAA process)
# master: start DAA process
addr = 0x7e << 1
m_ep.start(addr)

c()
expect([s, m], [['start', addr], []])

# slave: start_response
s_ep.acknowledge(ACK)

c()
expect([s, m], [[], ['ack', 0]])

# master: send ENTDAA Common Command Code
ccc_entdaa = b"%c" % 0x07
m_ep.sdr_write(ccc_entdaa)

c()
expect([s, m], [['write', ccc_entdaa], []])

### enter into DAA process from last step
# master: repeat start to assign dynamic address
addr = 0x7e << 1 | 1
m_ep.start(addr)

c()
expect([s, m], [['start', addr], []])

# slave: start_response
s_ep.acknowledge(ACK)

c()
expect([s, m], [[], ['ack', 0]])

# master: signal ready to slaves so that slaves will send their daa data
m_ep.daa_read()

c()
expect([s, m], [['daa_read'], []])

# slave: send daa data to master by daa_response()
s_ep.daa_response(0xabcd >> 16, (0xabcd >> 8) & 0xff, 0xabcd & 0xff)

c()
expect([s, m], [[], ['daa_response',
                     0xabcd >> 16,
                     (0xabcd >> 8) & 0xff,
                     0xabcd & 0xff]])

# master: send assigned address to slave by daa_address()
m_ep.write(0x01)

c()
expect([s, m], [['daa_address', 0x01], []])

# slave: ack the daa_address
s_ep.acknowledge(ACK)

c()
expect([s, m], [[], ['ack', 0]])

# master: repeat start
addr = 0x7e << 1 | 1
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
