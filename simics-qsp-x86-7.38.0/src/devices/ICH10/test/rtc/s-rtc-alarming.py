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


# s-rtc-alarming.py
# test the alarming function of the real-time clock
# in the LPC bridge in the ICH9 chip

from rtc_tb import *

def do_test():
    time1 = [0, 0, 0, 5, 1, 1, 0] # 2000-1-1, Saturday

    tb.irq.level = 0

    # Set the initial time of RTC
    tb.enable_rtc(0)
    tb.set_rtc(time1)

    # Enable the alarm interrupt
    tb.write_io_le(rtc_io_index, 8, 0xB)
    orig_regb = tb.read_io_le(rtc_io_data, 8)
    tb.write_io_le(rtc_io_index, 8, 0xB)
    tb.write_io_le(rtc_io_data, 8, orig_regb | 0x20)

    # Enable the RTC
    tb.enable_rtc(1)

    # Continue a length of one second and check the alarm interrupt
    tb.write_io_le(rtc_io_index, 8, 1)
    tb.write_io_le(rtc_io_data, 8, 1)
    SIM_continue(int(len_sec))
    raised = tb.irq.level
    expect(raised, 1, "a second alarm interrupt is raised")
    # Check and clear the interrupt flag
    tb.write_io_le(rtc_io_index, 8, 0xC)
    regc_val = tb.read_io_le(rtc_io_data, 8)
    expect(regc_val & 0xA0, 0xA0,
           "interrupt req and alarm flag in the flag reg")
    raised = tb.irq.level
    expect(raised, 0, "the second alarm interrupt is cleared")

    # Continue a length of one minute and check the alarm interrupt
    tb.write_io_le(rtc_io_index, 8, 3)
    tb.write_io_le(rtc_io_data, 8, 1)
    SIM_continue(int(len_min))
    raised = tb.irq.level
    expect(raised, 1, "a minute alarm interrupt is raised")
    # Check and clear the interrupt flag
    tb.write_io_le(rtc_io_index, 8, 0xC)
    regc_val = tb.read_io_le(rtc_io_data, 8)
    expect(regc_val & 0xA0, 0xA0,
           "interrupt req and alarm flag in the flag reg")
    raised = tb.irq.level
    expect(raised, 0, "the minute alarm interrupt is cleared")

    # Continue a length of one hour and check the alarm interrupt
    tb.write_io_le(rtc_io_index, 8, 5)
    tb.write_io_le(rtc_io_data, 8, 1)
    SIM_continue(int(len_hour))
    raised = tb.irq.level
    expect(raised, 1, "a hour alarm interrupt is raised")
    # Check and clear the interrupt flag
    tb.write_io_le(rtc_io_index, 8, 0xC)
    regc_val = tb.read_io_le(rtc_io_data, 8)
    expect(regc_val & 0xA0, 0xA0,
           "interrupt req and alarm flag in the flag reg")
    raised = tb.irq.level
    expect(raised, 0, "the hour alarm interrupt is cleared")

    # Continue a length of one day and check the alarm interrupt
    tb.write_io_le(rtc_io_index, 8, 0xD)
    tb.write_io_le(rtc_io_data, 8, 2)
    SIM_continue(int(len_day))
    raised = tb.irq.level
    expect(raised, 1, "a date alarm interrupt is raised")
    # Check and clear the interrupt flag
    tb.write_io_le(rtc_io_index, 8, 0xC)
    regc_val = tb.read_io_le(rtc_io_data, 8)
    expect(regc_val & 0xA0, 0xA0,
           "interrupt req and alarm flag in the flag reg")
    raised = tb.irq.level
    expect(raised, 0, "the date alarm interrupt is cleared")

do_test()
