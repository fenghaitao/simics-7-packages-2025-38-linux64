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


# s-ehci-compliance-transfers.py
# test EHCI compliance

# TODO: Generalize EHCI/OHCI registers and port registers

from usb_ctrl_common import *
from ehci_common import *

######

# TD 3.1 FRINDEX
def do_td_3_1():
    print("---> EHCI specification test TD 3.1 <---")
    # Reset controller, set the configure flag to enable EHCI port
    # ownership and set run bit
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        n_ports[i] = ehci_hcsparams_reg[i].n_ports

    # Construct a bulk of output data
    out_buf     = ehci_obuf_addr
    in_buf      = ehci_ibuf_addr
    test_size   = 68
    real_output = tuple((i & 0xFF) for i in range(test_size))
    write_mem(out_buf, real_output)
    # Clear the input buffer
    zero_bytes = tuple(0 for i in range(test_size))
    write_mem(in_buf, zero_bytes)

    # Connect high speed device for testing
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
            # Transmit data

    # Check that the FRINDEX matches SOF frame number
    sof = [None]*n_ehci
    for i in range(n_ehci):
        sof[i] = ehci_frindex_reg[i].frame_nr
        # Calculate SOF frame number


    # Remove device
    remove_usb_devices(n_ehci, n_ports, usb_device)


# TD 3.2 micro frame integrity
def do_td_3_2():
    print("---> EHCI specification test TD 3.2 <---")

# TD 3.3 Qhead Nak counter/empty list detection
def do_td_3_3():
    print("---> EHCI specification test TD 3.3 <---")

# TD 3.4 asynchronous service order
def do_td_3_4():
    print("---> EHCI specification test TD 3.4 <---")

# TD 3.5 asynchronous list advance doorbell
def do_td_3_5():
    print("---> EHCI specification test TD 3.5 <---")

# TD 3.6 PING protocol management
def do_td_3_6():
    print("---> EHCI specification test TD 3.6 <---")

# TD 3.7 PING protocol handling
def do_td_3_7():
    print("---> EHCI specification test TD 3.7 <---")

# TD 3.8 transfer interrupts
def do_td_3_8():
    print("---> EHCI specification test TD 3.8 <---")
    # Reset controller, set the configure flag to enable EHCI port
    # ownership and set run bit
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbcmd_reg[i].run_stop = 1
        n_ports[i] = ehci_hcsparams_reg[i].n_ports

    # Connect high and full speed devices for testing
    usb_device_hs = SIM_create_object('usb_device_wrapper',
                                      'usb0',
                                      [['usb_host', ehci_list[0]],
                                       ['device_speed', usb_speed_high]])
    usb_device_hs.device_connection = True
    usb_device_fs = SIM_create_object('usb_device_wrapper',
                                      'usb1',
                                      [['usb_host', ehci_list[0]],
                                       ['device_speed', usb_speed_full]])
    usb_device_fs.device_connection = True
    # Loop over valid values for interrupt threshold, bits 23:16
    for int_threshold in [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40]:
        ehci_usbcmd_reg[0].int_threshold_ctrl = int_threshold
        # Stimulate transfer events that generates interrupts
#TODO
#
# Do first part of bulk 3.10 and check usb_int

#
# qTD retirement w/IOC bit set (with and without short packet)
### ioc bit set in call to conf_queue_head in usbdata_out
# qTD retirement w/o IOC bit set (with and without short packet)
# qTD retirement on short packet


    usb_device_hs.device_connection = False
    SIM_delete_object(usb_device_hs)
    usb_device_fs.device_connection = False
    SIM_delete_object(usb_device_fs)

# TD 3.9 transfer error interrupts
def do_td_3_9():
    print("---> EHCI specification test TD 3.9 <---")
# Do almost 3.10 and check usb_err_int when timeout
# Babble detected, see qTD token bits 7:0 ? (Spec 3.5.3)


# TD 3.10 Qhead scatter/gather
def do_td_3_10_hs():
    print("---> EHCI specification test TD 3.10 (hs) <---")
    # Reset controller, set the configure flag to enable EHCI port
    # ownership, enable interrupts and set run bit
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbintr_reg[i].write(0x3F)
        ehci_pciconf_cmd_reg[i].write(0x5)  #  Bus Master Enable
        ehci_pciconf_ioaddr_reg[i].write(ehci_que_addr)
        ehci_usbcmd_reg[i].run_stop = 1
        ehci_usbcmd_reg[i].run_stop = 1
        n_ports[i] = ehci_hcsparams_reg[i].n_ports

    # Connect high speed device for testing
    usb_device_hs = SIM_create_object('usb_device_wrapper',
                                      'usb0',
                                      [['usb_host', ehci_list[0]],
                                       ['device_speed', usb_speed_high]])
    usb_device_hs.device_connection = True
    # Handle connection interrupt
    expect(ehci_usbsts_reg[0].port_change_detect, 1, 'Device was not connected')
    ehci_usbsts_reg[0].port_change_detect = 1
    #
    ### Transfer and verify data as asynchronous bulk
    #
    # Construct a bulk of output data
    test_data_size   = 20*1024
    output_data = tuple((i & 0xFF) for i in range(test_data_size))
    du_mem.write(ehci_obuf_addr, output_data)
    # Clear the input buffer
    zero_bytes = tuple(0 for i in range(test_data_size))
    du_mem.write(ehci_ibuf_addr, zero_bytes)
    # Prepare test comparison data and setup queuehead and qTD
    read_data_size   = 4096
    send_data_size   = 4*4096
    expect_input = du_mem.read(ehci_obuf_addr, send_data_size)
    usbctrl_set_address(du_mem, 0x0, 0x3, ehci_que_addr, ehci_obuf_addr)
    usbdata_out(du_mem, 0x0, 1, ehci_que_addr, ehci_obuf_addr, send_data_size)
    # Enable asynchronous schedule
    expect(ehci_usbsts_reg[0].asynch_sched_status,
           ehci_usbcmd_reg[0].asynch_sched_ena,
           'Should not enable asynchronous schedule')
    expect(ehci_usbsts_reg[0].asynch_sched_status, 0,
           'Should not modify asynchronous schedule register')
    ehci_asynclsta_reg[0].write(ehci_que_addr)
    ehci_usbcmd_reg[0].asynch_sched_ena = 1
    # Enable EHCI to poll frames
    ehci_list[0].async_list_polling_enabled = True
    # Run for an appropriate amount of time
    SIM_continue(enough_cycles)
    for i in range(4):
        # Clear asynch and run bit
        ehci_usbcmd_reg[0].run_stop = 0
        ehci_usbcmd_reg[0].asynch_sched_ena = 0
        # Handle usb interrupt
        expect(ehci_usbsts_reg[0].usb_int, 1, 'No usb int interrupt in USBSTS')
        ehci_usbsts_reg[0].usb_int = 1
        usbdata_in(du_mem, 0x0, 1, ehci_que_addr,
                   ehci_ibuf_addr+i*read_data_size,
                   read_data_size)
        # Set asynch and run bit and run for an appropriate amount of time
        ehci_usbcmd_reg[0].run_stop = 1
        ehci_usbcmd_reg[0].asynch_sched_ena = 1
        SIM_continue(enough_cycles)

    # Clear asynch and run bit
    ehci_usbcmd_reg[0].run_stop = 0
    ehci_usbcmd_reg[0].asynch_sched_ena = 0
    expect(ehci_usbsts_reg[0].usb_int, 1, 'No usb int interrupt in USBSTS')
    ehci_usbsts_reg[0].usb_int = 1
    # Check the input data
    input_data = du_mem.read(ehci_ibuf_addr, 4*read_data_size)
    expect(input_data, expect_input, 'data read from USB device')
    # Remove usb device
    usb_device_hs.device_connection = False
    SIM_delete_object(usb_device_hs)
    # Handle disconnection interrupt
    expect(ehci_usbsts_reg[0].port_change_detect, 1, 'Device was not disconnected')
    ehci_usbsts_reg[0].port_change_detect = 1

# TD 3.11 Qhead transfer size boundaries
def do_td_3_11_hs():
    print("---> EHCI specification test TD 3.11 (hs) <---")
    # Reset controller, set the configure flag to enable EHCI port
    # ownership, enable interrupts and set run bit
    n_ports = [None]*n_ehci
    for i in range(n_ehci):
        ehci_usbcmd_reg[i].hcreset = 1
        ehci_cfgflag_reg[i].configure_flag = 1
        ehci_usbintr_reg[i].write(0x3F)
        ehci_pciconf_cmd_reg[i].write(0x5)  #  Bus Master Enable
        ehci_pciconf_ioaddr_reg[i].write(ehci_que_addr)
        ehci_usbcmd_reg[i].run_stop = 1
        n_ports[i] = ehci_hcsparams_reg[i].n_ports

    # Connect high speed device for testing
    usb_device_hs = SIM_create_object('usb_device_wrapper',
                                      'usb0',
                                      [['usb_host', ehci_list[0]],
                                       ['device_speed', usb_speed_high]])
    usb_device_hs.device_connection = True
    # Handle connection interrupt
    expect(ehci_usbsts_reg[0].port_change_detect, 1, 'Device was not connected')
    ehci_usbsts_reg[0].port_change_detect = 1
    #
    ### Transfer and verify data as asynchronous bulk
    #
    # Construct a bulk of output data
    test_data_size   = 20*1024
    read_data_size   = 4096
    output_data = tuple((i & 0xFF) for i in range(test_data_size))
    # Send to output buffer and prepare test comparison data
    du_mem.write(ehci_obuf_addr, output_data)
    expect_input = du_mem.read(ehci_obuf_addr, 4*read_data_size)
    # Clear the input buffer
    zero_bytes = tuple(0 for i in range(test_data_size))
    du_mem.write(ehci_ibuf_addr, zero_bytes)
    # Setup queuehead and qTD
    usbctrl_set_address(du_mem, 0x0, 0x3, ehci_que_addr, ehci_obuf_addr)
    usbdata_out(du_mem, 0x0, 1, ehci_que_addr, ehci_obuf_addr, test_data_size)
    # Enable asynchronous schedule
    expect(ehci_usbsts_reg[0].asynch_sched_status,
           ehci_usbcmd_reg[0].asynch_sched_ena,
           'Should not enable asynchronous schedule')
    expect(ehci_usbsts_reg[0].asynch_sched_status, 0,
           'Should not modify asynchronous schedule register')
    ehci_asynclsta_reg[0].write(ehci_que_addr)
    ehci_usbcmd_reg[0].asynch_sched_ena = 1
    # Enable EHCI to poll frames
    ehci_list[0].async_list_polling_enabled = True
    # Run for an appropriate amount of time
    SIM_continue(enough_cycles)
    for i in range(4):
        # Clear asynch and run bit
        ehci_usbcmd_reg[0].run_stop = 0
        ehci_usbcmd_reg[0].asynch_sched_ena = 0
        # Handle usb interrupt
        expect(ehci_usbsts_reg[0].usb_int, 1, 'No usb int interrupt in USBSTS')
        ehci_usbsts_reg[0].usb_int = 1
        usbdata_in(du_mem, 0x0, 1, ehci_que_addr,
                   ehci_ibuf_addr+i*read_data_size,
                   read_data_size)
        # Set asynch and run bit and run for an appropriate amount of time
        ehci_usbcmd_reg[0].run_stop = 1
        ehci_usbcmd_reg[0].asynch_sched_ena = 1
        SIM_continue(enough_cycles)

    # Clear asynch and run bit
    ehci_usbcmd_reg[0].run_stop = 0
    ehci_usbcmd_reg[0].asynch_sched_ena = 0
    expect(ehci_usbsts_reg[0].usb_int, 1, 'No usb int interrupt in USBSTS')
    ehci_usbsts_reg[0].usb_int = 1
    # Check the input data
    input_data = du_mem.read(ehci_ibuf_addr, 4*read_data_size)
    expect(input_data, expect_input, 'data read from USB device')
    # Remove usb device
    usb_device_hs.device_connection = False
    SIM_delete_object(usb_device_hs)
    # Handle disconnection interrupt
    expect(ehci_usbsts_reg[0].port_change_detect, 1, 'Device was not disconnected')
    ehci_usbsts_reg[0].port_change_detect = 1

def do_td_3_11_fs():
    print("---> EHCI specification test TD 3.11 (fs) <---")

# TD 3.12 iTD scatter/gather
def do_td_3_12():
    print("---> EHCI specification test TD 3.12 <---")

# TD 3.13 iTD transfer size boundaries
def do_td_3_13():
    print("---> EHCI specification test TD 3.13 <---")

# TD 3.14 siTD scatter/gather
def do_td_3_14():
    print("---> EHCI specification test TD 3.14 <---")

# TD 3.15 siTD transfer size boundaries
def do_td_3_15():
    print("---> EHCI specification test TD 3.15 <---")

# TD 3.16 Qhead data toggle control
def do_td_3_16():
    print("---> EHCI specification test TD 3.16 <---")

# TD 3.17 frame boundary protection
def do_td_3_17():
    print("---> EHCI specification test TD 3.17 <---")

# TD 3.18 high-bandwidth interrupt
def do_td_3_18():
    print("---> EHCI specification test TD 3.18 <---")

# TD 3.19 high-bandwidth isochronous
def do_td_3_19():
    print("---> EHCI specification test TD 3.19 <---")

# TD 3.20 high-bandwidth isochronous
def do_td_3_20():
    print("---> EHCI specification test TD 3.20 <---")

# TD 3.21 short packets
def do_td_3_21():
    print("---> EHCI specification test TD 3.21 <---")

# TD 3.22 split-transaction interrupt streaming
def do_td_3_22():
    print("---> EHCI specification test TD 3.22 <---")

# TD 3.23 split-transaction isochronous streaming
def do_td_3_23():
    print("---> EHCI specification test TD 3.23 <---")

# TD 3.24 split-transaction isochronous streaming (error cases)
def do_td_3_24():
    print("---> EHCI specification test TD 3.24 <---")

# TD 3.25 split-transaction interrupt streaming (error cases)
def do_td_3_25():
    print("---> EHCI specification test TD 3.25 <---")

# TD 3.26 split-transaction asynchronous streaming (error cases)
def do_td_3_26():
    print("---> EHCI specification test TD 3.26 <---")

########################################################
########################################################

###### Transfers

def test_transfers():
#    do_td_3_1() # Isochronous not implemented
#    do_td_3_2() # Isochronous not implemented
#    do_td_3_3() # Not implemented, unclear test description
    do_td_3_4()
    do_td_3_5()
    do_td_3_6()
    do_td_3_7()
#    do_td_3_8()
    do_td_3_9()
    do_td_3_10_hs() # Only as asynchronous bulk
    do_td_3_11_hs() # Only as asynchronous bulk
    do_td_3_11_fs() # Only as asynchronous bulk
    do_td_3_12()
    do_td_3_13()
    do_td_3_14()
    do_td_3_15()
    do_td_3_16()
    do_td_3_17()
#    do_td_3_18() # Not implemented
#    do_td_3_19() # Not implemented
#    do_td_3_20() # Not implemented
#    do_td_3_21() # Not implemented
#    do_td_3_22() # Not implemented
#    do_td_3_23() # Not implemented
#    do_td_3_24() # Not implemented
#    do_td_3_25() # Not implemented
#    do_td_3_26() # Not implemented

######

test_transfers()
