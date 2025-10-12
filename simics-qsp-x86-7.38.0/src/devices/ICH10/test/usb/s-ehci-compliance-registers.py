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


# s-ehci-compliance-registers.py
# test EHCI compliance

# TODO: Generalize EHCI/OHCI registers and port registers

from usb_ctrl_common import *
from ehci_common import *

###### Host controller parameters

# TD 1.3 CONFIGFLAG
def do_td_1_3():
    print("---> EHCI specification test TD 1.3 <---")
    # Reset controller
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1

    # Check that the configure flag resets to default zero
    for i in range(n_ehci):
        expect(ehci_cfgflag_reg[i].configure_flag, 0,
               'CONFIGURE FLAG has not reset to zero')

    # Query host controller for N_PORTS
    # - number of physical ports on the host controller
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        n_ports[i] = ehci_hcsparams_reg[i].n_ports

    # Insert High-speed device in each port and see that it
    # enumerates as UHCI/OHCI and not EHCI.
    usb_device = [None]*sum(n_ports)
    for i in range(n_ehci):
        for j in range(n_ports[i]):
            if (i > 0):
                k = i * n_ports[i-1] + j
            else:
                k = j
            usb_device[k] = SIM_create_object('usb_device_wrapper',
                                              'usb%d'%k,
                                              [['usb_host', ehci_list[i]],
                                               ['device_speed', usb_speed_high]])
            usb_device[k].device_connection = True
            expect(uhci_portsc_reg[k].curr_conn_status, 1,
                   'PORTSC - device is not connected')

    # Set the configflag to enable EHCI port ownership
    for i in range(n_ehci):
        ehci_cfgflag_reg[i].configure_flag = 1
        for j in range(n_ports[i]):
            # Verify that port ownership is transferred to EHCI controller
            if (i > 0):
                k = i * n_ports[i-1] + j
            else:
                k = j
            expect(ehci_portsc_reg[k].curr_conn_status, 1,
                   'PORTSC - device is not connected')

    # Remove USB devices
    remove_usb_devices(n_ehci, n_ports, usb_device)

# TD 1.4 memory mapped I/O and PCI config
def do_td_1_4():
    print("---> EHCI specification test TD 1.4 <---")
    # Reset EHCI controller
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
    # Verify default values of the memory mapped EHCI I/O registers
    for i in range(len(ehci_reg_defaults)//2):
        expect(ehci_reg_defaults[i][0].read(), ehci_reg_defaults[i][1],
               "EHCI register did not reset to default value")

# TD 1.5 USBCMD register
def do_td_1_5():
    print("---> EHCI specification test TD 1.5 <---")
    # Reset controller
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
    for i in range(n_ehci):
        # Check that reset restored the default values to the i/o registers
        expect(ehci_reg_defaults[9 + i][0].read(), ehci_reg_defaults[9 + i][1],
               "EHCI USBCMD register did not reset to default value")
        # Set run bit and check result on USBSTS HCHalted bit
        ehci_usbcmd_reg[i].run_stop = 1
        expect(ehci_usbsts_reg[i].hchalted, 0, 'EHCI USBSTS - HCHalted is not zero')
        # Clear run bit and check USBSTS HCHalted bit
        ehci_usbcmd_reg[i].run_stop = 0
        expect(ehci_usbsts_reg[i].hchalted, 1, 'EHCI USBSTS - HCHalted is not set')

# TD 1.6 port routing
def do_td_1_6():
    print("---> EHCI specification test TD 1.6 <---")
    # Reset controller
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
    # Set the configflag to enable EHCI port ownership and set run bit
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        # Verify consistency on host controller of the number of companion
        # controllers, N_CC, the number of ports per companion controller,
        # N_PCC, and the number of physical ports on the host controller, N_PORTS
        n_ports[i] = ehci_hcsparams_reg[i].n_ports
        expect((ehci_hcsparams_reg[i].n_pcc)*(ehci_hcsparams_reg[i].n_cc),
               n_ports[i], 'Inconsistent number of ports')
        # Query host controller for the mapping strategy of ports to companion
        # controllers
        if ehci_hcsparams_reg[i].port_route_rules:
            print("Port_routing described by HCSP-PORTROUTE: not implemented")

    # Attach full speed device to port and check that it is associated with the
    # expected host controller - repeat for all ports
    usb_device = [None]*sum(n_ports)
    for i in range(n_ehci):
        for j in range(n_ports[i]):
            if (i > 0):
                k = i * n_ports[i-1] + j
            else:
                k = j
            usb_device[k] = SIM_create_object('usb_device_wrapper',
                                              'usb%d'%k,
                                              [['usb_host', ehci_list[i]],
                                               ['device_speed', usb_speed_full]])
            usb_device[k].device_connection = True
            expect(ehci_portsc_reg[k].curr_conn_status, 1, 'EHCI PORTSC - device is connected')
    # Remove USB devices
    remove_usb_devices(n_ehci, n_ports, usb_device)


# TD 1.7 periodic schedule runs before asynchronous schedule
def do_td_1_7():
    print("---> EHCI specification test TD 1.7 <---")

# TD 1.8 frame list rollover
def do_td_1_8():
    print("---> EHCI specification test TD 1.8 <---")

# TD 1.9 FLADJ register
def do_td_1_9():
    print("---> EHCI specification test TD 1.9 <---")
    # Reset controller
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
    # Set the configflag to enable EHCI port ownership and set run bit
    for i in range(n_ehci):
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        ehci_pciconf_fladj_reg[i].write(0x0)

# TD 1.10 32-bit HC ignores 64-bit interface extensions
def do_td_1_10():
    print("---> EHCI specification test TD 1.10 <---")

# TD 1.11 port wake capability register - PCI configuration space
def do_td_1_11():
    print("---> EHCI specification test TD 1.11 <---")
    # Reset controller
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
    # Set the configflag to enable EHCI port ownership and set run bit
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        # Query host controller for N_PORTS
        # - number of physical ports on the host controller
        n_ports[i] = ehci_hcsparams_reg[i].n_ports
        # Check if the PORT WAKE CAPABILITIES register is implemented,
        # bit 0 set to one
        portwakecap = ehci_pciconf_portwakecap_reg[i].read()
        print("portwakecap = 0x%x " % portwakecap)
        if (portwakecap & 0x1):
            print("portwakecap enabled")
            # Check that each port has a writable bit
            for j in range(n_ports[i]):
                if (i > 0):
                    k = i * n_ports[i-1] + j
                else:
                    k = j
                ehci_pciconf_portwakecap_reg[i].write(0x1 | (0x1 << k))
                expect(ehci_pciconf_portwakecap_reg[i].read(),
                       0x1 | (0x1 << k),
                       'PCICONFIG PORTWAKECAP error writing port bit')
        else:
            print("portwakecap disabled")


########################################################
########################################################

###### Host controller parameters

def test_hc_params():
# 1_1 to 1_2 are not independent tests but rather included in test strategy
    do_td_1_3()
    do_td_1_4()
    do_td_1_5()
    do_td_1_6()
#    do_td_1_7() # not implemented
#    do_td_1_8() # not implemented
    do_td_1_9() # TODO measure time
#    do_td_1_10() # not implemented
    do_td_1_11()

######

test_hc_params()
