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


# Common code for ahci controllers
from sata_tb import *
import dev_util as du

sata = conf.sata1
sata_dev = du.Dev([du.Sata])
sata.sata_device[0] = sata_dev.obj

# Registers
cap = du.Register_LE(sata.bank.ahci, 0, bitfield = du.Bitfield_LE(
        {'s64a': 31,
         'sncq': 30,
         'ssntf': 29,
         'smps':28,
         'sss': 27,
         'salp': 26,
         'sal': 25,
         'sclo': 24,
         'iss': (23, 20),
         'sam': 18,
         'spm': 17,
         'fbss': 16,
         'pmd': 15,
         'ssc': 14,
         'psc': 13,
         'ncs': (12, 8),
         'cccs': 7,
         'ems': 6,
         'sxs': 5,
         'np': (4, 0)}))

ghc = du.Register_LE(sata.bank.ahci, 0x4, bitfield = du.Bitfield_LE(
            {'ae': 31,
             'ie': 1,
             'reset': 0}))

# Registers for port 0
port_base = 0x100
cmd =  du.Register_LE(sata.bank.ahci, port_base + 0x18, bitfield=du.Bitfield_LE(
        {'icc': (31, 28),
         'asp': 27,
         'alpe': 26,
         'dlae': 25,
         'atapi': 24,
         'apste': 23,
         'fbscp': 22,
         'esp': 21,
         'cpd': 20,
         'mpsp': 19,
         'hpcp': 18,
         'pma': 17,
         'cps': 16,
         'cr': 15,
         'fr': 14,
         'mpss': 13,
         'ccs': (12, 8),
         'fre': 4,
         'clo': 3,
         'pod': 2,
         'sud': 1,
         'st': 0}))

tfd = du.Register_LE(sata.bank.ahci, port_base + 0x20,
                     bitfield = du.Bitfield_LE(
        {'err': (15, 8),
         'sts_bsy': 7,
         'sts_cs_hi': (6, 4),
         'sts_drq': 3,
         'sts_cs_lo': (1, 2),
         'sts_err': 0}))

ssts = du.Register_LE(sata.bank.ahci, port_base + 0x28,
                      bitfield = du.Bitfield_LE(
        {'ipm': (11, 8),
         'spd': (7, 4),
         'det': (3, 0)}))

sctl = du.Register_LE(sata.bank.ahci, port_base + 0x2c,
                      bitfield = du.Bitfield_LE(
        {'reserved': (31, 12),
         'ipm': (11, 8),
         'spd': (7, 4),
         'det': (3, 0)}))

ci = du.Register_LE(sata.bank.ahci, port_base + 0x38,
                    bitfield = du.Bitfield_LE(
        {'reserved': (31, 6),
         'c5': 5,
         'c4': 4,
         'c3': 3,
         'c2': 2,
         'c1': 1,
         'c0': 0 }))

serr = du.Register_LE(sata.bank.ahci, port_base + 0x30,
                      bitfield=du.Bitfield_LE(
        {'diag_x': 26,
         'diag_f': 25,
         'diag_t': 24,
         'diag_s': 23,
         'diag_h': 22,
         'diag_c': 21,
         'diag_d': 20,
         'diag_b': 19,
         'diag_w': 18,
         'diag_i': 17,
         'diag_n': 16,
         'err_e' : 11,
         'err_p' : 10,
         'err_c' : 9,
         'err_t' : 8,
         'err_m' : 1,
         'err_i' : 0}))

isr = du.Register_LE(sata.bank.ahci, port_base + 0x10,
                      bitfield = du.Bitfield_LE(
        {'cpds': 31,
         'tfes': 30,
         'hbfs': 29,
         'hbds': 28,
         'ifs' : 27,
         'infs': 26,
         'ofst' : 24,
         'ipms': 23,
         'prcs': 22,
         'dmps': 7,
         'pcs' : 6,
         'dps' : 5,
         'ufs' : 4,
         'sdbs': 3,
         'dss' : 2,
         'pss' : 1,
         'dhrs': 0}))

# Definitions
port_states = {"P_NOT_RUNNING": 0x12,
               "P_IDLE": 0x1a,
               "ERR_WAIT_FOR_CLEAR": 0x20}

# FIS TYPE
FIS_REG_H2D             = 0x27
FIS_REG_D2H             = 0x34
FIS_DMA_ACTIVATE_D2H    = 0x39
FIS_DMA_SETUP_BI        = 0x41  # 'BI': bi-direction
FIS_DATA_BI             = 0x46
FIS_BIST_ACTIVATE_BI    = 0x58
FIS_PIO_SETUP_D2H       = 0x5F
FIS_SET_DEVICE_BIT_D2H  = 0xA1
FIS_UNKNOWN             = 0xFF

# Received FIS offsets
DSFIS_OFFSET            = 0
PSFIS_OFFSET            = 0x20
RFIS_OFFSET             = 0x40
SDBFIS_OFFSET           = 0x58
UFIS_OFFSET             = 0x60

# Structures
class PRDTItem:
    def __init__(self, dba, dbau = 0, dbc = 0, interrupt = 0):
        self.dba = dba
        self.dbau = dbau
        self.dbc = dbc
        self.interrupt = interrupt

    def serialize(self):
        return (self.dba & 0xfe, (self.dba >> 8) & 0xff,
                (self.dba >> 16) & 0xff, (self.dba >> 24) & 0xff,
                self.dbau & 0xff, (self.dbau >> 8) & 0xff,
                (self.dbau >> 16) & 0xff, (self.dbau >> 24) & 0xff,
                0, 0, 0, 0, (self.dbc & 0xff) | 1, (self.dbc >> 8) & 0xff,
                (self.dbc >> 16) & 0x7f, (self.interrupt & 1) << 7)

class CmdHeader:
    def __init__(self, prdtl = 0, pmp = 0, clear = 0, bist = 0, reset = 0,
                 pref = 0, write = 0, atapi = 0, cfl = 0, prdbc = 0,
                 ctba = 0, ctbau = 0):
        self.prdtl = prdtl
        self.pmp = pmp
        self.clear = clear
        self.bist = bist
        self.reset = reset
        self.pref = pref
        self.write = write
        self.atapi = atapi
        self.cfl = cfl
        self.prdbc = prdbc
        self.ctba = ctba
        self.ctbau = ctbau

    def serialize(self):
        return (self.pref << 7 | self.write << 6 | self.atapi << 5 | self.cfl,
                self.pmp << 4 | self.clear << 2 | self.bist << 1 | self.reset,
                self.prdtl & 0xff, self.prdtl >> 8,
                self.prdbc & 0xff, (self.prdbc >> 8) & 0xff,
                (self.prdbc >> 16) & 0xff, self.prdbc >> 24,
                self.ctba & 0xff, (self.ctba >> 8) & 0xff,
                (self.ctba >> 16) & 0xff, self.ctba >> 24,
                self.ctbau & 0xff, (self.ctbau >> 8) & 0xff,
                (self.ctbau >> 16) & 0xff, self.ctbau >> 24)

    def __str__(self):
        return str(self.serialize())

class simple_FIS:
    def __init__(self, fis_type = FIS_REG_D2H, length = 0x14):
        self.fis_type = fis_type
        self.length = length

    def serialize(self):
        return tuple([self.fis_type] + [0] * (self.length - 1))

class H2D_FIS:
    def __init__(self, pm_port = 0, c = 0, cmd = 0, features = 0, lbal = 0,
                 lbam = 0, lbah = 0, dev = 0, lbal_exp = 0, lbam_exp = 0,
                 lbah_exp = 0, feature_exp = 0, sec_cnt = 0,
                 sec_cnt_exp = 0, control = 0):
        self.fis_type = FIS_REG_H2D
        self.pm_port = pm_port
        self.c = c
        self.cmd = cmd
        self.features = features
        self.lbal = lbal
        self.lbam = lbam
        self.lbah = lbah
        self.dev = dev
        self.lbal_exp = lbal_exp
        self.lbam_exp = lbam_exp
        self.lbah_exp = lbah_exp
        self.feature_exp = feature_exp
        self.sec_cnt = sec_cnt
        self.sec_cnt_exp = sec_cnt_exp
        self.control = control

    def serialize(self):
        return (self.fis_type, self.c << 7 | self.pm_port, self.cmd,
                self.features, self.lbal, self.lbam, self.lbah, self.dev,
                self.lbal_exp, self.lbam_exp, self.lbah_exp, self.feature_exp,
                self.sec_cnt, self.sec_cnt_exp, 0, self.control, 0, 0, 0, 0)


class D2H_FIS:
    def __init__(self, pm_port = 0, i = 0, status = 0, error = 0,
                 lbal = 0, lbam = 0, lbah = 0, dev = 0, lbal_exp = 0,
                 lbam_exp = 0, lbah_exp = 0, feature_exp = 0, sec_cnt = 0,
                 sec_cnt_exp = 0):
        self.fis_type = FIS_REG_D2H
        self.pm_port = pm_port
        self.i = i
        self.status = status
        self.error = error
        self.lbal = lbal
        self.lbam = lbam
        self.lbah = lbah
        self.dev = dev
        self.lbal_exp = lbal_exp
        self.lbam_exp = lbam_exp
        self.lbah_exp = lbah_exp
        self.feature_exp = feature_exp
        self.sec_cnt = sec_cnt
        self.sec_cnt_exp = sec_cnt_exp

    def serialize(self):
        return (self.fis_type, self.i << 6 | self.pm_port, self.status,
                self.error, self.lbal, self.lbam, self.lbah, self.dev,
                self.lbal_exp, self.lbam_exp, self.lbah_exp, self.feature_exp,
                self.sec_cnt, self.sec_cnt_exp, 0, 0, 0, 0, 0, 0)

class SDB_FIS:
    def __init__(self, pm_port = 0, i = 0, n = 0, status_lo = 0,
                 status_hi = 0, error = 0, rev = 0):
        self.fis_type = FIS_SET_DEVICE_BIT_D2H
        self.pm_port = pm_port
        self.i = i
        self.n = n
        self.status_lo = status_lo
        self.status_hi = status_hi
        self.error = error
        self.rev = rev

    def serialize(self):
        return (self.fis_type, self.pm_port | (self.i << 6) | (self.n << 7),
                self.status_lo | (self.status_hi << 4), self.error,
                self.rev & 0xff, (self.rev >> 8) & 0xff,
                (self.rev >> 16) & 0xff, self.rev >> 24)

class PIO_FIS:
    def __init__(self, d, transfer_cnt, pm_port = 0, i = 0, status = 0,
                 error = 0, lba = 0, lba_exp = 0, device = 0,
                 sector_cnt = 0, e_status = 0):
        self.fis_type = FIS_PIO_SETUP_D2H
        self.pm_port = pm_port
        self.d = d
        self.i = i
        self.status = status
        self.error = error
        self.lba = lba
        self.lba_exp = lba_exp
        self.device = device
        self.sector_cnt = sector_cnt
        self.e_status = e_status
        self.transfer_cnt = transfer_cnt

    def serialize(self):
        return (self.fis_type, self.pm_port | (self.d << 5) | (self.i << 6),
                self.status, self.error, self.lba & 0xff,
                (self.lba >> 8) & 0xff, self.lba >> 16, self.device,
                self.lba_exp & 0xff, (self.lba_exp >> 8) & 0xff,
                self.lba_exp >> 16, 0, self.sector_cnt & 0xff,
                self.sector_cnt >> 8, 0, self.e_status,
                self.transfer_cnt & 0xff, self.transfer_cnt >> 8, 0, 0)

class DMA_SETUP_FIS:
    def __init__(self, pm_port = 0, r = 0, d = 0, i = 0, a = 0,
                 buf_id_low = 0, buf_id_high = 0, buf_offs = 0, count = 0):
        self.fis_type = FIS_DMA_SETUP_BI
        self.pm_port = pm_port
        self.r = r
        self.d = d
        self.i = i
        self.a = a
        self.buf_id_low = buf_id_low
        self.buf_id_high = buf_id_high
        self.buf_offs = buf_offs
        self.count = count

    def serialize(self):
        return (self.fis_type, (self.a << 7) | (self.i << 6) | (self.d << 5)
                | (self.r << 4) | self.pm_port, self.buf_id_low & 0xff,
                (self.buf_id_low >> 8) & 0xff, (self.buf_id_low >> 16) & 0xff,
                (self.buf_id_low >> 24) & 0xff, self.buf_id_high & 0xff,
                (self.buf_id_high >> 8) & 0xff, (self.buf_id_high >> 16) & 0xff,
                (self.buf_id_high >> 24) & 0xff, 0, 0, 0, 0,
                self.buf_offs & 0xff, (self.buf_offs >> 8) & 0xff,
                (self.buf_offs >> 16) & 0xff, (self.buf_offs >> 24) & 0xff,
                self.count & 0xff, (self.count >> 8) & 0xff,
                (self.count >> 16) & 0xff, (self.count >> 24) & 0xff,
                0, 0, 0, 0)

# Methods
# Rebase port and initialize memory
def rebase_port(port, enable_fre = True):
    base = port_base + port * 0x80

    # Disable ST, CR, FRE first
    cmd.st = 0
    cmd.cr = 0
    cmd.fre = 0

    # command list max size = 32*32 = 1K per port
    cmd_list_base = ahci_mem_base + (port << 10)
    # Config command list pointer
    tb.ahci_wr_reg(base + 0x4, cmd_list_base >> 32)
    tb.ahci_wr_reg(base + 0x0, cmd_list_base & 0xffffffff)
    tb.write_value_le(cmd_list_base, 1024 * 8, 0)

    # FIS entry size is 256B per port
    fis_base = ahci_mem_base + (32 << 10) + (port << 8)
    # Config fis structure pointer
    tb.ahci_wr_reg(base + 0xc, fis_base >> 32)
    tb.ahci_wr_reg(base + 0x8, fis_base & 0xffffffff)
    tb.write_value_le(fis_base, 256 * 8, 0)

    cmd_base = ahci_mem_base + (40 << 10) + (port << 13)
    # allocate 8 prdt entries per command table
    for i in range(32):
        cmdheader = CmdHeader(prdtl = 8, cfl = 5,
                              ctbau = (cmd_base + (i << 8)) >> 32,
                              ctba = (cmd_base + (i << 8)) & 0xffffffff)
        tb.write_mem(cmd_list_base + (i << 5), cmdheader.serialize())

    if enable_fre:
        # Enable FRE again
        cmd.fre = 1

def hba_reset():
    ghc.ae = 1
    ghc_val = tb.ahci_rd_reg(0x04)
    tb.ahci_wr_reg(0x04, ghc_val | 1)

def hba_init(enable_fre = True):
    hba_reset()
    for port in range(tb.ahci_aidp_rd(0x0) & 0x1f):
        rebase_port(port, enable_fre)

    # Enable AHCI
    ghc.ae = 1

    if enable_fre:
        # Enable receiving FIS
        cmd.fre = 1

def reset_and_enter_idle():
    hba_init()
    # Enable receiving FIS
    cmd.fre = 1
    # Send FIS to clear drq
    d2h_fis = D2H_FIS()
    tb.sata1.fis_seq = d2h_fis.serialize()
    # Start Port
    cmd.st = 1

def set_busy():
    sata.ahci_p0pcr_tfd |= 0x80

def set_drq():
    sata.ahci_p0pcr_tfd |= 0x8

# Set a command slot as active to pretend a command has been sent to device
def activate_command_slot(slot, bsy = True, drq = False):
    sata.ahci_p0pcr_p_issue_slot = slot
    # Set CI slot
    sata.ahci_p0pcr_ci = 1 << slot
    sata.ahci_p0pcr_tfd = 0
    if drq:
        set_drq()
    if bsy:
        set_busy()

# Clear command slot
def clear_command_slots():
    sata.ahci_p0pcr_p_issue_slot = 32
    # Set CI slot
    sata.ahci_p0pcr_ci = 0
