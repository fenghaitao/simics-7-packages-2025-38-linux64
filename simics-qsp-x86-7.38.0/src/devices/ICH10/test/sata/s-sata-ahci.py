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


# s-sata-ahci.py
# AHCI mode of ICH10 SATA controllers

from sata_ahci import *

# Test we can read the register values correctly
def do_test1():
    expect_hex(tb.sata1_rd_pci_config(0x0a,  8), 0x06, "PCI-Config:SCC-AHCI")
    expect_hex(tb.sata1_rd_pci_config(0x34,  8), 0x80, "PCI-Config:CAP-AHCI")

    # Access AHCI registers via AIDP
    tb.sata1_do_bm_mapping()

    # AHCI Generic Host Control Registers
    expect_hex(tb.ahci_aidp_rd(0x0),  0xFF22FFC5, "CAP")
    expect_hex(tb.ahci_aidp_rd(0x4),  0x00000000, "GHC")
    expect_hex(tb.ahci_aidp_rd(0x8),  0x00000000, "Interrupt Status")
    expect_hex(tb.ahci_aidp_rd(0xc),  0x0000003f, "Ports Implemented")
    expect_hex(tb.ahci_aidp_rd(0x10), 0x00010200, "AHCI Version")
    # According to AHCI 1.3, EN bit is reset 0
    expect_hex(tb.ahci_aidp_rd(0x14), 0x00010130, "CCC_CTL")
    expect_hex(tb.ahci_aidp_rd(0x18), 0x00000000, "CCC_PORTS")
    expect_hex(tb.ahci_aidp_rd(0x1c), 0x01000002, "EM_LOC")
    expect_hex(tb.ahci_aidp_rd(0x20), 0x07010000, "EM_CTRL")
    expect_hex(tb.ahci_aidp_rd(0x24), 0x00000000, "CAP2")
    expect_hex(tb.ahci_aidp_rd(0x28), 0x00000000, "BOHC")

    # Vendor Specific Registers
    expect_hex(tb.ahci_aidp_rd(0xa0), 0x00000000, "Vendor Specific")

    num_ports = tb.ahci_aidp_rd(0x0) & 0x1f

    # Port Registers
    for port in range(num_ports):
        base = 0x100 + port * 0x80
        tb.ahci_aidp_rd(base + 0x00)  # PnCLB
        tb.ahci_aidp_rd(base + 0x04)  # PnCLBU
        tb.ahci_aidp_rd(base + 0x08)  # PnFB
        tb.ahci_aidp_rd(base + 0x0C)  # PnFBU
        expect_hex(tb.ahci_aidp_rd(base + 0x10), 0x00000000, "P%dIS"   % port)
        expect_hex(tb.ahci_aidp_rd(base + 0x14), 0x00000000, "P%dIE"   % port)
        tb.ahci_aidp_rd(base + 0x18)  # PnCMD
        expect_hex(tb.ahci_aidp_rd(base + 0x20), 0x0000007F, "P%dTFD"  % port)
        expect_hex(tb.ahci_aidp_rd(base + 0x24), 0xFFFFFFFF, "P%dSIG"  % port)
        expect_hex(tb.ahci_aidp_rd(base + 0x28), 0x00000000, "P%dSSTS" % port)
        expect_hex(tb.ahci_aidp_rd(base + 0x2C), 0x00000004, "P%dSCTL" % port)
        expect_hex(tb.ahci_aidp_rd(base + 0x30), 0x00000000, "P%dSERR" % port)
        expect_hex(tb.ahci_aidp_rd(base + 0x34), 0x00000000, "P%dSACT" % port)
        expect_hex(tb.ahci_aidp_rd(base + 0x38), 0x00000000, "P%dCI"   % port)
        expect_hex(tb.ahci_aidp_rd(base + 0x3C), 0x00000000, "P%dSNTF" % port)
        expect_hex(tb.ahci_aidp_rd(base + 0x40), 0x00000000, "P%dFBS"  % port)

    # Access AHCI registers via ABAR
    tb.map_ahci_registers()

    stest.expect_true(tb.ahci_aidp_rd(0x00) == tb.ahci_rd_reg(0x00), "CAP")
    stest.expect_true(tb.ahci_aidp_rd(0x04) == tb.ahci_rd_reg(0x04), "GHC")
    stest.expect_true(tb.ahci_aidp_rd(0x08) == tb.ahci_rd_reg(0x08), "Interrupt Status")
    stest.expect_true(tb.ahci_aidp_rd(0x0c) == tb.ahci_rd_reg(0x0c), "Ports Implemented")
    stest.expect_true(tb.ahci_aidp_rd(0x10) == tb.ahci_rd_reg(0x10), "AHCI Version")
    stest.expect_true(tb.ahci_aidp_rd(0x14) == tb.ahci_rd_reg(0x14), "CCC_CTL")
    stest.expect_true(tb.ahci_aidp_rd(0x18) == tb.ahci_rd_reg(0x18), "CCC_PORTS")
    stest.expect_true(tb.ahci_aidp_rd(0x1c) == tb.ahci_rd_reg(0x1c), "EM_LOC")
    stest.expect_true(tb.ahci_aidp_rd(0x20) == tb.ahci_rd_reg(0x20), "EM_CTRL")
    stest.expect_true(tb.ahci_aidp_rd(0x24) == tb.ahci_rd_reg(0x24), "CAP2")
    stest.expect_true(tb.ahci_aidp_rd(0x28) == tb.ahci_rd_reg(0x28), "BOHC")

    for port in range(num_ports):
        base = 0x100 + port * 0x80
        stest.expect_true(tb.ahci_aidp_rd(base + 0x00) == tb.ahci_rd_reg(base + 0x00), "P%dCLB"  % port)
        stest.expect_true(tb.ahci_aidp_rd(base + 0x04) == tb.ahci_rd_reg(base + 0x04), "P%dCLBU" % port)
        stest.expect_true(tb.ahci_aidp_rd(base + 0x08) == tb.ahci_rd_reg(base + 0x08), "P%dFB"   % port)
        stest.expect_true(tb.ahci_aidp_rd(base + 0x0C) == tb.ahci_rd_reg(base + 0x0C), "P%dFBU"  % port)
        stest.expect_true(tb.ahci_aidp_rd(base + 0x10) == tb.ahci_rd_reg(base + 0x10), "P%dIS"   % port)
        stest.expect_true(tb.ahci_aidp_rd(base + 0x14) == tb.ahci_rd_reg(base + 0x14), "P%dIE"   % port)
        stest.expect_true(tb.ahci_aidp_rd(base + 0x18) == tb.ahci_rd_reg(base + 0x18), "P%dCMD"  % port)
        stest.expect_true(tb.ahci_aidp_rd(base + 0x20) == tb.ahci_rd_reg(base + 0x20), "P%dTFD"  % port)
        stest.expect_true(tb.ahci_aidp_rd(base + 0x24) == tb.ahci_rd_reg(base + 0x24), "P%dSIG"  % port)
        stest.expect_true(tb.ahci_aidp_rd(base + 0x28) == tb.ahci_rd_reg(base + 0x28), "P%dSSTS" % port)
        stest.expect_true(tb.ahci_aidp_rd(base + 0x2C) == tb.ahci_rd_reg(base + 0x2C), "P%dSCTL" % port)
        stest.expect_true(tb.ahci_aidp_rd(base + 0x30) == tb.ahci_rd_reg(base + 0x30), "P%dSERR" % port)
        stest.expect_true(tb.ahci_aidp_rd(base + 0x34) == tb.ahci_rd_reg(base + 0x34), "P%dSACT" % port)
        stest.expect_true(tb.ahci_aidp_rd(base + 0x38) == tb.ahci_rd_reg(base + 0x38), "P%dCI"   % port)
        stest.expect_true(tb.ahci_aidp_rd(base + 0x3C) == tb.ahci_rd_reg(base + 0x3C), "P%dSNTF" % port)
        stest.expect_true(tb.ahci_aidp_rd(base + 0x40) == tb.ahci_rd_reg(base + 0x40), "P%dFBS"  % port)

# check that PnCLB, PnCLBU, PnFB and PnFBU are writable
def test_bug21477():
    num_ports = tb.ahci_aidp_rd(0x0) & 0x1f
    for port in range(num_ports):
        base = 0x100 + port * 0x80
        tb.ahci_aidp_wr(base + 0x0, 0x3400)     # PnCLB
        tb.ahci_aidp_wr(base + 0x4, 0x4)        # PnCLBU
        tb.ahci_aidp_wr(base + 0x8, 0x5100)     # PnFB
        tb.ahci_aidp_wr(base + 0xc, 0x6)        # PnFBU
        stest.expect_equal(tb.ahci_aidp_rd(base + 0x00), 0x3400)
        stest.expect_equal(tb.ahci_aidp_rd(base + 0x04), 0x4)
        stest.expect_equal(tb.ahci_aidp_rd(base + 0x08), 0x5100)
        stest.expect_equal(tb.ahci_aidp_rd(base + 0x0c), 0x6)

        tb.ahci_aidp_wr(base + 0x0, 0)
        tb.ahci_aidp_wr(base + 0x4, 0)
        tb.ahci_aidp_wr(base + 0x8, 0)
        tb.ahci_aidp_wr(base + 0xc, 0)
        stest.expect_equal(tb.ahci_aidp_rd(base + 0x08), 0)
        stest.expect_equal(tb.ahci_aidp_rd(base + 0x0c), 0)
        stest.expect_equal(tb.ahci_aidp_rd(base + 0x08), 0)
        stest.expect_equal(tb.ahci_aidp_rd(base + 0x0c), 0)

# Issue commands on slots
# slots - slots to issue, bit 0 meaning slot 0 and so on.
def command_issue(slots):
    tb.ahci_wr_reg(port_base + 0x38, slots)

# Test post received fis function
def test_post_fis():
    # Enable Bus master
    tb.sata1_wr_pci_config(0x4, 16, tb.sata1_rd_pci_config(0x4, 16) | 0x4)

    reset_and_enter_idle()
    activate_command_slot(0)

    # Read FIS base address
    fis_base = tb.ahci_rd_reg(port_base + 0x8)

    # Test FIS is successfully posted in memory (only for port 0)
    # Several FIS with different types will be tested
    # a. D2H FIS
    fis = D2H_FIS(sec_cnt = 0xab, status = 0xfe).serialize()
    tb.sata1.fis_seq = fis
    stest.expect_equal(tb.read_mem(fis_base + RFIS_OFFSET, len(fis)), fis)

    # b. SDB FIS
    fis = SDB_FIS(status_lo = 0xa, status_hi = 0xb).serialize()
    tb.sata1.fis_seq = fis
    stest.expect_equal(tb.read_mem(fis_base + SDBFIS_OFFSET, len(fis)), fis)

    # c. PIO setup FIS
    fis = list(PIO_FIS(d = 1, transfer_cnt = 2).serialize())
    tb.sata1.fis_seq = tuple(fis)
    stest.expect_equal(tb.read_mem(fis_base + PSFIS_OFFSET, len(fis)),
                       tuple(fis))

    # d. DMA setup FIS
    fis = simple_FIS(fis_type = FIS_DMA_SETUP_BI, length = 0x1c).serialize()
    tb.sata1.fis_seq = fis
    stest.expect_equal(tb.read_mem(fis_base + DSFIS_OFFSET, len(fis)), fis)

    # Write to memory where FIS should be posted.
    tmp_mem = tuple([0xbb] * 64)
    tb.write_mem(fis_base + UFIS_OFFSET, tmp_mem)
    # e. Unknown FIS (less than 64 bytes)
    fis = simple_FIS(fis_type = FIS_UNKNOWN, length = 0x10).serialize()
    tb.sata1.fis_seq = fis
    stest.expect_equal(tb.read_mem(fis_base + UFIS_OFFSET, len(fis)), fis)
    stest.expect_equal(tb.ahci_rd_reg(port_base + 0x10) & 0x10, 0x10)

    # Write to memory where FIS should be posted.
    tmp_mem = tuple([0xaa] * 64)
    tb.write_mem(fis_base + UFIS_OFFSET, tmp_mem)
    # e. Unknown FIS (larger than 64 bytes)
    fis = simple_FIS(fis_type = FIS_UNKNOWN, length = 0x41).serialize()
    tb.sata1.fis_seq = fis
    stest.expect_equal(tb.read_mem(fis_base + UFIS_OFFSET, 64), tmp_mem)
    stest.expect_equal(tb.ahci_rd_reg(port_base + 0x10) & 0x8000000,
                       0x8000000)

# Set up a Physical Region Descriptor Table
# cmd_table_base - Base of command table
# data_base      - Base for read/stored data
# prds           - list of sizes for each region in the table
def setup_prdt(cmd_table_base, data_base, prds, space = 0):
    prdt_base = cmd_table_base + 0x80
    total_size = 0
    for i in range(len(prds)):
        # Have some space between data in memory
        prd_data_base = data_base + total_size + space * i
        prdt_item = PRDTItem(prd_data_base, 0, prds[i] - 1, 0)
        tb.write_mem(prdt_base + (i << 4), prdt_item.serialize())
        total_size += prds[i]

# Set up and send Command FIS and then receive a Data FIS for port 0.
def test_data_receive():
    reset_and_enter_idle()

    cmd_table_base = ahci_mem_base + (40 << 10)

    # Set up the 8 PRDT items in the PRDT table.
    prd_data_size = 256
    number_prds = 8
    pr_space = 0x20
    prds = tuple([prd_data_size] * number_prds)
    data_base = ahci_mem_base + 0x100000
    setup_prdt(cmd_table_base, data_base, prds, pr_space)

    # Command FIS at table 0 will be fetched from command table and sent to
    # device when command 0 is issued.
    cmdfis = H2D_FIS(c = 1, cmd = 0xca)
    tb.write_mem(cmd_table_base, cmdfis.serialize())

    # Setup data to be received and create a Data FIS.
    indata = []
    for i in range(number_prds):
        indata += [i*7] * prd_data_size
    data_fis = tuple([0x46, 0, 0, 0] + indata)

    # Set up precondition
    cmd.st = 1
    sata.ahci_p0pcr_port_state = port_states["P_IDLE"]

    # Start issuing command 0.
    command_issue(1)

    # Send Data FIS to HBA
    tb.sata1.fis_seq = data_fis

    received_data = []
    for i in range(number_prds):
        received_data += tb.read_mem(data_base
                                     + (prd_data_size + pr_space) * i,
                                     prd_data_size)
    stest.expect_equal(received_data, indata)
    stest.expect_equal(sata_dev.sata.reqs[-1],
                       ["receive_fis", cmdfis.serialize()])

# Receive more than one Data FIS in a row to port 0
def test_receive_large_data():
    reset_and_enter_idle()

    cmd_table_base = ahci_mem_base + (40 << 10)

    # Set up the 8 PRDT items in the PRDT table.
    prd_data_size = 0x1400
    number_prds = 8
    pr_space = 0x100
    prds = [prd_data_size] * number_prds
    data_base = ahci_mem_base + 0x200000
    setup_prdt(cmd_table_base, data_base, prds, pr_space)

    # Command FIS at table 0 will be fetched from command table and sent to
    # device when command 0 is issued.
    cmdfis = H2D_FIS(c = 1, cmd = 0xca)
    tb.write_mem(cmd_table_base, cmdfis.serialize())

    # Start issuing command 0.
    command_issue(1)

    sata.ahci_p0pcr_current_prdt = 0
    sata.ahci_p0pcr_prdt_pos = 0

    # Setup data to be received and create 3 Data FISes of size 8 Kbyte.
    indata = []
    for i in range(3):
        data_fis_size = 0x2000 # Size of one FIS
        indata_part = []
        for j in range(data_fis_size):
            indata_part.append((i * 7 + j) % 0xff)
        data_fis = tuple([0x46, 0, 0, 0] + indata_part)
        # Send Data FIS to HBA
        tb.sata1.fis_seq = data_fis
        indata += indata_part

    received_data = []
    for i in range(number_prds):
        n = prd_data_size // 0x400
        for j in range(n):
            # tb.read_mem() can only read 1 Kbyte at a time.
            received_data += tb.read_mem(data_base + 0x400 * j
                                         + (prd_data_size + pr_space) * i,
                                         0x400)
        if (prd_data_size % 0x400):
            received_data += tb.read_mem(data_base + 0x400 * n
                                         + (prd_data_size + pr_space) * i,
                                         prd_data_size % 0x400)

    received_data = received_data[0:len(indata)]
    stest.expect_equal(received_data, indata)
    stest.expect_equal(sata_dev.sata.reqs[-1],
                       ["receive_fis", cmdfis.serialize()])

def test_ncq():
    reset_and_enter_idle()
    base = 0x100
    cmd_header_base = (sata.ahci_p0pcr_clbu << 32) + sata.ahci_p0pcr_clb
    cmd_header_size = 0x20
    cmd_table_base = ahci_mem_base + (40 << 10)
    cmd_table_size = 0x200

    # Set up the PRDT
    for i in [0,2,5,8]:
        prdt_base = cmd_table_base + 0x80 + (cmd_table_size * i)
        prd_data_size = 32
        data_base = ahci_mem_base + 0x100000 + 0x1000 * i
        prdt_item = PRDTItem(data_base, 0, prd_data_size - 1, 0)
        tb.write_mem(prdt_base, prdt_item.serialize())
        tb.write_mem(data_base, tuple(range(prd_data_size)))

    # Slot0 contain READ FPDMA QUEUED command
    cmdfis0 = H2D_FIS(c = 1, cmd = 0x60)
    tb.write_mem(cmd_table_base, cmdfis0.serialize())
    cmdheader0 = CmdHeader(prdtl = 1, cfl = 5, ctba = cmd_table_base)
    tb.write_mem(cmd_header_base, cmdheader0.serialize())

    # Slot2 contain WRITE FPDMA QUEUED command
    cmdfis2 = H2D_FIS(c = 1, cmd = 0x61)
    tb.write_mem(cmd_table_base + cmd_table_size * 2, cmdfis2.serialize())
    cmdheader2 = CmdHeader(prdtl = 1, write = 1, cfl = 5,
                           ctba = cmd_table_base + cmd_table_size * 2)
    tb.write_mem(cmd_header_base + cmd_header_size * 2,
                 cmdheader2.serialize())

    # Slot5 contain READ FPDMA QUEUED command
    cmdfis5 = H2D_FIS(c = 1, cmd = 0x60)
    tb.write_mem(cmd_table_base + cmd_table_size * 5, cmdfis5.serialize())
    cmdheader5 = CmdHeader(prdtl = 1, cfl = 5,
                           ctba = cmd_table_base + cmd_table_size * 5)
    tb.write_mem(cmd_header_base + cmd_header_size * 5,
                 cmdheader5.serialize())

    # Slot8 contain WRITE FPDMA QUEUED command
    cmdfis8 = H2D_FIS(c = 1, cmd = 0x61)
    tb.write_mem(cmd_table_base + cmd_table_size * 8, cmdfis8.serialize())
    cmdheader8 = CmdHeader(prdtl = 1, write = 1, cfl = 5,
                           ctba = cmd_table_base + cmd_table_size * 8)
    tb.write_mem(cmd_header_base + cmd_header_size * 8,
                 cmdheader8.serialize())

    cmd.st = 1

    # Start issuing command (for slot0, 2, 5)
    tb.ahci_wr_reg(base + 0x34, 0x125)
    command_issue(0x25)

    # Receiving D2H FIS from sata dev
    fis = D2H_FIS(i = 0).serialize()
    tb.sata1.fis_seq = fis
    tb.sata1.fis_seq = fis
    tb.sata1.fis_seq = fis

    stest.expect_equal(sata.ahci_p0pcr_ci, 0x0, "PxCI incorrect")
    # Now HBA in idle state
    stest.expect_equal(sata.ahci_p0pcr_port_state, port_states["P_IDLE"],
                       "Port not in P:Idle state")

    # DMA setup FIS for slot 2
    dma_setup_fis = list(simple_FIS(fis_type = FIS_DMA_SETUP_BI, length = 0x1c).serialize())
    dma_setup_fis[4] = 2 # Tag
    tb.sata1.fis_seq = tuple(dma_setup_fis)

    # DMA activate FIS
    dma_act_fis = simple_FIS(fis_type = FIS_DMA_ACTIVATE_D2H, length = 4)
    tb.sata1.fis_seq = dma_act_fis.serialize()

    stest.expect_equal(sata_dev.sata.reqs[-1][-1],
                       tuple([70,0,0,0] + list(range(32))))

    # Issue command in slot8
    command_issue(0x100)
    tb.sata1.fis_seq = fis
    stest.expect_equal(sata.ahci_p0pcr_ci, 0x0, "PxCI incorrect")

    # DMA setup FIS for slot 5
    dma_setup_fis[4] = 5 # Tag
    tb.sata1.fis_seq = tuple(dma_setup_fis)

    # data FIS
    # Setup data to be received and create a Data FIS.
    indata = [0xa, 0xb, 0xc, 0xd] + list(range(26)) + [0xe, 0xf]
    data_fis = tuple([0x46, 0, 0, 0] + indata)
    tb.sata1.fis_seq = data_fis

    stest.expect_equal(tb.read_mem(ahci_mem_base + 0x100000 + 0x1000 * 5, 32),
                       tuple(indata))
    stest.expect_equal(sata.ahci_p0pcr_sact, 0x125, "PxSACT incorrect")

    # Send SDB FIS to indicated slot 2 and 5 has complete
    sdb_fis = SDB_FIS(i = 1, rev = 0x24)
    tb.sata1.fis_seq = sdb_fis.serialize()

    stest.expect_true(sata.ahci_p0pcr_isr != 0, "Interrupt not assert")
    stest.expect_equal(sata.ahci_p0pcr_sact, 0x101, "PxSACT incorrect")

    # DMA setup FIS for slot 8
    dma_setup_fis[4] = 8 # Tag
    tb.sata1.fis_seq = tuple(dma_setup_fis)

    # DMA activate FIS for slot 8
    dma_act_fis = simple_FIS(fis_type = FIS_DMA_ACTIVATE_D2H, length = 4)
    tb.sata1.fis_seq = dma_act_fis.serialize()

    stest.expect_equal(sata_dev.sata.reqs[-1][-1],
                       tuple([70,0,0,0] + list(range(32))))

    # Send SDB FIS to indicated slot 8 has complete
    sdb_fis = SDB_FIS(i = 1, rev = 0x100)
    tb.sata1.fis_seq = sdb_fis.serialize()
    stest.expect_equal(sata.ahci_p0pcr_sact, 0x1, "PxSACT incorrect")

    # DMA setup FIS for slot 0
    dma_setup_fis[4] = 0 # Tag
    tb.sata1.fis_seq = tuple(dma_setup_fis)

    # data FIS
    # Setup data to be received and create a Data FIS.
    indata = [0xf, 0xe, 0xd, 0xc] + list(range(26)) + [0xb, 0xa]
    data_fis = tuple([0x46, 0, 0, 0] + indata)
    tb.sata1.fis_seq = data_fis

    stest.expect_equal(tb.read_mem(ahci_mem_base + 0x100000, 32),
                       tuple(indata))

    # Send SDB FIS to indicated slot 0 has complete
    sdb_fis = SDB_FIS(i = 1, rev = 0x1)
    tb.sata1.fis_seq = sdb_fis.serialize()
    stest.expect_equal(sata.ahci_p0pcr_sact, 0, "PxSACT incorrect")

def test_port0_reset():
    try:
        stest.expect_equal(sata.ahci_p0pcr_p_update_sig, 1, "pUpdateSig")
        stest.expect_equal(sata.ahci_p0pcr_p_dev_issue, 0, "pDevIssue")
        stest.expect_equal(sata.ahci_p0pcr_p_issue_slot, 32, "pIssueSlot")
        stest.expect_equal(sata.ahci_p0pcr_p_data_slot, 0, "pDataSlot")
        stest.expect_equal(sata.ahci_p0pcr_p_xfer_atapi, 0, "pXferAtapi")
        stest.expect_equal(sata.ahci_p0pcr_p_pio_xfer, 0, "pPioXfer")
        stest.expect_equal(sata.ahci_p0pcr_p_pio_e_sts, 0, "pPioESts")
        stest.expect_equal(sata.ahci_p0pcr_p_pio_err, 0, "pPioErr")
        stest.expect_equal(sata.ahci_p0pcr_p_pio_ibit, 0, "pPio_Ibit")
        stest.expect_equal(sata.ahci_p0pcr_p_dma_xfer_cnt, 0, "pDmaXferCnt")
        stest.expect_equal(sata.ahci_p0pcr_p_cmd_to_issue, 0, "pCmdToIssue")
        stest.expect_equal(sata.ahci_p0pcr_p_prd_intr, 0, "pPrdIntr")
        stest.expect_equal(sata.ahci_p0pcr_p_s_active, 0, "pSActive")
        stest.expect_equal(sata.ahci_p0pcr_p_slot_loc, cap.ncs, "pSlotLoc")
    except stest.TestFailure:
        print("HBA Port state machine variables not correctly reset.")
        raise
    stest.expect_equal(sata.ahci_p0pcr_port_state, port_states["P_NOT_RUNNING"],
                       "Port not in P:NotRunning state after reset.")
    stest.expect_equal(cmd.st, 0, "CMD.ST not cleared after reset.")
    stest.expect_equal(tfd.read() & 0xff, 0x7f,
                       "PxTDF.STS not correctly reset.")

def test_hba_reset():
    ghc.ae = 1
    hba_reset()
    stest.expect_equal(ghc.read(), 0,
                       "HBA reset does not reset GHC")
    # Test port 0
    test_port0_reset()

def test_start_comm():
    ssts.det = 0
    serr.diag_x = 0
    ghc.ae = 1
    stest.expect_equal(sata.ahci_p0pcr_port_state, port_states["P_NOT_RUNNING"])
    # Spin up device
    cmd.sud = 1
    # Device detection initialization
    sctl.det = 1
    SIM_continue(int(1000 * tb.bus_clk.freq_mhz)) # wait 1 ms
    sctl.det = 0

    stest.expect_equal(ssts.det, 3)
    stest.expect_equal(serr.diag_x, 1)

def test_interrupt():
    # Enable interrupt
    ghc.ie = 1

    # Enable interrupt
    tb.sata1_wr_pci_config(0x4, 16,
                           tb.sata1_rd_pci_config(0x4, 16) & 0xfffffbff)

    # Enable bit-level interrupt
    tb.ahci_wr_reg(port_base + 0x14, 0xff)

    # Enable receiving FIS
    cmd.fre = 1

    interrupt_pin = sata.pci_config_interrupt_pin - 1

    # Unknown FIS (larger than 64 bytes)
    fis = simple_FIS(fis_type = FIS_UNKNOWN, length = 0x41).serialize()
    tb.sata1.fis_seq = fis

    stest.expect_true((sata.pci_config_interrupts >> interrupt_pin) & 1,
                      "interrupt not assert")

    # write 1 to clear interrupt
    tb.ahci_wr_reg(port_base + 0x14, 0x0)
    tb.ahci_wr_reg(0x08, 0xff)
    stest.expect_false((sata.pci_config_interrupts >> interrupt_pin) & 1,
                       "interrupt wrongly asserted")

    # TODO: test other kinds of interrupt source

    # Reset
    hba_init()

def test_port0_enter_idle():
    assert (ghc.ae == 1
            and sata.ahci_p0pcr_port_state == port_states["P_NOT_RUNNING"])

    # Enable receiving FIS
    cmd.fre = 1
    # Send FIS to clear drq
    d2h_fis = D2H_FIS()
    tb.sata1.fis_seq = d2h_fis.serialize()

    # Start Port
    cmd.st = 1
    stest.expect_equal(sata.ahci_p0pcr_port_state,
                       port_states["P_IDLE"])
    stest.expect_equal(cmd.cr, 1)

def test_d2h_reg_fis():
    sata.ahci_p0pcr_port_state = port_states["P_IDLE"]
    activate_command_slot(0)
    d2h_fis = D2H_FIS(lbal = 0xaa, lbam = 0x20, lbah = 1, sec_cnt = 4)
    tb.sata1.fis_seq = d2h_fis.serialize()
    fis_base = (tb.ahci_rd_reg(port_base + 0xc) << 32) | (tb.ahci_rd_reg(port_base + 0x8))
    stest.expect_equal(tb.read_mem(fis_base + RFIS_OFFSET, 0x14),
                       d2h_fis.serialize())


def test_set_device_bits():
    sata.ahci_p0pcr_port_state = port_states["P_IDLE"]
    activate_command_slot(0)
    cs_lo = 3
    cs_hi = 5
    sdb_fis = SDB_FIS(status_lo = (cs_lo << 1), status_hi = cs_hi)
    tb.sata1.fis_seq = sdb_fis.serialize()
    fis_base = (tb.ahci_rd_reg(port_base + 0xc) << 32) | (tb.ahci_rd_reg(port_base + 0x8))
    stest.expect_equal(tb.read_mem(fis_base + SDBFIS_OFFSET, 8),
                       sdb_fis.serialize())
    stest.expect_equal(tfd.sts_cs_lo, cs_lo)
    stest.expect_equal(tfd.sts_cs_hi, cs_hi)

def test_receive_FIS_when_ahci_disabled():
    activate_command_slot(0)
    # Disable AHCI
    ghc.ae = 0
    sdb_fis = SDB_FIS(status_lo = 3 , status_hi = 2)
    fis_base = (tb.ahci_rd_reg(port_base + 0xc) << 32) | (tb.ahci_rd_reg(port_base + 0x8))
    # Write to mem where SDB FIS would be stored
    mem_value = (0xfa, 0x1a, 0xfe, 0x10, 0xba, 0xbe, 0x22, 0x01)
    tb.write_mem(fis_base + SDBFIS_OFFSET, mem_value)
    tb.sata1.fis_seq = sdb_fis.serialize()
    # Nothing should have been written
    stest.expect_equal(tb.read_mem(fis_base + SDBFIS_OFFSET, 8), mem_value)
    # Reenable AHCI
    ghc.ae = 1

def test_non_data_fises():
    reset_and_enter_idle()
    print(" * D2H")
    test_d2h_reg_fis()
    print(" * SDB")
    test_set_device_bits()
    print(" * AHCI disabled")
    test_receive_FIS_when_ahci_disabled()

def test_pio_op():
    def xmit_fis():
        tb.sata1.fis_seq = tuple(fis)

    def check_attribute(name, value):
        if (name == "Port state"):
            (attr, checker) = (sata.ahci_p0pcr_port_state, pio_state)
        elif (name == "pPioXfer"):
            (attr, checker) = (sata.ahci_p0pcr_p_pio_xfer, pio_xfer)
        elif (name == "pDmaXferCnt"):
            (attr, checker) = (sata.ahci_p0pcr_p_dma_xfer_cnt, dma_xfer_cnt)
        elif (name == "p0tfd.sts"):
            (attr, checker) = (tfd.read() & 0xff, tfd_sts)
        elif (name == "p0isr"):
            (attr, checker) = ((sata.ahci_p0pcr_isr >> 30) & 1, isr)
        if (checker == 1):
            stest.expect_equal(attr, value, name)
            checker = 0
        return checker

    # Read FIS base address
    fis_base = tb.ahci_rd_reg(port_base + 0x8)
    for (d, i, status, error, e_status, transfer_cnt) in (
        (d, i, status, error, e_status, transfer_cnt)
        for d in [0,1]
        for i in [0,1]
        for status in [0,1,0xf,0x7f,0xff]
        for error in [0,1,0xff]
        for e_status in [0,1,0xf,0xff]
        for transfer_cnt in [0,1,12,16,0xfe,0xff]):
        # Reinit HBA
        hba_init()
        activate_command_slot(0)

        # Init all counts
        pio_state = 1
        pio_xfer = 1
        dma_xfer_cnt = 1
        tfd_sts = 1
        isr = 1

        # PIO:Entry
        fis = list(PIO_FIS(d = d, transfer_cnt = transfer_cnt,
                           e_status = e_status, error = error, i = i,
                           status = status).serialize())
        if (transfer_cnt == 0):
            stest.expect_log(xmit_fis, [], log_type = "spec-viol", msg = "Transfer count value shall be non-zero.")
        elif ((transfer_cnt & 1) == 1):
            stest.expect_log(xmit_fis, [], log_type = "spec-viol", msg = "Low order bit of Transfer count shall be zero.")
        else:
            xmit_fis()

        # Verify PIO setup FIS has been posted into memory
        stest.expect_equal(tb.read_mem(fis_base + PSFIS_OFFSET, len(fis)),
                           tuple(fis))

        # Verify p* internal attributes have correctly set
        if ((status & 1) == 1):
            # ERR:FatalTaskfile
            pio_state = check_attribute("Port state", port_states["ERR_WAIT_FOR_CLEAR"])
            pio_xfer = check_attribute("pPioXfer", 1)
            tfd_sts = check_attribute("p0tfd.sts", status)
            dma_xfer_cnt = check_attribute("pDmaXferCnt", transfer_cnt)
            isr = check_attribute("p0isr", 1)

        if (d == 0):
            # Go through DX:Entry & PIO:update
            pio_xfer = check_attribute("pPioXfer", 0)
            dma_xfer_cnt = check_attribute("pDmaXferCnt", 0)
            if ((e_status & 1) == 1):
                pio_state = check_attribute("Port state", port_states["ERR_WAIT_FOR_CLEAR"])
                tfd_sts = check_attribute("p0tfd.sts", e_status)
                isr = check_attribute("p0isr", 1)
        else:
            pio_xfer = check_attribute("pPioXfer", 1)
            dma_xfer_cnt = check_attribute("pDmaXferCnt", transfer_cnt)

        pio_state = check_attribute("Port state", port_states["P_IDLE"])
        tfd_sts = check_attribute("p0tfd.sts", status)
        stest.expect_equal(sata.ahci_p0pcr_p_pio_e_sts, e_status, "pPioESts")
        stest.expect_equal(sata.ahci_p0pcr_p_pio_err, error, "pPioErr")
        stest.expect_equal(sata.ahci_p0pcr_p_pio_ibit, i, "pPioIbit")

def create_taskfile_error(fis_type, error_code):
    assert fis_type in (FIS_REG_D2H, FIS_PIO_SETUP_D2H, FIS_SET_DEVICE_BIT_D2H)
    if fis_type == FIS_REG_D2H:
        fis = D2H_FIS(status = 1, error = error_code)
    elif fis_type == FIS_PIO_SETUP_D2H:
        fis = PIO_FIS(d = 1, transfer_cnt = 0x10, status = 1,
                      error = error_code)
    else:
        fis = SDB_FIS(status_lo = 1, error = error_code)
    return fis.serialize()

def test_task_file_error():
    # Test the three types of FIS's that can set taskfile error
    for (fis_type, fis_offset, fis_str) in ((FIS_REG_D2H, RFIS_OFFSET,
                                             "REG_D2H"),
                                            (FIS_PIO_SETUP_D2H, PSFIS_OFFSET,
                                             "PIO"),
                                            (FIS_SET_DEVICE_BIT_D2H,
                                             SDBFIS_OFFSET, "SDB")):
        print(" * FISTYPE %s" % fis_str)
        error_code = 1
        reset_and_enter_idle()
        # Clear Task file error status interrupt
        isr.tfes = 1
        stest.expect_equal(isr.tfes, 0)

        stest.expect_equal(sata.ahci_p0pcr_port_state, port_states["P_IDLE"],
                           "Should be in P:Idle state")
        activate_command_slot(0)

        fistype_base = ((tb.ahci_rd_reg(port_base + 0xc) << 32)
                        | (tb.ahci_rd_reg(port_base + 0x8) + fis_offset))

        fis = create_taskfile_error(fis_type, error_code)
        tb.sata1.fis_seq = fis
        stest.expect_equal(sata.ahci_p0pcr_port_state,
                           port_states["ERR_WAIT_FOR_CLEAR"],
                           "Should be in ERR:WaitForClear state")
        stest.expect_equal(tb.read_mem(fistype_base, len(fis)), fis)
        stest.expect_equal(isr.tfes, 1,
                           "Task file error status interrupt not set")
        err = (sata.ahci_p0pcr_p_pio_err if fis_type == FIS_PIO_SETUP_D2H else
               tfd.err)
        stest.expect_equal(err, error_code)

        # Test receive while in Error State - should not write anything
        mem_clearer = tuple([0] * len(fis))
        tb.write_mem(fistype_base, mem_clearer)
        tb.sata1.fis_seq = fis
        stest.expect_equal(tb.read_mem(fistype_base, len(fis)), mem_clearer)

        # Test sending while in Error State - should result in spec-violation
        # and no command issued.
        clear_command_slots()
        sata.ahci_p0pcr_tfd = 0
        cmd_table_base = ahci_mem_base + (40 << 10)
        cmdfis = H2D_FIS(c = 1, cmd = 0xca)
        tb.write_mem(cmd_table_base, cmdfis.serialize())
        old_log_level = sata.bank.ahci.log_level
        sata.bank.ahci.log_level = 2
        stest.expect_log(command_issue, (1,), log_type = "spec-viol")
        sata.bank.ahci.log_level = old_log_level
        # TFD would change if command was issued
        stest.expect_equal(sata.ahci_p0pcr_tfd, 0)

        # Clear PxCMD.ST and make sure PxCMD.CR is 0
        cmd.st = 0
        stest.expect_equal(cmd.cr, 0)

def get_prd_byte_count(cmd_header_base, slot = 0):
    bc = tb.read_mem(cmd_header_base + 0x20 * slot + 4, 4)
    assert len(bc) == 4
    return bc[0] | (bc[1] << 8) | (bc[2] << 16) | (bc[3] << 24)

# Receive larger amount of data then there is space for in PRD tables
def test_receive_overflow():
    reset_and_enter_idle()

    # Clear interrupt that is to be checked later
    isr.ofst = 1
    stest.expect_equal(isr.ofst, 0)

    cmd_list_base = ahci_mem_base
    cmd_table_base = ahci_mem_base + (40 << 10)

    data_base = ahci_mem_base + 0x300000
    # Clear memory
    tb.write_mem(data_base, tuple([0] * 0x80))

    pr_space = 0
    prds = (4, 4, 8, 8, 4, 4, 16, 16) # Total size 64 bytes
    setup_prdt(cmd_table_base, data_base, prds, pr_space)

    stest.expect_equal(sata.ahci_p0pcr_port_state,
                       port_states["P_IDLE"])

    cmdfis = H2D_FIS(c = 1, cmd = 0xca)
    tb.write_mem(cmd_table_base, cmdfis.serialize())

    command_issue(1)

    data_fis = tuple([FIS_DATA_BI, 0, 0, 0] + [0xbe] * 0x80)
    tb.sata1.fis_seq = data_fis

    stest.expect_equal(tb.read_mem(data_base, 0x80),
                       tuple([0xbe] * 0x40 + [0] * 0x40),
                       "Wrong data read")
    stest.expect_equal(get_prd_byte_count(cmd_list_base, 0), sum(prds),
                       "Incorrect byte count")
    stest.expect_equal(isr.ofst, 1, "Overflow interrupt not raised")

def test_send_large():
    reset_and_enter_idle()
    # Clear interrupt that is to be checked later
    isr.ofst = 1
    stest.expect_equal(isr.ofst, 0)

    cmd_list_base = ahci_mem_base
    cmd_table_base = ahci_mem_base + (40 << 10)

    data_base = ahci_mem_base + 0x300000

    pr_space = 0x10
    prds = (8192, 2048, 4096, 8192, 12000, 16, 100000, 32)
    setup_prdt(cmd_table_base, data_base, prds, pr_space)

    # Create expected FIS's and write data to memory
    fis_sizes = []
    remaining_size = sum(prds)
    while remaining_size > 0:
        fis_size = 8192 if remaining_size >= 8192 else remaining_size
        fis_sizes.append(fis_size)
        remaining_size -= 8192
    fis_data = []
    serial_data = []
    i = 0
    for fis_size in fis_sizes:
        new_data = [(0x11 * (i + 1)) & 0xff] * fis_size
        fis_data.append(tuple(new_data))
        serial_data += new_data
        i += 1
    data_pos = 0
    i = 0
    for prd_size in prds:
        tb.write_mem(data_base + data_pos + i * pr_space,
                     tuple(serial_data[data_pos: data_pos + prd_size]))
        data_pos += prd_size
        i += 1

    # Command FIS at table 0 will be fetched from command table and sent to
    # device when command 0 is issued.
    cmdfis = H2D_FIS(c = 1, cmd = 0xca)
    tb.write_mem(cmd_table_base, cmdfis.serialize())

    cmd_header_base = (sata.ahci_p0pcr_clbu << 32) + sata.ahci_p0pcr_clb
    cmdheader0 = CmdHeader(prdtl = len(prds), write = 1, cfl = 5,
                           ctba = cmd_table_base)
    tb.write_mem(cmd_header_base, cmdheader0.serialize())

    ci.c0 = 1
    sata_dev.sata.reqs = []
    for data in fis_data:
        tb.sata1.fis_seq = (FIS_DMA_ACTIVATE_D2H, 0, 0, 0)
        stest.expect_equal(sata_dev.sata.reqs[-1][1][4:], data)
    stest.expect_equal(get_prd_byte_count(cmd_list_base, 0), sum(prds),
                       "Incorrect byte count")


def test_receive_wrong_fis_len():
    fises = ((simple_FIS(FIS_REG_D2H, 0x14),"REGISTER"),
             (simple_FIS(FIS_DMA_ACTIVATE_D2H, 0x4), "DMA ACTIVATE"),
             (simple_FIS(FIS_DMA_SETUP_BI, 0x1c), "DMA SETUP"),
             (simple_FIS(FIS_BIST_ACTIVATE_BI, 0xc), "BIST"),
             (simple_FIS(FIS_PIO_SETUP_D2H, 0x14), "PIO SETUP"),
             (simple_FIS(FIS_SET_DEVICE_BIT_D2H, 0x8), "SET DEVICE BIT"))
    for (fis, fis_name) in fises:
        reset_and_enter_idle()

        # Set BSY-bit of TFD, faking we have sent a command.
        sata.ahci_p0pcr_tfd = 0x80
        activate_command_slot(0)

        # Test with different diffs in FIS length
        for i in (-2, 2, 7):
            # Clear tested interrupt and error-bit
            isr.infs = 1
            stest.expect_equal(isr.infs, 0)
            serr.err_p = 1
            stest.expect_equal(serr.err_p, 0)

            if i < 0:
                broken_fis = fis.serialize()[:i]
            else:
                broken_fis = tuple(list(fis.serialize()) + [0] * i)
            tb.sata1.fis_seq = broken_fis
            try:
                stest.expect_equal(isr.infs, 1)
                stest.expect_equal(serr.err_p, 1)
                stest.expect_equal(sata.ahci_p0pcr_port_state,
                                   port_states["P_IDLE"])
            except stest.TestFailure:
                print(("FIS of type %s that differs %d from its real length." %
                       (fis_name, i)))
                raise

def test_receive_without_active_slot():
    reset_and_enter_idle()

    stest.expect_equal(sata.ahci_p0pcr_ci, 0)
    stest.expect_equal(sata.ahci_p0pcr_sact, 0)

    fis_base = tb.ahci_rd_reg(port_base + 0x8)
    reg_fis = D2H_FIS(sec_cnt = 0x11, status = 0x88).serialize()
    clear_data = tuple(range(len(reg_fis)))
    assert clear_data != reg_fis
    tb.write_mem(fis_base + RFIS_OFFSET, clear_data)
    tb.sata1.fis_seq = reg_fis
    stest.expect_equal(tb.read_mem(fis_base + RFIS_OFFSET, len(reg_fis)),
                       clear_data)

    stest.expect_equal(sata.ahci_p0pcr_ci, 0)
    stest.expect_equal(sata.ahci_p0pcr_sact, 0)
    dma_fis = DMA_SETUP_FIS(buf_id_low = 1, count = 0x10).serialize()
    clear_data = tuple(range(len(dma_fis)))
    assert clear_data != dma_fis
    tb.write_mem(fis_base + DSFIS_OFFSET, clear_data)
    tb.sata1.fis_seq = dma_fis
    stest.expect_equal(tb.read_mem(fis_base + DSFIS_OFFSET, len(dma_fis)),
                       clear_data)
    stest.expect_equal(isr.ifs, 1)

def test_initial_reg_d2h():
    hba_init(enable_fre = False)

    clear_mem = tuple([0] * 0x14)
    fis_base = tb.ahci_rd_reg(port_base + 0x8)
    tb.write_mem(fis_base + RFIS_OFFSET, clear_mem)
    # FRE should be 0 and TFD should be 0x7f after reset
    stest.expect_equal(cmd.fre, 0)
    stest.expect_equal(tb.ahci_rd_reg(port_base + 0x20), 0x7f)
    stest.expect_equal(sata.ahci_p0pcr_port_state, port_states["P_NOT_RUNNING"])

    d2h_fis = D2H_FIS(lbal = 1, sec_cnt = 1)
    tb.sata1.fis_seq = d2h_fis.serialize()
    assert d2h_fis.serialize() != clear_mem

    # Should only set PxSIG
    stest.expect_equal(tb.ahci_rd_reg(port_base + 0x24), 0x0101)
    # TFD should still be 0x7f
    stest.expect_equal(tb.ahci_rd_reg(port_base + 0x20), 0x7f)
    # Nothing should be written to memory
    stest.expect_equal(tb.read_mem(fis_base + RFIS_OFFSET, 0x14), clear_mem)
    stest.expect_equal(sata.ahci_p0pcr_port_state, port_states["P_NOT_RUNNING"])
    # Enable FRE: should set TFD and post FIS
    cmd.fre = 1
    stest.expect_equal(cmd.fre, 1)
    stest.expect_equal(tb.ahci_rd_reg(port_base + 0x20), 0x0)
    stest.expect_equal(tb.read_mem(fis_base + RFIS_OFFSET, 0x14),
                       d2h_fis.serialize())
    stest.expect_equal(sata.ahci_p0pcr_port_state, port_states["P_NOT_RUNNING"])

# Add a new command to command queue by writing PxCI while an old transfer is
# still active.
# Tests bug 18117 - SATA model tries to malloc an extremely large buffer.
def test_adding_command_while_running():
    reset_and_enter_idle()

    cmd_table_0_base = ahci_mem_base + (40 << 10)
    cmd_table_1_base = ahci_mem_base + (40 << 11)

    data_0_base = ahci_mem_base + 0x300000
    tb.write_mem(data_0_base, tuple([0] * 40960))
    data_1_base = ahci_mem_base + 0x400000
    tb.write_mem(data_1_base, tuple([0xff] * 40960))

    # Set up 2 prd, the last one smaller than the first
    prds0 = [4096] * 10
    prds1 = [4096] * 3

    expect_fis_0 = []
    for i in range(5):
        expect_fis_0.append([0] * 8192)
    expect_fis_1 = [[0xff] * 8192, [0xff] * 4096]

    setup_prdt(cmd_table_0_base, data_0_base, prds0)
    setup_prdt(cmd_table_1_base, data_1_base, prds1)

    cmdheader0 = CmdHeader(prdtl = len(prds0), write = 1, cfl = 5,
                           ctba = cmd_table_0_base)
    cmdheader1 = CmdHeader(prdtl = len(prds1), write = 1, cfl = 5,
                           ctba = cmd_table_1_base)
    cmd_header_base = (sata.ahci_p0pcr_clbu << 32) + sata.ahci_p0pcr_clb
    tb.write_mem(cmd_header_base, cmdheader0.serialize())
    tb.write_mem(cmd_header_base + 0x20, cmdheader1.serialize())

    dma_write_cmd_fis = H2D_FIS(c = 1, cmd = 0xca)
    tb.write_mem(cmd_table_0_base, dma_write_cmd_fis.serialize())
    tb.write_mem(cmd_table_1_base, dma_write_cmd_fis.serialize())

    sata_dev.sata.reqs = []
    # Run command 0
    ci.write(1)
    # Continue transmitting past the size of the prdt for command 1
    for i in range(2):
        tb.sata1.fis_seq = (FIS_DMA_ACTIVATE_D2H, 0, 0, 0)
        stest.expect_equal(sata_dev.sata.reqs[-1][1][4:],
                           tuple(expect_fis_0[i]),
                           "First transfer, Activate #%u" % i)
    # Queue up command 2 by writing to PxCI.
    ci.write(2)
    # Complete the whole first transfer
    for i in range(3):
        tb.sata1.fis_seq = (FIS_DMA_ACTIVATE_D2H, 0, 0, 0)
        # Malloc fault would occur here
        stest.expect_equal(sata_dev.sata.reqs[-1][1][4:],
                           tuple(expect_fis_0[i]),
                           "First transfer, Activate #%u" % (i + 2))

    # Receive REG D2H at end of first transfer
    tb.sata1.fis_seq = tuple([FIS_REG_D2H] + [0] * 19)

    # Then expect second command to run
    for i in range(2):
        tb.sata1.fis_seq = (FIS_DMA_ACTIVATE_D2H, 0, 0, 0)
        stest.expect_equal(sata_dev.sata.reqs[-1][1][4:],
                           tuple(expect_fis_1[i]),
                           "Second transfer, Activate #%u" % i)

    # Receive REG D2H at end of second transfer
    tb.sata1.fis_seq = tuple([FIS_REG_D2H] + [0] * 19)

tb.select_sata_mode(AHCI_MODE)
do_test1()
test_bug21477()

print("*** POST FIS ***")
test_post_fis()
print("*** HBA RESET ***")
test_hba_reset()
print("*** STARTCOMM ***")
test_start_comm()
print("*** INTERRUPT ***")
test_interrupt()
print("*** PORT0 ENTER IDLE ***")
test_port0_enter_idle()
print("*** NCQ ***")
test_ncq()
print("*** NON-DATA FISES ***")
test_non_data_fises()
print("*** RECEIVE DATA ***")
test_data_receive()
print("*** RECEIVE SEVERAL DATA-FIS'S ***")
test_receive_large_data()
print("*** PIO OPERATION ***")
test_pio_op()
print("*** RECEIVE FIS WITH ERRORCODE ***")
test_task_file_error()
print("*** RECEIVE OVERFLOW OF DATA ***")
test_receive_overflow()
print("*** RECEIVE INCORRECT FIS-LENGTH ***")
test_receive_wrong_fis_len()
print("*** SEND MORE DATA THAN FITS IN ONE FIS ***")
test_send_large()
print("*** RECEIVE W/O ACTIVE COMMAND SLOT ***")
test_receive_without_active_slot()
print("*** INITIAL REGISTER D2H FIS ***")
test_initial_reg_d2h()
print("*** ADDING NEW COMMAND WHILE RUNNING (BUG 18117) ***")
test_adding_command_while_running()
