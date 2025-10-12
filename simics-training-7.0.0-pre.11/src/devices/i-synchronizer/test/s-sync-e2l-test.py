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

# Create an instance of the subsystem to test, 
# with the e2l devices
t = i_sync_common.create_test_subsystem(name="t",with_e2l=True)

# Logging on! 
cli.global_cmds.log_level(level=3)


##-----------------------------------------------------------
## 2. Test the synchronizer device with signal bus and e2l
##   
##    Assume the "sync-basic" test covers the basics
##-----------------------------------------------------------

# Get a dev util for the registers
tregs = dev_util.bank_regs(t.dev.bank.regs)

## Reset the synchronizer device to get the decrementer value
t.dev.port.reset.iface.signal.signal_raise()
t.dev.port.reset.iface.signal.signal_lower()

# Check all e2l initial state - should be not-signalling
# And they should not have signalled the connected device
for o in t.e2l:
    stest.expect_equal(o.attr.level_out_state,False)
    stest.expect_equal(o.irq_rec.attr.raise_count,0)

## Write once from each "processor"
## Knowing that the decrement register is mapped at 0x1000 + 0x1000 * i 
addr = 0x1004  # offset to decrementer register
for i in range(len(t.e2l)):
    t.memmap.cli_cmds.write(address=addr + (i * 0x1000),
                            value=0x1, size=4, _l=True)
# Check that we did hit the synchronizer device
stest.expect_equal(tregs.decrementer_value.read(), 0)

# Now we should get an interrupt and notifier in N cycles
#   Check that it was not triggered to early!
stest.expect_equal(t.notifier_rec.attr.notifier_seen, False)
stest.expect_equal(t.signal_bus.attr.level,0)

## Run for N cycles
cli.global_cmds.run(unit="cycles", count=t.dev.attr.irq_delay)

## Sync IRQ should trigger! 
# Check that the signal bus got the message to raise and lower
stest.expect_equal(t.signal_bus.attr.level,0)

# Check that all e2l got updated 
# And signalled their outbound IRQs high - but not yet lowered
for o in t.e2l:
    stest.expect_equal(o.attr.level_out_state,True)
    stest.expect_equal(o.irq_rec.attr.raise_count,1)
    stest.expect_equal(o.irq_rec.attr.lower_count,0)

# Check that the notifier got notified
stest.expect_equal(t.notifier_rec.notifier_seen, True)

# Check that IRQs can be lowered
for i in range(len(t.e2l)):
    addr = 0x10000 + (0x1000 * i)
    # check before lowering - duplicate with above, but that is OK
    stest.expect_equal(t.e2l[i].irq_rec.attr.lower_count,0)
    # Write to IRQ register
    t.memmap.cli_cmds.write(address=addr, value=0x1, size=4, _l=True)
    # Check that signal out was lowered
    stest.expect_equal(t.e2l[i].irq_rec.attr.lower_count,1)
    # And that the e2l device state is correct
    stest.expect_equal(t.e2l[i].attr.level_out_state,False)

#



