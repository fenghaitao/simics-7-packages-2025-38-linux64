# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import dev_util
import simics
from lpc_tb import *

run_command('log-level 4')

io_dec = dev_util.Register_LE(tb.lpc.bank.pci_config, 0x80, size = 2)
io_dec.write(0x0001) # map com1 to 0x3F8 and com2 to 0x2F8
lpc_en = dev_util.Register_LE(tb.lpc.bank.pci_config, 0x82, size = 2)
lpc_en.write(0x3) # Enable COMA and COMB

io_space = tb.io_space.iface.memory_space

# access NS16550 register
data = 0x34
io_space.write(None, 0x3fb, (data, ), 0)
expect_hex(tb.coms[0].regs_lcr, data, 'write to lcr register of com1')
io_space.write(None, 0x2fb, (data, ), 0)
expect_hex(tb.coms[1].regs_lcr, data, 'write to lcr register of com2')

io_dec.write(0x0075) # COMB: com3 to 0x3E8, COMA: com4 to 0x2E8

# interrupt test
irq3 = tb.lpc.ports.com3_in.signal
irq4 = tb.lpc.ports.com4_in.signal

irq3.signal_raise()
expect(tb.intc_state[tb.lpc.comb_level], 1, 'COM B interrupt raised')
irq3.signal_lower()
expect(tb.intc_state[tb.lpc.comb_level], 0, 'COM B interrupt lowered')

irq4.signal_raise()
expect(tb.intc_state[tb.lpc.coma_level], 1, 'COM A interrupt raised')
irq4.signal_lower()
expect(tb.intc_state[tb.lpc.coma_level], 0, 'COM A interrupt lowered')
