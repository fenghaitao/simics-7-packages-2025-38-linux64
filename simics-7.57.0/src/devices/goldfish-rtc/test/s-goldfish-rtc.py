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

import time

import simics
import conf
import dev_util
from stest import expect_equal, expect_false, expect_true

class fake_signal_target:
    cls = simics.confclass('fake-signal-target')
    cls.attr.state('b', default=False)

    @cls.iface.signal.signal_raise
    def signal_raise(self):
        expect_false(self.state, "signal raised when already high")
        self.state = True

    @cls.iface.signal.signal_lower
    def signal_lower(self):
        expect_true(self.state, "signal lowered when already low")
        self.state = False

clock = simics.pre_conf_object("clock", "clock")
clock.freq_mhz = 2000

timer = simics.pre_conf_object("timer", "goldfish-rtc")
timer.queue = clock
timer.irq_dev = simics.SIM_create_object("fake-signal-target", "irq_dev", [])
initial_time = int(time.time())
timer.attr.initial_time = initial_time

simics.SIM_add_configuration([clock, timer], None)
timer = conf.timer

regs = dev_util.bank_regs(timer.bank.regs)

NS_PER_SECOND = 1000 * 1000 * 1000
cycles_per_ns = clock.freq_mhz // 1000
cycles_per_second = clock.freq_mhz * 1000 * 1000

# Define registers here to be able to generate 32-bit transactions even though
# the registers in the model are 64-bit.
time_low = dev_util.Register_LE(timer.bank.regs, 0x00, size=4)
time_high = dev_util.Register_LE(timer.bank.regs, 0x04, size=4)
alarm_low = dev_util.Register_LE(timer.bank.regs, 0x08, size=4)
alarm_high = dev_util.Register_LE(timer.bank.regs, 0x0C, size=4)


def low32(n):
    return n & 0xFFFF_FFFF


def high32(n):
    return n >> 32


def hreset():
    timer.port.HRESET.iface.signal.signal_raise()
    timer.port.HRESET.iface.signal.signal_lower()


def test_time_low_updates_time_high():
    """time_high is not updated until time_low is read"""
    hreset()
    now_ns = initial_time * NS_PER_SECOND + int(simics.SIM_time(timer) * NS_PER_SECOND)

    expect_equal(time_low.read(), low32(now_ns))

    # advance the clock by 2^32 ns so that time_low is the same and time_high is incremented by 1
    simics.SIM_continue(2**32 * cycles_per_ns)

    # time_high is not updated since the write because time_low has not been read yet
    expect_equal(time_high.read(), high32(now_ns))

    expect_equal(time_low.read(), low32(now_ns))
    expect_equal(time_high.read(), high32(now_ns) + 1)


def test_write_read_time():
    """time read is the written time plus the current sim time"""
    hreset()
    now_ns = int(simics.SIM_time(timer) * NS_PER_SECOND)

    time_high.write(high32(5 * NS_PER_SECOND))
    time_low.write(low32(5 * NS_PER_SECOND))

    expected = now_ns + 5 * NS_PER_SECOND

    simics.SIM_continue(1 * cycles_per_ns)

    expect_equal(time_low.read(), low32(expected + 1))
    expect_equal(time_high.read(), high32(expected))


def test_immediate_alarm():
    """setting the alarm to the current time should trigger the alarm immediately"""
    hreset()
    current_time = time_low.read()
    current_time |= time_high.read() << 32

    regs.irq_enabled.write(1)
    alarm_high.write(high32(current_time))
    expect_false(timer.irq_dev.state)
    alarm_low.write(low32(current_time))
    simics.SIM_continue(1)  # necessary for the immediate after statement to execute?
    expect_true(timer.irq_dev.state)


def test_future_alarm(irq):
    """test setting an alarm in the future"""
    print("test_future_alarm irq:", irq)
    hreset()
    current_time = time_low.read()
    current_time |= time_high.read() << 32
    alarm_time = current_time + 1 * NS_PER_SECOND

    alarm_high.write(high32(alarm_time))
    alarm_low.write(low32(alarm_time))
    regs.irq_enabled.write(1 if irq else 0)

    # advance simulation to 1 cycle before the alarm should trigger
    simics.SIM_continue(1 * cycles_per_second - 1)

    expect_equal(regs.alarm_status.read(), 1)
    expect_false(timer.irq_dev.state)

    simics.SIM_continue(1)

    if irq:
        expect_true(timer.irq_dev.state)
        regs.clear_interrupt.write(1)
    expect_false(timer.irq_dev.state)
    expect_equal(regs.alarm_status.read(), 0)


def test_clear_alarm():
    """set an alarm, then clear it and verify that it does not trigger"""
    hreset()
    current_time = time_low.read()
    current_time |= time_high.read() << 32
    alarm_time = current_time + 2

    regs.irq_enabled.write(1)
    alarm_high.write(high32(alarm_time))
    alarm_low.write(low32(alarm_time))
    simics.SIM_continue(1)
    expect_equal(regs.alarm_status.read(), 1)
    regs.clear_alarm.write(1)
    expect_equal(regs.alarm_status.read(), 0)
    expect_false(timer.irq_dev.state)
    simics.SIM_continue(2 * cycles_per_ns)
    expect_false(timer.irq_dev.state)


def test_hreset():
    """hreset should reset all registers, set the time to the initial_time
    attribute and cancel any running alarms"""
    time_high.write(high32(5 * NS_PER_SECOND))
    time_low.write(low32(5 * NS_PER_SECOND))
    current_time = time_low.read()
    current_time |= time_high.read() << 32
    regs.irq_enabled.write(1)
    alarm_high.write(high32(current_time))
    alarm_low.write(low32(current_time))

    # let alarm trigger
    simics.SIM_continue(1)

    # set new alarm in the future
    alarm_time = current_time + 2
    alarm_high.write(high32(alarm_time))
    alarm_low.write(low32(alarm_time))

    # continue until time is different, but before the alarm would trigger
    simics.SIM_continue(1 * cycles_per_ns)
    now_ns = int(simics.SIM_time(timer) * NS_PER_SECOND)

    # irq should still be active since last alarm triggered
    expect_equal(timer.bank.regs.irq_pending, True)

    hreset()
    expect_false(timer.irq_dev.state)
    expect_equal(time_high.read(), 0)
    expect_equal(time_low.read(), low32(initial_time * NS_PER_SECOND + now_ns))
    expect_equal(alarm_high.read(), 0)
    expect_equal(alarm_low.read(), 0)
    expect_equal(regs.irq_enabled.read(), 0)
    expect_equal(regs.alarm_status.read(), 0)
    expect_equal(timer.bank.regs.irq_pending, False)

    # continue until the alarm would trigger if still active
    simics.SIM_continue(1 * cycles_per_ns)
    expect_equal(timer.bank.regs.irq_pending, False)


timer.cli_cmds.log_level(level=4)
test_hreset()
test_time_low_updates_time_high()
test_write_read_time()
test_immediate_alarm()
test_future_alarm(irq=False)
test_future_alarm(irq=True)
test_clear_alarm()
