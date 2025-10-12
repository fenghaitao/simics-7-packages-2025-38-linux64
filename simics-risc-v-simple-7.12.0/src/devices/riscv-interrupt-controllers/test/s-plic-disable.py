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
random.seed("The Killing Joke")

num_ctx = 3
tb = create_tb(num_ctx)

test_intids = [1, 2, 4, 6, 7]
max_prio = 0xfff

def sig_state(c):
    tgt = tb.plic.obj.irq_dev[c]
    if hasattr(tgt, 'state'):
        return tgt.state
    else:
        return tgt[0].state

for c in range(num_ctx):
    en = 0
    for i in range(1,32):
        if (i % num_ctx) == c:
            en |= 1 << i

    ctx = tb.plic.context(c)
    ctx.enable[0].write(en)

# Enabled in context intid % num_ctx, sufficient prio
for intid in test_intids:
    prio = random.randrange(max_prio)
    tb.plic.priority[intid].write(prio)

    # no signals raised
    for c in range(num_ctx):
        stest.expect_false(sig_state(c))

    # interrupt is signalled to enabled contexts
    tb.plic.obj.port.IRQ[intid].iface.signal.signal_raise()
    for c in range(num_ctx):
        if (intid % num_ctx) == c:
            stest.expect_true(sig_state(c))
        else:
            stest.expect_false(sig_state(c))

    # interrupt is pending
    stest.expect_equal(tb.plic.pending[intid // 32].read(), 1 << (intid % 32))

    # claim the interrupt
    stest.expect_equal(tb.plic.context(intid % num_ctx).claim.read(), intid)

    # nothing pending
    stest.expect_equal(tb.plic.pending[intid // 32].read(), 0)

    # no signals raised
    for c in range(num_ctx):
        stest.expect_false(sig_state(c))

    # complete interrupts
    tb.plic.obj.port.IRQ[intid].iface.signal.signal_lower()
    tb.plic.context(intid % num_ctx).claim.write(intid)

# Set one high signal that should stay when DISABLE is raised
intidx = 11
intidy = 27

tb.plic.priority[intidx].write(random.randrange(max_prio))
tb.plic.priority[intidy].write(random.randrange(max_prio))

# interrupt is signalled to the enabled context
tb.plic.obj.port.IRQ[intidx].iface.signal.signal_raise()
tb.plic.obj.port.IRQ[intidy].iface.signal.signal_raise()
for c in range(num_ctx):
    if (intidx % num_ctx) == c or (intidy % num_ctx) == c:
        stest.expect_true(sig_state(c))
    else:
        stest.expect_false(sig_state(c))

# interrupt is pending
stest.expect_true(tb.plic.pending[intidx // 32].read() & 1 << (intidx % 32))
stest.expect_true(tb.plic.pending[intidy // 32].read() & 1 << (intidy % 32))

# Claim intidy
ctxy = intidy % num_ctx
stest.expect_equal(tb.plic.context(intidy % num_ctx).claim.read(), intidy)

# Time to sleep
tb.plic.obj.port.CLOCK_DISABLE.iface.signal.signal_raise()

# interrupt is still pending but read access ignored while clock is disabled
stest.expect_equal(tb.plic.pending[intidx // 32].read(), 0)

# Yank some other signals that shouldn't change whats pending
for intid in test_intids:
    # interrupt is signalled to enabled contexts
    tb.plic.obj.port.IRQ[intid].iface.signal.signal_raise()
    for c in range(num_ctx):
        # Only ctx raised before DISABLE should be raised
        if (intidx % num_ctx) == c:
            stest.expect_true(sig_state(c))
        else:
            stest.expect_false(sig_state(c))

    # none of the intid's should be pending
    stest.expect_false(tb.plic.pending[intid // 32].read() & 1 << (intid % 32))

# Reenable plic, all signals raised during DISABLE should be handled
tb.plic.obj.port.CLOCK_DISABLE.iface.signal.signal_lower()

for intid in range(1, 31):
    isset = intid in test_intids or intid == intidx or intid == intidy

    # interrupt is signalled to enabled contexts
    for c in range(num_ctx):
        if isset and (intid % num_ctx) == c:
            stest.expect_true(sig_state(c))

    # all of the intid's should be pending except for the one that is already claimed
    if isset and not intid == intidy:
        stest.expect_true(tb.plic.pending[intid // 32].read() & 1 << (intid % 32))
    else:
        stest.expect_false(tb.plic.pending[intid // 32].read() & 1 << (intid % 32))

irqraised = set(test_intids) | set([intidx])

for i in irqraised:
    stest.expect_true(tb.plic.pending[i // 32].read() & 1 << (i % 32))

for r in range(4):
    for c in range(num_ctx):

        if sig_state(c):
            intid = tb.plic.context(c).claim.read()
            stest.expect_true(intid in irqraised)
            irqraised.remove(intid)

            # complete interrupts
            tb.plic.obj.port.IRQ[intid].iface.signal.signal_lower()
            tb.plic.context(c).claim.write(intid)

stest.expect_false(irqraised)

# no signals raised
for c in range(num_ctx):
    stest.expect_false(sig_state(c))

# intidy should still be active
stest.expect_true(tb.plic.obj.bank.regs.active[intidy // 32] & 1 << (intidy % 32))

# complete intidy
tb.plic.obj.port.IRQ[intidy].iface.signal.signal_lower()
tb.plic.context(intidy % num_ctx).claim.write(intidy)

# Check that reset are handled at the right in combination with disable

tb.plic.obj.port.IRQ[intidy].iface.signal.signal_raise()
tb.plic.obj.port.CLOCK_DISABLE.iface.signal.signal_raise()
tb.plic.obj.port.IRQ[intidx].iface.signal.signal_raise()
tb.plic.obj.port.HRESET.iface.signal.signal_raise()

# Reset lowerd before clock is enabled => no reset
tb.plic.obj.port.HRESET.iface.signal.signal_lower()
tb.plic.obj.port.CLOCK_DISABLE.iface.signal.signal_lower()

# context for intidx and intidy should be raised
for c in range(num_ctx):
    if (intidx % num_ctx) == c or (intidy % num_ctx) == c:
        stest.expect_true(sig_state(c))
    else:
        stest.expect_false(sig_state(c))

# Claim and complete intidy
stest.expect_equal(tb.plic.context(intidy % num_ctx).claim.read(), intidy)
tb.plic.obj.port.IRQ[intidy].iface.signal.signal_lower()
tb.plic.context(intidy % num_ctx).claim.write(intidy)

# Claim and complete intidx
stest.expect_equal(tb.plic.context(intidx % num_ctx).claim.read(), intidx)
tb.plic.obj.port.IRQ[intidx].iface.signal.signal_lower()
tb.plic.context(intidx % num_ctx).claim.write(intidx)

# Expect no raised context
for c in range(num_ctx):
    stest.expect_false(sig_state(c))

# next reset check
tb.plic.obj.port.IRQ[intidy].iface.signal.signal_raise()
tb.plic.obj.port.CLOCK_DISABLE.iface.signal.signal_raise()
tb.plic.obj.port.IRQ[intidx].iface.signal.signal_raise()
tb.plic.obj.port.HRESET.iface.signal.signal_raise()

# Reset lowerd after clock is enabled => reset
tb.plic.obj.port.CLOCK_DISABLE.iface.signal.signal_lower()
tb.plic.obj.port.HRESET.iface.signal.signal_lower()

# High IRQs still cause pending IRQs
stest.expect_true(tb.plic.pending[intidx // 32].read() & 1 << (intidy % 32))
stest.expect_true(tb.plic.pending[intidy // 32].read() & 1 << (intidy % 32))

# Nothing enabled so no outgoing signals
for c in range(num_ctx):
    stest.expect_false(sig_state(c))
