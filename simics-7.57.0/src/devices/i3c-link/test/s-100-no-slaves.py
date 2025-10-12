# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

from common import *

# master - ep1
setup_no_slaves()

conf.link.cli_cmds.log_level(level=4)
conf.ep1.cli_cmds.log_level(level=4)
m = conf.master.object_data.reqs
m_ep = conf.ep1.iface.i3c_slave

expect(m, [])

m_ep.start(0x13)
expect(m, [])

c()
expect([m], [['ack', NACK]])

m_ep.stop()

c()
expect(m, [])
