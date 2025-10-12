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


# Test RTC by doing programming which triggered SIMICS-13195 bug

from rtc_tb import *

def do_test(time, timestr):
    time_bcd_12h = binary_to_bcd(time_to_12h(time))

    tb.enable_rtc(0)

    # Set data mode to binary and hour format to twenty-four hour mode:
    # this is intentionally and will be changed later
    tb.write_io_le(rtc_io_index, 8, 0xB)
    orig_regb = tb.read_io_le(rtc_io_data, 8)
    tb.write_io_le(rtc_io_index, 8, 0xB)
    tb.write_io_le(rtc_io_data, 8, orig_regb | 0b110)

    # Set the initial time of RTC
    tb.set_rtc(time_bcd_12h)

    # Set correct data mode (BCD) and hour format (twelve-hour mode)
    tb.write_io_le(rtc_io_index, 8, 0xB)
    orig_regb = tb.read_io_le(rtc_io_data, 8)
    tb.write_io_le(rtc_io_index, 8, 0xB)
    tb.write_io_le(rtc_io_data, 8, orig_regb & 0xf9)

    # Enable the RTC
    tb.enable_rtc(1)

    stest.expect_equal(tb.rtc.time, timestr)

from datetime import timedelta, datetime

def gen_daterange_day_step(start, end):
    for n in range(int((end - start).days) + 1):
        yield start + timedelta(days=n)

def gen_daterange_second_step(start):
    for n in range(60*60*24+1):
        yield start + timedelta(seconds=n)

start_dt = datetime(2015, 12, 20)
end_dt = datetime(2020, 12, 25)

for dt in gen_daterange_day_step(start_dt, end_dt):
    do_test(
        [dt.second, dt.minute, dt.hour, dt.weekday(),
         dt.day, dt.month, dt.year % 100],
        dt.strftime("%y-%m-%d %H:%M:%S")
    )

for dt in gen_daterange_second_step(start_dt):
    do_test(
        [dt.second, dt.minute, dt.hour, dt.weekday(),
         dt.day, dt.month, dt.year % 100],
        dt.strftime("%y-%m-%d %H:%M:%S")
    )
