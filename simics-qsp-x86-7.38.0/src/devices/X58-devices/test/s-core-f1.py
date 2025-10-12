# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import simics
import stest
from dev_util import Register_LE
import random
random.seed("Xerxes")

dev = simics.SIM_create_object('x58-core', 'dev', [])
scratch = [Register_LE(dev.bank.f1, 0x7c + i * 4) for i in range(24)]
conditional = [Register_LE(dev.bank.f1, 0xdc + i * 4 + (4 if i > 8 else 0))
               for i in range(24)]
increment = [Register_LE(dev.bank.f1, 0x140 + i * 4) for i in range(24)]

for (sr, cwr, ir) in zip(scratch, conditional, increment):
    stest.expect_equal(sr.read(), 0)
    val = random.randrange(1 << 32)
    cwr.write(val)
    stest.expect_equal(sr.read(), val)
    stest.expect_equal(cwr.read(), val)

    cwr.write(~val)  # does not bite because sr is nonzero
    stest.expect_equal(sr.read(), val)
    stest.expect_equal(cwr.read(), val)

    stest.expect_equal(ir.read(), val)
    stest.expect_equal(sr.read(), val + 1)
    stest.expect_equal(cwr.read(), val + 1)
    ir.write(random.randrange(1 << 32))
    stest.expect_equal(sr.read(), val + 2)
    stest.expect_equal(cwr.read(), val + 2)

    sr.write(0)
