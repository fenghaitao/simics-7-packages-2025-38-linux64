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


# s-ehci-compliance-ports.py
# test EHCI compliance

# TODO: Generalize EHCI/OHCI registers and port registers

from usb_ctrl_common import *
from ehci_common import *

######

# TD 2.1 port indicators
def do_td_2_1():
    print("---> EHCI specification test TD 2.1 <---")
    # Reset controller, set the configure flag to enable EHCI port
    # ownership and set run bit
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        # Query host controller for N_PORTS
        # - number of physical ports on the host controller
        n_ports[i] = ehci_hcsparams_reg[i].n_ports

    for i in range(n_ehci):
        # Check if port indicator control is implemented
        if ehci_hcsparams_reg[i].p_indicator:
            for j in range(n_ports[i]):
                if (i > 0):
                    k = i * n_ports[i-1] + j
                else:
                    k = j
                # Port indicator control is bit 15:14 in PORTSC: 01 amber, 10 green
                ehci_portsc_reg[k].port_ind_ctrl = 0x01
                ehci_portsc_reg[k].port_ind_ctrl = 0x10
        else:
            print("EHCI port indicators are not implemented")

# TD 2.2 port change detect
def do_td_2_2():
    print("---> EHCI specification test TD 2.2 <---")
    # Reset controller, set the configure flag to enable EHCI port
    # ownership and set run bit
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        n_ports[i] = ehci_hcsparams_reg[i].n_ports

    # Connect high-speed device in each port for testing
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
            expect(ehci_usbsts_reg[i].port_change_detect, 1,
                   'USBSTS did not detect port change on connect')

            # Suspend and resume device
            ehci_portsc_reg[k].suspend = 1
            ehci_portsc_reg[k].port_ena = 1
            ehci_portsc_reg[k].force_port_resume = 1
            expect(ehci_portsc_reg[k].conn_status_chg, 1,
                   'PORTSC did not detect port change on resume')
            expect(ehci_usbsts_reg[i].port_change_detect, 1,
                   'USBSTS did not detect port change on resume')

            # Remove device
            usb_device[k].device_connection = False
            expect(ehci_usbsts_reg[i].port_change_detect, 1,
                   'USBSTS did not detect port change on disconnect')
            usb_device[k].device_connection = True

    # Remove the usb devices
    remove_usb_devices(n_ehci, n_ports, usb_device)

# TD 2.3 port test modes
def do_td_2_3():
    print("---> EHCI specification test TD 2.3 <---")
    # Reset controller, set the configure flag to enable EHCI port
    # ownership and set run bit
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        n_ports[i] = ehci_hcsparams_reg[i].n_ports

    # Connect high-speed device in each port for testing J-state
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
            expect(ehci_portsc_reg[k].port_test_ctrl, 0,
                   'PORTSC test mode enabled')
            # Test J_STATE
            ehci_portsc_reg[k].port_test_ctrl = 0x01

    # Remove the usb devices and reset controller
    remove_usb_devices(n_ehci, n_ports, usb_device)
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1

    # Connect high-speed device and test K-state
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
            expect(ehci_portsc_reg[k].port_test_ctrl, 0,
                   'PORTSC test mode enabled')
            # Test K_STATE
            ehci_portsc_reg[k].port_test_ctrl = 0x02

    # Remove the usb devices and reset controller
    remove_usb_devices(n_ehci, n_ports, usb_device)
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1

    # Connect high-speed device and test SE0_NAK state
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
            expect(ehci_portsc_reg[k].port_test_ctrl, 0,
                   'PORTSC test mode enabled')
            # Test SE0_NAK
            ehci_portsc_reg[k].port_test_ctrl = 0x03

    # Remove the usb devices and reset controller
    remove_usb_devices(n_ehci, n_ports, usb_device)
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1

    # Connect high-speed device and test Packet state
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
            expect(ehci_portsc_reg[k].port_test_ctrl, 0,
                   'PORTSC test mode enabled')
            # Test Packet
            ehci_portsc_reg[k].port_test_ctrl = 0x04

    # Remove the usb devices and reset controller
    remove_usb_devices(n_ehci, n_ports, usb_device)
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1

    # Connect high-speed device and test FORCE_ENABLE
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
            expect(ehci_portsc_reg[k].port_test_ctrl, 0,
                   'PORTSC test mode enabled')
            # Test FORCE_ENABLE
            ehci_portsc_reg[k].port_test_ctrl = 0x05

    # Remove the usb devices
    remove_usb_devices(n_ehci, n_ports, usb_device)

# TD 2.4 invalid port enable
def do_td_2_4():
    print("---> EHCI specification test TD 2.4 <---")
    # Reset controller, set the configure flag to enable EHCI port
    # ownership and set run bit
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        n_ports[i] = ehci_hcsparams_reg[i].n_ports

    # Connect high-speed device in each port for testing
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
            # Try to enable port
            ehci_portsc_reg[k].port_ena = 1
            expect(ehci_portsc_reg[k].port_ena, 0,
                   'PORTSC enabled port by setting the port_ena bit')

    # Remove the usb devices
    remove_usb_devices(n_ehci, n_ports, usb_device)

# TD 2.5 port disable
def do_td_2_5():
    print("---> EHCI specification test TD 2.5 <---")
    # Reset controller, set the configure flag to enable EHCI port
    # ownership and set run bit
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        n_ports[i] = ehci_hcsparams_reg[i].n_ports

    # Connect high-speed device in each port for testing
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
            # Try to disable port
            ehci_portsc_reg[k].port_ena = 0
            expect(ehci_portsc_reg[k].port_ena, 0,
                   'PORTSC could not disable port by clearing the port_ena bit')
            expect(ehci_portsc_reg[k].port_ena_chg, 0,
                   'PORTSC host controller have set port_ena_chg bit')

    # Remove the usb devices
    remove_usb_devices(n_ehci, n_ports, usb_device)

# TD 2.6 port routing/correct enumeration
def do_td_2_6():
    print("---> EHCI specification test TD 2.6 <---")
    # Reset controller, set the configure flag to enable EHCI port
    # ownership and set run bit
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        n_ports[i] = ehci_hcsparams_reg[i].n_ports

    # Connect high-speed device in each port for testing
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
            expect(ehci_portsc_reg[k].curr_conn_status, 1,
                   'EHCI PORTSC - device is connected')
            expect(uhci_portsc_reg[k].curr_conn_status, 0,
                   'UHCI PORTSC - device is not connected')

    # Remove the usb devices
    remove_usb_devices(n_ehci, n_ports, usb_device)

    # Connect full-speed device in each port for testing
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
            expect(ehci_portsc_reg[k].curr_conn_status, 1,
                   'EHCI PORTSC - device is connected')
            expect(uhci_portsc_reg[k].curr_conn_status, 0,
                   'UHCI PORTSC - device is not connected')

    # Remove the usb devices
    remove_usb_devices(n_ehci, n_ports, usb_device)

    # Connect low-speed device in each port for testing
    for i in range(n_ehci):
        for j in range(n_ports[i]):
            if (i > 0):
                k = i * n_ports[i-1] + j
            else:
                k = j
            usb_device[k] = SIM_create_object('usb_device_wrapper',
                                              'usb%d'%k,
                                              [['usb_host', ehci_list[i]],
                                               ['device_speed', usb_speed_low]])
            usb_device[k].device_connection = True
            expect(ehci_portsc_reg[k].curr_conn_status, 1,
                   'EHCI PORTSC - device is connected')
            expect(uhci_portsc_reg[k].curr_conn_status, 0,
                   'UHCI PORTSC - device is not connected')

    # Remove the usb devices
    remove_usb_devices(n_ehci, n_ports, usb_device)

    # Change config flag to route ownership to companion controller
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].run_stop = 0
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 0
        ehci_usbcmd_reg[i].run_stop = 1

    # Connect high-speed device in each port for testing
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
            expect(ehci_portsc_reg[k].curr_conn_status, 0,
                   'EHCI PORTSC - device is not connected')
            expect(uhci_portsc_reg[k].curr_conn_status, 1,
                   'UHCI PORTSC - device is connected')

    # Remove the usb devices
    remove_usb_devices(n_ehci, n_ports, usb_device)

    # Connect full-speed device in each port for testing
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
            expect(ehci_portsc_reg[k].curr_conn_status, 0,
                   'EHCI PORTSC - device is not connected')
            expect(uhci_portsc_reg[k].curr_conn_status, 1,
                   'UHCI PORTSC - device is connected')

    # Remove the usb devices
    remove_usb_devices(n_ehci, n_ports, usb_device)

    # Connect low-speed device in each port for testing
    for i in range(n_ehci):
        for j in range(n_ports[i]):
            if (i > 0):
                k = i * n_ports[i-1] + j
            else:
                k = j
            usb_device[k] = SIM_create_object('usb_device_wrapper',
                                              'usb%d'%k,
                                              [['usb_host', ehci_list[i]],
                                               ['device_speed', usb_speed_low]])
            usb_device[k].device_connection = True
            expect(ehci_portsc_reg[k].curr_conn_status, 0,
                   'EHCI PORTSC - device is not connected')
            expect(uhci_portsc_reg[k].curr_conn_status, 1,
                   'UHCI PORTSC - device is connected')

    # Remove the usb devices
    remove_usb_devices(n_ehci, n_ports, usb_device)


# TD 2.7 no SOFs when HC halted
def do_td_2_7():
    print("---> EHCI specification test TD 2.7 <---")
    # Reset controller, set the configure flag to enable EHCI port
    # ownership and set run bit
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        n_ports[i] = ehci_hcsparams_reg[i].n_ports

    # Connect high-speed device for testing
    usb_device = SIM_create_object('usb_device_wrapper', 'usb0',
                                   [['usb_host', ehci_list[0]],
                                    ['device_speed', usb_speed_high]])
    usb_device.device_connection = True
    # Halt the controllers
    for i in range(n_ehci):
        print("before hchalted = 0x%x" % ehci_usbsts_reg[i].hchalted)
        expect(ehci_usbsts_reg[i].hchalted, 0,
               'USBSTS HCHalted indicates controller is not running')
        ehci_usbcmd_reg[i].run_stop = 0
        print("after hchalted = 0x%x" % ehci_usbsts_reg[i].hchalted)
        expect(ehci_usbsts_reg[i].hchalted, 1,
               'USBSTS HCHalted indicates controller is not halted')
    # Check that SOFs are not sent
    sof = [None]*n_ehci
    for i in range(n_ehci):
        sof[i] = ehci_frindex_reg[i].frame_nr
    # Run for an appropriate amount of time
    SIM_continue(enough_cycles)
    for i in range(n_ehci):
        expect(ehci_frindex_reg[i].frame_nr, sof[i],
               'FRINDEX indicates SOF sent while halted')
    # Restart controller
    ehci_usbcmd_reg[n_ehci - 1].run_stop = 1
    # Remove the usb device
    usb_device.device_connection = False
    SIM_delete_object(usb_device)

# TD 2.8 port suspend/resume tests (host initiated resume)
def do_td_2_8():
    print("---> EHCI specification test TD 2.8 <---")
    # Reset controller, set the configure flag to enable EHCI port
    # ownership and set run bit
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        n_ports[i] = ehci_hcsparams_reg[i].n_ports

    # Connect high-speed device in each port for testing
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

    # Try to SUSPEND+RESUME one port at a time with all the other
    # ports enabled and check status
    for i in range(n_ehci):
        for j in range(n_ports[i]):
            if (i > 0):
                k = i * n_ports[i-1] + j
            else:
                k = j
            # Suspend and resume device
            ehci_portsc_reg[k].suspend = 1
            for m in range(sum(n_ports)):
                if (m==k):
                    expect(ehci_portsc_reg[m].curr_conn_status, 0,
                           'PORTSC did not change status on suspend')
                else:
                    expect(ehci_portsc_reg[m].curr_conn_status, 1,
                           'PORTSC did not change status on suspend')
            ehci_portsc_reg[k].port_ena = 1
            ehci_portsc_reg[k].force_port_resume = 1
            for m in range(sum(n_ports)):
                if (m==k):
                    expect(ehci_portsc_reg[k].conn_status_chg, 1,
                           'PORTSC did not detect port change on resume')
                else:
                    expect(ehci_portsc_reg[k].conn_status_chg, 0,
                           'PORTSC did not detect port change on resume')

    # Try to SUSPEND+RESUME one port at a time with all the other
    # ports suspended and check status
    for i in range(n_ehci):
        for j in range(n_ports[i]):
            if (i > 0):
                k = i * n_ports[i-1] + j
            else:
                k = j
            # Suspend devices
            ehci_portsc_reg[k].suspend = 1

    for i in range(n_ehci):
        for j in range(n_ports[i]):
            if (i > 0):
                k = i * n_ports[i-1] + j
            else:
                k = j
            # Resume device
            ehci_portsc_reg[k].port_ena = 1
            ehci_portsc_reg[k].force_port_resume = 1
            for m in range(sum(n_ports)):
                if (m==k):
                    expect(ehci_portsc_reg[k].conn_status_chg, 1,
                           'PORTSC did not detect port change on resume')
                else:
                    expect(ehci_portsc_reg[k].conn_status_chg, 0,
                           'PORTSC did not detect port change on resume')

            ehci_portsc_reg[k].suspend = 1
            for m in range(sum(n_ports)):
                if (m==k):
                    expect(ehci_portsc_reg[m].curr_conn_status, 0,
                           'PORTSC did not change status on suspend')
                else:
                    expect(ehci_portsc_reg[m].curr_conn_status, 1,
                           'PORTSC did not change status on suspend')


    # Remove the usb devices
    remove_usb_devices(n_ehci, n_ports, usb_device)

# TD 2.9 port suspend/resume tests (remote wake-up)
def do_td_2_9():
    print("---> EHCI specification test TD 2.9 <---")
    # Reset controller, set the configure flag to enable EHCI port
    # ownership and set run bit
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        n_ports[i] = ehci_hcsparams_reg[i].n_ports

    # Connect high-speed device in each port for testing
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

    # Try to SUSPEND and wait for RESUME on one port at a time with all
    # the other ports enabled and check status
    for i in range(n_ehci):
        for j in range(n_ports[i]):
            if (i > 0):
                k = i * n_ports[i-1] + j
            else:
                k = j
            # Suspend device and wait for remote wake-up and resume
            ehci_portsc_reg[k].suspend = 1
            for m in range(sum(n_ports)):
                if (m==k):
                    expect(ehci_portsc_reg[m].curr_conn_status, 0,
                           'PORTSC did not change status on suspend')
                else:
                    expect(ehci_portsc_reg[m].curr_conn_status, 1,
                           'PORTSC did not change status on suspend')
#            ehci_portsc_reg[k].port_ena = 1
# TODO WAITING
#            ehci_portsc_reg[k].force_port_resume = 1
            for m in range(sum(n_ports)):
                if (m==k):
                    expect(ehci_portsc_reg[k].conn_status_chg, 1,
                           'PORTSC did not detect port change on resume')
                else:
                    expect(ehci_portsc_reg[k].conn_status_chg, 0,
                           'PORTSC did not detect port change on resume')

    # Try to SUSPEND+RESUME one port at a time with all the other
    # ports suspended and check status
    for i in range(n_ehci):
        for j in range(n_ports[i]):
            if (i > 0):
                k = i * n_ports[i-1] + j
            else:
                k = j
            # Suspend devices
            ehci_portsc_reg[k].suspend = 1

    for i in range(n_ehci):
        for j in range(n_ports[i]):
            if (i > 0):
                k = i * n_ports[i-1] + j
            else:
                k = j
# TODO wait for remote wake-up and resume
            # Resume device
#            ehci_portsc_reg[k].port_ena = 1
#            ehci_portsc_reg[k].force_port_resume = 1
            for m in range(sum(n_ports)):
                if (m==k):
                    expect(ehci_portsc_reg[k].conn_status_chg, 1,
                           'PORTSC did not detect port change on resume')
                else:
                    expect(ehci_portsc_reg[k].conn_status_chg, 0,
                           'PORTSC did not detect port change on resume')

            ehci_portsc_reg[k].suspend = 1
            for m in range(sum(n_ports)):
                if (m==k):
                    expect(ehci_portsc_reg[m].curr_conn_status, 0,
                           'PORTSC did not change status on suspend')
                else:
                    expect(ehci_portsc_reg[m].curr_conn_status, 1,
                           'PORTSC did not change status on suspend')


    # Remove the usb devices
    remove_usb_devices(n_ehci, n_ports, usb_device)

# TD 2.10 port suspend/resume tests (reset a suspended port)
def do_td_2_10():
    print("---> EHCI specification test TD 2.10 <---")
    # Reset controller, set the configure flag to enable EHCI port
    # ownership and set run bit
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        n_ports[i] = ehci_hcsparams_reg[i].n_ports

    # Connect high-speed device in each port for testing
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
            # Suspend port
            ehci_portsc_reg[k].suspend = 1
            # Reset port
            ehci_portsc_reg[k].port_ena = 0
            ehci_portsc_reg[k].port_reset = 1
            # Check that suspend bit have been reset
            expect(ehci_portsc_reg[k].suspend, 0, 'PORTSC suspend bit is not reset')

    # Remove the usb devices
    remove_usb_devices(n_ehci, n_ports, usb_device)

########################################################
########################################################

###### Port operations

def test_port_ops():
    do_td_2_1() # Port indicator reg is implemented, but bit is zero
#    do_td_2_2() # Suspend / Force port resume unimplemented
#    do_td_2_3() # Test modes are unimplemented but test fails
                # as register is not cleared on HC reset!
    do_td_2_4()
    do_td_2_5()
    do_td_2_6()
    do_td_2_7()
#    do_td_2_8() # Suspend / Force port resume unimplemented
#    do_td_2_9() # Suspend / Force port resume unimplemented
#    do_td_2_10() # Controller fails - suspend bit not reset

######

test_port_ops()
