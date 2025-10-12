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


from rtc_tb import *

# set nmi bit when write to register IO_INDEX
tb.set_nmi_bit()
# Select the 24-hour format
tb.write_io_le(rtc_io_index, 8, 0xB)
tb.write_io_le(rtc_io_data, 8, 0x2)

def do_test(bcd_or_binary, sec, min, hour, dow, dom, month, year):
    sec_add  = 6
    min_add  = 6
    hour_add = 6
    day_add  = 6

    time1 = [sec, min, hour, dow, dom, month, year]
    b_time1 = time1
    if bcd_or_binary == "bcd":
        b_time1 = bcd_to_binary(time1)

    b_time2 = add_time(b_time1, [sec_add, 0, 0, 0])
    b_time3 = add_time(b_time1, [sec_add, min_add, 0, 0])
    b_time4 = add_time(b_time1, [sec_add, min_add, hour_add, 0])
    b_time5 = add_time(b_time1, [sec_add, min_add, hour_add, day_add])

    if bcd_or_binary == "bcd":
        time2 = binary_to_bcd(b_time2)
        time3 = binary_to_bcd(b_time3)
        time4 = binary_to_bcd(b_time4)
        time5 = binary_to_bcd(b_time5)
    else:
        time2 = b_time2
        time3 = b_time3
        time4 = b_time4
        time5 = b_time5

    tb.enable_rtc(0)
    # Set the initial time of RTC
    tb.set_rtc(time1)
    # Select the binary or BCD format
    tb.write_io_le(rtc_io_index, 8, 0xB)
    regb_val = tb.read_io_le(rtc_io_data, 8)
    if bcd_or_binary == "bcd":
        regb_val = regb_val & 0xFB
    else:
        regb_val = regb_val | 0x04
    tb.write_io_le(rtc_io_index, 8, 0xB)
    tb.write_io_le(rtc_io_data, 8, regb_val)
    # Enable the RTC
    tb.enable_rtc(1)

    # Continue a length of added seconds and check the RTC time
    SIM_continue(int(sec_add * len_sec))
    real_time = tb.get_rtc()
    expect_list(real_time, time2, "the minute will advance %d scale" % sec_add)

    # Continue a length of added minutes and check the RTC time
    SIM_continue(int(min_add * len_min))
    real_time = tb.get_rtc()
    expect_list(real_time, time3, "the minute will advance %d scales" % min_add)

    # Continue a length of added hours and check the RTC time
    SIM_continue(int(hour_add * len_hour))
    real_time = tb.get_rtc()
    expect_list(real_time, time4, "the hour will advance %d scales" % hour_add)

    # Continue a length of added days and check the RTC time
    SIM_continue(int(day_add * len_day))
    real_time = tb.get_rtc()
    expect_list(real_time, time5, "the day will advance %d scales" % day_add)

do_test("bcd", 0x12, 0x12, 0x12, 4, 0x17, 7, 9) # 2009-7-17:12:12:12, Friday
do_test("binary", 13, 12, 12, 4, 17, 7, 9) # 2009-7-17:12:12:13, Friday
