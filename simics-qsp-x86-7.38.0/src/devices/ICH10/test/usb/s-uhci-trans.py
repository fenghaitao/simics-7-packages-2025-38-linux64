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


# s-uhci-trans.py
# test the USB transfer of UHCI controllers in ICH9

from usb_tb import *

stest.untrap_log("spec-viol")

for i in range(ich9_uhci_cnt):
    tb.uhci[i].log_level = 2
tb.usb_dev.log_level = 4

# Map the USB I/O registers
for i in range(ich9_uhci_cnt):
    tb.map_hc_io("uhci", i)

def do_test(uhci_idx, port_idx, test_size):
    io_base     = ich9_uhci_io_base[uhci_idx]
    dev_addr    = test_usb_dev_addr
    ep_num      = 0
    is_low_dev  = 1 # is low-speed device or full-speed device
    setup_buf   = uhci_setup_addr
    out_buf     = uhci_obuf_addr
    in_buf      = uhci_ibuf_addr

    # Construct a bulk of output data
    real_output = tuple((i & 0xFF) for i in range(test_size))
    tb.write_mem(out_buf, real_output)
    expect_input = tuple(((test_size - 1 - i) & 0xFF) for i in range(test_size))
    # Clear the input buffer
    zero_bytes = tuple(0 for i in range(test_size))
    tb.write_mem(in_buf, zero_bytes)

    # Enable the master access in the pci configuration space
    tb.enable_pci_master("uhci", uhci_idx, 1)

    # Connect the test USB device with UHCI
    tb.usb_dev.usb_host = tb.uhci[uhci_idx]

    # Construct the transfer descriptor of the setup packet
    # is last TD, next address is 0, low-speed,
    first_td_addr = uhci_td_addr
    second_td_addr = upper_align_to_power2(first_td_addr + UsbConst.uhci_td_len, 4)
    second_td_addr = upper_align_to_power2(second_td_addr + UsbConst.uhci_td_len, 4)
    third_td_addr = upper_align_to_power2(second_td_addr + UsbConst.uhci_td_len, 4)
    tb.construct_uhci_setup_td(first_td_addr, setup_buf, dev_addr, is_low_dev)

    # Construct two TDs of one bulk output and one bulk input transfer
    tb.construct_uhci_td(second_td_addr, 1, 0, UsbConst.pid_out,
                         dev_addr, ep_num, is_low_dev, out_buf, test_size)
    tb.construct_uhci_td(third_td_addr, 1, 0, UsbConst.pid_in,
                         dev_addr, ep_num, is_low_dev, in_buf, test_size)

    # Construct three queue headers to hook above TDs
    first_qh_addr = uhci_que_addr
    second_qh_addr = upper_align_to_power2(first_qh_addr + UsbConst.uhci_qh_len, 4)
    third_qh_addr = upper_align_to_power2(second_qh_addr + UsbConst.uhci_qh_len, 4)
    tb.construct_uhci_qh(first_qh_addr, 0, first_td_addr, 0)
    tb.construct_uhci_qh(second_qh_addr, 0, second_td_addr, 0)
    tb.construct_uhci_qh(third_qh_addr, 0, third_td_addr, 1)

    # Construct the frame list to contain the two queue header
    frame1 = UsbConst.uhci_bf_frame.value(T = 0, Q = 1, FP = first_qh_addr >> 4)
    frame2 = UsbConst.uhci_bf_frame.value(T = 0, Q = 1, FP = second_qh_addr >> 4)
    frame3 = UsbConst.uhci_bf_frame.value(T = 0, Q = 1, FP = third_qh_addr >> 4)
    frame_cnt = 3
    tb.construct_uhci_frame_list(uhci_frame_list_addr, frame_cnt, frame1, frame2, frame3)

    # Configure the frame list base address
    tb.write_io_le(io_base + 0x08, 32, uhci_frame_list_addr)

    # Enable the UHCI to poll the frame list every 1ms
    tb.uhci[uhci_idx].frame_list_polling_enabled = True

    # Start the UHCI
    reg_val = tb.read_io_le(io_base + 0x00, 16)
    reg_val = reg_val | 0x21 # run/stop bit, asynch schedule enable bit
    tb.write_io_le(io_base + 0x00, 16, reg_val)

    # Continue one micro-second to let UHCI traverse the frame list
    SIM_continue(int(bus_clk_freq_mhz * 1000000 * 0.001 * (frame_cnt + 1)))

    # Verify the device address
    expect(tb.usb_dev.device_address, dev_addr,
           "device address configured by the EHCI")

    # Verify the input data
    real_input = tb.read_mem(in_buf, test_size)
    expect_list(real_input, expect_input, "the read-in data which is reverse of output data")

    # Stop this UHCI
    tb.write_io_le(io_base + 0x00, 16, 0x00)

for i in range(ich9_uhci_cnt):
    do_test(i, 0, 68)
