# © 2012 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Small test example for sample-event-device

import stest
import dev_util as du

# Create a clock for the timing needed for events
clock = SIM_create_object('clock', 'clock', freq_mhz=100)

# Create the sample event device with clock as queue
event_dev = SIM_create_object('sample_event_device', 'event_dev',
                              [['queue', clock]])

# The r1 register posts an event when writing to it
r1 = du.Register(event_dev.bank.regs, 0)

def post_event(cycles):
    r1.write(cycles)

# Test that event triggers and outputs logs.
def test_event():
    current_cycle = 0
    # Log at log-level 2 so that event log message is displayed.
    event_dev.log_level = 2
    event_dev.bank.regs.log_level = 2
    for time in (2, 4, 7):
        stest.expect_log(post_event, (time, ), log_type = 'info',
                         msg = 'posting event to trigger in %d cycles' % time)
        # Run to the cycle before the event should trigger.
        SIM_continue(time - 1)
        current_cycle += time
        # Run one more cycle and the event should trigger and produce a log
        stest.expect_log(SIM_continue, (1, ), log_type = 'info',
                         msg = ('event triggered, current time %d cycles'
                                % current_cycle))

test_event()

print("All tests passed.")
