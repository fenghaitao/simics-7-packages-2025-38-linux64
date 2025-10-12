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


# Test master write transaction
from common import *

# slave - ep1
# master - ep2
setup()

s = conf.slave.object_data.reqs
m = conf.master.object_data.reqs
m_ep = conf.ep2.iface.i3c_slave
s_ep = conf.ep1.iface.i3c_master

expect([s, m], [[], []])

# master: start_request with write address
m_ep.start(0x12)

c()
expect([s, m], [['start', 0x12], []])

# slave: start_response
s_ep.acknowledge(ACK)

c()
expect([s, m], [[], ['ack', 0]])

# master: write_request
m_ep.sdr_write(b"%c" % 0x7f)

c()
expect([s, m], [['write', b"%c" % 0x7f], []])

# master: stop
m_ep.stop()

c()
expect([s, m], [['stop'], []])
