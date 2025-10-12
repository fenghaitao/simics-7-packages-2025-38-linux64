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


# s-hpe-timer-comp-lag-cnt.py
# test the case: timer's compare register is written with a value
# smaller than main counter's current value

from hpe_timer_common import *
import random

LAGS1 = 0x10000000
LAGS2 = 0x1

MAIN_CNT = "MAIN_CNT"

def test_comp_lag_counter(timN):
    def one_test(timN, nCycles, lags):
        timer.write_register(MAIN_CNT, nCycles + lags)
        timer.start_timer()
        timer.set_timer_intr_conf(timN, 1, 1, 0)
        timer.set_32bit_mode(timN, 1)
        timer.set_time_countABS(timN, nCycles)

        # if (lags==1), then
        # a) run steps= 0xFFFFFFFf for interrupt coming
        # b) when interrupt occurred, main_cnt = (nCycles)
        SIM_continue(MAX32 - lags )

        SIM_continue(1)
        timer.assert_intr_state(timN, 1)
        timer.clear_intr()

        cnt = timer.read_register(MAIN_CNT)
        expect_hex(cnt & MAX32MASK, nCycles)

    one_test(timN, 0x10000, LAGS1)
    timer.reset("HRESET")
    one_test(timN, 0x1000000, LAGS2)
    timer.reset("HRESET")

timer = ICH9R_HPE_TIMER()
clk = timer.get_clock()

for index in [0, 1, 2, 3]:
    test_comp_lag_counter(index)

#test_comp_lag_counter(1, 0x10000, LAGS1)
#timer.reset("HRESET")
#test_comp_lag_counter(1, 0x1000000, LAGS2)
