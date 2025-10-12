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


# s-ehci-compliance-miscellaneous.py
# test EHCI compliance

# TODO: Generalize EHCI/OHCI registers and port registers

from usb_ctrl_common import *
from ehci_common import *

###### Multiple data streams

# TD 4.1 periodic list - end of list mark detection
def do_td_4_1():
    print("---> EHCI specification test TD 4.1 <---")

# TD 4.2 periodic schedule inter-operability
def do_td_4_2():
    print("---> EHCI specification test TD 4.2 <---")

# TD 4.3 asynchronous schedule inter-operability
def do_td_4_3():
    print("---> EHCI specification test TD 4.3 <---")

# TD 4.4 EHCI inter-operability
def do_td_4_4():
    print("---> EHCI specification test TD 4.4 <---")

###### Miscellaneous

# TD 6.1 PID (data-toggle) mis-match events
def do_td_6_1():
    print("---> EHCI specification test TD 6.1 <---")

# TD 6.2 handling STALL handshake
def do_td_6_2():
    print("---> EHCI specification test TD 6.2 <---")

###### Debug port

# TD 7.1 debug port PCI configuration space registers
def do_td_7_1():
    print("---> EHCI specification test TD 7.1 <---")
    # Reset controller
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
    # Set the configflag to enable EHCI port ownership and set run bit
    for i in range(n_ehci):
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        expect(ehci_pciconf_dbg_capid_reg[i].read(), 0xA,
               'Debug port capabilities register value mismatch')

# TD 7.2 debug port host controller capability registers
def do_td_7_2():
    print("---> EHCI specification test TD 7.2 <---")
    # Reset controller
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
    # Set the configflag to enable EHCI port ownership and set run bit
    for i in range(n_ehci):
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        dbg_base = ehci_pciconf_dbg_base_reg[i].read()
        bar_num = (dbg_base >> 12) & 0x000F
        valid_bar = 0
        for x in [0,2,4]:
            if bar_num==x:
                valid_bar = 1
        expect(valid_bar, 1, 'BAR number for debug port invalid')

# TD 7.3 debug port host controller registers
def do_td_7_3():
    print("---> EHCI specification test TD 7.3 <---")

# TD 7.4 debug port control/status registers
def do_td_7_4():
    print("---> EHCI specification test TD 7.4 <---")

# TD 7.5 debug port data streaming
def do_td_7_5():
    print("---> EHCI specification test TD 7.5 <---")

# TD 7.6 debug port error test
def do_td_7_6():
    print("---> EHCI specification test TD 7.6 <---")

###### IBIT

# TD 8.1 interactive on next transaction bit
def do_td_8_1():
    print("---> EHCI specification test TD 8.1 <---")

###### FSTN

# TD 9.1 periodic frame span traversal node
def do_td_9_1():
    print("---> EHCI specification test TD 9.1 <---")

# TD 9.2 periodic frame span traversal node
def do_td_9_2():
    print("---> EHCI specification test TD 9.2 <---")

###### PCI power management

# TD 10.1 PCI PM remote wake from all supported D-states
def do_td_10_1():
    print("---> EHCI specification test TD 10.1 <---")

# TD 10.2 PCI PM ignore disconnect event from all supported D-states
def do_td_10_2():
    print("---> EHCI specification test TD 10.2 <---")

# TD 10.3 PCI PM signal disconnect event from all supported D-states
def do_td_10_3():
    print("---> EHCI specification test TD 10.3 <---")

# TD 10.4 PCI PM ignore connect event from all supported D-states
def do_td_10_4():
    print("---> EHCI specification test TD 10.4 <---")

# TD 10.5 PCI PM report connect event from all supported D-states
def do_td_10_5():
    print("---> EHCI specification test TD 10.5 <---")

########################################################
########################################################

###### Multiple data streams

def test_multi_streams():
    do_td_4_1()
    do_td_4_2()
    do_td_4_3()
    do_td_4_4()

###### Miscellaneous

def test_misc():
    do_td_6_1()
    do_td_6_2()

###### Debug port

def test_debug_port():
    do_td_7_1()
    do_td_7_2()
    do_td_7_3()
    do_td_7_4()
    do_td_7_5()
    do_td_7_6()

###### IBIT and FSTN

def test_ibit_fstn():
    do_td_8_1()
    do_td_9_1()
    do_td_9_2()

###### PCI power management

def test_pci_power_mngmt():
    do_td_10_1()
    do_td_10_2()
    do_td_10_3()
    do_td_10_4()
    do_td_10_5()

######

#test_multi_streams()
#test_misc()
test_debug_port()
#test_ibit_fstn()
#test_pci_power_mngmt()
