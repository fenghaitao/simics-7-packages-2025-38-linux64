# Test that Simics writes an error message if unused data isn't all ones
# in ShortTx mode.

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


from test_shell import *

testsh = TestShell()
#Init Ethernet card 0
testsh.initiate_eth(0)
testsh.set_cu_base(0, cu_base[0])
testsh.set_ru_base(0, ru_base[0])

def do_test():
    cu_action = cu_tx()
    cu_action.set_i()
    cu_action.set_link_addr_val(0x100)
    cu_action.set_tbd_addr_val(0xdeadbeef)
    cu_action.set_tcb_count_val(20)
    cu_action.add_payload(eth_frame_short)
    cu_action.set_tbd_eof()
    mem_write(cu_base[0], tuple(cu_action.cu_buf))
    with stest.expect_log_mgr(log_type="spec-viol"):
        testsh.start_cu(0, 0)

do_test()
