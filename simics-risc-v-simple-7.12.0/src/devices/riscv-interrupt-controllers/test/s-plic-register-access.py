# © 2019 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from riscv_intc_common import create_tb
from dev_util import MemoryError
import simics
import stest
import random
random.seed("Late Night Lover")

num_harts = 3
tb = create_tb(num_harts)
num_ctx = num_harts * 2  # MEIP & SEIP on each HART

# PRIORITY
for r in tb.plic.priority[1:]:
    stest.expect_equal(r.read(), 0)
    r.write(-1)
    stest.expect_equal(r.read(), 0xffffffff)

# PENDING
for r in tb.plic.pending:
    stest.expect_equal(r.read(), 0)
    with stest.expect_log_mgr(log_type='spec-viol'):
        r.write(-1)
    stest.expect_equal(r.read(), 0)

# CONTEXT registers:
for c in range(num_ctx):
    ctx = tb.plic.context(c)
    for r in ctx.enable + [ctx.threshold]:
        stest.expect_equal(r.read(), 0)
        r.write(-1)
        exp = 0xfffffffe if r == ctx.enable[0] else 0xffffffff
        stest.expect_equal(r.read(), exp)
    stest.expect_equal(ctx.claim.read(), 0)
    ctx.claim.write(42) # silently ignored
    stest.expect_equal(ctx.claim.read(), 0)

# Invalid CONTEXT
ctx = tb.plic.context(num_ctx)
for r in [ctx.enable[0], ctx.enable[31], ctx.threshold, ctx.claim]:
    with stest.expect_log_mgr(log_type = 'spec-viol'):
        with stest.expect_exception_mgr(MemoryError):
            r.read()
    with stest.expect_log_mgr(log_type = 'spec-viol'):
        with stest.expect_exception_mgr(MemoryError):
            r.write(-1)

# INVALID INTID
with stest.expect_log_mgr(log_type = 'spec-viol'):
    tb.plic.priority[0].read()
with stest.expect_log_mgr(log_type = 'spec-viol'):
    tb.plic.priority[0].write(-1)

# Configurable number of interrupts
tb.plic.obj.max_interrupt = 31
good = [tb.plic.priority[31], tb.plic.pending[0], tb.plic.context(0).enable[0]]
for r in good:
    r.read()
    if r not in tb.plic.pending:  # 'pending' is read-only
        r.write(-1)

bad = [tb.plic.priority[32], tb.plic.pending[1], tb.plic.context(0).enable[1]]
for r in bad:
    with stest.expect_log_mgr(log_type = 'spec-viol'):
        r.read()
    if r not in tb.plic.pending:  # 'pending' is read-only
        with stest.expect_log_mgr(log_type = 'spec-viol'):
            r.write(-1)

# number of interrupts doesn't have to be a multiple of 32
tb.plic.obj.max_interrupt = 35
tb.plic.context(0).enable[0].write(-1)
stest.expect_equal(tb.plic.context(0).enable[0].read(), 0xfffffffe)
tb.plic.context(0).enable[1].write(-1)
stest.expect_equal(tb.plic.context(0).enable[1].read(), 0b1111)

# Raising an unimplemented interrupt is a modeling error
p = tb.plic.obj.port.IRQ[36]
with stest.expect_log_mgr(log_type="error", obj=p):
    p.iface.signal.signal_raise()

# It's not possible to set pending bits that are not implemented, but
# let's fake that they are anyway by setting the backing attribute
tb.plic.obj.bank.regs.pending[1] = -1
stest.expect_equal(tb.plic.pending[1].read(), 0b1111)
tb.plic.obj.bank.regs.pending[1] = 0

# Discover max threshold and priority
bits = random.randrange(2, 32)
max_prio = (1 << bits) - 1
tb.plic.obj.max_priority = max_prio
for r in [tb.plic.priority[1], tb.plic.context(0).threshold]:
    r.write(0)
    stest.expect_equal(r.read(), 0)
    r.write(-1)
    stest.expect_equal(r.read(), max_prio)

# One context has lower maximum threshold
max_thr = (1 << (bits - 1)) - 1
tb.plic.obj.max_threshold = [0, max_thr]
exp_thr = [max_prio, max_thr, max_prio]
contexts = [tb.plic.context(c) for c in range(num_ctx)]
for thr, ctx in zip(exp_thr, contexts):
    ctx.threshold.write(0)
    stest.expect_equal(ctx.threshold.read(), 0)
    ctx.threshold.write(-1)
    stest.expect_equal(ctx.threshold.read(), thr)

# Lock bits in enable-registers
tb.plic.obj.max_interrupt = 1023
contexts = [tb.plic.context(c) for c in range(num_ctx)]
enable_set = [[random.randrange(1 << 32) for _ in range(32)] for _ in contexts]
enable_clr = [[random.randrange(1 << 32) for _ in range(32)] for _ in contexts]
tb.plic.obj.enable_set = enable_set
tb.plic.obj.enable_clr = enable_clr
for (ctx, setbits, clrbits) in zip(contexts, enable_set, enable_clr):
    for (r, s, c) in zip(ctx.enable, setbits, clrbits):
        if r == ctx.enable[0]:
            s &= 0xfffffffe  # interrupt 0 doesn't exist
        r.write(0)
        stest.expect_equal(r.read(), s & ~c)
        r.write(0xffffffff)
        stest.expect_true(r.read(), 0xffffffff & ~c)
