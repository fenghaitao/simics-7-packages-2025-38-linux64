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


# s-apic-mask.py
# test the masking of interrupts in the APIC interrupt controller
# in the ICH9 chip

from tb_apic import *

def do_test(intr_no):
    test_vec = 0x10 + intr_no
    test_dest_mode = 1
    test_dest = 0x80 # CPU #7
    test_deliv_mode = 0x4 # NMI
    test_trig_mode = 1

    # Enable the interrupt
    tb.enable_intr(intr_no, "yes")
    tb.set_intr_paras(intr_no, test_vec, test_dest_mode, test_dest,
                      test_deliv_mode, test_trig_mode)
    # Trigger the interrupt
    tb.write_value_le(apic_client_bank_base + 0x8, 32, (test_vec << 16) + intr_no)
    tb.write_value_le(apic_client_bank_base, 32, 0x1)
    # Examine the received parameters in the pseudo APIC bus
    examine_intr_paras(intr_no,
                       test_vec, test_dest, test_dest_mode, test_deliv_mode)
    tb.apic_bus.current_interrupt = {}

    # Clear the interrupt
    tb.write_value_le(apic_client_bank_base, 32, 0x2)

    # Disable the interrupt
    tb.enable_intr(intr_no, "no")

    # Trigger the interrupt
    tb.write_value_le(apic_client_bank_base + 0x8, 32, intr_no)
    tb.write_value_le(apic_client_bank_base, 32, 0x1)
    # Examine the received parameters in the pseudo APIC bus
    expect_dict(tb.apic_bus.current_interrupt, {},
                "no interrupt request when IRQ %d is disabled" % intr_no)

for i in range(apic_int_cnt):
    do_test(i)
