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


from lpc_tb import *
from stest import expect_log

tb.lpc.bank.cs_conf.log_level = 2
test_addr = [0x0088, #cir1, register use cs_init_reg template
             0x0f20, #cir13, field use cs_init_reg template
             ]
for addr in test_addr:
    reg = dev_util.Register_LE(tb.lpc.bank.cs_conf, addr, 2)
    expect_log(reg.write, [0], tb.lpc.bank.cs_conf, 'spec-viol',
               "write to cs_init_reg with incorrect value should spec-viol")
