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


# s-8259-nested-mode.py
# test the nested interrupts in the 8259A interrupt controller
# in the ICH9 chip

from tb_8259 import *

def do_test():
    # Make several interrupts with next priority is higher than the previous
    highers = [7, 6, 5]
    lowers  = [8, 9, 10]
    for no in highers:
        tb.enable_interrupt(no, 1)

    # Trigger the first interrupt in highers
    tb.i8259.iface.simple_interrupt.interrupt(highers[0])

    # Advance one step to allow the interrupt event to be triggered
    SIM_continue(1)

    # Get the interrupt vector is expected
    expect_list(tb.iack.current_interrupt, [tb.irq_no_to_vector(highers[0])],
                "interrupt vector of IRQ %d got from the 8259" % highers[0])

    # Trigger the second interrupt in highers
    tb.iack.current_interrupt = []
    tb.i8259.iface.simple_interrupt.interrupt(highers[1])
    SIM_continue(1)
    expect_list(tb.iack.current_interrupt, [tb.irq_no_to_vector(highers[1])],
                "interrupt vector of IRQ %d got from the 8259" % highers[1])

    # Trigger the third interrupt in highers
    tb.iack.current_interrupt = []
    tb.i8259.iface.simple_interrupt.interrupt(highers[2])
    SIM_continue(1)
    expect_list(tb.iack.current_interrupt, [tb.irq_no_to_vector(highers[2])],
                "interrupt vector of IRQ %d got from the 8259" % highers[2])

    tb.iack.current_interrupt = []
    for no in highers:
        tb.enable_interrupt(no, 0)

    # Enable the lower interrupts
    for no in lowers:
        tb.enable_interrupt(no, 1)

    # Trigger the first interrupt in highers
    tb.i8259.iface.simple_interrupt.interrupt(lowers[0])

    # Advance one step to allow the interrupt event to be triggered
    SIM_continue(1)

    # Get the interrupt vector is expected
    expect_list(tb.iack.current_interrupt, [tb.irq_no_to_vector(lowers[0])],
                "interrupt vector of IRQ %d got from the 8259" % lowers[0])

    # Trigger the second interrupt in lowers
    tb.iack.current_interrupt = []
    tb.i8259.iface.simple_interrupt.interrupt(lowers[1])
    SIM_continue(1)
    expect_list(tb.iack.current_interrupt, [],
                "no interrupt vector got from the 8259")

    # Trigger the third interrupt in highers
    tb.iack.current_interrupt = []
    tb.i8259.iface.simple_interrupt.interrupt(lowers[2])
    SIM_continue(1)
    expect_list(tb.iack.current_interrupt, [],
                "no interrupt vector got from the 8259")

    # Clear the interrupts in the lowers from highest to lowest
    tb.clear_interrupt(lowers[0])
    expect_list(tb.iack.current_interrupt, [tb.irq_no_to_vector(lowers[1])],
                "interrupt vector of IRQ %d got from the 8259" % lowers[1])

    tb.iack.current_interrupt = []
    tb.clear_interrupt(lowers[1])
    expect_list(tb.iack.current_interrupt, [tb.irq_no_to_vector(lowers[2])],
                "interrupt vector of IRQ %d got from the 8259" % lowers[2])

    tb.iack.current_interrupt = []
    tb.clear_interrupt(lowers[2])
    expect_list(tb.iack.current_interrupt, [],
                "no interrupt vector got from the 8259")

do_test()
