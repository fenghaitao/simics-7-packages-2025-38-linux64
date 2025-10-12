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


# Test master read transaction
from common import *

# slave - ep1
# master - ep2
setup()

s = conf.slave.object_data.reqs
m = conf.master.object_data.reqs
m_ep = conf.ep2.iface.i3c_slave
s_ep = conf.ep1.iface.i3c_master

expect([s, m], [[], []])

# master: start_request with read address
m_ep.start(0x13)

c()
expect([s, m], [['start', 0x13], []])

# slave: start_response
s_ep.acknowledge(ACK)

c()
expect([s, m], [[], ['ack', ACK]])

# master: read_request
m_ep.read()

c()
expect([s, m], [['read'], []])

# slave: read_response
s_ep.read_response(0x7f, False)

c()
expect([s, m], [[], ['r_resp', 0x7f, False]])

# master: stop
m_ep.stop()

c()
expect([s, m], [['stop'], []])
