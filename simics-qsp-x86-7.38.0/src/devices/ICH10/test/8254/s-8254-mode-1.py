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


# s-8254-mode-1.py
# test the mode 1 triggering of the 8254 timer in the LPC bridge in the ICH9 chip

from timer_tb import *

def do_test(c):
    ctrl_val = (c << 6) + 0x12 # counter 0/1/2, LSB, mode 1
    tb.write_io_le(0x43, 8, ctrl_val)

    initial_cnt = 0xFF
    io_addr = 0x40 + c

    tb.signal[c].level = 1

    tb.write_io_le(io_addr, 8, initial_cnt)

    SIM_continue(1)

    expect(tb.signal[c].level, 0, "initial output from the counter %d" % c)

    SIM_continue(initial_cnt - 1)
    expect(tb.signal[c].level, 1,
           "output changed to 1 when counter %d is triggered" % c)

    # Next cycle output goes back to 0 again
    for i in range(initial_cnt):
        SIM_continue(1)
        expect(tb.signal[c].level, 0,
               "output went back to 0 one cycle after counter %d is triggered" % c)



do_test(0)
do_test(1)
do_test(2)
