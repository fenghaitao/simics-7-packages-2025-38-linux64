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


# Used to create cards with specific attributes for the generic-mmc-card device.
#
# To create a new card, add a subclass for the specific card based on the
# mmc_card_base class. In that class you should create an instance of the
# registers you would like to change,
# ex cid = CID().
# Then change values of your instance,
# ex cid.PRV = xx
# Finally you set the cards registers with the get function,
# ex card.CID = cid.get()


import simics
from comp import *


class OCR:
    "OCR base class with default values"
    OCR_LOW_VOLTAGE    = 0x00000080 # bit 7
    OCR_VOLTAGES       = 0x00FF8000 # bit 8-15
    OCR_CCS            = 0x40000000 # bit 29-30, Access Mode
    OCR_READY          = 0x80000000 # bit 31 Card Ready? Should be true

    def get(self):
        'Get OCR as a 32 bit integer.'
        return (self.OCR_LOW_VOLTAGE | self.OCR_VOLTAGES
                | self.OCR_CCS | self.OCR_READY)

class SCR:
    "SCR base class with default values"
    SCR_STRUCTURE         = 0
    SD_SPEC               = 2
    DATA_STAT_AFTER_ERASE = 1
    SD_SECURITY           = 0
    SD_BUS_WIDTHS         = 4
    SD_SPEC3              = 0
    EX_SECURITY           = 0
    CMD_SUPPORT           = 0

    def get(self):
        'Get SCR as 8 bytes raw data in a tuple.'
        dst=[0]*8
        dst[0] = ((self.SCR_STRUCTURE & 0xf) << 4) + (self.SD_SPEC & 0xf)
        dst[1] = (((self.DATA_STAT_AFTER_ERASE & 1) << 7)
                  | ((self.SD_SECURITY & 7) << 4)
                  | ((self.SD_BUS_WIDTHS & 0xf)))
        dst[2] = (  ((self.SD_SPEC3 & 1) << 7)
                    | ((self.EX_SECURITY & 0xf) << 3))
        dst[3] = self.CMD_SUPPORT & 3
        for i in range(4, 8):
            dst[i] = 0
        return tuple(dst)


class CID_MMC:
    "CID base class with default values for MMC"
    MID = 0x13      # Manufacturer ID
    CBX = 0         # Card/BGA (0 = removable)
    OID = " "       # OEM/Application ID
    PNM = "MMCxxM"  # Product Name (6 bytes)
    PRV = 0         # Product Revision
    PSN = 0         # Product Serial Number (4 bytes)
    MDT = 0xcd      # Manufacturing date (dec 2010)
    CRC = 0         # CRC7 Checksum

    def get(self):
        'Get CID as a 16 bytes raw data in a tuple.'
        cidbuf = [0]*16
        cidbuf[0] = self.MID
        cidbuf[1] = self.CBX & 3
        cidbuf[2] = ord(self.OID)
        i = 3
        for char in list(self.PNM):
            cidbuf[i] = ord(char)
            i += 1
            if i > 8: break
        cidbuf[9] = self.PRV
        cidbuf[10] = self.PSN >> 24
        cidbuf[11] = (self.PSN >> 16) & 0xff
        cidbuf[12] = (self.PSN >> 8) & 0xff
        cidbuf[13] = self.PSN & 0xff
        cidbuf[14] = self.MDT
        cidbuf[15] = (self.CRC << 1) | 1
        return tuple(cidbuf)

class CID_SDHC:
    "CID base class with default values for SDHC"
    MID=0x13       # Manufacturer ID
    OID="\x01\x00" #      # OEM/Application ID
    PNM="SD04G"    # Product Name (5 bytes)
    PRV=0          # Product Revision
    PSN=0          # Product Serial Number (4 bytes)
    MDT=0x11       # Manufacturing date
    CRC=0          # CRC7 Checksum

    def get(self):
        'Get CID as 16 bytes raw data in a tuple.'
        cidbuf = [0]*16
        cidbuf[0] = self.MID
        cidbuf[1] = ord(self.OID[0])
        cidbuf[2] = ord(self.OID[1])
        i = 3
        for char in list(self.PNM):
            cidbuf[i] = ord(char)
            i += 1
            if i > 7: break
        cidbuf[8] = self.PRV
        cidbuf[9] = self.PSN >> 24
        cidbuf[10] = (self.PSN >> 16) & 0xff
        cidbuf[11] = (self.PSN >> 8) & 0xff
        cidbuf[12] = self.PSN & 0xff
        cidbuf[13] = self.MDT >> 8
        cidbuf[14] = self.MDT & 0xff
        cidbuf[15] = (self.CRC << 1) | 1
        return tuple(cidbuf)



class CSD:
    "CSD base class with default values"
    CSD_STRUCTURE       = 0x02  # CSD1.2
    SPEC_VERS           = 0x04  # Version 4.41
    TAAC                = 0x2F  # 20ms
    NSAC                = 0x01  # 100
    TRAN_SPEED          = 0x32  # 26MHz
    CCC                 = 0x0F5 # 0, 2, 4, 5, 6, 7
    READ_BL_LEN         = 0x09  # 512 bytes
    READ_BL_PARTIAL     = 0     # No
    WRITE_BLK_MISALIGN  = 0     # No
    READ_BLK_MISALIGN   = 0     # No
    DRS_IMP             = 0     # No
    C_SIZE              = 0xfff # 4095
    VDD_R_CURR_MIN      = 0x6   # 60mA
    VDD_R_CURR_MAX      = 0x6   # 80mA
    VDD_W_CURR_MIN      = 0x6   # 60mA
    VDD_W_CURR_MAX      = 0x6   # 80mA
    C_SIZE_MULT         = 0x7   # 512
    ERASE_GRP_SIZE      = 0x1F  # 32
    ERASE_GRP_MULT      = 0x1F  # 32
    WP_GRP_SIZE         = 0X07  # 8
    WP_GRP_ENABLE       = 1     # Yes
    DEFAULT_ECC         = 0x0   # None
    R2W_FACTOR          = 0x4   # 16
    WRITE_BL_LEN        = 0x9   # 512 byte
    WRITE_BL_PARTIAL    = 0     # No
    CONTENT_PROT_APP    = 0     # Not Supported
    FILE_FORMAT_GRP     = 0     # HDD-like file system
    COPY                = 1     # Copy
    PERM_WRITE_PROTECT  = 0     # No
    TMP_WRITE_PROTECT   = 0     # No
    FILE_FORMAT         = 0x0   # HDD-like file system
    ECC                 = 0x0   # None
    CRC                 = 0
    LAST                = 1     # Always 1

    def get(self):
        'Get CSD as 16 bytes raw data in a tuple.'
        raw=[0]*16
        raw[0] = (self.CSD_STRUCTURE << 6) + (self.SPEC_VERS << 2)
        raw[1] = self.TAAC
        raw[2] = self.NSAC
        raw[3] = self.TRAN_SPEED
        raw[4] = (self.CCC >> 4)
        raw[5] = ((self.CCC & 0x0f) << 4) + self.READ_BL_LEN
        raw[6] = ((self.READ_BL_PARTIAL << 7) + (self.WRITE_BLK_MISALIGN << 6)
                  + (self.READ_BLK_MISALIGN << 5) + (self.DRS_IMP << 4)
                  + (self.C_SIZE >> 10))
        raw[7] = (self.C_SIZE >> 2) & 0xff
        raw[8] = (((self.C_SIZE & 0x03) << 6) + (self.VDD_R_CURR_MIN << 3)
                  + self.VDD_R_CURR_MAX)
        raw[9] = ((self.VDD_W_CURR_MIN << 5) + (self.VDD_W_CURR_MAX << 2)
                  + (self.C_SIZE_MULT >> 1))
        raw[10] = (((self.C_SIZE_MULT & 1) << 7) + (self.ERASE_GRP_SIZE << 2)
                   + (self.ERASE_GRP_MULT >> 3))
        raw[11] = (((self.ERASE_GRP_MULT & 7) << 5) + self.WP_GRP_SIZE)
        raw[12] = ((self.WP_GRP_ENABLE << 7) + (self.DEFAULT_ECC << 5)
                   + (self.R2W_FACTOR << 2) + (self.WRITE_BL_LEN >> 2))
        raw[13] = (((self.WRITE_BL_LEN & 3) << 6) + (self.WRITE_BL_PARTIAL << 5)
                   + self.CONTENT_PROT_APP)
        raw[14] = ((self.FILE_FORMAT_GRP << 7) + (self.COPY << 6)
                   + (self.PERM_WRITE_PROTECT << 5)
                   + (self.TMP_WRITE_PROTECT << 4) + (self.FILE_FORMAT << 2)
                   + self.ECC)
        raw[15] = (self.CRC << 1) + 1
        return tuple(raw)

class CSD_SDHC(CSD):
    "CSD base class with default values for SDHC"
    CSD_STRUCTURE = 1
    C_SIZE = 0x1cff # user area size of 4GB card
    SECTOR_SIZE = 0x7f
    ERASE_BLK_EN = 1
    CCC = 0x5B5 # 0, 2, 4, 5, 7,8, 10
    def get(self):
        'Get CSD as a 16 bytes raw data in a tuple.'
        raw=[0]*16
        raw[0] = (self.CSD_STRUCTURE << 6)
        raw[1] = self.TAAC
        raw[2] = self.NSAC
        raw[3] = self.TRAN_SPEED
        raw[4] = (self.CCC >> 4)
        raw[5] = ((self.CCC & 0x0f) << 4) + self.READ_BL_LEN
        raw[6] = ((self.READ_BL_PARTIAL << 7) + (self.WRITE_BLK_MISALIGN << 6)
                  + (self.READ_BLK_MISALIGN << 5) + (self.DRS_IMP << 4)
                  + (self.C_SIZE >> 10))
        raw[7] = (self.C_SIZE >> 16) & 0xff
        raw[8] = (self.C_SIZE >> 8) & 0xff
        raw[9] = self.C_SIZE & 0xff
        raw[10] = (((self.ERASE_BLK_EN & 1) << 6)
                   | ((self.SECTOR_SIZE & 0x7f) >> 1))

        raw[11] = (((self.SECTOR_SIZE & 1) << 7) + self.WP_GRP_SIZE)
        raw[12] = ((self.WP_GRP_ENABLE << 7) + (self.DEFAULT_ECC << 5)
                   + (self.R2W_FACTOR << 2) + (self.WRITE_BL_LEN >> 2))
        raw[13] = (((self.WRITE_BL_LEN & 3) << 6) + (self.WRITE_BL_PARTIAL << 5)
                   + self.CONTENT_PROT_APP)
        raw[14] = ((self.FILE_FORMAT_GRP << 7) + (self.COPY << 6)
                   + (self.PERM_WRITE_PROTECT << 5)
                   + (self.TMP_WRITE_PROTECT << 4) + (self.FILE_FORMAT << 2)
                   + self.ECC)
        raw[15] = (self.CRC << 1) + 1
        return tuple(raw)

class ExtCSD:
    "ExtCSD base class with default values"
    EXT_SECURITY_ERR    = 0x0
    S_CMD_SET           = 0x1
    HPI_FEATURES        = 0x0
    BKOPS_SUPPORT       = 0x0
    MAX_PACKED_READS    = 0x0
    MAX_PACKED_WRITES   = 0x0
    DATA_TAG_SUPPORT    = 0x0
    TAG_UNIT_SIZE       = 0x0
    TAG_RES_SIZE        = 0x0
    CONTEXT_CAPABILITIES = 0x0
    LARGE_UNIT_SIZE_M1  = 0x0
    EXT_SUPPORT         = 0x0
    SUPPORTED_MODES     = 0x0
    DEVICE_LIFE_TIME_EST_TYP_B = 0x0
    DEVICE_LIFE_TIME_EST_TYP_A = 0x0
    PRE_EOL_INFO        = 0x0
    OPTIMAL_READ_SIZE   = 0x0
    OPTIMAL_WRITE_SIZE  = 0x0
    OPTIMAL_TRIM_UNIT_SIZE = 0x0
    DEVICE_VERSION      = 0x0
    FIRMWARE_VERSION    = 0x0
    PWR_CL_DDR_200_360  = 0x0
    CACHE_SIZE          = 0x0
    GENERIC_CMD6_TIME   = 0x0
    POWER_OFF_LONG_TIME = 0x0
    BKOPS_STATUS        = 0x0
    INI_TIMEOUT_AP      = 0x14
    PWR_CL_DDR_52_360   = 0x0
    PWR_CL_DDR_52_195   = 0x0
    PWR_CL_200_195      = 0x0
    PWR_CL_200_130      = 0x0
    MIN_PERF_DDR_W_8_52 = 0x0
    MIN_PERF_DDR_R_8_52 = 0x0
    TRIM_MULT           = 0x1
    SEC_FEATURE_SUPPORT = 0x15
    SEC_ERASE_MULT      = 0x1
    SEC_TRIM_MULT       = 0x1
    BOOT_INFO           = 0x5
    BOOT_SIZE_MULT      = 0x10
    ACC_SIZE            = 0x6
    HC_ERASE_GP_SIZE    = 0x8
    ERASE_TIMEOUT_MULT  = 0x1
    REL_WR_SEC_C        = 0x8
    HC_WP_GRP_SIZE      = 0x8
    S_C_VCC             = 0x7
    S_C_VCCQ            = 0x6
    PRODUCTION_STATE_AWARENESS_TIMEOUT = 0x0
    S_A_TIMEOUT         = 0x0F
    SLEEP_NOTIFICATION_TIME = 0x0
    SEC_COUNT           = 0x740000
    MIN_PERF_W_8_52     = 0x8
    MIN_PERF_R_8_52     = 0x8
    MIN_PERF_W_8_26_4_52 = 0x8
    MIN_PERF_R_8_26_4_52 = 0x8
    MIN_PERF_W_4_26     = 0x8
    MIN_PERF_R_4_26     = 0x8
    PWR_CL_26_360       = 0x0
    PWR_CL_52_360       = 0x0
    PWR_CL_26_195       = 0x0
    PWR_CL_52_195       = 0x0
    PARTITION_SWITCH_TIME = 0x0
    OUT_OF_INTERRUPT_TIME = 0x0
    DRIVER_STRENGTH     = 0x0
    CARD_TYPE           = 0x3
    CSD_STRUCTURE       = 0x2
    EXT_CSD_REV         = 0x5
    CMD_SET             = 0x0
    CMD_SET_REV         = 0x0
    POWER_CLASS         = 0x0
    HS_TIMING           = 0x0
    BUS_WIDTH           = 0x1
    ERASED_MEM_CONT     = 0x0
    PARTITION_CONFIG    = 0x0
    BOOT_CONFIG_PROT    = 0x0
    BOOT_BUS_WIDTH      = 0x0
    ERASE_GROUP_DEF     = 0x0
    BOOT_WP_STATUS      = 0x0
    BOOT_WP             = 0x0
    USER_WP             = 0x0
    FW_CONFIG           = 0x0
    RPMB_SIZE_MULTI     = 0x1
    WR_REL_SET          = 0x0
    WR_REL_PARAM        = 0x0
    SANITIZE_START      = 0x0
    BKOPS_START         = 0x0
    BKOPS_EN            = 0x0
    RST_n_FUNCTION      = 0x0
    HPI_MGMT            = 0x0
    PARTITIONING_SUPPORT = 0x3
    MAX_ENH_SIZE_MULT   = 0x0
    PARTITIONS_ATTRIBUTE = 0x0
    PARTITIONS_SETTING_COMPLETED = 0x0
    GP_SIZE_MULT        = 0x0
    ENH_SIZE_MULT       = 0x0
    ENH_START_ADDR      = 0x0
    SEC_BAD_BLK_MGMNT   = 0x0
    PRODUCTION_STATE_AWARENESS = 0x0
    TCASE_SUPPORT       = 0x0
    PERIODIC_WAKEUP     = 0x0
    PROGRAM_CID_CSD_DDR_SUPPORT = 0x0
    VENDOR_SPECIFIC_FIELD = 0x0
    NATIVE_SECTOR_SIZE  = 0x0
    USE_NATIVE_SECTOR   = 0x0
    DATA_SECTOR_SIZE    = 0x0
    MAX_PRE_LOADING_DATA_SIZE = 0x0
    PRODUCT_STATE_AWARENESS_ENABLEMENT = 0x0
    SECURE_REMOVAL_TYPE = 0x0

    def get(self):
        'Get ExtCSD as 512 bytes of data in a tuple.'
        extdata=[0]*512
        extdata[505] = self.EXT_SECURITY_ERR
        extdata[504] = self.S_CMD_SET
        extdata[503] = self.HPI_FEATURES
        extdata[502] = self.BKOPS_SUPPORT
        extdata[501] = self.MAX_PACKED_READS
        extdata[500] = self.MAX_PACKED_WRITES
        extdata[499] = self.DATA_TAG_SUPPORT
        extdata[498] = self.TAG_UNIT_SIZE
        extdata[497] = self.TAG_RES_SIZE
        extdata[496] = self.CONTEXT_CAPABILITIES
        extdata[495] = self.LARGE_UNIT_SIZE_M1
        extdata[494] = self.EXT_SUPPORT
        extdata[493] = self.SUPPORTED_MODES
        extdata[269] = self.DEVICE_LIFE_TIME_EST_TYP_B
        extdata[268] = self.DEVICE_LIFE_TIME_EST_TYP_A
        extdata[267] = self.PRE_EOL_INFO
        extdata[266] = self.OPTIMAL_READ_SIZE
        extdata[265] = self.OPTIMAL_WRITE_SIZE
        extdata[264] = self.OPTIMAL_TRIM_UNIT_SIZE
        extdata[263] = (self.DEVICE_VERSION >> 8) & 0xff
        extdata[262] = self.DEVICE_VERSION & 0xff
        extdata[261] = (self.FIRMWARE_VERSION >> (8 * 7)) & 0xff
        extdata[260] = (self.FIRMWARE_VERSION >> (8 * 6)) & 0xff
        extdata[259] = (self.FIRMWARE_VERSION >> (8 * 5)) & 0xff
        extdata[258] = (self.FIRMWARE_VERSION >> (8 * 4)) & 0xff
        extdata[257] = (self.FIRMWARE_VERSION >> (8 * 3)) & 0xff
        extdata[256] = (self.FIRMWARE_VERSION >> (8 * 2)) & 0xff
        extdata[255] = (self.FIRMWARE_VERSION >> (8 * 1)) & 0xff
        extdata[254] = self.FIRMWARE_VERSION & 0xff
        extdata[253] = self.PWR_CL_DDR_200_360
        extdata[252] = (self.CACHE_SIZE >> (8 * 3)) & 0xff
        extdata[251] = (self.CACHE_SIZE >> (8 * 2)) & 0xff
        extdata[250] = (self.CACHE_SIZE >> (8 * 1)) & 0xff
        extdata[249] = self.CACHE_SIZE & 0xff
        extdata[248] = self.GENERIC_CMD6_TIME
        extdata[247] = self.POWER_OFF_LONG_TIME
        extdata[246] = self.BKOPS_STATUS
        extdata[241] = self.INI_TIMEOUT_AP
        extdata[239] = self.PWR_CL_DDR_52_360
        extdata[238] = self.PWR_CL_DDR_52_195
        extdata[237] = self.PWR_CL_200_195
        extdata[236] = self.PWR_CL_200_130
        extdata[235] = self.MIN_PERF_DDR_W_8_52
        extdata[234] = self.MIN_PERF_DDR_R_8_52
        extdata[232] = self.TRIM_MULT
        extdata[231] = self.SEC_FEATURE_SUPPORT
        extdata[230] = self.SEC_ERASE_MULT
        extdata[229] = self.SEC_TRIM_MULT
        extdata[228] = self.BOOT_INFO
        extdata[226] = self.BOOT_SIZE_MULT
        extdata[225] = self.ACC_SIZE
        extdata[224] = self.HC_ERASE_GP_SIZE
        extdata[223] = self.ERASE_TIMEOUT_MULT
        extdata[222] = self.REL_WR_SEC_C
        extdata[221] = self.HC_WP_GRP_SIZE
        extdata[220] = self.S_C_VCC
        extdata[219] = self.S_C_VCCQ
        extdata[218] = self.PRODUCTION_STATE_AWARENESS_TIMEOUT
        extdata[217] = self.S_A_TIMEOUT
        extdata[216] = self.SLEEP_NOTIFICATION_TIME
        extdata[215] = self.SEC_COUNT >> 24
        extdata[214] = (self.SEC_COUNT >> 16) & 0xff
        extdata[213] = (self.SEC_COUNT >> 8) & 0xff
        extdata[212] = self.SEC_COUNT & 0xff
        extdata[210] = self.MIN_PERF_W_8_52
        extdata[209] = self.MIN_PERF_R_8_52
        extdata[208] = self.MIN_PERF_W_8_26_4_52
        extdata[207] = self.MIN_PERF_R_8_26_4_52
        extdata[206] = self.MIN_PERF_W_4_26
        extdata[205] = self.MIN_PERF_R_4_26
        extdata[203] = self.PWR_CL_26_360
        extdata[202] = self.PWR_CL_52_360
        extdata[201] = self.PWR_CL_26_195
        extdata[200] = self.PWR_CL_52_195
        extdata[199] = self.PARTITION_SWITCH_TIME
        extdata[198] = self.OUT_OF_INTERRUPT_TIME
        extdata[196] = self.DRIVER_STRENGTH
        extdata[196] = self.CARD_TYPE
        extdata[194] = self.CSD_STRUCTURE
        extdata[192] = self.EXT_CSD_REV
        extdata[191] = self.CMD_SET
        extdata[189] = self.CMD_SET_REV
        extdata[187] = self.POWER_CLASS
        extdata[185] = self.HS_TIMING
        extdata[183] = self.BUS_WIDTH
        extdata[181] = self.ERASED_MEM_CONT
        extdata[179] = self.PARTITION_CONFIG
        extdata[178] = self.BOOT_CONFIG_PROT
        extdata[177] = self.BOOT_BUS_WIDTH
        extdata[175] = self.ERASE_GROUP_DEF
        extdata[173] = self.BOOT_WP_STATUS
        extdata[173] = self.BOOT_WP
        extdata[171] = self.USER_WP
        extdata[169] = self.FW_CONFIG
        extdata[168] = self.RPMB_SIZE_MULTI
        extdata[167] = self.WR_REL_SET
        extdata[166] = self.WR_REL_PARAM
        extdata[165] = self.SANITIZE_START
        extdata[164] = self.BKOPS_START
        extdata[163] = self.BKOPS_EN
        extdata[162] = self.RST_n_FUNCTION
        extdata[161] = self.HPI_MGMT
        extdata[160] = self.PARTITIONING_SUPPORT
        extdata[159] = self.MAX_ENH_SIZE_MULT >> 16
        extdata[158] = (self.MAX_ENH_SIZE_MULT >> 8) & 0xff
        extdata[157] = self.MAX_ENH_SIZE_MULT & 0xff
        extdata[156] = self.PARTITIONS_ATTRIBUTE
        extdata[155] = self.PARTITIONS_SETTING_COMPLETED
        extdata[143] = self.GP_SIZE_MULT
        extdata[140] = self.ENH_SIZE_MULT
        extdata[139] = self.ENH_START_ADDR >> 24
        extdata[138] = (self.ENH_START_ADDR >> 16) & 0xff
        extdata[137] = (self.ENH_START_ADDR >> 8) & 0xff
        extdata[136] = self.ENH_START_ADDR & 0xff
        extdata[134] = self.SEC_BAD_BLK_MGMNT
        extdata[133] = self.PRODUCTION_STATE_AWARENESS
        extdata[132] = self.TCASE_SUPPORT
        extdata[131] = self.PERIODIC_WAKEUP
        extdata[130] = self.PROGRAM_CID_CSD_DDR_SUPPORT
        extdata[127] = (self.VENDOR_SPECIFIC_FIELD >> (8 * 2)) & 0xff
        extdata[126] = (self.VENDOR_SPECIFIC_FIELD >> (8 * 1)) & 0xff
        extdata[125] = self.VENDOR_SPECIFIC_FIELD & 0xff
        extdata[63]  = self.NATIVE_SECTOR_SIZE
        extdata[62]  = self.USE_NATIVE_SECTOR
        extdata[61]  = self.DATA_SECTOR_SIZE
        extdata[21]  = (self.MAX_PRE_LOADING_DATA_SIZE >> (8 * 3)) & 0xff
        extdata[20]  = (self.MAX_PRE_LOADING_DATA_SIZE >> (8 * 2)) & 0xff
        extdata[19]  = (self.MAX_PRE_LOADING_DATA_SIZE >> (8 * 1)) & 0xff
        extdata[18]  = self.MAX_PRE_LOADING_DATA_SIZE & 0xff
        extdata[17]  = self.PRODUCT_STATE_AWARENESS_ENABLEMENT
        extdata[16]  = self.SECURE_REMOVAL_TYPE
        return tuple(extdata)

class ExtCSD2GB(ExtCSD):
    SEC_COUNT           = 0x400000
    BOOT_INFO           = 0
    BOOT_SIZE_MULT      = 0
    PARTITIONING_SUPPORT= 0

class mmc_card_base(StandardConnectorComponent):
    """The generic_mmc_card component represents an MMC/SD/SDHC/SDIO card. Size
    is set on commandline and other specifications are default from generic
    model."""
    _class_desc = 'a MMC/SD card'
    _do_not_init = object()

    class basename(StandardConnectorComponent.basename):
        val = 'mmc_card'

    class size(SimpleAttribute(0, 'i', attr = simics.Sim_Attr_Pseudo)):
        """Card size, in bytes"""

        def getter(self):
            c = self._up.get_slot('card')
            return c.size

    class file(SimpleConfigAttribute(None, 's|n')):
        """File with disk contents for the full disk. Either a raw file or
        a virtual disk file in craff, DMG, or VHDX format"""

    class use_generic_sdmmc_card(SimpleConfigAttribute(True, 'b')):
        """TRUE for using the newer generic-sdmmc-card device, or FALSE
        for the older and outdated generic-mmc-card device."""

    class component(StandardConnectorComponent.component):
        def pre_instantiate(self):
            if self._up.file.val:
                if not simics.SIM_lookup_file(self._up.file.val):
                    print('could not find disk file', self._up.file.val)
                    return False
                self._up.get_slot('image').files = [[self._up.file.val, 'ro',
                                                     0, 0]]
            return True

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_connectors(self):
        self.add_connector('mmc_controller', MMCUpConnector('card'))

    def get_image_size(self):
        raise CompException('get_image_size must be implemented.')

    def add_objects(self):
        # Backing image
        image = self.add_pre_obj('image', 'image')
        image.size = self.get_image_size()

class micron_mtfc4ggqdi_sdhc_card(mmc_card_base):
    """A SDHC card component similar to Micron MTFC4GGQDI-IT eMMC."""
    _class_desc = 'a SHDC card'

    class basename(StandardConnectorComponent.basename):
        val = 'micron_sdhc'

    def get_image_size(self):
        return 0x1d00 << 19

    def add_objects(self):
        mmc_card_base.add_objects(self)

        csd = CSD_SDHC()
        ocr = OCR()
        cid = CID_SDHC()
        scr = SCR()

        csd.C_SIZE = (self.get_image_size() >> 19) - 1 # user area size of 4GB card
        csd.CCC = csd.CCC | 0x400                      # Enable Switching

        ocr.OCR_CCS = 0
        ocr.OCR_LOW_VOLTAGE = 0

        if self.use_generic_sdmmc_card.val:
            card = self.add_pre_obj('card', 'sd_card')
            card.sd_type = 0
        else:
            card = self.add_pre_obj('card', 'generic-mmc-card')
            card.card_type = 2
            card.CSD = csd.get()
            card.OCR = ocr.get()
            card.CID = cid.get()
            card.SCR = scr.get()

        card.flash_image = self.get_slot('image')
        card.size = (csd.C_SIZE + 1) * 512 * 1024


class micron_mtfc4ggqdi_emmc_card(mmc_card_base):
    """A Micron MTFC4GGQDI-IT eMMC Card."""
    _class_desc = 'high capacity eMMC card'

    class basename(StandardConnectorComponent.basename):
        val = 'micron_emmc'

    def get_image_size(self):
        boot_part_size = 0x10 * 1024 * 128
        rpmb_part_size = 1024 * 128
        user_area_size = 0x740000 * 512    # 3712 MB
        return 2 * boot_part_size + rpmb_part_size + user_area_size

    def add_objects(self):
        mmc_card_base.add_objects(self)

        csd = CSD()
        ocr = OCR()
        cid = CID_MMC()
        scr = SCR()
        extcsd = ExtCSD()

        if self.use_generic_sdmmc_card.val:
            card = self.add_pre_obj('card', 'mmc_card')
        else:
            card = self.add_pre_obj('card', 'generic-mmc-card')
            card.card_type = 0
            card.SCR = scr.get()
            card.CSD = csd.get()
            card.OCR = ocr.get()
            card.CID = cid.get()
            card.ExtCSD = extcsd.get()

        card.flash_image = self.get_slot('image')
        card.size = self.get_image_size()


class micron_mtfc2ggqdi_emmc_card(mmc_card_base):
    """A 2GB Micron eMMC card."""
    _class_desc = 'high capacity eMMC card'

    class basename(StandardConnectorComponent.basename):
        val = 'micron_emmc'

    def get_image_size(self):
        boot_part_size = 0x10 * 1024 * 128
        rpmb_part_size = 1024 * 128
        user_area_size = 0x400000 * 512                # 2147 MB
        return 2 * boot_part_size + rpmb_part_size + user_area_size

    def add_objects(self):
        mmc_card_base.add_objects(self)

        if self.use_generic_sdmmc_card.val:
            card = self.add_pre_obj('card', 'mmc_card')
        else:
            card = self.add_pre_obj('card', 'generic-mmc-card')
            card.card_type = 0
            card.ExtCSD = ExtCSD2GB().get()

        card.flash_image = self.get_slot('image')
        card.size = self.get_image_size()


class ExtCSD_mtfc4gacaeam(ExtCSD):
    "ECSD Values for MTFC4GACAEAM card"
    EXT_SECURITY_ERR                   = 0
    S_CMD_SET                          = 1
    HPI_FEATURES                       = 1
    BKOPS_SUPPORT                      = 1
    MAX_PACKED_READS                   = 0x3f
    MAX_PACKED_WRITES                  = 0x3f
    DATA_TAG_SUPPORT                   = 1
    TAG_UNIT_SIZE                      = 3
    TAG_RES_SIZE                       = 0
    CONTEXT_CAPABILITIES               = 5
    LARGE_UNIT_SIZE_M1                 = 1
    EXT_SUPPORT                        = 3
    SUPPORTED_MODES                    = 3
    DEVICE_LIFE_TIME_EST_TYP_B         = 1
    DEVICE_LIFE_TIME_EST_TYP_A         = 1
    PRE_EOL_INFO                       = 1
    OPTIMAL_READ_SIZE                  = 1
    OPTIMAL_WRITE_SIZE                 = 4
    OPTIMAL_TRIM_UNIT_SIZE             = 1

    DEVICE_VERSION                     = 0
    FIRMWARE_VERSION                   = 6
    PWR_CL_DDR_200_360                 = 0
    CACHE_SIZE                         = 0x400
    GENERIC_CMD6_TIME                  = 0x19
    POWER_OFF_LONG_TIME                = 0xff
    BKOPS_STATUS                       = 0
    INI_TIMEOUT_AP                     = 0x64
    PWR_CL_DDR_52_360                  = 0
    PWR_CL_DDR_52_195                  = 0
    PWR_CL_200_195                     = 0x40
    PWR_CL_200_130                     = 0
    MIN_PERF_DDR_W_8_52                = 0
    MIN_PERF_DDR_R_8_52                = 0
    TRIM_MULT                          = 5
    SEC_FEATURE_SUPPORT                = 0x55
    SEC_ERASE_MULT                     = 1
    SEC_TRIM_MULT                      = 1
    BOOT_INFO                          = 7
    BOOT_SIZE_MULT                     = 0x10
    ACC_SIZE                           = 6
    HC_ERASE_GP_SIZE                   = 1
    ERASE_TIMEOUT_MULT                 = 5
    REL_WR_SEC_C                       = 1
    HC_WP_GRP_SIZE                     = 0x10
    S_C_VCC                            = 6
    S_C_VCCQ                           = 7
    PRODUCTION_STATE_AWARENESS_TIMEOUT = 0x14
    S_A_TIMEOUT                        = 0x12
    SLEEP_NOTIFICATION_TIME            = 0xf
    SEC_COUNT                          = 0x748000
    MIN_PERF_W_8_52                    = 8
    MIN_PERF_R_8_52                    = 8
    MIN_PERF_W_8_26_4_52               = 8
    MIN_PERF_R_8_26_4_52               = 8
    MIN_PERF_W_4_26                    = 8
    MIN_PERF_R_4_26                    = 8
    PWR_CL_26_360                      = 0
    PWR_CL_52_360                      = 0
    PWR_CL_26_195                      = 0
    PWR_CL_52_195                      = 0
    PARTITION_SWITCH_TIME              = 3
    OUT_OF_INTERRUPT_TIME              = 0xa
    DRIVER_STRENGTH                    = 0x1f
    CARD_TYPE                          = 0x57
    CSD_STRUCTURE                      = 2
    EXT_CSD_REV                        = 7
    CMD_SET                            = 0
    CMD_SET_REV                        = 0
    POWER_CLASS                        = 0
    HS_TIMING                          = 0
    BUS_WIDTH                          = 0
    ERASED_MEM_CONT                    = 0
    PARTITION_CONFIG                   = 0
    BOOT_CONFIG_PROT                   = 0
    BOOT_BUS_WIDTH                     = 0
    ERASE_GROUP_DEF                    = 0
    BOOT_WP_STATUS                     = 0
    BOOT_WP                            = 0
    USER_WP                            = 0
    FW_CONFIG                          = 0
    RPMB_SIZE_MULTI                    = 1
    WR_REL_SET                         = 0x1f
    WR_REL_PARAM                       = 0x15
    SANITIZE_START                     = 0
    BKOPS_START                        = 0
    BKOPS_EN                           = 0
    RST_n_FUNCTION                     = 0
    HPI_MGMT                           = 0
    PARTITIONING_SUPPORT               = 7
    MAX_ENH_SIZE_MULT                  = 0xe9
    PARTITIONS_ATTRIBUTE               = 0
    PARTITIONS_SETTING_COMPLETED       = 0
    GP_SIZE_MULT                       = 0
    ENH_SIZE_MULT                      = 0
    ENH_START_ADDR                     = 0
    SEC_BAD_BLK_MGMNT                  = 0
    PRODUCTION_STATE_AWARENESS         = 0
    TCASE_SUPPORT                      = 0
    PERIODIC_WAKEUP                    = 0
    PROGRAM_CID_CSD_DDR_SUPPORT        = 1
    VENDOR_SPECIFIC_FIELD              = 0x10
    NATIVE_SECTOR_SIZE                 = 0
    USE_NATIVE_SECTOR                  = 0
    DATA_SECTOR_SIZE                   = 0
    MAX_PRE_LOADING_DATA_SIZE          = 0x3a4000
    PRODUCT_STATE_AWARENESS_ENABLEMENT = 1
    SECURE_REMOVAL_TYPE                = 0

class CSD_mtfc4gacaeam(CSD):
    CSD_STRUCTURE  = 3
    TAAC           = 0x4f
    DSR_IMP        = 1
    VDD_R_CURR_MIN = 7
    VDD_R_CURR_MAX = 7
    VDD_W_CURR_MIN = 7
    VDD_W_CURR_MAX = 7
    WP_GRP_SIZE    = 0x1f
    R2W_FACTOR     = 2
    COPY           = 0

class CID_mtfc4gacaeam(CID_MMC):
    MID = 0xfe
    CBX = 1

class micron_mtfc4gacaeam_emmc_card(mmc_card_base):
    """A Micron MTFC4GACAEAM-1M WT eMMC Card."""
    _class_desc = 'eMMC card'

    class basename(StandardConnectorComponent.basename):
        val = 'micron_mtfc4gacaeam_emmc'

    def get_image_size(self):
        user_area = 0x748000 * 512           # 3728 MB
        boot_area = 2 * 128 * 1024 * 16      # 2 * 2 MB
        rpmb_area = 1 * 128 * 1024           # 128 KB
        return user_area + boot_area + rpmb_area

    def add_objects(self):
        mmc_card_base.add_objects(self)

        csd = CSD_mtfc4gacaeam()
        ocr = OCR()
        cid = CID_mtfc4gacaeam()
        scr = SCR()
        extcsd = ExtCSD_mtfc4gacaeam()

        if self.use_generic_sdmmc_card.val:
            card = self.add_pre_obj('card', 'mmc_card')
        else:
            card = self.add_pre_obj('card', 'generic-mmc-card')
            card.card_type = 0
            card.CSD = csd.get()
            card.OCR = ocr.get()
            card.CID = cid.get()
            card.SCR = scr.get()
            card.ExtCSD = extcsd.get()

        card.flash_image = self.get_slot('image')
        card.size = self.get_image_size()


class micron_mtfc4gacaeam_emmc_card_with_boot_part(micron_mtfc4gacaeam_emmc_card):
    """A Micron MTFC4GACAEAM-1M WT eMMC Card with adjustable partitions."""
    _class_desc = 'eMMC card'

    class boot0_part(SimpleConfigAttribute(None, 's', simics.Sim_Attr_Optional)):
        """Boot 0 partition file"""

    class boot1_part(SimpleConfigAttribute(None, 's', simics.Sim_Attr_Optional)):
        """Boot 1 partition file"""

    class rpbm_part(SimpleConfigAttribute(None, 's', simics.Sim_Attr_Optional)):
        """RPBM partition file"""

    def setup(self):
        self.GIGABYTE = 1024*1024*1024
        self.MEGABYTE = 1024*1024
        self.KILOBYTE = 1024

        super().setup()
        if not self.instantiated.val:
            self.add_objects()

    def add_objects(self):
        super().add_objects()

        card = self.get_slot("card")

        card.partition_map = [None] * 7
        def add_part(nr, name, part_size, file):
            image = self.add_pre_obj(name, "image", size=part_size)
            if file:
                start = 0
                file_size = 0 # 0 = take it from the binary size
                image.files = [[file, "ro", start, file_size]]
            card.partition_map[nr] = image

        add_part(0, "boot0_part", 8 * self.MEGABYTE, self.boot0_part.val)
        add_part(1, "boot1_part", 8 * self.MEGABYTE, self.boot1_part.val)
        add_part(2, "rpbm_part", 8 * self.MEGABYTE, self.rpbm_part.val)


class ExtCSD_mtfc8gacaeam(ExtCSD_mtfc4gacaeam):
    TRIM_MULT = 7
    ACC_SIZE = 7
    ERASE_TIMEOUT_MULT = 7
    SEC_COUNT = 0xe90000
    MAX_ENH_SIZE_MULT = 0x1d2
    MAX_PRE_LOADING_DATA_SIZE = 0x748000

class micron_mtfc8gacaeam_emmc_card(mmc_card_base):
    """A Micron MTFC8GACAEAM-1M WT eMMC Card."""
    _class_desc = 'eMMC card'

    class basename(StandardConnectorComponent.basename):
        val = 'micron_mtfc8gacaeam_emmc'

    def get_image_size(self):
        user_area = 0xe90000 * 512           # 7456 MB
        boot_area = 2 * 128 * 1024 * 16      # 2 * 2 MB
        rpmb_area = 1 * 128 * 1024           # 128 KB
        return user_area + boot_area + rpmb_area

    def add_objects(self):
        mmc_card_base.add_objects(self)

        csd = CSD_mtfc4gacaeam()
        ocr = OCR()
        cid = CID_mtfc4gacaeam()
        scr = SCR()
        extcsd = ExtCSD_mtfc8gacaeam()

        if self.use_generic_sdmmc_card.val:
            card = self.add_pre_obj('card', 'mmc_card')
        else:
            card = self.add_pre_obj('card', 'generic-mmc-card')
            card.card_type = 0
            card.CSD = csd.get()
            card.OCR = ocr.get()
            card.CID = cid.get()
            card.SCR = scr.get()
            card.ExtCSD = extcsd.get()

        card.flash_image = self.get_slot('image')
        card.size = self.get_image_size()

# Add support for Micron MTFC8GAM, MTFC16GAP, MTFC32GP, MTFC64GAP, MTFC128GAP
# https://static6.arrow.com/aropdfconversion/d12a643f8a0d6dd17f4596a7b99f1614bd4cfbe0/auto_emmc_8-128gb_5_1.pdf

def byteize(bit_offset, bit_size):
    """Split up bit offsets into a vector of byte-aligned pieces with mask."""
    end_bit = bit_offset + bit_size
    while bit_offset < end_bit:
        min_bit = bit_offset & 7
        bit_size = 8 - min_bit
        if bit_offset + bit_size > end_bit:
            bit_size = end_bit - bit_offset
        min_mask = 0xFF << min_bit
        max_mask = 0xFF >> (8 - bit_size - min_bit)
        bit_mask = min_mask & max_mask
        yield (bit_offset, bit_size, bit_mask)
        bit_offset += bit_size

def set_bits(data, bit_offset, bit_size, value):
    """Write the value into the specified bits, in big-endian."""
    stop_bit = len(data) * 8
    if bit_offset + bit_size > stop_bit:
        raise ValueError('Writing outside data ({}..{} > max bit {})'.format(
            bit_offset, bit_offset + bit_size - 1, stop_bit - 1))
    for (offs, size, mask) in byteize(bit_offset, bit_size):
        shift = offs & 7
        keep_mask = 0xFF ^ mask
        byte = len(data) - 1 - offs // 8
        data[byte] = (data[byte] & keep_mask) | ((value << shift) & mask)
        value >>= size

def get_bits(data, bit_offset, bit_size):
    """Read a value from the specified bits in the data, in big-endian."""
    stop_bit = len(data) * 8
    if bit_offset + bit_size > stop_bit:
        raise ValueError('Reading outside data ({}..{} > max bit {})'.format(
            bit_offset, bit_offset + bit_size - 1, stop_bit - 1))
    value = 0
    shift = 0
    for (offs, size, mask) in byteize(bit_offset, bit_size):
        byte = len(data) - 1 - offs // 8
        value += ((data[byte] & mask) >> (offs & 7)) << shift
        shift += size
    return value

def set_bytes(data, byte_offset, byte_size, value):
    """Write a value to the specified bytes, in little-endian."""
    if byte_offset + byte_size > len(data):
        raise ValueError('Writing outside data ({}..{} > max byte {})'.format(
            byte_offset, byte_offset + byte_size - 1, len(data) - 1))
    for offs in range(byte_offset, byte_offset + byte_size):
        data[offs] = value & 0xFF
        value >>= 8

def get_bytes(data, byte_offset, byte_size):
    """Read a value from the specified bytes, in little-endian."""
    if byte_offset + byte_size > len(data):
        raise ValueError('Reading outside data ({}..{} > max byte {}'.format(
            byte_offset, byte_offset + byte_size - 1, len(data) - 1))
    value = 0
    shift = 0
    for offs in range(byte_offset, byte_offset + byte_size):
        value += data[offs] << shift
        shift += 8
    return value

# Typically 33030144 bytes (252 * 128 * 1024 = 31.5 MiB)
def get_boot_area_size(ecsd_regs):
    """Read the boot area size from the default value."""
    (_, _, mult) = ecsd_regs['BOOT_SIZE_MULT']
    return mult * 128 * 1024

def get_user_area_size(ecsd_regs):
    """Read the user area size from the default value."""
    (_, _, secs) = ecsd_regs['SEC_COUNT']
    return secs * 512

def get_rpmb_area_size(ecsd_regs):
    """Read the rpmb area size from the default value."""
    (_, _, mult) = ecsd_regs['RPMB_SIZE_MULT']
    return mult * 128 * 1024

# CID register format:
# 'field name': (bit offset, bit size, value),
MTFCxxGAy_CID = {
    'MID': (120, 8, 0x13),  # Micron
    # Reserved 119:114
    'CBX': (112, 2, 0x01),
    'OID': (104, 8, None),
    'PNM': (56, 48, None),  # Size dependent
    'PRV': (48, 8, None),
    'PSN': (16, 32, None),
    'MDT': (8, 8, None),
    'CRC': (1, 7, None),
    # Bit 0 not used, always 1
}

# CSD register format:
# 'field name': (bit offset, bit size, value),
MTFCxxGAy_CSD = {
    'CSD_STRUCTURE': (126, 2, 0x3),
    'SPEC_VERS': (122, 4, 0x4),
    # Reserved 121:120
    'TAAC': (112, 8, 0x7F),
    'NSAC': (104, 8, 0x01),
    'TRAN_SPEED': (96, 8, 0x32),
    'CCC': (84, 12, 0x8F5),
    'READ_BL_LEN': (80, 4, 0x09),
    'READ_BL_PARTIAL': (79, 1, 0),
    'WRITE_BLK_MISALIGN': (78, 1, 0),
    'READ_BLK_MISALIGN': (77, 1, 0),
    'DSR_IMP': (76, 1, 0),
    # Reserved 75:74
    'C_SIZE': (62, 12, 0xFFF),
    'VDD_R_CURR_MIN': (59, 3, 0),
    'VDD_R_CURR_MAX': (56, 3, 0),
    'VDD_W_CURR_MIN': (53, 3, 0),
    'VDD_W_CURR_MAX': (50, 3, 0),
    'C_SIZE_MULT': (47, 3, 7),
    'ERASE_GRP_SIZE': (42, 5, 0x1F),
    'ERASE_GRP_MULT': (37, 5, 0x1F),
    'WP_GRP_SIZE': (32, 5, 0x0F),
    'WP_GRP_ENABLE': (31, 1, 1),
    'DEFAULT_ECC': (29, 2, 0),
    'R2W_FACTOR': (26, 3, 0x01),
    'WRITE_BL_LEN': (22, 4, 0x09),
    'WRITE_BL_PARTIAL': (21, 1, 0),
    # Reserved 20:17
    'CONTENT_PROT_APP': (16, 1, 0),
    'FILE_FORMAT_GRP': (15, 1, 0),
    'COPY': (14, 1, 0),
    'PERM_WRITE_PROTECT': (13, 1, 0),
    'TMP_WRITE_PROTECT': (12, 1, 0),
    'FILE_FORMAT': (10, 2, 0),
    'ECC': (8, 2, 0),
    'CRC': (1, 7, None),
    # Bit 0 not used, always 1
}

# ECSD register format:
# 'field name': (offset (in bytes), size (in bytes), value),
MTFCxxGAy_ECSD = {
    # Reserved 511:506
    'EXT_SECURITY_ERR': (505, 1, 0x00),
    'S_CMD_SET': (504, 1, 0x01),
    'HPI_FEATURES': (503, 1, 0x01),
    'BKOPS_SUPPORT': (502, 1, 0x01),
    'MAX_PACKED_READS': (501, 1, 0x00),
    'MAX_PACKED_WRITES': (500, 1, 0x00),
    'DATA_TAG_SUPPORT': (499, 1, 0x01),
    'TAG_UNIT_SIZE': (498, 1, 0x03),
    'TAG_RES_SIZE': (497, 1, 0x00),
    'CONTEXT_CAPABILITIES': (496, 1, 0x05),
    'LARGE_UNIT_SIZE_M1': (495, 1, 0x03),
    'EXT_SUPPORT': (494, 1, 0x03),
    'SUPPORTED_MODES': (493, 1, 0x01),
    'FFU_FEATURES': (492, 1, 0x00),
    'OPERATION_CODE_TIMEOUT': (491, 1, 0x00),
    'FFU_ARG': (487, 4, 0x0000FFFF),
    'BARRIER_SUPPORT': (486, 1, 0x01),
    # Reserved 485:309
    'CMDQ_SUPPORT': (308, 1, 0x01),
    'CMDQ_DEPTH': (307, 1, 0x1F),
    # Reserved 306
    'NUMBER_OF_FW_SECTORS_CORRECTLY_PROGRAMMED': (302, 4, 0x00),
    'VENDOR_PROPRIETARY_HEALTH_REPORT': (270, 32, 0x00),
    'DEVICE_LIFE_TIME_EST_TYP_B': (269, 1, 0x01),
    'DEVICE_LIFE_TIME_EST_TYP_A': (258, 1, 0x01),
    'PRE_EOL_INFO': (267, 1, 0x01),
    'OPTIMAL_READ_SIZE': (266, 1, 0x00),
    'OPTIMAL_WRITE_SIZE': (265, 1, 0x40),
    'OPTIMAL_TRIM_UNIT_SIZE': (264, 1, 0x00),
    'DEVICE_VERSION': (262, 2, 0x0000),
    'FIRMWARE_VERSION': (254, 8, None),
    'PWR_CL_DDR_200_360': (253, 1, 0x00),
    'CACHE_SIZE': (249, 4, None),  # Size dependent
    'GENERIC_CMD6_TIME': (248, 1, 0x0A),
    'POWER_OFF_LONG_TIME': (247, 1, 0x32),
    'BKOPS_STATUS': (246, 1, 0x00),
    'CORRECTLY_PROG_SECTORS_NUM': (242, 4, 0x00000000),
    'INI_TIMEOUT_AP': (241, 1, 0x0A),
    'CACHE_FLUSH_POLICY': (240, 1, 0x01),
    'PWR_CL_DDR_52_360': (239, 1, 0x00),
    'PWR_CL_DDR_52_195': (238, 1, 0x00),
    'PWR_CL_200_195': (237, 1, 0x00),
    'PWR_CL_200_130': (236, 1, 0x00),
    'MIN_PERF_DDR_W_8_52': (235, 1, 0x00),
    'MIN_PERF_DDR_R_8_52': (234, 1, 0x00),
    # Reserved 233
    'TRIM_MULT': (232, 1, 0x1),
    'SEC_FEATURE_SUPPORT': (231, 1, 0x51),
    'SEC_ERASE_MULT': (230, 1, 0x01),
    'SEC_TRIM_MULT': (229, 1, 0x01),
    'BOOT_INFO': (228, 1, 0x07),
    # Reserved 227
    'BOOT_SIZE_MULT': (226, 1, 0xFC),
    'ACC_SIZE': (225, 1, 0x00),
    'HC_ERASE_GP_SIZE': (224, 1, 0x01),
    'ERASE_TIMEOUT_MULT': (223, 1, 0x01),
    'REL_WR_SEC_C': (222, 1, 0x01),
    'HC_WP_GRP_SIZE': (221, 1, None),  # Size dependent
    'S_C_VCC': (220, 1, 0x00),
    'S_C_VCCQ': (219, 1, 0x00),
    'PRODUCTION_STATE_AWARENESS_TIMEOUT': (218, 1, 0x00),
    'S_A_TIMEOUT': (217, 1, 0x14),
    'SLEEP_NOTIFICATION_TIME': (216, 1, 0x0E),
    'SEC_COUNT': (212, 4, None),  # Size dependent
    'SECURE_WP_INFO': (211, 1, 0x01),
    'MIN_PERF_W_8_52': (210, 1, 0x00),
    'MIN_PERF_R_8_52': (209, 1, 0x00),
    'MIN_PERF_W_8_26_4_52': (208, 1, 0x00),
    'MIN_PERF_R_8_26_4_52': (207, 1, 0x00),
    'MIN_PERF_W_4_26': (206, 1, 0x00),
    'MIN_PERF_R_4_26': (205, 1, 0x00),
    # Reserved 204
    'PWR_CL_26_360': (203, 1, 0x00),
    'PWR_CL_52_360': (202, 1, 0x00),
    'PWR_CL_26_195': (201, 1, 0x00),
    'PWR_CL_52_195': (200, 1, 0x00),
    'PARTITION_SWITCH_TIME': (199, 1, 0x01),
    'OUT_OF_INTERRUPT_TIME': (198, 1, 0x0F),
    'DRIVER_STRENGTH': (197, 1, 0x1F),
    'DEVICE_TYPE': (196, 1, 0x57),
    # Reserved 195
    'CSD_STRUCTURE': (194, 1, 0x02),
    # Reserved 193
    'EXT_CSD_REV': (192, 1, 0x08),
    'CMD_SET': (191, 1, 0x00),
    # Reserved 190
    'CMD_SET_REV': (189, 1, 0x00),
    # Reserved 188
    'POWER_CLASS': (187, 1, 0x00),
    # Reserved 186
    'HS_TIMING': (185, 1, 0x00),
    'STROBE_SUPPORT': (184, 1, 0x00),
    'BUS_WIDTH': (183, 1, 0x00),
    # Reserved 182
    'ERASED_MEM_CONT': (181, 1, 0x00),
    # Reserved 180
    'PARTITION_CONFIG': (179, 1, 0x00),
    'BOOT_CONFIG_PROT': (178, 1, 0x00),
    'BOOT_BUS_CONDITIONS': (177, 1, 0x00),
    # Reserved 176
    'ERASE_GROUP_DEF': (175, 1, 0x00),
    'BOOT_WP_STATUS': (174, 1, 0x00),
    'BOOT_WP': (173, 1, 0x00),
    # Reserved 172
    'USER_WP': (171, 1, 0x00),
    # Reserved 170
    'FW_CONFIG': (169, 1, 0x00),
    'RPMB_SIZE_MULT': (168, 1, 0x20),
    'WR_REL_SET': (167, 1, 0x1F),
    'WR_REL_PARAM': (166, 1, 0x15),
    'SANITIZE_START': (165, 1, 0x00),
    'BKOPS_START': (164, 1, 0x00),
    'BKOPS_EN': (163, 1, 0x00),
    'RST_n_FUNCTION': (162, 1, 0x00),
    'HPI_MGMT': (161, 1, 0x00),
    'PARTITIONING_SUPPORT': (160, 1, 0x07),
    'MAX_ENH_SIZE_MULT': (157, 3, None),  # Size dependent
    'PARTITIONS_ATTRIBUTE': (156, 1, 0x00),
    'PARTITIONS_SETTING_COMPLETED': (155, 1, 0x00),
    'GP_SIZE_MULT': (143, 12, 0x00),
    'ENH_SIZE_MULT': (140, 3, 0x000000),
    'ENH_START_ADDR': (136, 4, 0x00000000),
    # Reserved 135
    'SEC_BAD_BLK_MGMNT': (134, 1, 0x00),
    'PRODUCTION_STATE_AWARENESS': (133, 1, 0x00),
    'TCASE_SUPPORT': (132, 1, 0x00),
    'PERIODIC_WAKEUP': (131, 1, 0x00),
    'PROGRAM_CID_CSD_DDR_SUPPORT': (130, 1, 0x01),
    # Reserved 129:128
    'VENDOR_SPECIFIC_FIELD': (64, 64, None),
    'NATIVE_SECTOR_SIZE': (63, 1, 0x00),
    'USE_NATIVE_SECTOR': (62, 1, 0x00),
    'DATA_SECTOR_SIZE': (61, 1, 0x00),
    'INI_TIMEOUT_EMU': (60, 1, 0x00),
    'CLASS_6_CTRL': (59, 1, 0x00),
    'DYNCAP_NEEDED': (58, 1, 0x00),
    'EXCEPTION_EVENTS_CTRL': (56, 2, 0x0000),
    'EXCEPTION_EVENTS_STATUS': (54, 2, 0x0000),
    'EXT_PARTITIONS_ATTRIBUTE': (52, 2, 0x0000),
    'CONTEXT_CONF': (37, 15, 0x00),
    'PACKED_COMMAND_STATUS': (36, 1, 0x00),
    'PACKED_FAILURE_INDEX': (35, 1, 0x00),
    'POWER_OFF_NOTIFICATION': (34, 1, 0x00),
    'CACHE_CTRL': (33, 1, 0x00),
    'FLUSH_CACHE': (32, 1, 0x00),
    'BARRIER_CTRL': (31, 1, 0x00),
    'MODE_CONFIG': (30, 1, 0x00),
    'MODE_OPERATION_CODES': (29, 1, 0x00),
    # Reserved 28:27
    'FFU_STATUS': (26, 1, 0x00),
    'PRE_LOADING_DATA_SIZE': (22, 4, 0x00),
    'MAX_PRE_LOADING_DATA_SIZE': (18, 4, None),  # Size dependent
    'PRODUCT_STATE_AWARENESS_ENABLEMENT': (17, 1, 0x03),
    'SECURE_REMOVAL_TYPE': (16, 1, 0x01),
    'CMDQ_MODE_EN': (15, 1, 0x00),
    # Reserved 14:0
}

def mtfcXXgaY_init_card(card, cid_regs, csd_regs, ecsd_regs):
    card.OCR = OCR().get()
    # CID Registers
    cid_data = [0] * 16
    for (o, s, v) in cid_regs.values():
        if v is not None:
            set_bits(cid_data, o, s, v)
    set_bits(cid_data, 0, 1, 1) # Bit 0 is always 1
    card.CID = tuple(cid_data)
    # CSD Registers
    csd_data = [0] * 16
    for (o, s, v) in csd_regs.values():
        if v is not None:
            set_bits(csd_data, o, s, v)
    set_bits(csd_data, 0, 1, 1) # Bit 0 is always 1
    card.CSD = tuple(csd_data)
    # ECSD Registers
    ecsd_data = [0] * 512
    for (o, s, v) in ecsd_regs.values():
        if v is not None:
            set_bytes(ecsd_data, o, s, v)
    card.ExtCSD = tuple(ecsd_data)

class mtfcXXgaY_base:
    """A generic Micron MTFCxxGAy eMMC Card."""
    _class_desc = 'eMMC card'

    def get_image_size(self):
        user_area = get_user_area_size(self.ECSD_REG)
        boot_area = get_boot_area_size(MTFCxxGAy_ECSD)
        rpmb_area = get_rpmb_area_size(MTFCxxGAy_ECSD)
        return user_area + boot_area + rpmb_area

    def add_objects(self):
        mmc_card_base.add_objects(self)

        if self.use_generic_sdmmc_card.val:
            card = self.add_pre_obj('card', 'mmc_card')
        else:
            card = self.add_pre_obj('card', 'generic-mmc-card')
            card.card_type = 0

        self.cid_regs = dict(MTFCxxGAy_CID, **self.CID_REG)
        self.csd_regs = dict(MTFCxxGAy_CSD)
        self.ecsd_regs = dict(MTFCxxGAy_ECSD, **self.ECSD_REG)
        mtfcXXgaY_init_card(
            card, self.cid_regs, self.csd_regs, self.ecsd_regs)

        card.flash_image = self.get_slot('image')
        card.size = self.get_image_size()

    def get_default_value(self, reg_name):
        val = None
        if reg_name in self.cid_regs:
            (_, _, val) = self.cid_regs[reg_name]
        if reg_name in self.csd_regs:
            (_, _, val) = self.csd_regs[reg_name]
        if reg_name in self.ecsd_regs:
            (_, _, val) = self.ecsd_regs[reg_name]
        return val

    def get_value(self, reg_name):
        if reg_name in self.cid_regs:
            (o, s, _) = self.cid_regs[reg_name]
            return get_bits(self.obj.card.CID, o, s)
        if reg_name in self.csd_regs:
            (o, s, _) = self.csd_regs[reg_name]
            return get_bits(self.obj.card.CSD, o, s)
        if reg_name in self.ecsd_regs:
            (o, s, _) = self.ecsd_regs[reg_name]
            return get_bytes(self.obj.card.ExtCSD, o, s)
        return None

class micron_mtfc8gam_emmc_card(mtfcXXgaY_base, mmc_card_base):
    """A Micron 8 GB MTFC8GAM eMMC Card."""
    _class_desc = 'eMMC card'

    CID_REG = {
        'PNM': (56, 48, 0x53304A333541),
    }
    ECSD_REG = {
        'CACHE_SIZE': (249, 4, 0x00000200),
        'HC_WP_GRP_SIZE': (221, 1, 0x10),
        'SEC_COUNT': (212, 4, 0x00E90000),
        'MAX_ENH_SIZE_MULT': (157, 3, 0x0001C9),
        'MAX_PRE_LOADING_DATA_SIZE': (18, 4, 0x005D3310),
    }

    class basename(StandardConnectorComponent.basename):
        val = 'micron_mtfc8gam_emmc'

class micron_mtfc16gap_emmc_card(mtfcXXgaY_base, mmc_card_base):
    """A Micron 16 GB MTFC16GAP eMMC Card."""
    _class_desc = 'eMMC card'

    CID_REG = {
        'PNM': (56, 48, 0x53304A353658),
    }
    ECSD_REG = {
        'CACHE_SIZE': (249, 4, 0x00000400),
        'HC_WP_GRP_SIZE': (221, 1, 0x10),
        'SEC_COUNT': (212, 4, 0x01DA4000),
        'MAX_ENH_SIZE_MULT': (157, 3, 0x0003AB),
        'MAX_PRE_LOADING_DATA_SIZE': (18, 4, 0x00BDB320),
    }

    class basename(StandardConnectorComponent.basename):
        val = 'micron_mtfc16gap_emmc'

class micron_mtfc32gap_emmc_card(mtfcXXgaY_base, mmc_card_base):
    """A Micron 32 GB MTFC32GAP eMMC Card."""
    _class_desc = 'eMMC card'

    CID_REG = {
        'PNM': (56, 48, 0x53304A353758),
    }
    ECSD_REG = {
        'CACHE_SIZE': (249, 4, 0x00000800),
        'HC_WP_GRP_SIZE': (221, 1, 0x10),
        'SEC_COUNT': (212, 4, 0x03B48000),
        'MAX_ENH_SIZE_MULT': (157, 3, 0x000760),
        'MAX_PRE_LOADING_DATA_SIZE': (18, 4, 0x017B6640),
    }

    class basename(StandardConnectorComponent.basename):
        val = 'micron_mtfc32gap_emmc'

class micron_mtfc64gap_emmc_card(mtfcXXgaY_base, mmc_card_base):
    """A Micron 64 GB MTFC64GAP eMMC Card."""
    _class_desc = 'eMMC card'

    CID_REG = {
        'PNM': (56, 48, 0x53304A353858),
    }
    ECSD_REG = {
        'CACHE_SIZE': (249, 4, 0x00000800),
        'HC_WP_GRP_SIZE': (221, 1, 0x20),
        'SEC_COUNT': (212, 4, 0x07690000),
        'MAX_ENH_SIZE_MULT': (157, 3, 0x000764),
        'MAX_PRE_LOADING_DATA_SIZE': (18, 4, 0x02F6CCA8),
    }

    class basename(StandardConnectorComponent.basename):
        val = 'micron_mtfc64gap_emmc'

class micron_mtfc128gap_emmc_card(mtfcXXgaY_base, mmc_card_base):
    """A Micron 128 GB MTFC128GAP eMMC Card."""
    _class_desc = 'eMMC card'

    CID_REG = {
        'PNM': (56, 48, 0x53304A353958),
    }
    ECSD_REG = {
        'CACHE_SIZE': (249, 4, 0x00000800),
        'HC_WP_GRP_SIZE': (221, 1, 0x40),
        'SEC_COUNT': (212, 4, 0x0ED20000),
        'MAX_ENH_SIZE_MULT': (157, 3, 0x000766),
        'MAX_PRE_LOADING_DATA_SIZE': (18, 4, 0x05ED9978),
    }

    class basename(StandardConnectorComponent.basename):
        val = 'micron_mtfc128gap_emmc'

class micron_mtfc64ggqdi_sdhc_card(mmc_card_base):
    """A SDHC card component similar to Micron MTFC64GGQDI-IT eMMC."""
    _class_desc = 'a SDHC card'

    class basename(StandardConnectorComponent.basename):
        val = 'micron_shdc'

    def get_image_size(self):
        return 0x1d00 << 23

    def add_objects(self):
        mmc_card_base.add_objects(self)

        csd = CSD_SDHC()
        ocr = OCR()
        cid = CID_SDHC()
        scr = SCR()

        csd.C_SIZE = (self.get_image_size() >> 23) - 1 # user area size of 64GB card
        csd.CCC = csd.CCC | 0x400                      # enable switching

        ocr.OCR_CSS = 0
        ocr.OCR_LOW_VOLTAGE = 0

        if self.use_generic_sdmmc_card.val:
            card = self.add_pre_obj('card', 'sd_card')
            card.sd_type = 0
        else:
            card = self.add_pre_obj('card', 'generic-mmc-card')
            card.card_type = 2
            card.CSD = csd.get()
            card.OCR = ocr.get()
            card.CID = cid.get()
            card.SCR = scr.get()

        card.flash_image = self.get_slot('image')
        card.size = (csd.C_SIZE + 1) * 512 * 1024 * 16
