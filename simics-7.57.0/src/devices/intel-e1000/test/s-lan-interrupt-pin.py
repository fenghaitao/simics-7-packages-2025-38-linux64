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


from tb_lan import *

def do_test():
    pin_reg = dev_util.Register_LE(tb.lan.bank.pci_config, 0x3D, 1)
    for i in range(5):
        tb.lpc.d25p = i
        stest.expect_equal(pin_reg.read(), tb.lpc.d25p)
    tb.lpc.d25p = ~7 # Only first 4 bits are relevant
    stest.expect_different(pin_reg.read(), tb.lpc.d25p)


do_test()
