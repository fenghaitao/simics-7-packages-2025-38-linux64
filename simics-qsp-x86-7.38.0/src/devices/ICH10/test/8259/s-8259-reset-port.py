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


# s-8259-reset.py
# test the side-effects of the RESET signal port

from tb_8259 import *

i8259 = conf.i8259
#i8259.log_level = 4

def do_test():
    tb.init_i8259()

    tb.iack.auto_ack = False
    expect(tb.iack.irq_raised, False, "interrupt already raised")

    # Enable and trigger an interrupt
    intr_no = 1
    tb.enable_interrupt(intr_no, 1)
    tb.i8259.iface.simple_interrupt.interrupt(intr_no)

    # Advance one cycle to allow the interrupt event to be triggered
    SIM_continue(1)

    expect(tb.iack.irq_raised, True, "interrupt not raised")

    # Reset the device
    i8259.port.RESET.iface.signal.signal_raise()
    i8259.port.RESET.iface.signal.signal_lower()

    expect(tb.iack.irq_raised, False, "interrupt not cleared after reset")

do_test()

print("passed")
