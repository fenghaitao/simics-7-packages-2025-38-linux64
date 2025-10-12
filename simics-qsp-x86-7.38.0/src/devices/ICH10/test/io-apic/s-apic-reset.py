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


# s-apic-reset.py
# test the reset state of the APIC interrupt controller in the ICH9 chip

from tb_apic import *

def do_test():
    # APIC ID register
    id = tb.read_apic_reg(0, 32)
    expect_hex(id, ApicConst.reset_val["ID"], "APIC identification register")
    ver = tb.read_apic_reg(1, 32)
    expect_hex(ver, ApicConst.reset_val["VER"], "APIC version register")

    for i in range(apic_int_cnt):
        redir = tb.read_apic_reg(0x10 + 2 * i, 64)
        expect_hex(redir, ApicConst.reset_val["REDIR"],
                   "interrupt %d redirection value" % i)

do_test()
