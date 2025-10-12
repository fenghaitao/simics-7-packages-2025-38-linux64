# © 2012 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from common     import *
from test_shell import *

testsh = TestShell()
#Init Ethernet card 0
testsh.initiate_eth(0)
testsh.set_cu_base(0, cu_base[0])
testsh.set_ru_base(0, ru_base[0])

def do_test():
    # get the device into non-idle state
    testsh.rx_wait(0)
    # do a selective reset and check that the device is idle
    # and that the fr is cleared
    testsh.selective_reset(0)
    status = ethreg[0].read_reg("STATUS")
    if status & 0x40FC != 0:
        raise Exception("Cus and/or Rus not idle")

do_test()
