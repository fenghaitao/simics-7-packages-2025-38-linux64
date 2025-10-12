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

# A variant of s-1-read, but de/serialization is tested for every message sent
from stest import expect_equal
from common import *

def expect_message(sender_ep, receiver_ep, kind, status, data=()):
    # test that the queue can be de/serialized
    orig = list(receiver_ep.attr.delivery_queue)
    receiver_ep.attr.delivery_queue = []
    expect_equal(receiver_ep.attr.delivery_queue, [])
    receiver_ep.attr.delivery_queue = orig

    # test the expectation
    expect_equal(len(receiver_ep.delivery_queue), 1)
    [[_, _, msg]] = receiver_ep.attr.delivery_queue
    expect_equal(msg, [sender_ep.attr.id, kind, status, data])

# Taken from internal enum i3c_link_action_type_t
start_request = 0
start_response = 1
read_request = 2
read_response = 3
stop = 11

# slave - ep1
# master - ep2
setup()

s = conf.slave.object_data.reqs
m = conf.master.object_data.reqs
m_ep = conf.ep2
s_ep = conf.ep1
m_ep_i = m_ep.iface.i3c_slave
s_ep_i = s_ep.iface.i3c_master

expect([s, m], [[], []])

# master: start_request with read address
m_ep_i.start(0x13)
expect_message(m_ep, s_ep, start_request, 0x13)

c()
expect_equal(s_ep.attr.delivery_queue, [])
expect([s, m], [['start', 0x13], []])

# slave: start_response
s_ep_i.acknowledge(ACK)
expect_message(s_ep, m_ep, start_response, ACK)

c()
expect([s, m], [[], ['ack', ACK]])

# master: read_request
m_ep_i.read()
expect_message(m_ep, s_ep, read_request, 0)

c()
expect([s, m], [['read'], []])

# slave: read_response
s_ep_i.read_response(0x7f, False)
expect_message(s_ep, m_ep, read_response, False, (0x7f,))

c()
expect([s, m], [[], ['r_resp', 0x7f, False]])

# master: stop
m_ep_i.stop()
expect_message(m_ep, s_ep, stop, 0)

c()
expect([s, m], [['stop'], []])
