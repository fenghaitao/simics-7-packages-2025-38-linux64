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


# s-rtc-periodic.py
# test the periodic interrupt function of the real-time clock
# in the LPC bridge in the ICH9 chip

from rtc_tb import *

def do_test(rate):
    time1 = [0, 0, 0, 5, 1, 1, 0] # 2000-1-1, Saturday

    tb.irq.level = 0

    # Set the initial time of RTC
    tb.enable_rtc(0)
    tb.set_rtc(time1)

    # Select the periodic rate
    tb.write_io_le(rtc_io_index, 8, 0xA)
    tb.write_io_le(rtc_io_data, 8, 0x20 + rate)

    # Enable the periodic interrupt
    tb.write_io_le(rtc_io_index, 8, 0xB)
    orig_regb = tb.read_io_le(rtc_io_data, 8)
    tb.write_io_le(rtc_io_index, 8, 0xB)
    tb.write_io_le(rtc_io_data, 8, orig_regb | 0x40)

    # Enable the RTC
    tb.enable_rtc(1)

    if rate < 3:
        period = rate * 3.90625e-3
    else:
        period = (1 << (rate - 3)) * 0.122070e-3
    len_period = period * lpc_timer_mhz * 1e6 + 1 # Be careful to add 1

    # Loop several period time and check the periodic interrupt
    for i in range(3):
        SIM_continue(int(len_period))
        raised = tb.irq.level
        expect(raised, 1, "%d periodic interrupt is raised" % i)
        # Check and clear the interrupt flag
        tb.write_io_le(rtc_io_index, 8, 0xC)
        regc_val = tb.read_io_le(rtc_io_data, 8)
        expect(regc_val & 0xC0, 0xC0,
               "interrupt req and periodic flag in the flag reg")
        raised = tb.irq.level
        expect(raised, 0, "the periodic interrupt is cleared")


for rate in [1, 2, 3, 8, 15]:
    do_test(rate)
