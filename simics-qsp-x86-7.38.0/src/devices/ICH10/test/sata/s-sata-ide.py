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


# s-sata-reset.py
# IDE mode of ICH9 SATA controllers

from sata_tb import *

def do_test_sata1():
    # PCI config

    expect_hex(tb.sata1_rd_pci_config(0x00, 16), 0x8086,      "VID")
    expect_hex(tb.sata1_rd_pci_config(0x02, 16),
               (0x2920, 0x3A20)[ich_prefix.startswith('ich10')],
               "DID")
    expect_hex(tb.sata1_rd_pci_config(0x04, 16), 0x0000,      "PCICMD")
    expect_hex(tb.sata1_rd_pci_config(0x06, 16), 0x02b0,      "PCISTS")
    expect_hex(tb.sata1_rd_pci_config(0x08,  8), 0x00,        "RID")
    expect_hex(tb.sata1_rd_pci_config(0x09,  8), 0x8a,        "PI")
    expect_hex(tb.sata1_rd_pci_config(0x0a,  8), 0x01,        "SCC")
    expect_hex(tb.sata1_rd_pci_config(0x0b,  8), 0x01,        "BCC")
    expect_hex(tb.sata1_rd_pci_config(0x0d,  8), 0x00,        "PMLT")
    expect_hex(tb.sata1_rd_pci_config(0x10, 32), 0x00000001,  "PCMD_BAR")
    expect_hex(tb.sata1_rd_pci_config(0x14, 32), 0x00000001,  "PCNL_BAR")
    expect_hex(tb.sata1_rd_pci_config(0x18, 32), 0x00000001,  "SCMD_BAR")
    expect_hex(tb.sata1_rd_pci_config(0x1c, 32), 0x00000001,  "SCNL_BAR")
    expect_hex(tb.sata1_rd_pci_config(0x20, 32), 0x00000001,  "BAR")
    expect_hex(tb.sata1_rd_pci_config(0x24, 32), 0x00000001,  "SIDPBA")
    expect_hex(tb.sata1_rd_pci_config(0x2c, 16), 0x0000,      "SVID")
    expect_hex(tb.sata1_rd_pci_config(0x2e, 16), 0x0000,      "SID")
    expect_hex(tb.sata1_rd_pci_config(0x34,  8), 0x70,        "CAP")
    expect_hex(tb.sata1_rd_pci_config(0x3c,  8), 0x00,        "INT_LN")
    expect_hex(tb.sata1_rd_pci_config(0x3d,  8), 0x02,        "INT_PN")
    expect_hex(tb.sata1_rd_pci_config(0x40, 16), 0x0000,      "PIDE_TIM")
    expect_hex(tb.sata1_rd_pci_config(0x42, 16), 0x0000,      "SIDE_TIM")
    expect_hex(tb.sata1_rd_pci_config(0x70, 16), 0xb001,      "PID")
    expect_hex(tb.sata1_rd_pci_config(0x72, 16), 0x0003,      "PC")
    expect_hex(tb.sata1_rd_pci_config(0x74, 16), 0x0008,      "PMCS")
    expect_hex(tb.sata1_rd_pci_config(0x80, 16), 0x7005,      "MSICI")
    expect_hex(tb.sata1_rd_pci_config(0x82, 16), 0x0000,      "MSIMC")
    expect_hex(tb.sata1_rd_pci_config(0x84, 32), 0x00000000,  "MSIMA")
    expect_hex(tb.sata1_rd_pci_config(0x88, 16), 0x0000,      "MSIMD")
    expect_hex(tb.sata1_rd_pci_config(0x90,  8), 0x00,        "MAP")
    expect_hex(tb.sata1_rd_pci_config(0x92, 16), 0x0000,      "PCS")
    expect_hex(tb.sata1_rd_pci_config(0x94, 32), 0x00000000,  "SCLKCG")
    expect_hex(tb.sata1_rd_pci_config(0x9c, 32), 0x00000000,  "SCLKGC")
    expect_hex(tb.sata1_rd_pci_config(0xa8, 32), 0x00000000,  "SCAP0")
    expect_hex(tb.sata1_rd_pci_config(0xac, 32), 0x00000000,  "SCAP1")
    expect_hex(tb.sata1_rd_pci_config(0xb0, 16), 0x0013,      "FLRCID")
    expect_hex(tb.sata1_rd_pci_config(0xb2, 16), 0x0306,      "FLRCLV")
    expect_hex(tb.sata1_rd_pci_config(0xb4, 16), 0x0000,      "FLRCTRL")
    expect_hex(tb.sata1_rd_pci_config(0xc0,  8), 0x00,        "ATC")
    expect_hex(tb.sata1_rd_pci_config(0xc4,  8), 0x00,        "ATS")
    expect_hex(tb.sata1_rd_pci_config(0xd0, 32), 0x00000000,  "SP")
    expect_hex(tb.sata1_rd_pci_config(0xe0, 32), 0x00000000,  "BFCS")
    expect_hex(tb.sata1_rd_pci_config(0xe4, 32), 0x00000000,  "BFTD1")
    expect_hex(tb.sata1_rd_pci_config(0xe8, 32), 0x00000000,  "BFTD2")

    # Map the other banks
    tb.sata1_do_default_mappings()

    # Bus Master IDE I/O Registers

    expect_hex(tb.sata1_rd_bm_reg(0x0,  8), 0x00, "BMICP")
    expect_hex(tb.sata1_rd_bm_reg(0x2,  8), 0x00, "BMISP")
    tb.sata1_rd_bm_reg(0x4, 32)  # BMIDP
    expect_hex(tb.sata1_rd_bm_reg(0x8,  8), 0x00, "BMICS")
    expect_hex(tb.sata1_rd_bm_reg(0xa,  8), 0x00, "BMISS")
    tb.sata1_rd_bm_reg(0xc, 32)  # BMIDS

    # Serial ATA Index/Data Pair Superset Registers

    expect_hex(tb.sata1_rd_sata_reg(0, 0), 0x0, "P0SSTS")
    expect_hex(tb.sata1_rd_sata_reg(0, 1), 0x4, "P0SCTL")
    expect_hex(tb.sata1_rd_sata_reg(0, 2), 0x0, "P0SERR")
    expect_hex(tb.sata1_rd_sata_reg(1, 0), 0x0, "P2SSTS")
    expect_hex(tb.sata1_rd_sata_reg(1, 1), 0x4, "P2SCTL")
    expect_hex(tb.sata1_rd_sata_reg(1, 2), 0x0, "P2SERR")
    expect_hex(tb.sata1_rd_sata_reg(2, 0), 0x0, "P1SSTS")
    expect_hex(tb.sata1_rd_sata_reg(2, 1), 0x4, "P1SCTL")
    expect_hex(tb.sata1_rd_sata_reg(2, 2), 0x0, "P1SERR")
    #expect_hex(tb.sata1_rd_sata_reg(3, 0), 0x0, "P3SSTS")
    #expect_hex(tb.sata1_rd_sata_reg(3, 1), 0x4, "P3SCTL")
    #expect_hex(tb.sata1_rd_sata_reg(3, 2), 0x0, "P3SERR")

def do_test_sata2():
    # PCI config

    expect_hex(tb.sata2_rd_pci_config(0x00, 16), 0x8086,      "VID")
    expect_hex(tb.sata2_rd_pci_config(0x02, 16),
               (0x2926, 0x3A26)[ich_prefix.startswith('ich10')],
               "DID")
    expect_hex(tb.sata2_rd_pci_config(0x04, 16), 0x0000,      "PCICMD")
    expect_hex(tb.sata2_rd_pci_config(0x06, 16), 0x02b0,      "PCISTS")
    expect_hex(tb.sata2_rd_pci_config(0x08,  8), 0x00,        "RID")
    expect_hex(tb.sata2_rd_pci_config(0x09,  8), 0x85,        "PI")
    expect_hex(tb.sata2_rd_pci_config(0x0a,  8), 0x01,        "SCC")
    expect_hex(tb.sata2_rd_pci_config(0x0b,  8), 0x01,        "BCC")
    expect_hex(tb.sata2_rd_pci_config(0x0d,  8), 0x00,        "PMLT")
    expect_hex(tb.sata2_rd_pci_config(0x10, 32), 0x00000001,  "PCMD_BAR")
    expect_hex(tb.sata2_rd_pci_config(0x14, 32), 0x00000001,  "PCNL_BAR")
    expect_hex(tb.sata2_rd_pci_config(0x18, 32), 0x00000001,  "SCMD_BAR")
    expect_hex(tb.sata2_rd_pci_config(0x1c, 32), 0x00000001,  "SCNL_BAR")
    expect_hex(tb.sata2_rd_pci_config(0x20, 32), 0x00000001,  "BAR")
    expect_hex(tb.sata2_rd_pci_config(0x24, 32), 0x00000001,  "SIDPBA")
    expect_hex(tb.sata2_rd_pci_config(0x2c, 16), 0x0000,      "SVID")
    expect_hex(tb.sata2_rd_pci_config(0x2e, 16), 0x0000,      "SID")
    expect_hex(tb.sata2_rd_pci_config(0x34,  8), 0x70,        "CAP")
    expect_hex(tb.sata2_rd_pci_config(0x3c,  8), 0x00,        "INT_LN")
    expect_hex(tb.sata2_rd_pci_config(0x3d,  8), 0x02,        "INT_PN")
    expect_hex(tb.sata2_rd_pci_config(0x40, 16), 0x0000,      "PIDE_TIM")
    expect_hex(tb.sata2_rd_pci_config(0x42, 16), 0x0000,      "SIDE_TIM")
    expect_hex(tb.sata2_rd_pci_config(0x70, 16), 0xb001,      "PID")
    expect_hex(tb.sata2_rd_pci_config(0x72, 16), 0x0003,      "PC")
    expect_hex(tb.sata2_rd_pci_config(0x74, 16), 0x0008,      "PMCS")
    expect_hex(tb.sata2_rd_pci_config(0x80, 16), 0x7005,      "MSICI")
    expect_hex(tb.sata2_rd_pci_config(0x82, 16), 0x0000,      "MSIMC")
    expect_hex(tb.sata2_rd_pci_config(0x84, 32), 0x00000000,  "MSIMA")
    expect_hex(tb.sata2_rd_pci_config(0x88, 16), 0x0000,      "MSIMD")
    expect_hex(tb.sata2_rd_pci_config(0x90,  8), 0x00,        "MAP")
    expect_hex(tb.sata2_rd_pci_config(0x92, 16), 0x0000,      "PCS")
    expect_hex(tb.sata2_rd_pci_config(0xa8, 32), 0x00000000,  "SCAP0")
    expect_hex(tb.sata2_rd_pci_config(0xac, 32), 0x00000000,  "SCAP1")
    expect_hex(tb.sata2_rd_pci_config(0xb0, 16), 0x0013,      "FLRCID")
    expect_hex(tb.sata2_rd_pci_config(0xb2, 16), 0x0306,      "FLRCLV")
    expect_hex(tb.sata2_rd_pci_config(0xb4, 16), 0x0000,      "FLRCTRL")
    expect_hex(tb.sata2_rd_pci_config(0xc0,  8), 0x00,        "ATC")
    expect_hex(tb.sata2_rd_pci_config(0xc4,  8), 0x00,        "ATS")

    # Map the other banks
    tb.sata2_do_default_mappings()

    # Bus Master IDE I/O Registers

    expect_hex(tb.sata2_rd_bm_reg(0x0,  8),     0x00, "BMICP")
    expect_hex(tb.sata2_rd_bm_reg(0x2,  8),     0x00, "BMISP")
    tb.sata2_rd_bm_reg(0x4, 32)  # BMIDP
    expect_hex(tb.sata2_rd_bm_reg(0x8,  8),     0x00, "BMICS")
    expect_hex(tb.sata2_rd_bm_reg(0xa,  8),     0x00, "BMISS")
    tb.sata2_rd_bm_reg(0xc, 32)  # BMIDS

    # Serial ATA Index/Data Pair Superset Registers

    expect_hex(tb.sata2_rd_sata_reg(0, 0), 0x0, "P4SSTS")
    expect_hex(tb.sata2_rd_sata_reg(0, 1), 0x4, "P4SCTL")
    expect_hex(tb.sata2_rd_sata_reg(0, 2), 0x0, "P4SERR")
    expect_hex(tb.sata2_rd_sata_reg(2, 0), 0x0, "P5SSTS")
    expect_hex(tb.sata2_rd_sata_reg(2, 1), 0x4, "P5SCTL")
    expect_hex(tb.sata2_rd_sata_reg(2, 2), 0x0, "P5SERR")

do_test_sata1()
do_test_sata2()
