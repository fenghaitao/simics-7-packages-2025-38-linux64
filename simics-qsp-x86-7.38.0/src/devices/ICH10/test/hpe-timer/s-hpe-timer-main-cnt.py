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


# s-hpe-timer-main-cnt.py
# test main counter(include wraparound case)

from hpe_timer_common import *
import random

def expect_hex_relaxed(cnt, expect):
    diff = cnt - expect
    if (diff < -1 or diff > 1):
        expect_hex(cnt, expect)

def verify_main_cnt(expect):
    cnt = timer.read_register("MAIN_CNT")
    expect_hex_relaxed(cnt, expect)


def test_main_cnt():
    timer.reset("HRESET")
    nStep = 0x10000
    timer.start_timer()
    SIM_continue(nStep - 1)  #The same effect as SIM_continue(nStep-1) ???
    SIM_continue(1)
    SIM_continue(1)
    expect_hex_relaxed(timer.read_register("MAIN_CNT"), nStep + 1)
    timer.stop_timer()

    nStep = 0x100000
    pre_cnt = timer.read_register("MAIN_CNT") #must read before start again
    timer.start_timer()
    SIM_continue(nStep)
    expect_hex_relaxed(timer.read_register("MAIN_CNT") - pre_cnt, nStep)

    SIM_continue(nStep)
    SIM_continue(1)
    expect_hex_relaxed(timer.read_register("MAIN_CNT") - pre_cnt, 2 * nStep + 1)
    timer.stop_timer()

    nStep = MAX32
    pre_cnt = timer.read_register("MAIN_CNT") #must read before start again
    timer.start_timer()
    SIM_continue(nStep)
    expect_hex_relaxed(timer.read_register("MAIN_CNT") - pre_cnt, nStep)
    timer.stop_timer()

def test_wrap_around_with32BitTimer():
    timer.reset("HRESET")
    timN = 1

    def do_one_countdown(timN):
        pre_cnt = timer.read_register("MAIN_CNT") #must read before start again
        timer.start_timer()
        timer.set_timer_intr_conf(timN, 1, 1, 1)
        nStep = MAX32
        #nStep = 0x10000
        timer.set_32bit_mode(timN, 1)
        timer.set_time_count(timN, nStep)

        SIM_continue(nStep - 2)
        cnt = timer.read_register("MAIN_CNT")
        expect_hex_relaxed(cnt - pre_cnt, nStep - 2)

        SIM_continue(1)
        cnt = timer.read_register("MAIN_CNT")
        expect_hex_relaxed(cnt - pre_cnt, nStep - 1)
        SIM_continue(1)
        cnt = timer.read_register("MAIN_CNT")
        expect_hex_relaxed(cnt - pre_cnt, nStep)

        SIM_continue(1)
        cnt = timer.read_register("MAIN_CNT")
        expect_hex_relaxed(cnt - pre_cnt, nStep + 1) #main_cnt not LIMITED by 32BITs

        #expect_hex_relaxed(cnt, nStep)
        timer.start_timer()

    do_one_countdown(timN)
    do_one_countdown(timN)
    do_one_countdown(timN)

    timer.stop_timer()

def test_wrap_around_with64BitTimer():
    '''Not applicable in current Simics'''
    assert 0
    timer.reset("HRESET")
    timN = 0
    timer.start_timer()

    def do_one_countdown(timN):
        timer.set_timer_intr_conf(timN, 1, 1, 1)
        timer.set_time_count(timN, MAX64 - 2)
        nStep = MAX64Plus1
        MAX16 = 0xFFFF
        for iLoop1 in range(MAX16 + 2):
            for iLoop2 in range(MAX16):
                SIM_continue(MAX32)
        SIM_continue(MAX32)
        SIM_continue(MAX32)

        cnt = timer.read_register("MAIN_CNT")
        expect(cnt, nStep - 1)
        SIM_continue(1)
        cnt = timer.read_register("MAIN_CNT")
        expect(cnt, nStep - 1)
        SIM_continue(1)
        cnt = timer.read_register("MAIN_CNT")
        expect(cnt, 0)

    do_one_countdown(timN)
    timer.stop_timer()

def test_wrap_around_notimer():
    timer.reset("HRESET")
    timN = 0

    timer.start_timer()
    timer.set_timer_intr_conf(timN, 1, 1, 1)
    nStep = MAX32Plus1
    timer.set_32bit_mode(timN, 1)
    SIM_continue(nStep - 2)
    #cnt = timer.read_register("MAIN_CNT")
    #expect(cnt, nStep - 2)
    SIM_continue(1)
    #cnt = timer.read_register("MAIN_CNT")
    #expect(cnt, nStep - 1)
    SIM_continue(1)
    #cnt = timer.read_register("MAIN_CNT")
    #expect(cnt, 0)
    timer.stop_timer()

    #for 64bits
    timer.reset("HRESET")
    timer.start_timer()
    timer.set_timer_intr_conf(timN, 1, 1, 1)
    nStep = MAX64Plus1
    timer.set_32bit_mode(timN, 0)
    SIM_continue(nStep - 2)
    cnt = timer.read_register("MAIN_CNT")
    expect(cnt, nStep - 2)
    SIM_continue(1)
    cnt = timer.read_register("MAIN_CNT")
    expect(cnt, nStep - 1)
    SIM_continue(1)
    cnt = timer.read_register("MAIN_CNT")
    expect(cnt, 0)
    timer.stop_timer()

timer = ICH9R_HPE_TIMER()
clk = timer.get_clock()

timer.start_timer()
SIM_continue(1)
verify_main_cnt(1)
timer.start_timer()
SIM_continue(1)
verify_main_cnt(2)
timer.start_timer()
SIM_continue(1)
verify_main_cnt(3)
timer.stop_timer()

test_main_cnt()

test_wrap_around_with32BitTimer()
