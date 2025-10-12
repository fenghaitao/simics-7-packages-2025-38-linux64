# © 2019 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Test that two lower bits in config_address ignore writes (HSD-ES 1806517538).

from dmi_common import *

def do_test():
    reg_config_address = dev_util.Register_LE(conf.pci_bus.bridge.bank.io_regs,
                                              io_reg_offsets.config_address)

    reg_config_address.write(0x80000002)
    test_val = reg_config_address.read()

    #check 2 low bits always should be equal 0
    stest.expect_equal(0x80000000, test_val,
                           "Invalid data read from config_data" )

do_test()
