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
# test the reset state of the 8259A interrupt controller in the ICH9 chip

from tb_8259 import *

def do_test():
    elcr1 = tb.read_value_le(0x4D0, 8)
    elcr2 = tb.read_value_le(0x4D1, 8)
    expect(elcr1, 0x00, "Master Controller Edge/Level Triggered Register")
    expect(elcr2, 0x00, "Slave Controller Edge/Level Triggered Register")

    tb.init_i8259()
    # Check the interrupt mask is expected
    expect_list(tb.i8259.irq_mask, [0xFF, 0xFF], "Interrupt mask")

do_test()
