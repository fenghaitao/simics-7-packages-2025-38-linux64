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


# s-spi-prog-access.py
# tests the programming register accessing of SPI flash in the ICH9

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
hsfs_clear  = hsfs_bf.value(FDONE = 1)

fdata0_off  = Ich9SpiConst.reg_info["FDATA0"][0]
faddr_off   = Ich9SpiConst.reg_info["FADDR"][0]

# maximal number of bytes which can be read from flash
def get_max_read_len(bar):
    return { SPIBAR: 64, GBEBAR: 4 }[bar]

def test_sw_read_command(bar):
    # Test the read command
    read_addr = 0x789
    read_len = get_max_read_len(bar)
    fake_data = [((~i) & 0xFF) for i in range(read_len)]
    # Clear the Cycle Done Status bit
    tb.write_value_le(bar + ssfs_off, ssfs_bits, ssfs_clear)
    # Fill data in the image
    tb.fill_flash(read_addr, fake_data)
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
    # Examine the Flash Status register
    ssfs_val = tb.read_value_le(bar + ssfs_off, ssfs_bits)
    ssfs_val = ssfs_bf.fields(ssfs_val)
    expect(ssfs_val['CDS'], 1, "cycle done status after the read command")

    # Get the readout
    read_out = []
    reg_off = fdata0_off
    while reg_off < (fdata0_off + read_len):
        reg_val = tb.read_value_le(bar + reg_off, 32)
        read_out += list(dev_util.value_to_tuple_le(reg_val, 4))
        reg_off += 4

    if reg_off - fdata0_off > read_len:
        del read_out[read_len:]

    expect_list(read_out, fake_data, "read data from the SPI flash")



def test_spi_status_register(bar):
    # Tell SPI the read address
    fl_addr = 0x876
    tb.write_value_le(bar + faddr_off, 32, fl_addr)

    # 1) Test the read status command
    # clear the Cycle Done Status bit first
    tb.write_value_le(bar + ssfs_off, ssfs_bits, ssfs_clear)
    ssfs_val = tb.read_value_le(bar + ssfs_off, ssfs_bits)
    ssfs_val = ssfs_bf.fields(ssfs_val)
    expect(ssfs_val['CDS'], 0, "cycle done status after write '1' clear")
    expect(ssfs_val['SCIP'], 0, "cycle done status after write '1' clear")

    ctrl = ssfc_bf.value(SCF = 0o01, SME = 1, DS = 1, DBC = 0,
                         COP = M25p80Const.read_index,
                         SPOP = ICH9_SPI_WRITE_DIS_PREFIX,
                         ACS = 0, SCGO = 1)
    tb.write_value_le(bar + ssfc_off, ssfc_bits, ctrl)

    # now examine the SPI status register again:
    ssfs_val = tb.read_value_le(bar + ssfs_off, ssfs_bits)
    ssfs_val = ssfs_bf.fields(ssfs_val)
    expect(ssfs_val['CDS'], 1, "cycle done status after the write command")
    expect(ssfs_val['SCIP'], 0, "cycle done status after the write command")


def test_hw_read_command(bar):
    # Test the read command
    read_addr = 0x789
    read_len = get_max_read_len(bar)
    fake_data = [((~i) & 0xFF) for i in range(read_len)]
    # Clear the Cycle Done Status bit
    val = tb.read_value_le(bar + hsfs_off, hsfs_bits)
    val |= 0x01  #write 'FDONE' '1' to clear
    tb.write_value_le(bar + hsfs_off, hsfs_bits, val)

    # Fill data in the image
    tb.fill_flash(read_addr, fake_data)

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

    # Get the readout
    read_out = []
    reg_off = fdata0_off
    while reg_off < (fdata0_off + read_len):
        reg_val = tb.read_value_le(bar + reg_off, 32)
        read_out += list(dev_util.value_to_tuple_le(reg_val, 4))
        reg_off += 4

    if reg_off - fdata0_off > read_len:
        del read_out[read_len:]

    expect_list(read_out, fake_data, "read data from the SPI flash")




def do_test(bar):
    # access through 'hsfc' register
    test_hw_read_command(bar)

    # access through 'ssfc' register
    test_sw_read_command(bar)
    test_spi_status_register(bar)

#run_command('log-level 4')
tb = TestBench(1, True, False)

do_test(SPIBAR)
do_test(GBEBAR)
