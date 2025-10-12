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


# s-spi-erase.py
# tests the ERASE command of SPI flash in the ICH9

from tb_spi import *

import random

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

# Unit size used when reading from the flash. The GBEBAR only supports
# 4 byte accesses while the SPIBAR supports 64-byte accesses.
def get_bytes_per_unit(bar):
    return { SPIBAR: 64, GBEBAR: 4, }[bar]

fake_data = [((~i) & 0xFF) for i in range(flash_rom_size)]


def verify_erase_result(bar, len):
    off = fdata0_off
    read_out = []
    while off < (fdata0_off + len):
        read_val = tb.read_value_le(bar + off, 32)
        read_out +=list(dev_util.value_to_tuple_le(read_val,4))
        off += 4
    expected = [0xFF for i in range(len)]
    expect_list(read_out, expected, "data compare after page erase")


def issue_read_cmd(bar, read_addr, read_len):
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


def fill_all_sel_unit(selected):
    for (start, size) in selected:
        tb.fill_flash(start, fake_data[start : start + size], False)


def issue_hw_erase_cmd(bar, address):
    # Tell SPI the write address
    tb.write_value_le(bar + faddr_off, 32, address)

    # Program the flash control register with WRITE command
    ctrl = hsfc_bf.value(SME = 1, DBC = 0,
                         FCYCLE = 0x3, FGO = 1)

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



def test_sw_sector_erase_command(bar):
    # Test the sector erase command

    # First, Pick up one random address within the flash size:
    addr = 0xFFFFFFFF
    while (addr >= flash_rom_size):
        addr = int(random.random() * (0xFFFFFFFF))
    first = addr - (addr % spi_flash_sector_size)
    last = first + spi_flash_sector_size

    # then choose some small-pieces to check (not check whole sector
    # for saving time)
    bpu = get_bytes_per_unit(bar)
    rand_sel = build_random_selector(first // bpu, last // bpu, bpu)

    # Fill data into the sector include choose address:
    fill_all_sel_unit(rand_sel)

    # issue ERASE command (need Wr_EN_Prefix)
    tb.write_value_le(bar + faddr_off, 32, addr)
    ctrl = ssfc_bf.value(SCF = 0o01, SME = 1, DS = 0, DBC = 0,
                         COP = M25p80Const.sector_erase_index,
                         #SPOP = ICH9_SPI_WRITE_DIS_PREFIX,
                         SPOP = ICH9_SPI_WRITE_EN_PREFIX,
                         ACS = 1, SCGO = 1)
    tb.write_value_le(bar + ssfc_off, ssfc_bits, ctrl)
    simics.SIM_continue(1)

    for (start, size) in rand_sel:
        issue_read_cmd(bar, start, size)
        verify_erase_result(bar, size)       #at uint 64 Bytes


def test_sw_bulk_erase_command(bar):
    # Test the bulk erase command

    # just select a few small block to test for saving time
    bpu = get_bytes_per_unit(bar)
    rand_sel = build_random_selector(0, flash_rom_size // bpu, bpu)

    # Fill data into the sector include choose address:
    fill_all_sel_unit(rand_sel)

    # issue Bulk_ERASE command (need Wr_EN_Prefix), need no address specify
    #tb.write_value_le(bar + faddr_off, 32, addr)
    ctrl = ssfc_bf.value(SCF = 0o01, SME = 1, DS = 0, DBC = 0,
                         COP = M25p80Const.bulk_erase_index,
                         SPOP = ICH9_SPI_WRITE_EN_PREFIX,
                         ACS = 1, SCGO = 1)
    tb.write_value_le(bar + ssfc_off, ssfc_bits, ctrl)
    simics.SIM_continue(1)

    for (start, size) in rand_sel:
        issue_read_cmd(bar, start, size)
        verify_erase_result(bar, size)       #at uint 64 Bytes



def test_hw_erase_command(bar):
    # Test the sector erase command

    bpu = get_bytes_per_unit(bar)
    rand_sel = build_random_selector(0, flash_rom_size // bpu, bpu)

    # Fill data into the sector include choose address:
    fill_all_sel_unit(rand_sel)

    # issue ERASE command (need Wr_EN_Prefix)
    issue_hw_erase_cmd(bar, 0x0)

    for (start, size) in rand_sel:
        issue_hw_read_cmd(bar, start, size)
        verify_erase_result(bar, size)       #at uint 64 Bytes

def test_unit(bar):
    # access through 'hsfc' register
    test_hw_erase_command(bar)

    # access through 'ssfc' register
    test_sw_sector_erase_command(bar)
    test_sw_bulk_erase_command(bar)

def do_test():
    test_unit(SPIBAR)
    test_unit(GBEBAR)


tb = TestBench(1, True, False)
do_test()
