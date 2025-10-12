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


# s-8259-eoi.py
# test the end-of-interrupt command of the 8259A interrupt controller
# in the ICH9 chip

from tb_8259 import *

tb.init_i8259()

def do_test():
    # Enable several interrupts
    tb.enable_interrupt(3, 1)
    tb.enable_interrupt(6, 1)
    tb.enable_interrupt(9, 1)

    # Trigger these interrupts
    tb.i8259.iface.simple_interrupt.interrupt(3)
    tb.i8259.iface.simple_interrupt.interrupt(6)
    tb.i8259.iface.simple_interrupt.interrupt(9)

    # Advance one step to allow the interrupt event to be triggered
    SIM_continue(1)

    # Get the interrupt vector is expected
    expect_list(tb.iack.current_interrupt, [0x71],
                "interrupt vector 0x%x got from the 8259" % 0x71)

    # Clear the current interrupts in pseudo processor
    tb.iack.current_interrupt = []

    # Clear the interrupt
    tb.clear_interrupt(9)

    # Get the interrupt vector is expected
    expect_list(tb.iack.current_interrupt, [0xB],
                "interrupt vector 0x%x got from the 8259" % 0xB)

    # Clear the current interrupts in pseudo processor
    tb.iack.current_interrupt = []

    # Clear the interrupt
    tb.clear_interrupt(3)

    # Get the interrupt vector is expected
    expect_list(tb.iack.current_interrupt, [0xE],
                "interrupt vector 0x%x got from the 8259" % 0xE)

    # Clear the current interrupts in pseudo processor
    tb.iack.current_interrupt = []

    # Clear the interrupt
    tb.clear_interrupt(6)

    SIM_continue(10)
    expect_list(tb.iack.current_interrupt, [],
                "no interrupt vector got from the 8259")

    # Disable the interrupt
    tb.enable_interrupt(3, 0)
    tb.enable_interrupt(6, 0)
    tb.enable_interrupt(9, 0)

do_test()
