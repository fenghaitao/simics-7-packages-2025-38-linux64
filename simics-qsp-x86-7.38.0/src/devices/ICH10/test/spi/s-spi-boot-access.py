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


# s-spi-boot-access.py
# test the access of the SPI flash during the booting process
from tb_spi import *

def region_test_common(rgnName, rgnBase, rgnSize,
        rgnmapAddr, off_list, expectBytes, regs_bar):

    fregX_off = Ich9SpiConst.reg_info[rgnName][0]
    fregX_bits = Ich9SpiConst.reg_info[rgnName][1] * 8
    val = tb.read_value_le(regs_bar + fregX_off, fregX_bits)
    members = flreg_bf.fields(val)
    val = members['RB'] << 12
    expect(val, rgnBase, "region base inside flash rom")
    val = members['RL'] << 12
    expect(val, rgnBase + rgnSize, "region limit inside flash rom")

    # Note: this should not be Addr-inside-Flash,
    # but be Addr-in-Ram where BIOS/GbE mapped to!
    for code_off in off_list:
        ram_addr = rgnmapAddr + code_off
        val = tb.read_value_le(ram_addr, 32)
        #print "val=0x%x @0x%x" % (val, ram_addr)
        ex_val = dev_util.tuple_to_value_le(
                tuple(expectBytes[code_off : code_off + 4]))
        expect_hex(val, ex_val,
                "boot code at address 0x%x" % ram_addr)

def bios_region_test():
    region_test_common('FREG1', REGION1_BASE,
            BIOS_SIZE, BIOS_FLASH_MAP_ADDR, bios_off_list, tb.boot_codes,
                       SPIBAR)

def gbe_region_test():
    region_test_common('FREG3', REGION3_BASE,
            GBE_SIZE, GBE_FLASH_MAP_ADDR, gbe_off_list, tb.gbe_codes,
                       GBEBAR)


def do_test():
    bios_region_test()
    gbe_region_test()

def get_off_list(rgnSize):
    off_list = [0]
    iLoop = 0
    while (iLoop < 8):
        off_list += [int((rgnSize - 4) * random.random())]
        iLoop += 1
    off_list += [rgnSize - 4]
    return off_list

tb = TestBench(4, False, False)

#prepare BIOS/GbE region
bios_off_list = get_off_list(BIOS_SIZE)
gbe_off_list = get_off_list(GBE_SIZE)

tb.construct_region1_rand(tb.boot_codes, bios_off_list)
tb.construct_region3_rand(tb.gbe_codes, gbe_off_list)

do_test()
