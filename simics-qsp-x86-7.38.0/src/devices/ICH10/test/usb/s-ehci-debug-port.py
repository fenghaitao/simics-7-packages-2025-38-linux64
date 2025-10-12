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


# s-ehci-reset.py
# test the reset state of EHCI controllers in ICH9

from usb_tb import *

CAP_ID_DEBUG_PORT = 0x0A

dp_ctrl_status_bf = dev_util.Bitfield_LE({
        'O'     : (30), # Owner
        'EN'    : (28), # Enabled
        'D'     : (16), # Done
        'IU'    : (10), # In Use
        'EX'    : (9, 7), # Exception
        'ERR'   : (6),  # Error/Good#
        'G'     : (5),  # Go
        'RW'    : (4),  # Write/Read#
        'DL'    : (3, 0), # Data Length
    })

for i in range(ich9_ehci_cnt):
    tb.map_hc_mem("ehci", i)
    tb.ehci[i].log_level = 1

def do_test(ehci_idx):
    conf_base = ich9_ehci_reg_addr[ehci_idx]
    io_base   = ich9_ehci_io_base[ehci_idx]

    port_num = (tb.read_value_le(io_base + 0x4, 32) >> 20) & 0xF
    stest.expect_true(port_num >= 1, "port number should be one-based")

    cap_ptr = tb.read_value_le(conf_base + 0x34, 8)
    stest.expect_true(cap_ptr >= 0x40,
                      "capabilities pointer should be 0x40 or greater")

    while cap_ptr:
        cap_id   = tb.read_value_le(conf_base + cap_ptr, 8)
        if cap_id == CAP_ID_DEBUG_PORT:
            break
        cap_ptr = tb.read_value_le(conf_base + cap_ptr + 1, 8)

    stest.expect_true(cap_ptr != 0,
                      "debug port capability pointer should exist")

    bar_pos = tb.read_value_le(conf_base + cap_ptr + 2, 16)
    bar_off = bar_pos & 0x1FFF
    bar_num = bar_pos >> 13

    stest.expect_true(bar_num >= 1,
                      "base address register index should be one-based")
    if bar_num > 1:
        raise Exception("other base address register than 0x10 is not supported")

    dp_base = io_base + bar_off
    dp_ctrl_status = tb.read_value_le(dp_base, 32)
    dp_pids        = tb.read_value_le(dp_base + 0x4, 32)
    dp_buf1        = tb.read_value_le(dp_base + 0x8, 32)
    dp_buf2        = tb.read_value_le(dp_base + 0xC, 32)
    dp_dev_addr    = tb.read_value_le(dp_base + 0x10,32)
    stest.expect_equal(dp_ctrl_status, 0, "debug port control/status register")
    stest.expect_equal(dp_pids, 0, "debug port USB PIDs register")
    stest.expect_equal(dp_buf1, 0, "debug port data buffer (bytes 3-0)")
    stest.expect_equal(dp_buf2, 0, "debug port data buffer (bytes 7-4)")
    stest.expect_equal(dp_dev_addr, 0x7F01, "debug port device address register")

    # Enable the DMA master of the EHCI
    tb.ehci[ehci_idx].pci_config_command = 0x14
    # Force the 6 USB ports to be owned by the EHCI
    tb.ehci[ehci_idx].usb_regs_prtsc = [0x1000] * 6
    tb.usb_dev.usb_host = tb.ehci[ehci_idx]

    data = [ord('A') + i for i in range(8)]
    exp_data = data[0:]
    exp_data.reverse()

    # Enable the debug port
    tb.write_value_le(dp_base, 32, dp_ctrl_status_bf.value(EN = 1, O = 1))

    # Use the debug port to write 8 bytes to the connected USB device
    tb.write_value_le(dp_base + 0x8, 32,
                      dev_util.tuple_to_value_le(tuple(data[0:4])))
    tb.write_value_le(dp_base + 0xC, 32,
                      dev_util.tuple_to_value_le(tuple(data[4:8])))
    tb.write_value_le(dp_base + 0x4, 32, UsbConst.pid_out)
    tb.write_value_le(dp_base, 32,
                      dp_ctrl_status_bf.value(EN = 1, O = 1, D = 1))
    fields = dp_ctrl_status_bf.fields(tb.read_value_le(dp_base, 32))
    stest.expect_equal(fields['D'], 0, "done bit cleared by writing 1 to it")
    tb.write_value_le(dp_base, 32,
        dp_ctrl_status_bf.value(DL = 8, RW = 1, G = 1, EN = 1, O = 1))
    fields = dp_ctrl_status_bf.fields(tb.read_value_le(dp_base, 32))
    stest.expect_equal(fields['D'], 1, "done bit set by the hardware")
    stest.expect_equal(fields['ERR'], 0, "no error in the writing")

    # Read the 8 bytes just written through the debug port
    tb.write_value_le(dp_base + 0x4, 32, UsbConst.pid_in)
    tb.write_value_le(dp_base, 32,
                      dp_ctrl_status_bf.value(EN = 1, O = 1, D = 1))
    fields = dp_ctrl_status_bf.fields(tb.read_value_le(dp_base, 32))
    stest.expect_equal(fields['D'], 0, "done bit cleared by writing 1 to it")
    tb.write_value_le(dp_base, 32,
        dp_ctrl_status_bf.value(DL = 8, RW = 0, G=1, EN = 1, O = 1))
    fields = dp_ctrl_status_bf.fields(tb.read_value_le(dp_base, 32))
    read_data = list(tb.read_mem(dp_base + 0x8, 8))
    stest.expect_equal(read_data, exp_data,
        "read data which should be the reversing of the write data")
    stest.expect_equal(fields['D'], 1, "done bit set by the hardware")
    stest.expect_equal(fields['ERR'], 0, "no error in the reading")

for i in range(ich9_ehci_cnt):
    do_test(i)
