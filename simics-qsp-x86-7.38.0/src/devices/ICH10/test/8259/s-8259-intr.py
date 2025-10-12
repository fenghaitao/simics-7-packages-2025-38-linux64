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


# s-8259-intr.py
# test the 15 interrupts of the 8259A interrupt controller in the ICH9 chip

from tb_8259 import *

tb.init_i8259()

def do_test(intr_no):
    # Enable the interrupt
    tb.enable_interrupt(intr_no, 1)

    # Trigger an interrupt
    tb.i8259.iface.simple_interrupt.interrupt(intr_no)

    # Check the interrupt request bit is set
    if intr_no < 8:
        expect_hex((tb.read_irr_isr("irr", "master") >> intr_no) & 0x1, 1,
                   "interrupt request bit %d is set" % intr_no)
    else:
        expect_hex((tb.read_irr_isr("irr", "slave") >> (intr_no - 8)) & 0x1, 1,
                   "interrupt request bit %d is set" % intr_no)

    # Advance one step to allow the interrupt event to be triggered
    SIM_continue(1)

    # Check the interrupt service bit is set
    if intr_no < 8:
        expect_hex((tb.read_irr_isr("isr", "master") >> intr_no) & 0x1, 1,
                   "interrupt service bit %d is set" % intr_no)
    else:
        expect_hex((tb.read_irr_isr("isr", "slave") >> (intr_no - 8)) & 0x1, 1,
                   "interrupt service bit %d is set" % intr_no)

    # Check the interrupt request bit is cleared
    if intr_no < 8:
        expect_hex((tb.read_irr_isr("irr", "master") >> intr_no) & 0x1, 0,
                   "interrupt request bit %d is cleared" % intr_no)
    else:
        expect_hex((tb.read_irr_isr("irr", "slave") >> (intr_no - 8)) & 0x1, 0,
                   "interrupt request bit %d is cleared" % intr_no)

    # Get the interrupt vector is expected
    expected_iv = 0x08 + intr_no
    if intr_no > 7:
        expected_iv = 0x70 + intr_no - 8
    expect_list(tb.iack.current_interrupt, [expected_iv],
                "interrupt vector 0x%x got from the 8259" % expected_iv)

    # Clear the interrupt
    tb.clear_interrupt(intr_no)

    # Clear the current interrupts in pseudo processor
    tb.iack.current_interrupt = []

    # Check the interrupt service bit is cleared
    if intr_no < 8:
        expect_hex((tb.read_irr_isr("isr", "master") >> intr_no) & 0x1, 0,
                   "interrupt service bit %d is cleared" % intr_no)
    else:
        expect_hex((tb.read_irr_isr("isr", "slave") >> (intr_no - 8)) & 0x1, 0,
                   "interrupt service bit %d is cleared" % intr_no)

    # Disable the interrupt
    tb.enable_interrupt(intr_no, 0)

for i in range(16):
    if i == 2:
        continue
    do_test(i)
