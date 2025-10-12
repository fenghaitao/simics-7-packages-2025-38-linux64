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


# s-uhci-reset.py
# test the reset state of UHCI controllers in ICH9

from usb_tb import *

#for i in range(ich9_uhci_cnt):
#    tb.uhci[i].log_level = 4

def do_test(uhci_idx):
    base = ich9_uhci_reg_addr[uhci_idx]
    io_base = ich9_uhci_io_base[uhci_idx]

    vid = tb.read_value_le(base, 16)
    expect_hex(vid, UhciConst.reset_val["VID"], "Vendor identification")
    did = tb.read_value_le(base + 2, 16)
    expect_hex(did, UhciConst.reset_val["DID"] + uhci_idx, "Device identification of UHCI %d" % uhci_idx)

    cmd = tb.read_value_le(base + 4, 16)
    expect_hex(cmd, UhciConst.reset_val["CMD"], "Command")
    sts = tb.read_value_le(base + 6, 16)
    expect_hex(sts, UhciConst.reset_val["STS"], "Status")

    rid = tb.read_value_le(base + 8, 8)
    expect_hex(rid, UhciConst.reset_val["RID"], "Revision Identification")
    pi = tb.read_value_le(base + 9, 8)
    expect_hex(pi, UhciConst.reset_val["PI"], "Programming Interface")
    scc = tb.read_value_le(base + 0xA, 8)
    expect_hex(scc, UhciConst.reset_val["SCC"], "Sub Class Code")
    bcc = tb.read_value_le(base + 0xB, 8)
    expect_hex(bcc, UhciConst.reset_val["BCC"], "Base Class Code")

    uhci_bar = tb.read_value_le(base + 0x20, 32)
    expect_hex(uhci_bar, UhciConst.reset_val["BASE"], "UHCI I/O Base Address Register")

    svid = tb.read_value_le(base + 0x2C, 16)
    expect_hex(svid, UhciConst.reset_val["SVID"], "Subsystem Vendor ID")
    sid = tb.read_value_le(base + 0x2E, 16)
    expect_hex(sid, UhciConst.reset_val["SID"], "Subsystem ID")

    captr = tb.read_value_le(base + 0x34, 8)
    expect_hex(captr, UhciConst.reset_val["CAPTR"], "Capabilities Pointer")

    intln = tb.read_value_le(base + 0x3C, 8)
    expect_hex(intln, UhciConst.reset_val["INTLN"], "Interrupt Line")
    intpn = tb.read_value_le(base + 0x3D, 8)
    uhci_pin_rst = [1, 2, 3, 1, 2, 3]
    expect_hex(intpn, uhci_pin_rst[uhci_idx], "Interrupt Pin")

    # Capability registers

    flr_cid = tb.read_value_le(base + 0x50, 8)
    expect_hex(flr_cid, UhciConst.reset_val["FLRCID"], "Function Level Reset Capability ID")

    flr_ncp = tb.read_value_le(base + 0x51, 8)
    expect_hex(flr_ncp, UhciConst.reset_val["FLRNCP"], "Function Level Reset Next Capability Pointer")

    flr_clv = tb.read_value_le(base + 0x52, 16)
    expect_hex(flr_clv, UhciConst.reset_val["FLRCLV"], "Function Level Reset Capability Length and Version")

    usb_flrctrl = tb.read_value_le(base + 0x54, 8)
    expect_hex(usb_flrctrl, UhciConst.reset_val["USB_FLRCTRL"], "FLR Control Register")

    usb_flrstat = tb.read_value_le(base + 0x55, 8)
    expect_hex(usb_flrstat, UhciConst.reset_val["USB_FLRSTAT"], "FLR Status Register")

    usb_relnum = tb.read_value_le(base + 0x60, 8)
    expect_hex(usb_relnum, UhciConst.reset_val["USB_RELNUM"], "USB Release Number Register")

    usb_legkey = tb.read_value_le(base + 0xC0, 16)
    expect_hex(usb_legkey, UhciConst.reset_val["USB_LEGKEY"], "USB Legacy Keyboard/Mouse Control Register")

    usb_res = tb.read_value_le(base + 0xC4, 8)
    expect_hex(usb_res, UhciConst.reset_val["USB_RES"], "USB Resume Enable Register")

    cwp = tb.read_value_le(base + 0xC8, 8)
    expect_hex(cwp, UhciConst.reset_val["CWP"], "Core Well Policy Register")

    ucr1 = tb.read_value_le(base + 0xCA, 8)
    expect_hex(ucr1, UhciConst.reset_val["UCR1"], "UHCI Configuration Register 1")


    # USB I/O registers
    tb.map_hc_io("uhci", uhci_idx)

    usb_cmd = tb.read_io_le(io_base + 0x0, 16)
    expect_hex(usb_cmd, UhciConst.reset_val["USBCMD"], "USB Command Register")

    usb_sts = tb.read_io_le(io_base + 0x2, 16)
    expect_hex(usb_sts, UhciConst.reset_val["USBSTS"], "USB Status Register")

    usb_intr = tb.read_io_le(io_base + 0x4, 16)
    expect_hex(usb_intr, UhciConst.reset_val["USBINTR"], "USB Interrupt Enable")

    frm_num = tb.read_io_le(io_base + 0x6, 16)
    expect_hex(frm_num, UhciConst.reset_val["FRNUM"], "Frame Number Register")

    frm_bar = tb.read_io_le(io_base + 0x8, 32)
    expect_hex(frm_bar, UhciConst.reset_val["FRBASEADD"], "Frame List Base Address Register")

    start = tb.read_io_le(io_base + 0xC, 8)
    expect_hex(start, UhciConst.reset_val["SOFMOD"], "Start of Frame Modify Register")

    port_sc0 = tb.read_io_le(io_base + 0x10, 16)
    expect_hex(port_sc0, UhciConst.reset_val["PORTSC0"], "Port 0 Status/Control Register")

    port_sc1 = tb.read_io_le(io_base + 0x12, 16)
    expect_hex(port_sc1, UhciConst.reset_val["PORTSC1"], "Port 1 Status/Control Register")


for i in range(ich9_uhci_cnt):
    do_test(i)
