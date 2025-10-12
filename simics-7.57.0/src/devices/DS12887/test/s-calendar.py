# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Test the DS12887 calendar functions, including alarm interrupts

from common import *
from stest import expect_equal, scratch_file

(ds, clk, pic_state) = create_config()
regs = ds_regs(ds)

def set_calendar(time):
    y, mon, d, wday, h, min, s = time
    regs.year.write(y)
    regs.month.write(mon)
    regs.day.write(d)
    regs.weekday.write(wday)
    regs.hour.write(h)
    regs.min.write(min)
    regs.sec.write(s)

def get_calendar():
    return [r.read() for r in (regs.year, regs.month, regs.day, regs.weekday,
                               regs.hour, regs.min, regs.sec)]

# test that the calendar is updated reasonably when time passes
def test_calendar():
    print("Testing calendar")

    regs.b.write(0x86)               # set time, binary format, 24 hour
    # set time to 1996-02-28 23:59:57 (Wednesday)
    set_calendar((96, 2, 28, 4, 23, 59, 57))
    regs.b.write(0x06)               # time has been set

    regs.a.write(0x20)               # turn on oscillator

    SIM_continue(5 * cpufreq)       # proceed 5 seconds

    # We now expect time to be 1996-02-29 00:00:02 (Thursday)
    expect_equal(get_calendar(), [96, 2, 29, 5, 0, 0, 2])

# test that alarms raise interrupts correctly
def test_alarm():
    print("Testing alarm")

    regs.b.write(0x80)               # set time, BCD format, 12 hour
    # set time to 1969-07-20 20:17:40 (Sunday)
    set_calendar((0x69, 0x07, 0x20, 1, 0x88, 0x17, 0x40))
    # set alarm to 21:09:38
    regs.hour_alarm.write(0x89)
    regs.min_alarm.write(0x09)
    regs.sec_alarm.write(0x38)
    regs.b.write(0x24)               # time has been set, enable alarm

    regs.a.write(0x20)               # turn on oscillator

    pic_state.seq = []
    c0 = SIM_cycle_count(clk)
    SIM_continue(3600 * cpufreq)    # proceed 1 hour

    # Reading register C will clear interrupts as a side-effect
    c = regs.c.read()
    expect_equal(c & 0xa0, 0xa0)

    # Calculate what cycle we expect the alarm interrupt to be raised in
    alarm_seconds = 3600 - 8 * 60 - 2   # seconds to set alarm
    alarm_cycle = c0 + alarm_seconds * cpufreq
    alarm_cycle -= cpufreq * 0.5     # update starts 500 ms after enabling osc.
    alarm_cycle += cpufreq * 244 / 1000000 # 244 us periodic update delay
    now = SIM_cycle_count(clk)

    # Check that the device emitted interrupt edges at the correct cycles
    expect_equal(pic_state.seq, [(1, 17, alarm_cycle), (0, 17, now)])

# test that the calendar supports persistent save/load functionality
def test_persistent_state():
    print("Testing persistent state")

    # setup calendar (see test_calendar() for reference)
    regs.b.write(0x86)
    origin = [96, 2, 28, 4, 23, 59, 57]
    set_calendar(origin)
    regs.b.write(0x06)
    regs.a.write(0x20)

    # save persistent state
    state_file = scratch_file('state')
    SIM_run_command('save-persistent-state %s' %state_file)

    # proceed 5 seconds, or just enough to get a new time
    SIM_continue(5 * cpufreq)

    # restore the persistent state and compare calendar
    SIM_run_command('load-persistent-state %s' %state_file)
    expect_equal(get_calendar(), origin)


test_calendar()
test_alarm()
test_persistent_state()
