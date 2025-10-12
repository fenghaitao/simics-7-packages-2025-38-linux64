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


# s-vtd-reset.py
# tests the default state of VTd hardware after a reset

from vtd_tb import *

def do_test():
    tb.vtd_hw_drv.reset_vtd_hw()
    for reg_name in list(VTdConst.reg_info.keys()):
        val = tb.vtd_hw_drv.read_reg(reg_name)
        stest.expect_equal(val, default_of(reg_name),
                   "default value of %s" % reg_name)

do_test()
