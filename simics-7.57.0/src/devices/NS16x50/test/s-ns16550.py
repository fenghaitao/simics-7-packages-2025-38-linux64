# © 2011 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import common_test as c

config = c.TestConfig('NS16550')
regs = c.UartRegs(config.uart)

c.test_read_only_regs(config.uart, regs, True)
c.test_soft_reset(config.uart, regs)
c.test_hard_reset(config.uart, regs)
c.test_receive(config, regs)
c.test_transmit(config, regs)
c.test_recv_fifo(config, regs)
c.test_xmit_fifo(config, regs)
