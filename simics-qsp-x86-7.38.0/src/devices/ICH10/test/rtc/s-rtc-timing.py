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


# s-rtc-timing.py
# test the timing function of the real-time clock
# in the LPC bridge in the ICH9 chip

from rtc_tb import *
import cli

# test requires high latency to fast forward time quickly
cli.global_cmds.set_min_latency(count=1, unit="s")

def do_test():
    time1 = [0, 0, 0, 5, 1, 1, 0] # 2000-1-1, Saturday
    time2 = [0, 1, 0, 5, 1, 1, 0]
    time3 = [0, 0, 1, 5, 1, 1, 0]
    time4 = [0, 0, 0, 6, 2, 1, 0]
    time5 = [0, 0, 0, 5, 8, 1, 0]
    time6 = [0, 0, 0, 1, 1, 2, 0]
    #time7 = [0, 0, 0, 0, 1, 1, 1] # 2001-1-1, Monday

    tb.enable_rtc(0)
    # Set the initial time of RTC
    tb.set_rtc(time1)
    # Enable the RTC
    tb.enable_rtc(1)

    # Continue a length of one minute and check the RTC time
    SIM_continue(int(len_min))
    real_time = tb.get_rtc()
    expect_list(real_time, time2, "the minute will advance one scale")

    # Continue a length of one hour and check the RTC time
    SIM_continue(int(len_hour - len_min))
    real_time = tb.get_rtc()
    expect_list(real_time, time3, "the hour will advance one scale")

    # Continue a length of one day and check the RTC time
    SIM_continue(int(len_day - len_hour))
    real_time = tb.get_rtc()
    expect_list(real_time, time4, "the day will advance one scale")

    # Continue a length of one week and check the RTC time
    SIM_continue(int(len_week - len_day))
    real_time = tb.get_rtc()
    expect_list(real_time, time5, "the week will advance one scale")

    # Continue a length of the January and check the RTC time
    SIM_continue(int(len_jan - len_week))
    real_time = tb.get_rtc()
    expect_list(real_time, time6, "the January will advance to the February")

    # Continue a length of the year 2000 and check the RTC time,
    # commented now for it will breakdown the simics
    #SIM_continue(len_2000 - len_jan)
    #real_time = tb.get_rtc()
    #expect_list(real_time, time7, "the year 2000 will advance to 2001")


do_test()
