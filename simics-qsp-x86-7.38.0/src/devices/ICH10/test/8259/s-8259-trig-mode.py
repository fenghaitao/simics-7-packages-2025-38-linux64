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


# s-8259-trig-mode.py
# test the two triggering mode of the 8259A interrupt controller
# in the ICH9 chip

from tb_8259 import *

def do_test(intr_no, trig_mode):
    tb.set_trig_mode(intr_no, trig_mode)

    # Enable the interrupt
    tb.enable_interrupt(intr_no, 1)

    # Trigger the interrupt
    tb.i8259.iface.simple_interrupt.interrupt(intr_no)

    # Advance one step to allow the interrupt event to be triggered
    SIM_continue(1)

    # Get the interrupt vector is expected
    expect_list(tb.iack.current_interrupt, [tb.irq_no_to_vector(intr_no)],
                "interrupt vector of IRQ %d got from the 8259" % intr_no)
    tb.iack.current_interrupt = []

    # Mask then clear the interrupt
    tb.enable_interrupt(intr_no, 0)
    tb.clear_interrupt(intr_no)

    SIM_continue(1)

    # Unmask the interrupt
    tb.enable_interrupt(intr_no, 1)
    SIM_continue(1)

    if trig_mode == "level":
        # Check the interrupt service bit is set again
        if intr_no < 8:
            expect_hex((tb.read_irr_isr("isr", "master") >> intr_no) & 0x1, 1,
                       "interrupt service bit %d is set" % intr_no)
        else:
            expect_hex((tb.read_irr_isr("isr", "slave") >> (intr_no - 8)) & 0x1, 1,
                   "interrupt service bit %d is set" % intr_no)
        expect_list(tb.iack.current_interrupt, [tb.irq_no_to_vector(intr_no)],
                    "interrupt vector of IRQ %d got from the 8259" % intr_no)
    else:
        # Check the interrupt service bit is still cleared
        if intr_no < 8:
            expect_hex((tb.read_irr_isr("isr", "master") >> intr_no) & 0x1, 0,
                       "interrupt service bit %d is still cleared" % intr_no)
        else:
            expect_hex((tb.read_irr_isr("isr", "slave") >> (intr_no - 8)) & 0x1, 0,
                       "interrupt service bit %d is still cleared" % intr_no)


do_test(0, "edge")
do_test(0, "level")
