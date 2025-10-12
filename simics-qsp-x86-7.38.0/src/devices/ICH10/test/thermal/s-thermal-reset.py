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


# s-thermal-reset.py
# tests the reset state of ICH9 thermal sensor module

from thermal_tb import *

def do_test():
    vid = tb.read_value_le(thermal_reg_addr, 16)
    expect_hex(vid, ThermalConst.reset_val["VID"], "Vendor identification")
    did = tb.read_value_le(thermal_reg_addr + 2, 16)
    expect_hex(did, ThermalConst.reset_val["DID"], "Device identification")
    cmd = tb.read_value_le(thermal_reg_addr + 4, 16)
    expect_hex(cmd, ThermalConst.reset_val["CMD"], "Command")
    sts = tb.read_value_le(thermal_reg_addr + 6, 16)
    expect_hex(sts, ThermalConst.reset_val["STS"], "Status")
    rid = tb.read_value_le(thermal_reg_addr + 8, 8)
    expect_hex(rid, ThermalConst.reset_val["RID"], "Revision Identification")
    pi = tb.read_value_le(thermal_reg_addr + 9, 8)
    expect_hex(pi, ThermalConst.reset_val["PI"], "Programming Interface")
    scc = tb.read_value_le(thermal_reg_addr + 0xA, 8)
    expect_hex(scc, ThermalConst.reset_val["SCC"], "Sub Class Code")
    bcc = tb.read_value_le(thermal_reg_addr + 0xB, 8)
    expect_hex(bcc, ThermalConst.reset_val["BCC"], "Base Class Code")
    cls = tb.read_value_le(thermal_reg_addr + 0xC, 8)
    expect_hex(cls, ThermalConst.reset_val["CLS"], "Cache Line Size")
    lt = tb.read_value_le(thermal_reg_addr + 0xD, 8)
    expect_hex(lt, ThermalConst.reset_val["LT"], "Latency Timer")
    htype = tb.read_value_le(thermal_reg_addr + 0xE, 8)
    expect_hex(htype, ThermalConst.reset_val["HTYPE"], "Header Type")
    bist = tb.read_value_le(thermal_reg_addr + 0xF, 8)
    expect_hex(bist, ThermalConst.reset_val["BIST"], "Built-in Self Test")
    tbar = tb.read_value_le(thermal_reg_addr + 0x10, 32)
    expect_hex(tbar, ThermalConst.reset_val["TBAR"], "Thermal Base")
    tbarh = tb.read_value_le(thermal_reg_addr + 0x14, 32)
    expect_hex(tbarh, ThermalConst.reset_val["TBARH"], "Thermal Base High DWord")
    svid = tb.read_value_le(thermal_reg_addr + 0x2C, 16)
    expect_hex(svid, ThermalConst.reset_val["SVID"], "Subsystem Vendor ID")
    sid = tb.read_value_le(thermal_reg_addr + 0x2E, 16)
    expect_hex(sid, ThermalConst.reset_val["SID"], "Subsystem ID")
    cap_ptr = tb.read_value_le(thermal_reg_addr + 0x34, 8)
    expect_hex(cap_ptr, ThermalConst.reset_val["CAP_PTR"], "Capabilities Pointer")
    intln = tb.read_value_le(thermal_reg_addr + 0x3C, 8)
    expect_hex(intln, ThermalConst.reset_val["INTLN"], "Interrupt Line")
    intpn = tb.read_value_le(thermal_reg_addr + 0x3D, 8)
    expect_hex(intpn, ThermalConst.reset_val["INTPN"], "Interrupt Pin")

    # Capabilities
    tbarb = tb.read_value_le(thermal_reg_addr + 0x40, 32)
    expect_hex(tbarb, ThermalConst.reset_val["TBARB"],
                        "BIOS Assigned Thermal Base Address")
    tbarbh = tb.read_value_le(thermal_reg_addr + 0x44, 32)
    expect_hex(tbarbh, ThermalConst.reset_val["TBARBH"],
                        "BIOS Assigned Thermal Base Address High DWord")
    pid = tb.read_value_le(thermal_reg_addr + 0x50, 16)
    expect_hex(pid, ThermalConst.reset_val["PID"],
                        "PCI Power Management Capability ID")
    pc = tb.read_value_le(thermal_reg_addr + 0x52, 16)
    expect_hex(pc, ThermalConst.reset_val["PC"],
                        "PCI Power Management Capabilities")
    pcs = tb.read_value_le(thermal_reg_addr + 0x54, 32)
    expect_hex(pcs, ThermalConst.reset_val["PCS"],
                        "PCI Power Management Control and Status")

    # Map the thermal function register bank
    tb.map_thermal_func(thermal_mapped_addr)

    # Read the thermal function registers
    ts0e = tb.read_value_le(thermal_mapped_addr + 1, 8)
    expect_hex(ts0e, ThermalConst.reset_val["TS0E"], "Thermal Sensor 0 Enable")
    ts0s = tb.read_value_le(thermal_mapped_addr + 2, 8)
    expect_hex(ts0s, ThermalConst.reset_val["TS0S"], "Thermal Sensor 0 Status")
    ts0ttp = tb.read_value_le(thermal_mapped_addr + 4, 32)
    expect_hex(ts0ttp, ThermalConst.reset_val["TS0TTP"],
                       "Thermal Sensor 0 Catastrophic Trip Point")
    ts0co = tb.read_value_le(thermal_mapped_addr + 8, 8)
    expect_hex(ts0co, ThermalConst.reset_val["TS0CO"],
                        "Thermal Sensor 0 Catastrophic Lock-Down")
    ts0pc = tb.read_value_le(thermal_mapped_addr + 0xE, 8)
    expect_hex(ts0pc, ThermalConst.reset_val["TS0PC"],
                        "Thermal Sensor 0 Policy Control")
    ts0lock = tb.read_value_le(thermal_mapped_addr + 0x83, 8)
    expect_hex(ts0lock, ThermalConst.reset_val["TS0LOCK"],
                        "Thermal Sensor 0 Register Lock Control")

    ts1e = tb.read_value_le(thermal_mapped_addr + 0x41, 8)
    expect_hex(ts1e, ThermalConst.reset_val["TS1E"], "Thermal Sensor 1 Enable")
    ts1s = tb.read_value_le(thermal_mapped_addr + 0x42, 8)
    expect_hex(ts1s, ThermalConst.reset_val["TS1S"], "Thermal Sensor 1 Status")
    ts1ttp = tb.read_value_le(thermal_mapped_addr + 0x44, 32)
    expect_hex(ts1ttp, ThermalConst.reset_val["TS1TTP"],
                       "Thermal Sensor 1 Catastrophic Trip Point")
    ts1co = tb.read_value_le(thermal_mapped_addr + 0x48, 8)
    expect_hex(ts1co, ThermalConst.reset_val["TS1CO"],
                        "Thermal Sensor 1 Catastrophic Lock-Down")
    ts1pc = tb.read_value_le(thermal_mapped_addr + 0x4E, 8)
    expect_hex(ts1pc, ThermalConst.reset_val["TS1PC"],
                        "Thermal Sensor 1 Policy Control")
    ts1lock = tb.read_value_le(thermal_mapped_addr + 0xC3, 8)
    expect_hex(ts1lock, ThermalConst.reset_val["TS1LOCK"],
                        "Thermal Sensor 1 Register Lock Control")

do_test()
