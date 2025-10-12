# © 2022 Intel Corporation
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
from simics import confclass

class frequency_provider:
    cls = confclass('frequency-provider')

    def __init__(self):
        self.frequency = 0.0

    def notify_new_frequency(self, obj, new_freq):
        self.frequency = new_freq
        simics.SIM_notify(obj, simics.Sim_Notify_Frequency_Change)

    @cls.iface.frequency.get
    def get(self):
        return self.frequency

cpu1 = simics.SIM_create_object('frequency-provider', None)
cpu2 = simics.SIM_create_object('frequency-provider', None)
for cpu in (cpu1, cpu2):
    simics.SIM_register_notifier(simics.SIM_object_class(cpu),
                                 simics.Sim_Notify_Frequency_Change, None)

notifier = simics.SIM_create_object('sample_notifier_dml', None,
                                    [['frequency_provider', cpu1]])

notified_frequencies = {}

def on_notify(obj, src, data):
    notified_frequencies[obj] = src.iface.frequency.get()

for cpu in (cpu1, cpu2):
    simics.SIM_add_notifier(notifier, simics.Sim_Notify_Frequency_Change,
                            cpu, on_notify, None)

def test_frequency_notification(cpu, freq, expected_multiplier):
    global notified_frequencies
    notified_frequencies = {}
    cpu.object_data.notify_new_frequency(cpu, freq)
    expected_freq = cpu.object_data.frequency * expected_multiplier
    stest.expect_equal(notified_frequencies, {cpu1: expected_freq,
                                              cpu2: expected_freq})

def test_frequency_notification_nonreactive(cpu):
    global notified_frequencies
    notified_frequencies = {}
    cpu.object_data.notify_new_frequency(cpu, cpu.object_data.frequency)
    stest.expect_equal(notified_frequencies, {})


# default multiplier should be 1
test_frequency_notification(cpu1, 8, 1)
notifier.multiplier = 3.0
# multiplier change should trigger notification.
stest.expect_equal(notified_frequencies, {cpu1: 8 * 3, cpu2: 8 * 3})
test_frequency_notification(cpu1, 10, 3)

# cpu2 notification should not trigger further notification, as it's not the
# frequency provider
test_frequency_notification_nonreactive(cpu2)

cpu2.object_data.frequency = 16.0
notifier.frequency_provider = cpu2
# frequency provider change should trigger notification.
stest.expect_equal(notified_frequencies, {cpu1: 16 * 3, cpu2: 16 * 3})
test_frequency_notification(cpu2, 32, 3)
# cpu1 notification should not trigger further notification, as it's no longer
# the frequency provider
test_frequency_notification_nonreactive(cpu1)
