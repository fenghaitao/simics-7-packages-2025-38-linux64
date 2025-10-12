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


# tb_spi.py
# testbench of Serial Peripheral Interface in ICH9

import pyobj
import simics
import cli_impl
import stest
import dev_util
import conf
import random

# SIMICS-21543
conf.sim.deprecation_level = 0

sys_timer_mhz   = 14.18

main_ram_base   = 0x80000000
main_ram_size   = 0x100000

RCRB = 0x0
SPIBAR  = RCRB + 0x3800
GBEBAR  = RCRB + 0x4800
REGS_BAR  = SPIBAR
SPI_BANKSIZE  = 0x1000
GBE_BANKSIZE  = 0x1000

ICH9_SPI_FLASH_CNT          = 2
ICH_SPI_FLASH_SIGNATURE     = 0x0FF0A55A
ICH9_SPI_WRITE_EN_PREFIX    = 0
ICH9_SPI_WRITE_DIS_PREFIX   = 1

flash_rom_base          = 0x00
flash_rom_size          = 0x100000 # M25P80
spi_flash_sector_cnt    = 16
spi_flash_sector_size   = 0x10000 # 64K
spi_flash_page_size   = 0x100 # 256 bytes

# 4K, less than 64K to save time in initializing the image
BIOS_BOOT_ADDR          = 0xFE05B
BIOS_FLASH_MAP_ADDR     = 0xF0000 # The bottom of the BIOS flash or region are mapped to
GBE_FLASH_MAP_ADDR     = 0xA0000 # The bottom of the GbE flash or region are mapped to

#BIOS_SIZE               = 0x10000  # assume BIOS is 64K size;
BIOS_SIZE               = 0x1000  # assume BIOS is 4K size;
REGION1_BASE = 0x80000     # assume BIOS is at 0x80000(512k) offset within flash_rom;
REGION1_LIMIT = REGION1_BASE + BIOS_SIZE    #

GBE_SIZE               = 0x1000  # assume GBE-rom is 4K size;
REGION3_BASE = 0x90000     # assume GBE is at 0x80000(512k+64K) offset within flash_rom;
REGION3_LIMIT = REGION3_BASE + GBE_SIZE    #

# A Sample Flash Configuration
FLASH_REGION_CNT        = 5
FLASH_MASTER_CNT        = 3

FLASH_FD_BASE           = 0x00
FLASH_FD_LENGTH         = 0x10

FLASH_COMP_BASE         = 0x10
FLASH_COMP_LENGTH       = 0x0C

FLASH_RGN_BASE          = 0x20
FLASH_RGN_LENGTH        = 0x14

FLASH_MASTER_BASE       = 0x40
FLASH_MASTER_LENGTH     = 0x0C

FLASH_ICH_STRAP_BASE    = 0x50
FLASH_ICH_STRAP_LENGTH  = 0x80

FLASH_MCH_STRAP_BASE    = 0xD0 # Must be within 256-byte
FLASH_MCH_STRAP_LENGTH  = 0x80

FLASH_BIOS_BASE         = 0x200
FLASH_BIOS_LENGTH       = 0x100 # 256-byte

FLASH_ME_BASE           = 0x300
FLASH_ME_LENGTH         = 0x100

FLASH_GBE_BASE          = 0x400
FLASH_GBE_LENGTH        = 0x100

FLASH_PD_BASE           = 0x500
FLASH_PD_LENGTH         = 0x100

FLASH_WHOLE_LENGTH      = 0x600

# SPI memory-mapped register bitfields
# HSFC - Hardware Sequencing Flash Control Register
hsfc_bf     = dev_util.Bitfield_LE({'SME'   : (15),     # SPI SMI# Enable
                                    'DBC'   : (13, 8),  # Data Byte Count
                                    'FCYCLE' : (2, 1),   # Cycle Type
                                    'FGO'  : (0),      # SPI Cycle Go
                                   })

# HSFS - Hardware Sequencing Flash Status Register
hsfs_bf     = dev_util.Bitfield_LE({'FLOCKDN'   : (15), # Flash Configuration Lock-Down
                                    'FDV' : (14),       # Flash Descriptor Valid
                                    'FDOPSS'   : (13),  #
                                    'SCIP'  : (5),      # SPI Cycle In Progress
                                    'BERASE'  : (4,3),  # SPI Cycle In Progress
                                    'AEL'   : (2),      # Access Error Log
                                    'FCERR'  : (1),      # Flash Cycle Error
                                    'FDONE'  : (0),      # Flash Cycle Done
                                   })

# SSFC - Software Sequencing Flash Control Register
ssfc_bf     = dev_util.Bitfield_LE({'SCF'   : (18, 16), # SPI Cycle Frequency
                                    'SME'   : (15),     # SPI SMI# Enable
                                    'DS'    : (14),     # Data Cycle
                                    'DBC'   : (13, 8),  # Data Byte Count
                                    'COP'   : (6, 4),   # Cycle Opcode Pointer
                                    'SPOP'  : (3),      # Sequence Prefix Opcode Pointer
                                    'ACS'   : (2),      # Atomic Cycle Sequence
                                    'SCGO'  : (1),      # SPI Cycle Go
                                   })

# SSFS - Software Sequencing Flash Status Register
ssfs_bf     = dev_util.Bitfield_LE({'AEL'   : (4),      # Access Error Log
                                    'FCERR' : (3),      # Flash Cycle Error
                                    'CDS'   : (2),      # Cycle Done Status
                                    'SCIP'  : (0),      # SPI Cycle In Progress
                                   })

# PREOP - Prefix Opcode Configuration Register
preop_bf    = dev_util.Bitfield_LE({'PO1'   : (15, 8),  # Prefix Opcode 1
                                    'PO0'   : (7, 0),   # Prefix Opcode 0
                                   })

# OPTYPE - Opcode Type Configuration Register
optype_bf   = dev_util.Bitfield_LE({
                                    'OT7'   : (15, 14), # Opcode Type 7
                                    'OT6'   : (13, 12), # Opcode Type 6
                                    'OT5'   : (11, 10), # Opcode Type 5
                                    'OT4'   : (9, 8),   # Opcode Type 4
                                    'OT3'   : (7, 6),   # Opcode Type 3
                                    'OT2'   : (5, 4),   # Opcode Type 2
                                    'OT1'   : (3, 2),   # Opcode Type 1
                                    'OT0'   : (1, 0),   # Opcode Type 0
                                   })

opmenu_bf   = dev_util.Bitfield_LE({
                                    'AO7'   : (63, 56), # Allowable Opcode 7
                                    'AO6'   : (55, 48), # Allowable Opcode 6
                                    'AO5'   : (47, 40), # Allowable Opcode 5
                                    'AO4'   : (39, 32), # Allowable Opcode 4
                                    'AO3'   : (31, 24), # Allowable Opcode 3
                                    'AO2'   : (23, 16), # Allowable Opcode 2
                                    'AO1'   : (15, 8),  # Allowable Opcode 1
                                    'AO0'   : (7, 0),   # Allowable Opcode 0
                                   })

# SPI flash descriptor bitfields
flvalsig_bf = dev_util.Bitfield_LE({'SIG'  : (31, 0)})
flmap0_bf   = dev_util.Bitfield_LE({'NR'    : (26, 24), # Number of Regions
                                    'FRBA'  : (23, 16), # Flash region base region
                                    'NC'    : (9, 8), # Number of components
                                    'FCBA'  : (7, 0), # Flash component base address
                                   })

flmap1_bf   = dev_util.Bitfield_LE({'ISL'   : (31, 24), # ICH Strap Length
                                    'FISBA' : (23, 16), # Flash ICH Strap Base Address
                                    'NM'    : (10, 8), # Number of Masters
                                    'FMBA'  : (7, 0), # Flash Master Base Address
                                   })

flmap2_bf   = dev_util.Bitfield_LE({'MSL'   : (15, 8), # MCH Strap Length
                                    'FMSBA' : (7, 0), # Flash MCH Strap Base Address
                                   })

# Flash Components Register
flcomp_bf   = dev_util.Bitfield_LE({'RSCF'   : (29, 27), # Read ID and Read Status Clock Frequency
                                    'WCF'   : (26, 24), # Write and Erase Clock Frequency
                                    'FRCF'  : (23, 21), # Fast Read Clock Frequency
                                    'FRS'   : (20),     # Fast Read Support
                                    'RCF'   : (19, 17), # Read Clock Frequency
                                    'C2D'   : (5, 3),   # Component 2 Density
                                    'C1D'   : (2, 0),   # Component 1 Density
                                   })

# Flash Invalid Instructions Register
flill_bf    = dev_util.Bitfield_LE({'II3'   : (31, 24), # Invalid Instruction 3
                                    'II2'   : (23, 16), # Invalid Instruction 2
                                    'II1'   : (15, 8),  # Invalid Instruction 1
                                    'II0'   : (7, 0),   # Invalid Instruction 0
                                   })

# Flash Partition Boundary Register
flpb_bf     = dev_util.Bitfield_LE({
                                    'FPBA'  : (12, 0),  # Flash Partition Boundary Address
                                   })

# Region Section in the Flash Descriptor
flreg_bf    = dev_util.Bitfield_LE({'RL'    : (28, 16), # Region Limit
                                    'RB'    : (12, 0),  # Region Base
                                   })

# Master Section in the Flash
# Flash Master (Host CPU/BIOS)
flmstr_bf   = dev_util.Bitfield_LE({'PDRWA' : (28),     # Platform Data Region Write Access
                                    'GRWA'  : (27),     # GbE Region Write Access
                                    'MRWA'  : (26),     # ME Region Write Access
                                    'HCMRWA': (25),     # Host CPU/BIOS Master Region Write Access
                                    'FDRWA' : (24),     # Flash Descriptor Region Write Access
                                    # Read access authority bits
                                    'PDRRA' : (20),     # Platform Data Region Read Access
                                    'GRRA'  : (19),     # GbE Region Read Access
                                    'MRRA'  : (18),     # ME Region Read Access
                                    'HCMRRA': (17),     # Host CPU/BIOS Master Region Read Access
                                    'FDRRA' : (16),     # Flash Descriptor Region Read Access
                                    'RID'   : (15, 0),  # Requester ID
                                   })
class M25p80Const:
    opcode_info = [
                    # name, code, type, address bytes, data bytes)
                    # type: 'r' - read-like, 'w' - write-like, 'p' - prefix-like
                    ('read',    0x03, 'r', 3, 1), # Read an address
                    ('rdsr',    0x05, 'r', 0, 1), # Read Status Register
                    ('wrsr',    0x01, 'w', 0, 1), # Write Status Register
                    ('pp',      0x02, 'w', 3, 1), # Page Program
                    ('se',      0xD8, 'w', 3, 0), # Sector Erase
                    ('be',      0xC7, 'w', 0, 0), # Bulk Erase, i.e. chip erase
                    ('dp',      0xb9, 'w', 0, 0),  # deep mode
                    ('res',     0xab, 'r', 0, 3), # release from deep mode
                  ]
    read_index          = 0
    read_status_index   = 1
    write_status_index  = 2
    page_program_index  = 3
    sector_erase_index  = 4
    bulk_erase_index    = 5
    deep_mode_index      = 6
    release_dp_index     = 7

    pre_op_info = [
                    ('wren',    0x06, 'p', 0, 0), # Write Enable
                    ('wrdi',    0x04, 'p', 0, 0), # Write Disable
                ]

    status_bf  = dev_util.Bitfield_LE({
                    'SRWD'      : 7, # Status Register Write Protect
                    'BP2'       : 4, # Block Protect Bit 2
                    'BP1'       : 3, # Block Protect Bit 1
                    'BP0'       : 2, # Block Protect Bit 0
                    'WEL'       : 1, # Write Enable Latch Bit
                    'WIP'       : 0, # Write In Progress Bit
                   })


class Ich9SpiConst:
    reg_info = {
                    "BFPR"      :   (0x00, 4, 0x00000000),
                    "HSFSTS"    :   (0x04, 2, 0x0000),
                    "HSFCTL"    :   (0x06, 2, 0x0000),
                    "FADDR"     :   (0x08, 4, 0x00000000),
                    "FDATA0"    :   (0x10, 4, 0x00000000),
                    "FDATA1"    :   (0x14, 4, 0x00000000),
                    "FDATA2"    :   (0x18, 4, 0x00000000),
                    "FDATA3"    :   (0x1C, 4, 0x00000000),
                    "FDATA4"    :   (0x20, 4, 0x00000000),
                    "FDATA5"    :   (0x24, 4, 0x00000000),
                    "FDATA6"    :   (0x28, 4, 0x00000000),
                    "FDATA7"    :   (0x2C, 4, 0x00000000),
                    "FDATA8"    :   (0x30, 4, 0x00000000),
                    "FDATA9"    :   (0x34, 4, 0x00000000),
                    "FDATA10"   :   (0x38, 4, 0x00000000),
                    "FDATA11"   :   (0x3C, 4, 0x00000000),
                    "FDATA12"   :   (0x40, 4, 0x00000000),
                    "FDATA13"   :   (0x44, 4, 0x00000000),
                    "FDATA14"   :   (0x48, 4, 0x00000000),
                    "FDATA15"   :   (0x4C, 4, 0x00000000),
                    "FRACC"     :   (0x50, 4, 0x00000202),
                    "FREG0"     :   (0x54, 4, 0x00000000),
                    "FREG1"     :   (0x58, 4, 0x00000000),
                    "FREG2"     :   (0x5C, 4, 0x00000000),
                    "FREG3"     :   (0x60, 4, 0x00000000),
                    "FREG4"     :   (0x64, 4, 0x00000000),
                    "FPR0"      :   (0x74, 4, 0x00000000),
                    "FPR1"      :   (0x78, 4, 0x00000000),
                    "FPR2"      :   (0x7C, 4, 0x00000000),
                    "FPR3"      :   (0x80, 4, 0x00000000),
                    "FPR4"      :   (0x84, 4, 0x00000000),
                    "SSFS"      :   (0x90, 1, 0x00),
                    "SSFC"      :   (0x91, 3, 0x0000),
                    "PREOP"     :   (0x94, 2, 0x0000),
                    "OPTYPE"    :   (0x96, 2, 0x0000),
                    "OPMENU"    :   (0x98, 8, 0x0000000000000000),
                    "BBAR"      :   (0xA0, 4, 0x00000000),
                    "FDOC"      :   (0xB0, 4, 0x00000000),
                    "FDOD"      :   (0xB4, 4, 0x00000000),
                    "AFC"       :   (0xC0, 4, 0x00000000),
                    "LVSCC"     :   (0xC4, 4, 0x00000000),
                    "UVSCC"     :   (0xC8, 4, 0x00000000),
                    "FPB"       :   (0xD0, 4, 0x00000000),
                }

    gbe_regs_info = {
                    "BFPR"      :   (0x00, 4, 0x00000000),
                    "HSFSTS"    :   (0x04, 2, 0x0000),
                    "HSFCTL"    :   (0x06, 2, 0x0000),
                    "FADDR"     :   (0x08, 4, 0x00000000),
                    "FDATA0"    :   (0x10, 4, 0x00000000),
                    "FRACC"     :   (0x50, 4, 0x00000202),
                    "FREG0"     :   (0x54, 4, 0x00000000),
                    "FREG1"     :   (0x58, 4, 0x00000000),
                    "FREG2"     :   (0x5C, 4, 0x00000000),
                    "FREG3"     :   (0x60, 4, 0x00000000),
                    "FPR0"      :   (0x74, 4, 0x00000000),
                    "FPR1"      :   (0x78, 4, 0x00000000),
                    "SSFS"      :   (0x90, 1, 0x00),
                    "SSFC"      :   (0x91, 3, 0x0000),
                    "PREOP"     :   (0x94, 2, 0x0000),
                    "OPTYPE"    :   (0x96, 2, 0x0000),
                    "OPMENU"    :   (0x98, 8, 0x0000000000000000),
                }



class TestBench:
    spi_flash_region_names = ('fd', 'bios', 'me', 'gbe', 'pd')
    boot_codes = [i & 0xFF for i in range(BIOS_SIZE)]
    gbe_codes = [(i + 0xaa) & 0xFF for i in range(BIOS_SIZE)]

    # The scratch-pad memory
    scratch_pad_mem = dev_util.Memory()

    # The flash descriptor layout
    fd_layout = dev_util.Layout_LE(scratch_pad_mem,
                            FLASH_FD_BASE,
                            {'FLVALSIG' : (0, 4, flvalsig_bf),
                             'FLMAP0'   : (4, 4, flmap0_bf),
                             'FLMAP1'   : (8, 4, flmap1_bf),
                             'FLMAP2'   : (0xC, 4, flmap2_bf),
                             })
    fd_layout.clear() # Prepare for assigning value to any bitfield

    # The component descriptor layout
    comp_layout = dev_util.Layout_LE(scratch_pad_mem,
                            FLASH_COMP_BASE,
                            {'FLCOMP'   : (0, 4, flcomp_bf),
                             'FLILL'    : (4, 4, flill_bf),
                             'FLPB'     : (8, 4, flpb_bf),
                            })
    comp_layout.clear()

    # The region descriptor layout
    rgn_layout = dev_util.Layout_LE(scratch_pad_mem,
                            FLASH_RGN_BASE,
                            {'FLREG0'   : (0, 4, flreg_bf),
                             'FLREG1'   : (4, 4, flreg_bf),
                             'FLREG2'   : (8, 4, flreg_bf),
                             'FLREG3'   : (0xC, 4, flreg_bf),
                             'FLREG4'   : (0x10, 4, flreg_bf),
                            })
    rgn_layout.clear()

    # The master section layout
    master_layout = dev_util.Layout_LE(scratch_pad_mem,
                            FLASH_MASTER_BASE,
                            {'FLMSTR1'   : (0, 4, flmstr_bf),
                             'FLMSTR2'   : (4, 4, flmstr_bf),
                             'FLMSTR3'   : (8, 4, flmstr_bf),
                            })
    master_layout.clear()

    fp = None

    def __del__(self):
        #self.dbg("close")
        pass

    def __init__(self, level, bSetupOpcode, bUseNonDescMode):
        self.spi_flashes = []
        self.flash_images = []
        pre_conf_flash = []
        pre_conf_img = []
        #self.dbg("open")

        # Bus clock
        clk = simics.pre_conf_object('sys_timer_clk', 'clock')
        clk.freq_mhz = sys_timer_mhz
        simics.SIM_add_configuration([clk], None)
        self.sys_clk = conf.sys_timer_clk

        # Main memory and its image
        img = simics.pre_conf_object('main_img', 'image')
        img.size = main_ram_size
        main_ram = simics.pre_conf_object('main_ram', 'ram')
        main_ram.image = img
        simics.SIM_add_configuration([img, main_ram], None)
        self.main_ram_image = conf.main_img
        self.main_ram = conf.main_ram

        # Memory-space
        mem = simics.pre_conf_object('mem', 'memory-space')
        simics.SIM_add_configuration([mem], None)
        self.mem = conf.mem
        self.mem_iface = self.mem.iface.memory_space

        self.mem.log_level = level
        self.mem.map += [
                          [main_ram_base,       self.main_ram, 0, 0, main_ram_size],
                        ]

        # ICH9 SPI master (1)
        pre_spi_master = simics.pre_conf_object('spi_master', 'ich10_spi')

        # Two images
        for i in range(ICH9_SPI_FLASH_CNT):
            flash_img = simics.pre_conf_object('flash_img%d' % i, 'image')
            flash_img.size = flash_rom_size
            simics.SIM_add_configuration([flash_img], None)
            pre_conf_img.append(flash_img)

        self.construct_flash(bUseNonDescMode)

        # Two SPI flash
        for i in range(ICH9_SPI_FLASH_CNT):
            spi_flash = simics.pre_conf_object('spi_flash%d' % i, 'M25Pxx')
            #spi_flash.mem_block = pre_conf_img[i] #("flash_img%d" % i)
            spi_flash.mem_block = simics.SIM_get_object('flash_img%d' %i)
            spi_flash.sector_number = spi_flash_sector_cnt
            spi_flash.sector_size   = spi_flash_sector_size
            spi_flash.spi_master = pre_spi_master
            spi_flash.log_level = level
            pre_conf_flash.append(spi_flash)

        # ICH9 SPI master (2)
        pre_spi_master.log_level = level
        pre_spi_master.spi_slave = pre_conf_flash[0]
        #pre_confs = [pre_spi_master] + pre_conf_flash + pre_conf_img
        pre_confs = [pre_spi_master]  + pre_conf_flash
        simics.SIM_add_configuration(pre_confs, None)
        self.flash_images.append(simics.SIM_get_object("flash_img1"))
        self.spi_flashes.append(simics.SIM_get_object("spi_flash1"))

        self.ich10_spi = simics.SIM_get_object("spi_master")

        #  mapping:
        self.mem.map += [ [BIOS_FLASH_MAP_ADDR, [self.ich10_spi, "mem_bios"], 0, 0, BIOS_SIZE] ]
        self.mem.map += [ [GBE_FLASH_MAP_ADDR, [self.ich10_spi, "mem_gbe"], 0, 0, GBE_SIZE] ]
        self.mem.map += [ [SPIBAR, [self.ich10_spi, "spi_regs"], 0, 0, SPI_BANKSIZE] ]
        self.mem.map += [ [GBEBAR, [self.ich10_spi, "gbe_regs"], 0, 0, GBE_BANKSIZE] ]


        upper_mem = simics.pre_conf_object('upper_mem', 'memory-space')
        simics.SIM_add_configuration([upper_mem], None)
        upper_mem.map = [[0x00, self.mem, 0, 0, 0x10000]]

        # set_up data:
        if (bSetupOpcode):
            #setup opcode:
            self.setup_flash_opcodes(SPIBAR, M25p80Const.opcode_info)
            self.setup_flash_opcodes(GBEBAR, M25p80Const.opcode_info)

            #setup pre-opcode:
            #index = M25p80Const.write_en_index: wr_en
            self.setup_write_prefix(SPIBAR,M25p80Const.pre_op_info[0][1],
                           ICH9_SPI_WRITE_EN_PREFIX)
            #index = M25p80Const.write_dis_index: wr_dis
            self.setup_write_prefix(SPIBAR,M25p80Const.pre_op_info[1][1],
                           ICH9_SPI_WRITE_DIS_PREFIX)

            self.setup_write_prefix(GBEBAR,M25p80Const.pre_op_info[0][1],
                           ICH9_SPI_WRITE_EN_PREFIX)
            self.setup_write_prefix(GBEBAR,M25p80Const.pre_op_info[1][1],
                           ICH9_SPI_WRITE_DIS_PREFIX)

    # Memory operation methods
    def read_mem(self, addr, size):
        return self.mem_iface.read(None, addr, size, 0)

    def write_mem(self, addr, bytes):
        self.mem_iface.write(None, addr, bytes, 0)

    def read_value_le(self, addr, bits):
        return dev_util.tuple_to_value_le(self.read_mem(addr, bits // 8))

    def write_value_le(self, addr, bits, value):
        self.write_mem(addr, dev_util.value_to_tuple_le(value, bits // 8))


    def fill_flash(self, start, data, bTrace = True):
        off = 0
        while (off < len(data)):
            val = dev_util.tuple_to_value_le(tuple(data[off: off + 4]))

            #if (bTrace):
            #    self.dbg("write", "fill_flash write @0x%x = 0x%x" % (start + off, val))

            cli_impl.run_command('flash_img0.set %d 0x%x -l'
                                 % (start + off, val))
            off += 4

    def fill_flash_rand(self, start, data, off_pos):
        for off in off_pos:
            val = dev_util.tuple_to_value_le(tuple(data[off: off + 4]))
            cli_impl.run_command('flash_img0.set %d 0x%x -l'
                                 % (start + off, val))


    def dbg(self, action, str_parm=""):
        if (action == 'open'):
            self.fp = open("dgb_log.txt", 'w')
        if (action == "write"):
            if (self.fp != None):
                self.fp.write(str_parm + "\n")
        if (action == "close"):
            if (self.fp != None):
                self.fp.close()


    def construct_flash(self, bNonDescMode):
        if (bNonDescMode):
            # Set a not-0x0FF0A55A value to the first DWORD
            mod_sig = 0xa5a4c5c4
        else:
            # Set a 0x0FF0A55A value to the first DWORD
            mod_sig = ICH_SPI_FLASH_SIGNATURE
        self.construct_region0(mod_sig)
        #self.construct_region1(self.boot_codes)

    def construct_region1(self, codes):
        self.fill_flash(REGION1_BASE, codes)

    def construct_region3(self, codes):
        self.fill_flash(REGION3_BASE, codes)

    def construct_region1_rand(self, codes, off_pos):
        self.fill_flash_rand(REGION1_BASE, codes, off_pos)

    def construct_region3_rand(self, codes, off_pos):
        self.fill_flash_rand(REGION3_BASE, codes, off_pos)

    def construct_region1xxx(self, bios_codes):
        off = 0
        while (off < len(bios_codes)):
            val = dev_util.tuple_to_value_le(tuple(bios_codes[off: off + 4]))
            cli_impl.run_command('flash_img0.set %d 0x%x -l'
                                 % (REGION1_BASE + off, val))
            off += 4

    def construct_region0(self, flsigval):
        temp_buf = [0x00 for i in range(FLASH_FD_LENGTH)]
        # A_1): Construct uppermost flash descriptor in the layout
        self.fd_layout.FLVALSIG.SIG = flsigval
        self.fd_layout.FLMAP0.NR = FLASH_REGION_CNT
        #Note: FRBA just present the [11:4] bit, the real address's [3:0] == 0 !
        #Note: so is the FCBA, FMBA,
        self.fd_layout.FLMAP0.FRBA = (FLASH_RGN_BASE >> 4)
        self.fd_layout.FLMAP0.NC = ICH9_SPI_FLASH_CNT
        self.fd_layout.FLMAP0.FCBA = (FLASH_COMP_BASE >> 4)
        self.fd_layout.FLMAP1.ISL  = FLASH_ICH_STRAP_LENGTH
        self.fd_layout.FLMAP1.FISBA = (FLASH_ICH_STRAP_BASE >> 4)
        self.fd_layout.FLMAP1.NM  = FLASH_MASTER_CNT
        self.fd_layout.FLMAP1.FMBA = (FLASH_MASTER_BASE >> 4)
        self.fd_layout.FLMAP2.MSL = FLASH_MCH_STRAP_LENGTH
        self.fd_layout.FLMAP2.FMSBA = (FLASH_MCH_STRAP_BASE >> 4)

        # A_2): dump fd_layoutdata to Flash_Image
        temp_buf[0 : FLASH_FD_LENGTH] = self.scratch_pad_mem.read(FLASH_FD_BASE, FLASH_FD_LENGTH)
        self.fill_flash(0, temp_buf)


        # B_1): Construct region layout
        #assume region1(bios) is locate at [0x100000, 0x110000] of flash
        # ie. at [1M, 1M+64K] range; so:
        # base= 0x100000 >> 12 = 0x100 ,
        # limit = 0x100 + (0x10000 >> 12) = 0x110
        temp_buf = [0x00 for i in range(FLASH_RGN_LENGTH)]
        self.rgn_layout.FLREG1.RB = REGION1_BASE>>12
        self.rgn_layout.FLREG1.RL = REGION1_LIMIT>>12
        self.rgn_layout.FLREG3.RB = REGION3_BASE>>12
        self.rgn_layout.FLREG3.RL = REGION3_LIMIT>>12

        # B_2): dump rgn_layout data to Flash_Image:
        temp_buf[0 : FLASH_RGN_LENGTH] = self.scratch_pad_mem.read(FLASH_RGN_BASE, FLASH_RGN_LENGTH)
        self.fill_flash(FLASH_RGN_BASE, temp_buf)


    def setup_flash_opcodes(self, regsBAR, opcode_info):
        opmenu_off = Ich9SpiConst.reg_info['OPMENU'][0]
        opmenu_bits = Ich9SpiConst.reg_info['OPMENU'][1] * 8
        optype_off = Ich9SpiConst.reg_info['OPTYPE'][0]
        optype_bits = Ich9SpiConst.reg_info['OPTYPE'][1] * 8
        opmenu_val = 0
        optype_val = 0
        op_idx = 0
        for opcode in opcode_info:
            code = opcode[1]
            type = opcode[2]
            a_bytes = opcode[3] #means address bits
            op_idx += 1
            if type  == 'r' and a_bytes > 0:
                this_type = 0x2 # Read cycle with address
            elif type  == 'r' and a_bytes == 0:
                this_type = 0x0 # Read cycle without address
            elif type  == 'w' and a_bytes > 0:
                this_type = 0x3 # Write cycle with address
            elif type  == 'w' and a_bytes == 0:
                this_type = 0x1 # Write cycle without address
            else:
                continue
            optype_val += (this_type << ((op_idx - 1) * 2)) #will be 16bits data
            opmenu_val += (code << ((op_idx - 1) * 8))   #will be 64bits data

        self.write_value_le(regsBAR + opmenu_off,
                            opmenu_bits, opmenu_val)
        self.write_value_le(regsBAR + optype_off,
                            optype_bits, optype_val)

    def setup_write_prefix(self, regsBAR, dis_en_code, prefix_idx):
        preop_off = Ich9SpiConst.reg_info["PREOP"][0]
        preop_size = Ich9SpiConst.reg_info["PREOP"][1]
        reg_val = self.read_value_le(regsBAR + preop_off, preop_size * 8)
        if prefix_idx == 0:
            reg_val = (reg_val & 0xFF00) + dis_en_code
        else:
            reg_val = (reg_val & 0x00FF) + (dis_en_code << 8)
        self.write_value_le(regsBAR + preop_off, preop_size * 8, reg_val)


    def clear_fdata_regs(self, bar, num):
        fdata0_off  = Ich9SpiConst.reg_info["FDATA0"][0]
        i = 0
        if bar == SPIBAR :
            for i in range(num):
                self.write_value_le(SPIBAR + fdata0_off + 4 * i, 32, 0x0)
        if bar == GBEBAR :
            self.write_value_le(GBEBAR + fdata0_off, 32, 0x0)

def build_random_selector(base, top, uintsize):
#return  value is (piece1_addr, size), (piece2_addr, size), ...
    rand_sel = []
    def generator(base, top, size):
        _base = base
        _top = top
        _size = size
        def get_one():
            addr_index = _base + int(random.random() * (_top - _base))
            if (addr_index >= top):
                addr_index = top - 1
            return [(addr_index * _size, _size)]
        return get_one

    func = generator(base, top, uintsize)

    numbers = 6
    while numbers > 0 :
        rand_sel += func()
        numbers -= 1
    return rand_sel


def expect_string(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%s', expected '%s'" % (info, actual, expected))

def expect_hex(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '0x%x', expected '0x%x'" % (info, actual, expected))

def expect_list(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%r', expected '%r'" % (info, actual, expected))

def expect_dict(actual, expected, info):
    if actual != expected:
        raise Exception("%s: " % info, "got ", actual, ", expected ", expected)

def expect(actual, expected, info):
    if actual != expected:
        raise Exception("%s: got '%d', expected '%d'" % (info, actual, expected))
