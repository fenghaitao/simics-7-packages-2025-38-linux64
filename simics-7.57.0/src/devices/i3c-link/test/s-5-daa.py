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


# Test Dynamic Address Assignment process
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

# master: start_request, broadcast
addr = 0x7e << 1
m_ep.start(addr)

c()
expect([s, s3, m], [['start', addr], ['start', addr], []])

# slave: start_response
s_ep.acknowledge(ACK)
s3_ep.acknowledge(ACK)

c()
expect([s, s3, m], [[], [], ['ack', 0]])

# master: send ENTDAA Common Command Code
ccc_entdaa = b"%c" % 0x07
m_ep.sdr_write(ccc_entdaa)

c()
expect([s, s3, m], [['write', ccc_entdaa], ['write', ccc_entdaa], []])

# master: repeat start to assign dynamic address to the first slave
addr = 0x7e << 1 | 1
m_ep.start(addr)

c()
expect([s, s3, m], [['start', addr], ['start', addr], []])

# slave: start_response
s_ep.acknowledge(ACK)
s3_ep.acknowledge(ACK)

c()
expect([s, s3, m], [[], [], ['ack', 0]])

# master: signal daa read to slaves then slaves will send their daa data
m_ep.daa_read()

c()
expect([s, s3, m], [['daa_read'], ['daa_read'], []])

# slave: send daa data to master by daa_response(), forward the lowest to master
s_ep.daa_response(0xabcd >> 16, (0xabcd >> 8) & 0xff, 0xabcd & 0xff)
s3_ep.daa_response(0xcdef >> 16, (0xcdef >> 8) & 0xff, 0xcdef & 0xff)

c()
expect([s, s3, m], [[], [], ['daa_response',
                             0xabcd >> 16,
                             (0xabcd >> 8) & 0xff,
                             0xabcd & 0xff]])

# master: send assigned address to the slave who wins arbitration
m_ep.write(0x01)

c()
expect([s, s3, m], [['daa_address', 0x01], [], []])

# slave: ack the daa_address with ACK
s_ep.acknowledge(ACK)

c()
expect([s, s3, m], [[], [], ['ack', 0]])

# master: repeat start to assign dynamic address to the second slave
addr = 0x7e << 1 | 1
m_ep.start(addr)

c()
expect([s, s3, m], [['start', addr], ['start', addr], []])

# slave: start_response
s_ep.acknowledge(NACK)
s3_ep.acknowledge(ACK)

c()
expect([s, s3, m], [[], [], ['ack', 0]])

# master: signal daa read to slaves so that slaves will send their daa data
m_ep.daa_read()

c()
expect([s, s3, m], [[], ['daa_read'], []])

# slave: send daa data to master by daa_response()
s3_ep.daa_response(0xcdef >> 16, (0xcdef >> 8) & 0xff, 0xcdef & 0xff)

c()
expect([s, s3, m], [[], [], ['daa_response',
                             0xcdef >> 16,
                             (0xcdef >> 8) & 0xff,
                             0xcdef & 0xff]])

# master: send daa address to the selected slave
m_ep.write(0x03)

c()
expect([s, s3, m], [[], ['daa_address', 0x03], []])

# slave: ack the daa_address
s3_ep.acknowledge(ACK)

c()
expect([s, s3, m], [[], [], ['ack', 0]])

# master: stop
m_ep.stop()

c()
expect([s, s3, m], [['stop'], ['stop'], []])
