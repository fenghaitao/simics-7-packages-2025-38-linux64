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


# s-thermal-func.py
# tests the function registers of thermal sensor module in ICH9

from thermal_tb import *

stest.untrap_log("spec-viol")

def do_test():
    # Map the thermal function register bank
    tb.map_thermal_func(thermal_mapped_addr)

    tb.write_value_le(thermal_mapped_addr + 1, 8, 0xBB)
    tse = tb.read_value_le(thermal_mapped_addr + 1, 8)
    expect_hex(tse, 0x00, "Default value of thermal sensor 0 enable")
    tb.write_value_le(thermal_mapped_addr + 0x41, 8, 0xBB)
    tse = tb.read_value_le(thermal_mapped_addr + 0x41, 8)
    expect_hex(tse, 0x00, "Default value of thermal sensor 1 enable")

    tb.write_value_le(thermal_mapped_addr + 1, 8, 0xBA)
    tse = tb.read_value_le(thermal_mapped_addr + 1, 8)
    expect_hex(tse, 0xBA, "Enabled value of thermal sensor 0 enable")
    tb.write_value_le(thermal_mapped_addr + 0x41, 8, 0xBA)
    tse = tb.read_value_le(thermal_mapped_addr + 0x41, 8)
    expect_hex(tse, 0xBA, "Enabled value of thermal sensor 1 enable")

    # Program the temperature of catastrophic trip point
    tb.write_value_le(thermal_mapped_addr + 0x4, 32, 66)
    ts_ttp = tb.read_value_le(thermal_mapped_addr + 0x4, 32)
    expect_hex(ts_ttp, 66, "Programmed temperature of catastrophic trip point in sensor 0")
    tb.write_value_le(thermal_mapped_addr + 0x44, 32, 66)
    ts_ttp = tb.read_value_le(thermal_mapped_addr + 0x44, 32)
    expect_hex(ts_ttp, 66, "Programmed temperature of catastrophic trip point in sensor 1")

    # Lock the catastrophic trip point
    tb.write_value_le(thermal_mapped_addr + 0x8, 8, 0x80)
    tb.write_value_le(thermal_mapped_addr + 0x48, 8, 0x80)

    # Test the locks
    tb.write_value_le(thermal_mapped_addr + 0x4, 32, 88)
    ts_ttp = tb.read_value_le(thermal_mapped_addr + 0x4, 32)
    expect_hex(ts_ttp, 66, "Locked temperature of catastrophic trip point in sensor 0")
    tb.write_value_le(thermal_mapped_addr + 0x44, 32, 88)
    ts_ttp = tb.read_value_le(thermal_mapped_addr + 0x44, 32)
    expect_hex(ts_ttp, 66, "Locked temperature of catastrophic trip point in sensor 1")

    # Try to unlock the locks, and fail
    tb.write_value_le(thermal_mapped_addr + 0x8, 8, 0x00)
    tb.write_value_le(thermal_mapped_addr + 0x48, 8, 0x00)
    ts_co = tb.read_value_le(thermal_mapped_addr + 0x8, 8)
    expect_hex(ts_co, 0x80, "Locked lock-down register in sensor 0")
    ts_co = tb.read_value_le(thermal_mapped_addr + 0x48, 8)
    expect_hex(ts_co, 0x80, "Locked lock-down register in sensor 1")

    # Select the policy in policy control register
    tb.write_value_le(thermal_mapped_addr + 0xE, 8, 0x40)
    tb.write_value_le(thermal_mapped_addr + 0x4E, 8, 0x40)

    # Failed lock of the policy
    tb.write_value_le(thermal_mapped_addr + 0xE, 8, 0xC0)
    ts_pc = tb.read_value_le(thermal_mapped_addr + 0xE, 8)
    expect_hex(ts_pc, 0x40,
        "Unlocked policy when register lock control is not locked in sensor 0")
    tb.write_value_le(thermal_mapped_addr + 0x4E, 8, 0xC0)
    ts_pc = tb.read_value_le(thermal_mapped_addr + 0x4E, 8)
    expect_hex(ts_pc, 0x40,
        "Unlocked policy when register lock control is not locked in sensor 1")

    # Succeeded lock of the policy
    tb.write_value_le(thermal_mapped_addr + 0x83, 8, 0x4)
    tb.write_value_le(thermal_mapped_addr + 0xE, 8, 0xC0)
    ts_pc = tb.read_value_le(thermal_mapped_addr + 0xE, 8)
    expect_hex(ts_pc, 0xC0,
        "Locked policy when register lock control is locked in sensor 0")
    tb.write_value_le(thermal_mapped_addr + 0xC3, 8, 0x4)
    tb.write_value_le(thermal_mapped_addr + 0x4E, 8, 0xC0)
    ts_pc = tb.read_value_le(thermal_mapped_addr + 0x4E, 8)
    expect_hex(ts_pc, 0xC0,
        "Locked policy when register lock control is locked in sensor 1")

    # Failed to clear the policy now
    tb.write_value_le(thermal_mapped_addr + 0xE, 8, 0x00)
    tb.write_value_le(thermal_mapped_addr + 0x4E, 8, 0x00)
    ts_pc = tb.read_value_le(thermal_mapped_addr + 0xE, 8)
    expect_hex(ts_pc, 0xC0, "Locked policy in sensor 0")
    ts_pc = tb.read_value_le(thermal_mapped_addr + 0x4E, 8)
    expect_hex(ts_pc, 0xC0, "Locked policy in sensor 1")

    # Check the status bit
    SIM_continue(thermal_sensing_period - 1)
    ts0s = tb.read_value_le(thermal_mapped_addr + 0x2, 8)
    ts1s = tb.read_value_le(thermal_mapped_addr + 0x42, 8)
    expect_hex(ts0s, 0x0, "Status before the first sensing in sensor 0 is 0")
    expect_hex(ts1s, 0x0, "Status before the first sensing in sensor 1 is 0")

    SIM_continue(1)
    ts0s = tb.read_value_le(thermal_mapped_addr + 0x2, 8)
    ts1s = tb.read_value_le(thermal_mapped_addr + 0x42, 8)
    expect_hex(ts0s, 0x0,
        "The temperature 38 is below the catastrophic setting 66 in sensor 0")
    expect_hex(ts1s, 0x80,
        "The temperature 83 is above the catastrophic setting 66 in sensor 1")

do_test()
