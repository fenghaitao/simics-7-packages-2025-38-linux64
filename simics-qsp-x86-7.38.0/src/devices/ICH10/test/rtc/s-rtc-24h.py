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


# s-rtc-24h.py
# test the 24-hour or 12-hour format of the real-time clock
# in the LPC bridge in the ICH9 chip

from rtc_tb import *

def do_test(hour):
    add_hours = 3
    time1 = [1, 13, hour, 4, 17, 7, 9] # 2009-7-17:x-13:01, Friday
    time1_12h = time_to_12h(time1)

    time2 = add_time(time1, [0, 0, add_hours, 0])
    time2_12h = time_to_12h(time2)

    tb.enable_rtc(0)
    # Set the initial time of RTC
    tb.set_rtc(time1)
    # Select the binary 24-hour format
    tb.write_io_le(rtc_io_index, 8, 0xB)
    regb_val = tb.read_io_le(rtc_io_data, 8)
    regb_val = regb_val | 0x06
    tb.write_io_le(rtc_io_index, 8, 0xB)
    tb.write_io_le(rtc_io_data, 8, regb_val)
    # Enable the RTC
    tb.enable_rtc(1)

    SIM_continue(int(add_hours * len_hour))

    real_time = tb.get_rtc()
    expect_list(real_time, time2, "the time in 24-hour format")


    # Set the initial time of RTC
    tb.enable_rtc(0)
    # Select the binary 12-hour format
    tb.write_io_le(rtc_io_index, 8, 0xB)
    regb_val = tb.read_io_le(rtc_io_data, 8)
    regb_val = regb_val & 0xFD
    tb.write_io_le(rtc_io_index, 8, 0xB)
    tb.write_io_le(rtc_io_data, 8, regb_val)
    tb.set_rtc(time1_12h)
    # Enable the RTC
    tb.enable_rtc(1)
    real_time = tb.get_rtc()
    expect_list(real_time, time1_12h, "the time (%d) in 12-hour format" % hour)
    SIM_continue(int(add_hours * len_hour))
    real_time = tb.get_rtc()
    expect_list(real_time, time2_12h, "the time (%d + 3) in 12-hour format" % hour)

for i in range(24):
    do_test(i)
