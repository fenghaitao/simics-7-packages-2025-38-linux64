# The file to test basic configuration transmit and receive
# functionalities of INTEL 82559 model

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

#nic0.log_level = 3
#nic1.log_level = 3

testsh = TestShell()
#Init Ethernet card 0
testsh.initiate_eth(0)
testsh.set_cu_base(0, cu_base[0])
testsh.set_ru_base(0, ru_base[0])
#Init Ethernet card 1
testsh.initiate_eth(1)
testsh.set_cu_base(1, cu_base[1])
testsh.set_ru_base(1, ru_base[1])
#Disable irq for card 0 and 1
#testsh.disable_irq(0)
#testsh.disable_irq(1)

def do_test():
    # Call the test cases in TestShell
    # Test single ethernet card behavior
    testsh.eeprom_read_test(0)

    testsh.self_test(0)

    mac0 = (0x00, 0x13, 0x72, 0xEC, 0x91, 0x63)
    testsh.set_ia(0, mac0)
    mac1 = (0x00, 0x14, 0x73, 0xED, 0x92, 0x64)
    testsh.set_ia(1, mac1)

    testsh.clear_data_backup()
    #NOTE: Don't transmit before rx_wait()
    testsh.rx_wait(1)
    testsh.tx_test(0, FlexibleModeTx)
    testsh.rx_check(1, [117, 25, 78, 103])

    testsh.check_and_clear_interrupt(0)
    testsh.check_and_clear_interrupt(1)
    testsh.sw_set_interrupt_test(0)

    testsh.check_and_clear_interrupt(0)
    #testsh.wait(20000)
    testsh.clear_data_backup()
    testsh.tx_test(0, SimpleModeTx)

    testsh.clear_data_backup()
    testsh.cu_resume_test(0)

    testsh.check_and_clear_interrupt(0)
    testsh.cfg_and_dump_test(0)

do_test()
