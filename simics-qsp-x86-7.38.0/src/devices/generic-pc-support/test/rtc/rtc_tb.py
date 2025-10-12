# © 2025 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# lpc_tb.py
# testbench of SMBus Low Pin Controller devices in ICH9

import pyobj
import simics
import stest
import dev_util
import conf

# SIMICS-21543
#conf.sim.deprecation_level = 0

rtc_io_index    = 0x70
rtc_io_data     = 0x71
rtc_io_index_alias  = rtc_io_index + 4
rtc_io_data_alias   = rtc_io_data  + 4

rtc_reg_cnt     = 14
rtc_int_level   = 8

lpc_timer_mhz       = 1000. / 838.

# Real-time clock constants
secs_of_min     = 60
secs_of_hour    = secs_of_min * 60
secs_of_day     = secs_of_hour * 24
secs_of_week    = secs_of_day * 7
secs_of_jan     = secs_of_day * 31
secs_of_2000    = secs_of_day * (31 + 29 + 31 + 30 + 31 + 30
                               + 31 + 31 + 30 + 31 + 30 + 31)
len_sec         = 1 * lpc_timer_mhz * 1000000
len_min         = secs_of_min * lpc_timer_mhz * 1000000
len_hour        = secs_of_hour * lpc_timer_mhz * 1000000
len_day         = secs_of_day * lpc_timer_mhz * 1000000
len_week        = secs_of_week * lpc_timer_mhz * 1000000
len_jan         = secs_of_jan * lpc_timer_mhz * 1000000
len_2000        = secs_of_2000 * lpc_timer_mhz * 1000000

days = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def bcd_num_to_binary(val):
    high_digit = val >> 4
    low_digit = val & 0xF
    assert low_digit < 10, "BCD digit must be less than 10"
    assert high_digit < 10, "BCD digit must be less than 10"
    return high_digit * 10 + low_digit

def binary_num_to_bcd(val):
    assert val < 100, "1-byte BCD max number is 99"
    low_4bit = val % 10
    high_4bit = val // 10
    return (high_4bit << 4) + low_4bit

def bcd_to_binary(list_val):
    list_val = list(list_val)  # don't modify argument: make a copy of it
    hour = list_val.pop(2)  # hour may have PM (bit7) set so handle it specially
    ret_val = [bcd_num_to_binary(i) for i in list_val]
    ret_val.insert(2, (hour & 0x80) | bcd_num_to_binary(hour & 0x7f))
    return ret_val

def binary_to_bcd(list_val):
    list_val = list(list_val)  # don't modify argument: make a copy of it
    hour = list_val.pop(2)  # hour may have PM (bit7) set so handle it specially
    ret_val = [binary_num_to_bcd(i) for i in list_val]
    ret_val.insert(2, (hour & 0x80) | binary_num_to_bcd(hour & 0x7f))
    return ret_val

def days_in_month(year, month):
    if month == 2 and (year % 4) == 0:
        return 29
    else:
        return days[month - 1]

def print_time(time_list):
    [sec, min, hour, dow, dom, mon, year] = time_list
    print("Time: 20%02d-%d-%d:%02d:%02d:%02d, %s" \
          % (year, mon, dom, hour, min, sec, \
             ["Monday", "Tuesday", "Wednesday", "Thursday", \
              "Friday", "Saturday", "Sunday"][dow]))

def add_time(time_list, add_time_list):
    # time_list is like: [sec, min, hour, dow, dom, mon, year]
    # add_time_list is like: [seconds, minutes, hours, days]
    new_sec = time_list[0] + add_time_list[0]
    carry = 0
    if new_sec >= 60:
        carry = 1
        new_sec = new_sec - 60
    new_min = time_list[1] + add_time_list[1] + carry

    carry = 0
    if new_min >= 60:
        carry = 1
        new_min = new_min - 60
    new_hour = time_list[2] + add_time_list[2] + carry

    carry = 0
    if new_hour >= 24:
        carry = 1
        new_hour = new_hour - 24
    new_dom = time_list[4] + add_time_list[3] + carry
    new_dow = (time_list[3] + add_time_list[3] + carry) % 7

    carry = 0
    days = days_in_month(time_list[6], time_list[5])
    if new_dom > days:
        carry = 1
        new_dom -= days
    new_month = time_list[5] + carry
    new_year = time_list[6]

    if new_month > 12:
        new_year = new_year + 1
        new_month = 1
    return [new_sec, new_min, new_hour, new_dow, new_dom, new_month, new_year]

def time_to_12h(time_list):
    hour = time_list[2]
    assert hour <= 23, "Too large hour value"
    if hour == 0:
        h_12h = 12  # midnight is 12 a.m. not 0
    elif hour < 12:
        h_12h = hour
    elif hour == 12:
        h_12h = hour + 0x80
    else:
        h_12h = (hour % 12) + 0x80
    return [time_list[0], time_list[1], h_12h,
            time_list[3], time_list[4], time_list[5], time_list[6]]

class TimerOutSignal(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()
        self.level = 0

    class signal(pyobj.Interface):
        def signal_raise(self):
            self._up.level = 1
        def signal_lower(self):
            self._up.level = 0

    class simple_interrupt(pyobj.Interface):
        def interrupt(self, level):
            self._up.level = 1
        def interrupt_clear(self, level):
            self._up.level = 0

    class level(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.level
        def setter(self, val):
            self._up.level = val

class TestBench:
    def __init__(self, nmi_bit=False):
        # Bus clock
        clk = simics.pre_conf_object('lpc_timer_clk', 'clock')
        clk.freq_mhz = lpc_timer_mhz
        simics.SIM_add_configuration([clk], None)
        self.timer_clk = conf.lpc_timer_clk

        self.io_space = simics.SIM_create_object('memory-space', 'io_space', [])
        self.irq = simics.SIM_create_object('TimerOutSignal', 'irq_dev', [])
        self.rtc = simics.SIM_create_object('generic_rtc', 'rtc',
                                       [['queue', self.timer_clk]])
        self.rtc.irq_dev = self.irq
        self.io_space.map +=  [[rtc_io_index,       self.rtc.bank.fixed_io, 0, 0, 4],
                               [rtc_io_index_alias, self.rtc.bank.fixed_io, 0, 0, 4]]
        self.nmi_bit = nmi_bit

    def set_nmi_bit(self):
        self.nmi_bit = True

    # IO space operation methods
    def read_io(self, addr, size):
        return self.io_space.iface.memory_space.read(None, addr, size, 0)

    def write_io(self, addr, bytes):
        self.io_space.iface.memory_space.write(None, addr, bytes, 0)

    def read_io_le(self, addr, bits):
        return int.from_bytes(self.read_io(addr, bits // 8), 'little')

    def write_io_le(self, addr, bits, value):
        if addr == rtc_io_index and self.nmi_bit:
            value |= 0x80
        self.write_io(addr, tuple(value.to_bytes(bits // 8, 'little')))

    def set_rtc(self, time_list):
        [sec, min, hour, dow, dom, mon, year] = time_list
        # Inhibit the update cycle temporarily
        self.write_io_le(rtc_io_index, 8, 0xB)
        orig_regb = self.read_io_le(rtc_io_data, 8)
        self.write_io_le(rtc_io_index, 8, 0xB)
        self.write_io_le(rtc_io_data, 8, orig_regb | 0x80)

        val_list = [sec, min, hour]
        for i in range(len(val_list)):
            self.write_io_le(rtc_io_index, 8, 2 * i)
            self.write_io_le(rtc_io_data, 8, val_list[i])

        val_list = [dow, dom, mon, year]
        for i in range(len(val_list)):
            self.write_io_le(rtc_io_index, 8, 6 + i)
            self.write_io_le(rtc_io_data, 8, val_list[i])
        # Restore the original register B
        self.write_io_le(rtc_io_index, 8, 0xB)
        self.write_io_le(rtc_io_data, 8, orig_regb)

    def get_rtc(self):
        self.write_io_le(rtc_io_index, 8, 0)
        sec = self.read_io_le(rtc_io_data, 8)

        self.write_io_le(rtc_io_index, 8, 2)
        min = self.read_io_le(rtc_io_data, 8)

        self.write_io_le(rtc_io_index, 8, 4)
        hour = self.read_io_le(rtc_io_data, 8)

        self.write_io_le(rtc_io_index, 8, 6)
        dow = self.read_io_le(rtc_io_data, 8)

        self.write_io_le(rtc_io_index, 8, 7)
        dom = self.read_io_le(rtc_io_data, 8)

        self.write_io_le(rtc_io_index, 8, 8)
        mon = self.read_io_le(rtc_io_data, 8)

        self.write_io_le(rtc_io_index, 8, 9)
        year = self.read_io_le(rtc_io_data, 8)

        list_val = [sec, min, hour, dow, dom, mon, year]
        return list_val

    def enable_rtc(self, to_enable):
        # Select the divider chain select
        self.write_io_le(rtc_io_index, 8, 0xA)
        orig_rega = self.read_io_le(rtc_io_data, 8)
        self.write_io_le(rtc_io_index, 8, 0xA)
        self.write_io_le(rtc_io_data, 8, 0x20 + (orig_rega & 0x0F))

        self.write_io_le(rtc_io_index, 8, 0xB)
        orig_regb = self.read_io_le(rtc_io_data, 8)
        if to_enable:
            new_origb = orig_regb & 0x7F
        else:
            new_origb = orig_regb | 0x80
        self.write_io_le(rtc_io_index, 8, 0xB)
        self.write_io_le(rtc_io_data, 8, new_origb)


tb = TestBench()

def expect_string(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%s', expected '%s'" % (info, actual, expected))

def expect_hex(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '0x%x', expected '0x%x'" % (info, actual, expected))

def expect_list(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%r', expected '%r'" % (info, actual, expected))

def expect(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%d', expected '%d'" % (info, actual, expected))
