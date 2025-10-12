# © 2024 Intel Corporation
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
import conf
import stest
import i_sync_common

# Create an instance of the subsystem to test
t = i_sync_common.create_test_subsystem(name="t")

# Logging on! 
cli.global_cmds.log_level(level=3)

##-----------------------------------------------------------
## 1. Test the synchronizer device in isolation
## 
## i.e., without using the signal bus and endpoint devices
##-----------------------------------------------------------

# Get a dev util for the registers
tregs = dev_util.bank_regs(t.dev.bank.regs)

## Check that reset sets the decrementer register 
## to the same value as the configured number of subsystems
numss = t.dev.attr.num_sub_systems
stest.expect_equal(tregs.decrementer_value.read(), 0)
t.dev.port.reset.iface.signal.signal_raise()
t.dev.port.reset.iface.signal.signal_lower()
stest.expect_equal(tregs.decrementer_value.read(), numss)

## Write the decrementer register N times
##  The value should not matter
tregs.decrement.write(1)
stest.expect_equal(tregs.decrementer_value.read(), numss-1)
tregs.decrement.write(0)
stest.expect_equal(tregs.decrementer_value.read(), numss-2)
tregs.decrement.write(0xabba_cddc)
stest.expect_equal(tregs.decrementer_value.read(), numss-3)
# Finish up 
for i in range(numss-3):
    tregs.decrement.write(0xffff_ffff)
stest.expect_equal(tregs.decrementer_value.read(), 0)

# Now we should get an interrupt and notifier in N cycles
#   Check that it was not triggered to early!
stest.expect_equal(t.notifier_rec.notifier_seen, False)
stest.expect_equal(t.irq_rec.raise_count,0)

cli.global_cmds.run(unit="cycles", count=t.dev.attr.irq_delay)

# Check correct behavior of IRQ: fire an edge, i.e., raise and lower
stest.expect_equal(t.irq_rec.raise_count,1)
stest.expect_equal(t.irq_rec.lower_count,1)

# Check that the notifier got notified
stest.expect_equal(t.notifier_rec.notifier_seen, True)






