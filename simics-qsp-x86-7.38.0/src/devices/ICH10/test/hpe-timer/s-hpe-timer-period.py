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


# s-hpe-timer-period.py
# test period mode of the high-precision event timer in the ICH9

from hpe_timer_common import *
import random

timN = 0
nCycles = 0x10000

def period_level_intr():
    timer.start_timer()
    timer.set_timer_intr_conf(timN, 1, 1, 1)
    timer.set_comp_and_period(timN, nCycles, nCycles)

    def run_one_period_clear():
        SIM_continue(nCycles - 1)
        timer.assert_intr_state(timN, 0)

        SIM_continue(1)
        timer.assert_intr_state(timN, 1)
        clear_intr_state()

    def clear_intr_state():
        stat = timer.read_register("GINTR_STA")
        expect(stat, (1 << timN))
        timer.clear_intr()
        #SIM_continue(1)
        timer.assert_intr_state(timN, 0)
        stat = timer.read_register("GINTR_STA")
        expect(stat, 0)

    def run_some_cycles():
        SIM_continue(nCycles - 1)
        timer.assert_intr_state(timN, 0)
        SIM_continue(1)
        timer.assert_intr_state(timN, 1)
        nStep = nCycles * (5 * random.random() + 5)
        nStep = int(nStep)
        SIM_continue(nStep)
        timer.assert_intr_state(timN, 1)
        clear_intr_state()

    # run with intr-state cleared
    MAX_LOOP = 1
    nLoop = 0
    while (nLoop <= MAX_LOOP):
        nLoop += 1
        run_one_period_clear()

    # run some cycle without intr-state cleared
    run_some_cycles()

def period_edge_intr():
    timer.start_timer()
    timer.set_timer_intr_conf(timN, 1, 0, 1)
    timer.set_comp_and_period(timN, nCycles, nCycles)

    global expected_spike_cnt
    expected_spike_cnt = 0

    def run_one_period():
        global expected_spike_cnt
        SIM_continue(nCycles - 1)
        timer.assert_intr_state(timN, [0, 1][expected_spike_cnt != 0])
        timer.assert_intr_spikes(timN, expected_spike_cnt)

        SIM_continue(1)
        expected_spike_cnt += 1
        timer.assert_intr_state(timN, 1)
        timer.assert_intr_spikes(timN, expected_spike_cnt)

        # should not be flagged in status
        expect(timer.read_register("GINTR_STA"), 0)
        timer.clear_intr() # should have no effect
        timer.assert_intr_state(timN, 1)
        timer.assert_intr_spikes(timN, expected_spike_cnt)
        expect(timer.read_register("GINTR_STA"), 0)

    # run with intr-state cleared
    MAX_LOOP = 100
    for nLoop in range(0, MAX_LOOP):
        run_one_period()

timer = ICH9R_HPE_TIMER()
clk = timer.get_clock()

period_level_intr()

timer.reset()

expected_sig_state = 0
period_edge_intr()
