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


# s-hpe-timer-intr.py
# test interrupting of the high-precision event timer in the ICH9

from hpe_timer_common import *
from functools import reduce

def test_write_comp_inrun(timN = 1, nCycles = 0x1000):
    def assert_irq(raised):
        timer.assert_intr_state(timN, raised)
        expect(timer.read_register("GINTR_STA"),
               raised << timN)

    pause = 200
    timer.start_timer()
    timer.set_timer_intr_conf(timN, 1, 1, 0)
    timer.set_time_count(timN, nCycles)  # cnt set relative main counter

    SIM_continue(pause)
    #TEST POINT. Try write comp register while running
    timer.set_time_count(timN, nCycles)

    SIM_continue(nCycles - 1 - pause)
    assert_irq(0)
    SIM_continue(1)
    assert_irq(0)

    SIM_continue(pause - 1)
    assert_irq(0)

    SIM_continue(1)
    assert_irq(1)
    timer.clear_intr()
    assert_irq(0)

def test_tim123_individually(timN, nCycles = 0x1000):
    timer.start_timer()
    timer.set_timer_intr_conf(timN, 1, 1, 0)
    timer.set_time_count(timN, nCycles)

    SIM_continue(nCycles - 1)
    timer.assert_intr_state(timN, 0)

    SIM_continue(1)
    timer.assert_intr_state(timN, 1)

    stat = timer.read_register("GINTR_STA")
    expect(stat, (1 << timN))
    timer.clear_intr()
    SIM_continue(1)
    timer.assert_intr_state(timN, 0)
    stat = timer.read_register("GINTR_STA")
    expect(stat, 0)

def run_all_sidebyside(nCycles = 0x20000, level = True):
    timer.start_timer()

    id_list = [0, 1, 2, 3]
    irq_list = [20, 21, 11, 12]
    n_8259 = sum([x < 15 for x in irq_list])

    for i in range(len(id_list)):
        timer.set_timer_intr_conf(i, 1, level, 0)
        timer.set_timer_rout_conf(id_list[i], irq_list[i])
        timer.set_time_count(id_list[i], nCycles)

    SIM_continue(nCycles - 1)

    for index in id_list:
        timer.assert_intr_state(index, 0)

    SIM_continue(1)
    exp_8259, exp_apic = n_8259, len(id_list)
    for index in id_list:
        timer.assert_intr_state(index, exp_apic, exp_8259)

    for i in range(len(id_list)):
        irq = irq_list[i]

        if not level:
            continue

        if irq < 16:
            expect_ex("interrupt %d status in 8259" % irq,
                      timer.intr[0].simple_interrupt.raised[irq], 1)
            expect_ex("interrupt %d status in APIC" % irq,
                      timer.intr[1].regs_raised[irq], 1)
        else:
            expect_ex("interrupt %d status in 8259" % irq,
                      timer.intr[0].simple_interrupt.raised.get(irq, 0), 0)
            expect_ex("interrupt %d status in APIC" % irq,
                      timer.intr[1].regs_raised[irq], 1)

    v = 0
    if level:
        v = reduce(lambda x, y: x | y, [1 << x for x in id_list])

    expect(timer.read_register("GINTR_STA"), v)

    #clear intr and assert:
    timer.clear_intr()
    for index in id_list:
        if level:
            timer.assert_intr_state(index, 0)
        expect(timer.read_register("GINTR_STA"), 0)


timer = ICH9R_HPE_TIMER()
clk = timer.get_clock()

test_write_comp_inrun()

for timN in (1, 1, 1, 2, 3):
    for nCycle in (2, 3, 1000, 10000, 100000):
        test_tim123_individually(timN, nCycle)

timer.reset()
run_all_sidebyside(level = True)

timer.reset('SRESET')
run_all_sidebyside(level = False)
