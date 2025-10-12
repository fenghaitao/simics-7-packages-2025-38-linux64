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


# s-smbus-reset.py
# tests the reset state of ICH9 SMBus controller module

from smbus_tb import *

def do_test():
    vid = tb.read_value_le(smbus_reg_addr, 16)
    expect_hex(vid, SmbusConst.reset_val["VID"], "Vendor identification")
    did = tb.read_value_le(smbus_reg_addr + 2, 16)
    expect_hex(did, SmbusConst.reset_val["DID"], "Device identification")

    cmd = tb.read_value_le(smbus_reg_addr + 4, 16)
    expect_hex(cmd, SmbusConst.reset_val["CMD"], "Command")
    sts = tb.read_value_le(smbus_reg_addr + 6, 16)
    expect_hex(sts, SmbusConst.reset_val["STS"], "Status")

    rid = tb.read_value_le(smbus_reg_addr + 8, 8)
    expect_hex(rid, SmbusConst.reset_val["RID"], "Revision Identification")
    pi = tb.read_value_le(smbus_reg_addr + 9, 8)
    expect_hex(pi, SmbusConst.reset_val["PI"], "Programming Interface")
    scc = tb.read_value_le(smbus_reg_addr + 0xA, 8)
    expect_hex(scc, SmbusConst.reset_val["SCC"], "Sub Class Code")
    bcc = tb.read_value_le(smbus_reg_addr + 0xB, 8)
    expect_hex(bcc, SmbusConst.reset_val["BCC"], "Base Class Code")

    bar0 = tb.read_value_le(smbus_reg_addr + 0x10, 32)
    expect_hex(bar0, SmbusConst.reset_val["BAR0"], "SMBus Memory Base Address 0")
    bar1 = tb.read_value_le(smbus_reg_addr + 0x14, 32)
    expect_hex(bar1, SmbusConst.reset_val["BAR1"], "SMBus Memory Base Address 1")
    base = tb.read_value_le(smbus_reg_addr + 0x20, 32)
    expect_hex(base, SmbusConst.reset_val["BASE"], "SMBus Base Address Register")

    svid = tb.read_value_le(smbus_reg_addr + 0x2C, 16)
    expect_hex(svid, SmbusConst.reset_val["SVID"], "Subsystem Vendor ID")
    sid = tb.read_value_le(smbus_reg_addr + 0x2E, 16)
    expect_hex(sid, SmbusConst.reset_val["SID"], "Subsystem ID")

    intln = tb.read_value_le(smbus_reg_addr + 0x3C, 8)
    expect_hex(intln, SmbusConst.reset_val["INTLN"], "Interrupt Line")
    intpn = tb.read_value_le(smbus_reg_addr + 0x3D, 8)
    expect_hex(intpn, SmbusConst.reset_val["INTPN"], "Interrupt Pin")

    # Host configuration
    hostc = tb.read_value_le(smbus_reg_addr + 0x40, 8)
    expect_hex(hostc, SmbusConst.reset_val["HOSTC"], "Host Configuration Register")

    # Map the smbus function register bank
    tb.map_smbus_func(smbus_mapped_addr)

    # Read the smbus function registers
    hst_sts = tb.read_io_le(smbus_mapped_addr, 8)
    expect_hex(hst_sts, SmbusConst.reset_val["HST_STS"], "Host Status")
    hst_cnt = tb.read_io_le(smbus_mapped_addr + 0x2, 8)
    expect_hex(hst_cnt, SmbusConst.reset_val["HST_CNT"], "Host Control")
    hst_cmd = tb.read_io_le(smbus_mapped_addr + 0x3, 8)
    expect_hex(hst_cmd, SmbusConst.reset_val["HST_CMD"], "Host Command")

    xmit_slva = tb.read_io_le(smbus_mapped_addr + 0x4, 8)
    expect_hex(xmit_slva, SmbusConst.reset_val["XMIT_SLVA"], "Transmit Slave Address")
    hst_d0 = tb.read_io_le(smbus_mapped_addr + 0x5, 8)
    expect_hex(hst_d0, SmbusConst.reset_val["HST_D0"], "Host Data 0")
    hst_d1 = tb.read_io_le(smbus_mapped_addr + 0x6, 8)
    expect_hex(hst_d1, SmbusConst.reset_val["HST_D1"], "Host Data 1")
    host_blk_db = tb.read_io_le(smbus_mapped_addr + 0x7, 8)
    expect_hex(host_blk_db, SmbusConst.reset_val["HOST_BLK_DB"], "Host Block Data Byte")

    pec = tb.read_io_le(smbus_mapped_addr + 0x8, 8)
    expect_hex(pec, SmbusConst.reset_val["PEC"], "Packet Error Check")

    rcv_slva = tb.read_io_le(smbus_mapped_addr + 0x9, 8)
    expect_hex(rcv_slva, SmbusConst.reset_val["RCV_SLVA"], "Receive Slave Address")
    slv_data = tb.read_io_le(smbus_mapped_addr + 0xA, 16)
    expect_hex(slv_data, SmbusConst.reset_val["SLV_DATA"], "Receive Slave Data")

    aux_sts = tb.read_io_le(smbus_mapped_addr + 0xC, 8)
    expect_hex(aux_sts, SmbusConst.reset_val["AUX_STS"], "Auxiliary Status")
    aux_ctl = tb.read_io_le(smbus_mapped_addr + 0xD, 8)
    expect_hex(aux_ctl, SmbusConst.reset_val["AUX_CTL"], "Auxiliary Control")

    smlink_pin_ctl = tb.read_io_le(smbus_mapped_addr + 0xE, 8)
    expect_hex(smlink_pin_ctl, SmbusConst.reset_val["SMLINK_PIN_CTL"], "SMLink Pin Control")
    smbus_pin_ctl = tb.read_io_le(smbus_mapped_addr + 0xF, 8)
    expect_hex(smbus_pin_ctl, SmbusConst.reset_val["SMBUS_PIN_CTL"], "SMBus Pin Control")

    slv_sts = tb.read_io_le(smbus_mapped_addr + 0x10, 8)
    expect_hex(slv_sts, SmbusConst.reset_val["SLV_STS"], "Slave Status")
    slv_cmd = tb.read_io_le(smbus_mapped_addr + 0x11, 8)
    expect_hex(slv_cmd, SmbusConst.reset_val["SLV_CMD"], "Slave Command")

    notify_daddr = tb.read_io_le(smbus_mapped_addr + 0x14, 8)
    expect_hex(notify_daddr, SmbusConst.reset_val["NOTIFY_DADDR"], "Notify Device Address")
    notify_dlow = tb.read_io_le(smbus_mapped_addr + 0x16, 8)
    expect_hex(notify_dlow, SmbusConst.reset_val["NOTIFY_DLOW"], "Notify Data Low Byte")
    notify_dhigh = tb.read_io_le(smbus_mapped_addr + 0x17, 8)
    expect_hex(notify_dhigh, SmbusConst.reset_val["NOTIFY_DHIGH"], "Notify Data High Byte")

    tb.map_smbus_sram(0x888800000000)

do_test()
