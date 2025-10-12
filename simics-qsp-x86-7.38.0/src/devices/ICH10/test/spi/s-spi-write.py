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


# s-spi-write.py
# tests the PAGE PROGRAM opcode of SPI flash in the ICH9

from tb_spi import *

import random
random.seed("The Be Good Tanyas")

ssfc_off    = Ich9SpiConst.reg_info["SSFC"][0]
ssfc_bits   = Ich9SpiConst.reg_info["SSFC"][1] * 8
ssfs_off    = Ich9SpiConst.reg_info["SSFS"][0]
ssfs_bits   = Ich9SpiConst.reg_info["SSFS"][1] * 8
ssfs_clear  = ssfs_bf.value(CDS = 1)

hsfc_off    = Ich9SpiConst.reg_info["HSFCTL"][0]
hsfc_bits   = Ich9SpiConst.reg_info["HSFCTL"][1] * 8
hsfs_off    = Ich9SpiConst.reg_info["HSFSTS"][0]
hsfs_bits   = Ich9SpiConst.reg_info["HSFSTS"][1] * 8

fdata0_off  = Ich9SpiConst.reg_info["FDATA0"][0]
faddr_off   = Ich9SpiConst.reg_info["FADDR"][0]

# Unit size used for the test when reading from the flash. The GBEBAR
# only supports 4 byte accesses while the SPIBAR supports up to 64-byte
# accesses.
def get_bytes_per_unit(bar):
    return { SPIBAR: 8, GBEBAR: 4 }[bar]

def put_data_to_fdata_regs(bar, data):
    reg_off = fdata0_off
    data_len = len(data)
    assert (data_len % 4 == 0)
    index = 0
    while reg_off < (fdata0_off + data_len):
        # default REGS_BAR is 0x3800
        val = dev_util.tuple_to_value_le(tuple(data[index: index + 4]))
        tb.write_value_le(bar + reg_off, 32, val)
        reg_off += 4
        index += 4

def put_small_data_to_fdata_regs(bar, data):
    data_len = len(data)
    assert (data_len < 4)
    # default REGS_BAR is 0x3800
    val = dev_util.tuple_to_value_le(tuple(data[0: data_len]))
    tb.write_value_le(bar + fdata0_off, 32, val)


def verify_write_result(bar, expect):
    off = fdata0_off
    data_len = len(expect)
    read_out = []
    while off < (fdata0_off + data_len):
        read_val = tb.read_value_le(bar + off, 32)
        read_out +=list(dev_util.value_to_tuple_le(read_val,4))
        off += 4
    expect_list(read_out, expect, "data compare after page erase")

def verify_small_write_result(bar, expect):
    off = fdata0_off
    data_len = len(expect)
    assert (data_len < 4 )
    read_val = tb.read_value_le(bar + off, 32)
    read_out = list(dev_util.value_to_tuple_le(read_val,data_len))
    expect_list(read_out, expect, "data compare after page erase")

def issue_sw_write_cmd(bar, address, len):
    # Tell SPI the write address
    tb.write_value_le(bar + faddr_off, 32, address)

    # Program the flash control register with WRITE command
    ctrl = ssfc_bf.value(SCF = 0o01, SME = 1, DS = 1, DBC = len - 1,
                     COP = M25p80Const.page_program_index,
                     SPOP = ICH9_SPI_WRITE_EN_PREFIX,
                     ACS = 1, SCGO = 1)
    # Issue the command to SPI flash
    tb.write_value_le(bar + ssfc_off, ssfc_bits, ctrl)
    SIM_continue(1)


def issue_hw_erase_cmd(bar, address):
    # Tell SPI the write address
    tb.write_value_le(bar + faddr_off, 32, address)

    # Program the flash control register with WRITE command
    ctrl = hsfc_bf.value(SME = 1, DBC = 0,
                         FCYCLE = 0x3, FGO = 1)

    # Issue the command to SPI flash
    tb.write_value_le(bar + hsfc_off, hsfc_bits, ctrl)
    SIM_continue(1)


def issue_hw_write_cmd(bar, address, len):
    # Tell SPI the write address
    tb.write_value_le(bar + faddr_off, 32, address)

    # Program the flash control register with WRITE command
    ctrl = hsfc_bf.value(SME = 1, DBC = len - 1,
                         FCYCLE = 0x2, FGO = 1)

    # Issue the command to SPI flash
    tb.write_value_le(bar + hsfc_off, hsfc_bits, ctrl)
    SIM_continue(1)


def issue_hw_read_cmd(bar, read_addr, read_len):
    # Tell SPI the read address
    tb.write_value_le(bar + faddr_off, 32, read_addr)
    # Program the flash control register
    ctrl = hsfc_bf.value(SME = 1, DBC = read_len - 1,
                    FCYCLE = 0, FGO = 1)
    # Issue the command to SPI flash
    tb.write_value_le(bar + hsfc_off, hsfc_bits, ctrl)
    SIM_continue(1)
    # Examine the Flash Status register
    hsfs_val = tb.read_value_le(bar + hsfs_off, hsfs_bits)
    hsfs_val = hsfs_bf.fields(hsfs_val)
    expect(hsfs_val['FDONE'], 1, "cycle done status after the read command")


def issue_sw_read_cmd(bar, read_addr, read_len):
    # Tell SPI the read address
    tb.write_value_le(bar + faddr_off, 32, read_addr)
    # Program the flash control register
    ctrl = ssfc_bf.value(SCF = 0o01, SME = 1, DS = 1, DBC = read_len - 1,
                         COP = M25p80Const.read_index,
                         SPOP = ICH9_SPI_WRITE_DIS_PREFIX,
                         ACS = 0, SCGO = 1)
    # Issue the command to SPI flash
    tb.write_value_le(bar + ssfc_off, ssfc_bits, ctrl)
    SIM_continue(1)


def test_sw_write_command(bar):
    # configure data to write
    bpu = get_bytes_per_unit(bar)
    test_data = [ ~x & 0xFF for x in range(bpu)]

    # First, Pick up one random address within the flash size:
    addr = 0xFFFFFFFF
    while (addr >= flash_rom_size):
        addr = int(random.random() * (0xFFFFFFFF))
    first = addr - (addr % spi_flash_sector_size)
    last = first + spi_flash_sector_size
    # then, randomly select some small spices space to write:
    rand_sel = build_random_selector(first // bpu, last // bpu, bpu)

    for (start, size) in rand_sel:
        # Put data to SPI's FDATA registers:
        put_data_to_fdata_regs(bar, test_data)
        issue_sw_write_cmd(bar, start, size)
        issue_sw_read_cmd(bar, start, size)
        verify_write_result(bar, test_data)

# write dword case:
def test_hw_write_command(bar, piece_size):
    # configure data to write
    bpu = get_bytes_per_unit(bar)
    if (piece_size == 0):
        data_len = bpu
    else:
        assert ((piece_size % 4) == 0)
        data_len = piece_size

    test_data = [ ~x & 0xFF for x in range(data_len)]

    # First, Pick up one random address within the flash size:
    addr = 0xFFFFFFFF
    while (addr >= flash_rom_size):
        addr = int(random.random() * (0xFFFFFFFF))
    first = addr - (addr % spi_flash_sector_size)
    last = first + spi_flash_sector_size
    # then, randomly select some small spices space to write:
    rand_sel = build_random_selector(first // bpu, last // bpu, bpu)

    for (start, size) in rand_sel:
        # Put data to SPI's FDATA registers:
        put_data_to_fdata_regs(bar, test_data)
        # issue ERASE command before PAGE PROGRAM command (bug 21501)
        issue_hw_erase_cmd(bar, 0x0)
        issue_hw_write_cmd(bar, start, size)
        tb.clear_fdata_regs(bar, 16)
        issue_hw_read_cmd(bar, start, size)
        verify_write_result(bar, test_data)

# not dword, just 1 or 2 or 3 byte
def test_hw_write_small(bar, bytes_num):
    # configure data to write
    assert (bytes_num < 4) and (bytes_num > 0)
    data_len = bytes_num
    test_data = [ ~x & 0x8F for x in range(data_len)]

    # First, Pick up one random address within the flash size:
    addr = 0xFFFFFFFF
    while (addr >= flash_rom_size):
        addr = int(random.random() * (0xFFFFFFFF))
    first = addr - (addr % spi_flash_sector_size)
    last = first + spi_flash_sector_size
    # then, randomly select some small spices space to write:
    rand_sel = build_random_selector(first // data_len,
            last // data_len, data_len)

    for (start, size) in rand_sel:
        # Put data to SPI's FDATA registers:
        put_small_data_to_fdata_regs(bar, test_data)
        issue_hw_write_cmd(bar, start, size)
        tb.clear_fdata_regs(bar, 2)
        issue_hw_read_cmd(bar, start, size)
        if (((start & 0xFF) + size) < 0xFF):
            verify_small_write_result(bar, test_data)


# not dword, just 1 or 2 or 3 byte
def test_sw_write_small(bar, bytes_num):
    # configure data to write
    assert (bytes_num < 4) and (bytes_num > 0)
    data_len = bytes_num

    test_data = [ ~x & 0xFF for x in range(data_len)]

    # First, Pick up one random address within the flash size:
    addr = 0xFFFFFFFF
    while (addr >= flash_rom_size):
        addr = int(random.random() * (0xFFFFFFFF))
    first = addr - (addr % spi_flash_sector_size)
    last = first + spi_flash_sector_size
    # then, randomly select some small spices space to write:
    rand_sel = build_random_selector(first // data_len,
            last // data_len, data_len)

    for (start, size) in rand_sel:
        # Put data to SPI's FDATA registers:
        put_small_data_to_fdata_regs(bar, test_data)
        issue_sw_write_cmd(bar, start, size)
        tb.clear_fdata_regs(bar, 2)
        issue_sw_read_cmd(bar, start, size)
        if (((start & 0xFF) + size) < 0xFF):
            verify_small_write_result(bar, test_data)

def test_unit(bar):
    # access through 'hsfc' register
    test_hw_write_command(bar, 0)
    test_hw_write_small(bar, 1)
    test_hw_write_small(bar, 3)

    # access through 'ssfc' register
    test_sw_write_command(bar)
    test_sw_write_small(bar, 1)
    test_sw_write_small(bar, 3)


def do_test():
    test_unit(SPIBAR)
    test_unit(GBEBAR)

tb = TestBench(1, True, False)
do_test()
