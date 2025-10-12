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


# s-hpe-timer-stop-start.py
# test start, stop operation of the high-precision event timer in the ICH9

from hpe_timer_common import *
import random

def get_main_cnt():
    return timer.read_register("MAIN_CNT")

def test(timN, nCycles):
    timer.start_timer()
    timer.set_timer_intr_conf(timN, 1, 1, 0)

    #start first time:
    timer.set_time_count(timN, nCycles)
    SIM_continue(nCycles)
    timer.assert_intr_state(timN, 1)
    clear_intr_state(timN)

    #start second time:
    timer.set_time_count(timN, nCycles)
    SIM_continue(nCycles)
    timer.assert_intr_state(timN, 1)
    clear_intr_state(timN)

    #start third time:
    timer.set_time_count(timN, nCycles)
    SIM_continue(nCycles)
    timer.assert_intr_state(timN, 1)
    clear_intr_state(timN)

    if (timN == 0):
        timer.stop_timer()

def clear_intr_state(timN):
    stat = timer.read_register("GINTR_STA")
    expect(stat, (1 << timN))
    timer.clear_intr()
    timer.assert_intr_state(timN, 0)
    stat = timer.read_register("GINTR_STA")
    expect(stat, 0)

timer = HPE_TIMER()
clk = timer.get_clock()

for i in [1, 2, 3]:
    for nStep in [2, 4, 100, 10000]:
        test(i, nStep)

test(0, 2)
