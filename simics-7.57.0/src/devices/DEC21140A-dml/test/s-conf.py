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


# Test PCI configuration registers:
# This is only a superficial test of default configuration register values
# and that we can map the device registers into the memory space.
# In other words, it's mostly a test that the device interfaces well with PCI.

from common import *
from stest import expect_equal, fail

(eth, test_state) = create_config()
regs = dec_regs(eth)

# Verify default values of some configuration registers
default_values = {
    regs.cfid: 0x00091011,
    regs.cfcs: 0x02800000,
    regs.cfrv: 0x02000021,
    regs.cflt: 0x00000000,
    regs.cfit: 0x28140100,
    }

for reg in default_values:
    val = reg.read()
    if val != default_values[reg]:
        fail("conf reg %s: got 0x%x, expected 0x%x"
             % (reg.ofs, val, default_values[reg]))

# Map device registers into the memory space:

csr_base = 0xc3f97680
regs.cbma.write(csr_base)
expect_equal(regs.cbma.read(), csr_base)
regs.cfcs.mem = 1

# Verify that the bus got a request to map it
expect_equal(test_state.seq,
       [('add_map', eth.bank.csr, Sim_Addr_Space_Memory, None,
         csr_base, 0, 0x80)])
