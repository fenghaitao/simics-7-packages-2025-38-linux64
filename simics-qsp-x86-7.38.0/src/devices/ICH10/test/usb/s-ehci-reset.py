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

for i in range(ich9_ehci_cnt):
    tb.ehci[i].log_level = 1

def do_test(ehci_idx):
    base = ich9_ehci_reg_addr[ehci_idx]
    io_base     = ich9_ehci_io_base[ehci_idx]

    vid = tb.read_value_le(base, 16)
    expect_hex(vid, EhciConst.reset_val["VID"], "Vendor identification")
    did = tb.read_value_le(base + 2, 16)
    expect_hex(did, EhciConst.reset_val["DID"] + 2 * ehci_idx, "Device identification of EHCI %d" % ehci_idx)

    cmd = tb.read_value_le(base + 4, 16)
    expect_hex(cmd, EhciConst.reset_val["CMD"], "Command")
    sts = tb.read_value_le(base + 6, 16)
    expect_hex(sts, EhciConst.reset_val["STS"], "Status")

    rid = tb.read_value_le(base + 8, 8)
    expect_hex(rid, EhciConst.reset_val["RID"], "Revision Identification")
    pi = tb.read_value_le(base + 9, 8)
    expect_hex(pi, EhciConst.reset_val["PI"], "Programming Interface")
    scc = tb.read_value_le(base + 0xA, 8)
    expect_hex(scc, EhciConst.reset_val["SCC"], "Sub Class Code")
    bcc = tb.read_value_le(base + 0xB, 8)
    expect_hex(bcc, EhciConst.reset_val["BCC"], "Base Class Code")
    pmlt = tb.read_value_le(base + 0xD, 8)
    expect_hex(pmlt, EhciConst.reset_val["PMLT"], "Primary Master Latency Timer Register")

    ehci_bar = tb.read_value_le(base + 0x10, 32)
    expect_hex(ehci_bar, EhciConst.reset_val["BAR0"], "EHCI Memory Base Address Register")

    svid = tb.read_value_le(base + 0x2C, 16)
    expect_hex(svid, EhciConst.reset_val["SVID"], "Subsystem Vendor ID")
    sid = tb.read_value_le(base + 0x2E, 16)
    expect_hex(sid, EhciConst.reset_val["SID"], "Subsystem ID")

    captr = tb.read_value_le(base + 0x34, 8)
    expect_hex(captr, EhciConst.reset_val["CAPTR"], "Capabilities Pointer")

    intln = tb.read_value_le(base + 0x3C, 8)
    expect_hex(intln, EhciConst.reset_val["INTLN"], "Interrupt Line")
    intpn = tb.read_value_le(base + 0x3D, 8)
    ehci_pin_rst = [1, 3]
    expect_hex(intpn, ehci_pin_rst[ehci_idx], "Interrupt Pin")

    # Capability registers
    pwr_capid = tb.read_value_le(base + 0x50, 8)
    expect_hex(pwr_capid, EhciConst.reset_val["PWR_CAPID"], "PCI Power Management Capability ID")

    nxt_ptr1 = tb.read_value_le(base + 0x51, 8)
    expect_hex(nxt_ptr1, EhciConst.reset_val["NXT_PTR1"], "Next Item Pointer #1 Register")

    pwr_cap = tb.read_value_le(base + 0x52, 16)
    expect_hex(pwr_cap, EhciConst.reset_val["PWR_CAP"], "Power Management Capabilities Register")

    pwr_cntl_sts = tb.read_value_le(base + 0x54, 16)
    expect_hex(pwr_cntl_sts, EhciConst.reset_val["PWR_CNTL_STS"], "Power Management Control/Status Register")

    debug_capid = tb.read_value_le(base + 0x58, 8)
    expect_hex(debug_capid, EhciConst.reset_val["DEBUG_CAPID"], "Debug Port Capability ID Register")

    nxt_ptr2 = tb.read_value_le(base + 0x59, 8)
    expect_hex(nxt_ptr2, EhciConst.reset_val["NXT_PTR2"], "Next Item Pointer #2 Register")

    debug_base = tb.read_value_le(base + 0x5A, 16)
    expect_hex(debug_base, EhciConst.reset_val["DEBUG_BASE"], "Debug Port Base Offset Register")

    usb_relnum = tb.read_value_le(base + 0x60, 8)
    expect_hex(usb_relnum, EhciConst.reset_val["USB_RELNUM"], "USB Release Number Register")

    fl_adj = tb.read_value_le(base + 0x61, 8)
    expect_hex(fl_adj, EhciConst.reset_val["FL_ADJ"], "Frame Length Adjustment Register")

    pwake_cap = tb.read_value_le(base + 0x62, 16)
    expect_hex(pwake_cap, EhciConst.reset_val["PWAKE_CAP"], "Port Wake Capability Register")

    leg_ext_cap = tb.read_value_le(base + 0x68, 32)
    expect_hex(leg_ext_cap, EhciConst.reset_val["LEG_EXT_CAP"], "USB EHCI Legacy Support Extended Capability Register")

    leg_ext_cs = tb.read_value_le(base + 0x6C, 32)
    expect_hex(leg_ext_cs, EhciConst.reset_val["LEG_EXT_CS"], "USB EHCI Legacy Support Extended Control/State Register")

    special_smi = tb.read_value_le(base + 0x70, 32)
    expect_hex(special_smi, EhciConst.reset_val["SPECIAL_SMI"], "Intel Specific USB 2.0 SMI Register")

    access_cntl = tb.read_value_le(base + 0x80, 8)
    expect_hex(access_cntl, EhciConst.reset_val["ACCESS_CNTL"], "Access Control Register")

    ehciir1 = tb.read_value_le(base + 0x84, 8)
    expect_hex(ehciir1, EhciConst.reset_val["EHCIIR1"], "EHCI Initialization Register 1")

    flrcid = tb.read_value_le(base + 0x98, 8)
    expect_hex(flrcid, EhciConst.reset_val["FLRCID"], "Function Level Reset Capability ID")

    flrncp = tb.read_value_le(base + 0x99, 8)
    expect_hex(flrncp, EhciConst.reset_val["FLRNCP"], "Function Level Reset Next Capability Pointer")

    flrclv = tb.read_value_le(base + 0x9A, 16)
    expect_hex(flrclv, EhciConst.reset_val["FLRCLV"], "Function Level Reset Capability Length and Version")

    flrctrl = tb.read_value_le(base + 0x9C, 8)
    expect_hex(flrctrl, EhciConst.reset_val["FLRCTRL"], "FLR Control Register")

    flrstat = tb.read_value_le(base + 0x9D, 8)
    expect_hex(flrstat, EhciConst.reset_val["FLRSTAT"], "FLR Status Register")

    ehciir2 = tb.read_value_le(base + 0xFC, 32)
    expect_hex(ehciir2, EhciConst.reset_val["EHCIIR2"], "EHCI Configuration Register 2")


    # USB I/O registers
    tb.map_hc_mem("ehci", ehci_idx)

    caplength = tb.read_value_le(io_base + 0x0, 8)
    expect_hex(caplength, EhciConst.reset_val["CAPLENGTH"], "Capability Registers Length Register")

    hciversion = tb.read_value_le(io_base + 0x2, 16)
    expect_hex(hciversion, EhciConst.reset_val["HCIVERSION"], "Host Controller Interface Version Number")

    hcsparams = tb.read_value_le(io_base + 0x4, 32)
    expect_hex(hcsparams, EhciConst.reset_val["HCSPARAMS"], "Host Controller Structural Parameters")

    hccparams = tb.read_value_le(io_base + 0x8, 32)
    expect_hex(hccparams, EhciConst.reset_val["HCCPARAMS"], "Host Controller Capability Parameters")

    usb20_cmd = tb.read_value_le(io_base + 0x20, 32)
    expect_hex(usb20_cmd, EhciConst.reset_val["USB2.0_CMD"], "USB 2.0 Command Register")

    usb20_sts = tb.read_value_le(io_base + 0x24, 32)
    expect_hex(usb20_sts, EhciConst.reset_val["USB2.0_STS"], "USB 2.0 Status Register")

    usb20_intr = tb.read_value_le(io_base + 0x28, 32)
    expect_hex(usb20_intr, EhciConst.reset_val["USB2.0_INTR"], "USB 2.0 Interrupt Enable")

    frindex = tb.read_value_le(io_base + 0x2C, 32)
    expect_hex(frindex, EhciConst.reset_val["USB2.0_INTR"], "USB 2.0 Frame Index")

    ctrldssegment = tb.read_value_le(io_base + 0x30, 32)
    expect_hex(ctrldssegment, EhciConst.reset_val["CTRLDSSEGMENT"], "Control Data Structure Segment")

    periodiclistbase = tb.read_value_le(io_base + 0x34, 32)
    expect_hex(periodiclistbase, EhciConst.reset_val["PERIODICLISTBASE"], "Periodic Frame List Base Address")

    asynclistaddr = tb.read_value_le(io_base + 0x38, 32)
    expect_hex(asynclistaddr, EhciConst.reset_val["ASYNCLISTADDR"], "Current Asynchronous List Address")

    configflag = tb.read_value_le(io_base + 0x60, 32)
    expect_hex(configflag, EhciConst.reset_val["CONFIGFLAG"], "Configure Flag")

    port0sc = tb.read_value_le(io_base + 0x64, 32)
    expect_hex(port0sc, EhciConst.reset_val["PORT0SC"], "Port 0 Status and Control")

    port1sc = tb.read_value_le(io_base + 0x68, 32)
    expect_hex(port1sc, EhciConst.reset_val["PORT1SC"], "Port 1 Status and Control")

    port2sc = tb.read_value_le(io_base + 0x6C, 32)
    expect_hex(port2sc, EhciConst.reset_val["PORT2SC"], "Port 2 Status and Control")

    port3sc = tb.read_value_le(io_base + 0x70, 32)
    expect_hex(port3sc, EhciConst.reset_val["PORT3SC"], "Port 3 Status and Control")

    port4sc = tb.read_value_le(io_base + 0x74, 32)
    expect_hex(port4sc, EhciConst.reset_val["PORT4SC"], "Port 4 Status and Control")

    port5sc = tb.read_value_le(io_base + 0x78, 32)
    expect_hex(port5sc, EhciConst.reset_val["PORT5SC"], "Port 5 Status and Control")

for i in range(ich9_ehci_cnt):
    do_test(i)
