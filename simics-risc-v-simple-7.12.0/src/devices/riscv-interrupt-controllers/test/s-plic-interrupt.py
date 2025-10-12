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

test_intids = [1023, 1, random.randint(2,1022)]
max_prio = 0xffffffff

def sig_state(c):
    tgt = tb.plic.obj.irq_dev[c]
    if hasattr(tgt, 'state'):
        return tgt.state
    else:
        return tgt[0].state

# Enabled in all contexts, sufficient prio
for intid in test_intids:
    prio = random.randrange(max_prio)
    tb.plic.priority[intid].write(prio)

    for c in range(num_ctx):
        # Enable in all contexts
        ctx = tb.plic.context(c)
        ctx.enable[intid // 32].write(1 << (intid % 32))

    # no signals raised
    for c in range(num_ctx):
        stest.expect_false(sig_state(c))

    # interrupt is signalled to all contexts
    tb.plic.obj.port.IRQ[intid].iface.signal.signal_raise()
    for c in range(num_ctx):
        stest.expect_true(sig_state(c))

    # interrupt is pending
    stest.expect_equal(tb.plic.pending[intid // 32].read(), 1 << (intid % 32))

    # claim the interrupt
    stest.expect_equal(tb.plic.context(0).claim.read(), intid)

    # nothing pending
    stest.expect_equal(tb.plic.pending[intid // 32].read(), 0)

    # nothing to claim
    for c in range(0, num_ctx):
        stest.expect_equal(tb.plic.context(0).claim.read(), 0)

    # no signals raised
    for c in range(num_ctx):
        stest.expect_false(sig_state(c))

    # pulse the signal, intid is active so this is ignored
    tb.plic.obj.port.IRQ[intid].iface.signal.signal_lower()
    tb.plic.obj.port.IRQ[intid].iface.signal.signal_raise()

    # still nothing to claim
    for c in range(0, num_ctx):
        stest.expect_equal(tb.plic.context(0).claim.read(), 0)

    # disable in ctx0
    tb.plic.context(0).enable[intid // 32].write(0)

    # ctx0 can't complete the interrupt
    tb.plic.context(0).claim.write(intid)

    # but any other context can (weird but that's the spec)
    tb.plic.context(random.randrange(1, num_ctx)).claim.write(intid)

    # intid is active, but disabled in ctx0
    for c in range(num_ctx):
        if c == 0:
            stest.expect_false(sig_state(c))
        else:
            stest.expect_true(sig_state(c))

    # nothing to claim for ctx0
    stest.expect_equal(tb.plic.context(0).claim.read(), 0)

    # claim it in the last context
    stest.expect_equal(tb.plic.context(num_ctx - 1).claim.read(), intid)

    # nothing more to claim
    for c in range(0, num_ctx):
        stest.expect_equal(tb.plic.context(0).claim.read(), 0)

    # no signals raised
    for c in range(num_ctx):
        stest.expect_false(sig_state(c))

    # complete interrupt
    tb.plic.context(num_ctx - 1).claim.write(intid)

    # enable in ctx0
    tb.plic.context(0).enable[intid // 32].write(1 << (intid % 32))

    # intid is active
    for c in range(num_ctx):
        stest.expect_true(sig_state(c))

    # raise the threshold in some ctx
    ctx = tb.plic.context(random.randrange(num_ctx))
    ctx.threshold.write(prio)

    # intid is not signaled because of threshold
    for c in range(num_ctx):
        if c == ctx.index:
            stest.expect_false(sig_state(c))
        else:
            stest.expect_true(sig_state(c))

    # but we can still claim it
    stest.expect_equal(ctx.claim.read(), intid)

    # no signals raised
    for c in range(num_ctx):
        stest.expect_false(sig_state(c))

    # lower signal, complete interrupt and restore threshold
    tb.plic.obj.port.IRQ[intid].iface.signal.signal_lower()
    ctx.claim.write(intid)
    ctx.threshold.write(0)

    # still no signals raised
    for c in range(num_ctx):
        stest.expect_false(sig_state(c))


# Test some bad values, should be silently ignored
tb.plic.context(0).claim.write(0)
tb.plic.context(0).claim.write(-1)
tb.plic.context(0).claim.write(1024)
