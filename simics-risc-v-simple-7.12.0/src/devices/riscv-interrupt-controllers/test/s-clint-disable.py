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
import simics
import stest
import random
random.seed("Poppy")

tb = create_tb(num_harts=7)

harts = [h.obj for h in tb.harts]

# SIM_run_command("clint.log-level -r 3")

for (hart, mtimecmp) in zip(tb.harts, tb.clint.mtimecmp):
    mtimecmp.write(-1)

# Test normal MTIP
for (hart, mtimecmp) in zip(tb.harts, tb.clint.mtimecmp):
    stest.expect_false(hart.obj.port.MTIP.state)
    count = random.randint(1, 1000)
    mtimecmp.write(tb.clint.mtime.read() + count)
    stest.expect_false(hart.obj.port.MTIP.state)
    simics.SIM_continue(count - 1)
    stest.expect_false(hart.obj.port.MTIP.state)
    simics.SIM_continue(1)
    stest.expect_true(hart.obj.port.MTIP.state)

# Setup mtimecmp to soon
for (hart, mtimecmp) in zip(tb.harts, tb.clint.mtimecmp):
    mtimecmp.write(tb.clint.mtime.read() + 10)

now = tb.clint.mtime.read()
tb.clint.obj.port.CLOCK_DISABLE.iface.signal.signal_raise()

# Continue way more than 'soon'
simics.SIM_continue(100000)

# register accesses are ignored
stest.expect_equal(0, tb.clint.mtime.read())
stest.expect_equal(now, tb.clint.obj.bank.regs.mtime)

# Verify that no MTIP has fired
for (hart, mtimecmp) in zip(tb.harts, tb.clint.mtimecmp):
    stest.expect_false(hart.obj.port.MTIP.state)

tb.clint.obj.port.CLOCK_DISABLE.iface.signal.signal_lower()
stest.expect_equal(now, tb.clint.mtime.read())

simics.SIM_continue(8)

# Verify that no MTIP has fired
for (hart, mtimecmp) in zip(tb.harts, tb.clint.mtimecmp):
    stest.expect_false(hart.obj.port.MTIP.state)

for (hart, mtimecmp) in zip(tb.harts, tb.clint.mtimecmp):
    mtimecmp.write(-1)

# Verify normal behaviour again
for (hart, mtimecmp) in zip(tb.harts, tb.clint.mtimecmp):
    stest.expect_false(hart.obj.port.MTIP.state)
    count = random.randint(1, 1000)
    now = tb.clint.mtime.read()
    mtimecmp.write(now + count)
    stest.expect_false(hart.obj.port.MTIP.state)
    simics.SIM_continue(count - 1)
    stest.expect_false(hart.obj.port.MTIP.state)
    simics.SIM_continue(20)
    stest.expect_true(hart.obj.port.MTIP.state)

# Check that reset are handled at the right moment
now = tb.clint.mtime.read()
tb.clint.obj.port.CLOCK_DISABLE.iface.signal.signal_raise()

simics.SIM_continue(100000)

tb.clint.obj.port.HRESET.iface.signal.signal_raise()

simics.SIM_continue(100000)

# Reset lowerd before clock is enabled => no reset
tb.clint.obj.port.HRESET.iface.signal.signal_lower()

tb.clint.obj.port.CLOCK_DISABLE.iface.signal.signal_lower()
stest.expect_equal(now, tb.clint.mtime.read())

simics.SIM_continue(100)

now = tb.clint.mtime.read()
tb.clint.obj.port.CLOCK_DISABLE.iface.signal.signal_raise()

simics.SIM_continue(100000)

tb.clint.obj.port.HRESET.iface.signal.signal_raise()

simics.SIM_continue(100000)

# Reset lowerd after clock is enabled => reset
tb.clint.obj.port.CLOCK_DISABLE.iface.signal.signal_lower()
tb.clint.obj.port.HRESET.iface.signal.signal_lower()
stest.expect_equal(0, tb.clint.mtime.read())
