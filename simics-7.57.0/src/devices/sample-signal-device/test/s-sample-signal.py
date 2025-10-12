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


import stest
import dev_util as du
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

# A clock is needed for events
clock = SIM_create_object('clock', 'clock', freq_mhz=1)

# Create a signal device that can receive signals from our device
receiver = du.Dev([du.Signal], name = "receiver")

signal_conf = pre_conf_object('signal_dev', 'sample_signal_device_impl')
signal_conf.attr.period = 0.05
signal_conf.attr.count = 5
signal_conf.attr.queue = clock
signal_conf.attr.outgoing_receiver = receiver.obj

SIM_add_configuration([signal_conf], None)
signal_dev = conf.signal_dev

def incoming_raise():
    signal_dev.ports.incoming.signal.signal_raise()

def incoming_lower():
    signal_dev.ports.incoming.signal.signal_lower()

# Test incoming interrupts and that incount attribute is updated
def test_interrupts():
    for count in range(1, 4):
        stest.expect_log(incoming_raise, [], log_type = "info", msg = "RAISE")
        stest.expect_equal(signal_dev.attr.incount, count)
        stest.expect_log(incoming_lower, [], log_type = "info", msg = "LOWER")

# Test the event so that it outputs a periodical signal
def test_event():
    signal_dev.attr.out_level = 0  # Start with low level
    for count in range(signal_dev.attr.count):
        # Run until just after signal should have been raised
        run_command("run-seconds %f" % (signal_dev.attr.period / 2.0,))
        stest.expect_equal(receiver.signal.level, 1, "Signal should be raised")

        # Run until just after signal should have been lowered
        run_command("run-seconds %f" % (signal_dev.attr.period / 2.0,))
        stest.expect_equal(receiver.signal.level, 0, "Signal should be lowered")

    # Test the trigger_output attribute
    for signal_level in (1, 0):
        signal_dev.attr.trigger_output = 1
        stest.expect_equal(receiver.signal.level, signal_level,
                           "Trigger should %s" % ("raise" if signal_level
                                                  else "lower"))


test_interrupts()
test_event()

print("All tests passed.")
