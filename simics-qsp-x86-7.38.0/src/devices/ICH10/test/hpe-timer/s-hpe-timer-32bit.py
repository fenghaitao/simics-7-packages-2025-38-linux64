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


# s-hpe-timer-32bit.py
# test 32-bit mode of the high-precision event timer in the ICH9

from hpe_timer_common import *
import random

def test_32bit_mode(timN, nCycles):
    timer.start_timer()
    timer.set_timer_intr_conf(timN, 1, 1, 1)
    timer.set_32bit_mode(timN, 1)
    timer.set_comp_and_period(timN, nCycles, nCycles)

    real_Cycle = (nCycles % MAX32Plus1)
    def run_one_period_clear():
        SIM_continue(real_Cycle - 1)
        timer.assert_intr_state(timN, 0)
        SIM_continue(1)
        timer.assert_intr_state(timN, 1)
        clear_intr_state()

    def clear_intr_state():
        stat = timer.read_register("GINTR_STA")
        expect(stat, (1 << timN))
        timer.clear_intr()
        timer.assert_intr_state(timN, 0)
        stat = timer.read_register("GINTR_STA")
        expect(stat, 0)

    # run with intr-state cleared
    MAX_LOOP = 10
    nLoop = 0
    while (nLoop <= MAX_LOOP):
        nLoop += 1
        run_one_period_clear()

timer = ICH9R_HPE_TIMER()
clk = timer.get_clock()

SIM_run_command("log-level 4")
test_32bit_mode(0, MAX32Plus1 + 2)
