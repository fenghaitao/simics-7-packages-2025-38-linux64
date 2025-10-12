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


# vtd_tb.py
# testbench of Intel(r) Virtualization Technology (Intel(r) VT) for \
# Directed I/O (Intel(r) VT-d)
# remapping hardware


import math

import simics
import conf
import dev_util
import pyobj
import stest

# SIMICS-21634
conf.sim.deprecation_level = 0


# Global switch to turn on/off the debugging information
PRINT_DEBUG_INFO        = True

class Bitfield_LE_Ex(dev_util.Bitfield_LE):
    def __init__(self, fields, ones=0):
        dev_util.Bitfield_LE.__init__(self, fields, ones)

    def value_ex(self, dict):
        value = 0
        for key in dict:
            (start, stop) = self.field_ranges[key]
            max = (1 << (stop + 1 - start)) - 1

            if not (0 <= dict[key] and dict[key] <= max):
                raise Exception(
                    "Value 0x%x is larger than maximum 0x%x for %s '%s'."
                    % (dict[key], max, 'bitfield', key))

            # Insert field into final value
            value |= dict[key] << start
        return value | self.ones

class VTdConst:
    _reg_space_size       = 0x1000  # 4KB register space
    _page_size            = 0x1000  # Standard 4KB page
    _root_entry_size      = 16
    _context_entry_size   = 16
    _interrupt_entry_size = 16
    _pte_size             = 8
    _inv_descriptor_size  = 16
    _fault_record_size    = 16

    _undef_reg_off        = 0xFFFF

    ver_bf = Bitfield_LE_Ex({
                'MAX'   : (7, 4),
                'MIN'   : (3, 0),
            })

    cap_bf = Bitfield_LE_Ex({
                'DRD'   : (55),     # DMA Read Draining
                'DWD'   : (54),     # DMA Write Draining
                'MAMV'  : (53, 48), # Maximum Address Mask Value
                'NFR'   : (47, 40), # Number of Fault-recording Registers
                'PSI'   : (39),     # Page Selective Invalidation
                'SPS'   : (37, 34), # Super-Page Support
                'FRO'   : (33, 24), # Fault-recording Register Offset
                'ISOCH' : (23),     # Isochrony
                'ZLR'   : (22),     # Zero Length Read
                'MGAW'  : (21, 16), # Maximum Guest Address Width
                'SAGAW' : (12, 8),  # Supported Adjusted Guest Address Width
                'CM'    : (7),      # Caching Mode
                'PHMR'  : (6),      # Protected High-Memory Region
                'PLMR'  : (5),      # Protected Low-Memory Region
                'RWBF'  : (4),      # Required Write-Buffer Flushing
                'AFL'   : (3),      # Advanced Fault Logging
                'ND'    : (2, 0),   # Number of Domains supported
            })

    ext_cap_bf = Bitfield_LE_Ex({
                'MHMV'  : (23, 20), # Maximum Handle Mask Value
                'IRO'   : (17, 8),  # IOTLB Register Offset
                'SC'    : (7),      # Snoop Control
                'PT'    : (6),      # Pass Through
                'CH'    : (5),      # Caching Hints
                'EIM'   : (4),      # Extended Interrupt Mode
                'IR'    : (3),      # Interrupt Remapping support
                'DI'    : (2),      # Device IOTLB support
                'QI'    : (1),      # Queued Invalidation support
                'C'     : (0),      # Coherency
            })

    gcmd_bf = Bitfield_LE_Ex({
                'TE'    : (31),     # Translation Enable
                'SRTP'  : (30),     # Set Root Table Pointer
                'SFL'   : (29),     # Set Fault Log
                'EAFL'  : (28),     # Enable Advanced Fault Logging
                'WBF'   : (27),     # Write Buffer Flush
                'QIE'   : (26),     # Queued Invalidation Enable
                'IRE'   : (25),     # Interrupt Remapping Enable
                'SIRTP' : (24),     # Set Interrupt Remapping Table Pointer
                'CFI'   : (23),     # Compatibility Format Interrupt
            })

    gsts_bf = Bitfield_LE_Ex({
                'TES'   : (31),     # Translation Enable Status
                'RTPS'  : (30),     # Root Table Pointer Status
                'FLS'   : (29),     # Fault Log Status
                'AFLS'  : (28),     # Advanced Fault Logging Status
                'WBFS'  : (27),     # Write Buffer Flush Status
                'QIES'  : (26),     # Queued Invalidation Enable Status
                'IRES'  : (25),     # Interrupt Remapping Enable Status
                'IRTPS' : (24),     # Interrupt Remapping Table Pointer Status
                'CFIS'  : (23),     # Compatibility Format Interrupt Status
            })

    rtaddr_bf = Bitfield_LE_Ex({
                'RTA'   : (63, 12), # Root Table Address
            })

    ccmd_bf = Bitfield_LE_Ex({
                'ICC'   : (63),     # Invalidate Context-Cache
                'CIRG'  : (62, 61), # Context Invalidation Request Granularity
                'CAIG'  : (60, 59), # Context Actual Invalidation Granularity
                'FM'    : (33, 32), # Function Mask
                'SID'   : (31, 16), # Source ID
                'DID'   : (15, 0),  # Domain ID
            })

    fsts_bf = Bitfield_LE_Ex({
                'FRI'   : (15, 8),  # Fault Record Index
                'ITE'   : (6),      # Invalidation Time-out Error
                'ICE'   : (5),      # Invalidation Completion Error
                'IQE'   : (4),      # Invalidation Queue Error
                'APF'   : (3),      # Advanced Pending Fault
                'AFO'   : (2),      # Advanced Fault Overflow
                'PPF'   : (1),      # Primary Pending Fault
                'PFO'   : (0),      # Fault Overview
            })

    fectl_bf = Bitfield_LE_Ex({
                'IM'    : (31),     # Interrupt Mask
                'IP'    : (30),     # Interrupt Pending
            })

    fedata_bf = Bitfield_LE_Ex({
                'EIMD'  : (31, 16), # Extended Interrupt Message Data
                'IMD'   : (15, 0),  # Interrupt Message Data
            })

    feaddr_bf = Bitfield_LE_Ex({
                'MA'    : (31, 2),  # Message Address
            })

    feuaddr_bf = Bitfield_LE_Ex({
                'MUA'   : (31, 0),  # Message Upper Address
            })

    aflog_bf = Bitfield_LE_Ex({
                'FLA'   : (63, 12), # Fault Log Address
                'FLS'   : (11, 9),  # Fault Log Size
            })

    pmen_bf = Bitfield_LE_Ex({
                'EPM'   : (31),     # Enable Protected Memory
                'PRS'   : (0),      # Protected Region Status
            })

    plmbase_bf = Bitfield_LE_Ex({
                'PLMB'  : (31, 0),  # Protected Low-Memory Base
            })

    plmlimit_bf = Bitfield_LE_Ex({
                'PLML'  : (31, 0),  # Protected Low-Memory Limit
            })

    phmbase_bf = Bitfield_LE_Ex({
                'PHMB'  : (63, 0),  # Protected High-Memory Base
            })

    phmlimit_bf = Bitfield_LE_Ex({
                'PHML'  : (63, 0),  # Protected High-Memory Limit
            })

    iqh_bf = Bitfield_LE_Ex({
                'QH'    : (18, 4),  # Queue Head
            })


    iqt_bf = Bitfield_LE_Ex({
                'QT'    : (18, 4),  # Queue Tail
            })

    iqa_bf = Bitfield_LE_Ex({
                'IQA'   : (63, 12), # Invalidation Queue Base
                'QS'    : (2, 0),   # Queue Size
            })

    ics_bf = Bitfield_LE_Ex({
                'IWC'   : (0),      # Invalidation Wait Descriptor
            })

    iectl_bf = Bitfield_LE_Ex({
                'IM'    : (31),     # Interrupt Mask
                'IP'    : (30),     # Interrupt Pending
            })

    iedata_bf = Bitfield_LE_Ex({
                'EIMD'  : (31, 16), # Extended Interrupt Message Data
                'IMD'   : (15, 0),  # Interrupt Message Data
            })

    ieaddr_bf = Bitfield_LE_Ex({
                'MA'    : (31, 2),  # Message Address
            })

    ieuaddr_bf = Bitfield_LE_Ex({
                'MUA'   : (31, 0),  # Message Upper Address
            })

    irta_bf = Bitfield_LE_Ex({
                'IRTA'  : (63, 12), # Interrupt Remapping Table Address
                'EIME'  : (11),     # Extended Interrupt Mode Enable
                'S'     : (3, 0),   # Size
            })

    iotlb_bf = Bitfield_LE_Ex({
                'IVT'   : (63),     # Invalidate IOTLB
                'IIRG'  : (61, 60), # IOTLB Invalidation Request Granularity
                'IAIG'  : (58, 57), # IOTLB Actual Invalidation Granularity
                'DR'    : (49),     # Drain Reads
                'DW'    : (48),     # Drain Writes
                'DID'   : (47, 32), # Domain -ID
            })

    iva_bf = Bitfield_LE_Ex({
                'ADDR'  : (63, 12), # Address
                'IH'    : (6),      # Invalidation Hint
                'AM'    : (5, 0),   # Address Mask
            })

    frcd_bf = Bitfield_LE_Ex({
                'F'     : (127),        # Fault
                'T'     : (126),        # Type
                'AT'    : (125, 124),   # Address Type
                'FR'    : (103, 96),    # Fault Reason
                'SID'   : (79, 64),     # Source Identifier
                'FI'    : (63, 12),     # Fault Info
            })

    class RegInfoSt:
        def __init__(self, _offset, _size, _def_val, _bitfield_obj):
            self.offset         = _offset
            self.size           = _size
            self.def_val        = _def_val
            self.bitfield_obj   = _bitfield_obj

    reg_info = {
            'VER'   : RegInfoSt(0x000, 4, 0x00, ver_bf), # Version
            'CAP'   : RegInfoSt(0x008, 8, 0x0, cap_bf), # Capability
            'ECAP'  : RegInfoSt(0x010, 8, 0x0, ext_cap_bf), # Extended Capability
            'GCMD'  : RegInfoSt(0x018, 4, 0x0, gcmd_bf), # Global Command
            'GSTS'  : RegInfoSt(0x01C, 4, 0x0, gsts_bf), # Global Status
            'RTADDR': RegInfoSt(0x020, 8, 0x0, rtaddr_bf), # Root-Entry Table Address
            'CCMD'  : RegInfoSt(0x028, 8, 0x0, ccmd_bf), # Context Command
            'FSTS'  : RegInfoSt(0x034, 4, 0x0, fsts_bf), # Fault Status
            'FECTL' : RegInfoSt(0x038, 4, 0x80000000, fectl_bf), # Fault Event Control
            'FEDATA': RegInfoSt(0x03C, 4, 0x0, fedata_bf), # Fault Event Data
            'FEADDR': RegInfoSt(0x040, 4, 0x0, feaddr_bf), # Fault Event Address
            'FEUADDR':RegInfoSt(0x044, 4, 0x0, feuaddr_bf), # Fault Event Upper Address
            'AFLOG' : RegInfoSt(0x058, 8, 0x0, aflog_bf), # Advanced Fault Log
            'PMEN'  : RegInfoSt(0x064, 4, 0x0, pmen_bf), # Protected Memory Enable
            'PLMBASE':RegInfoSt(0x068, 4, 0x0, plmbase_bf), # Protected Low-Memory Base
            'PLMLIMIT':RegInfoSt(0x06C,4, 0x0, plmlimit_bf), # Protected Low-Memory Limit
            'PHMBASE':RegInfoSt(0x070, 8, 0x0, phmbase_bf), # Protected High-Memory Base
            'PHMLIMIT':RegInfoSt(0x078,8, 0x0, phmlimit_bf), # Protected High-Memory Limit
            'IQH'   : RegInfoSt(0x080, 8, 0x0, iqh_bf), # Invalidation Queue Head
            'IQT'   : RegInfoSt(0x088, 8, 0x0, iqt_bf), # Invalidation Queue Tail
            'IQA'   : RegInfoSt(0x090, 8, 0x0, iqa_bf), # Invalidation Queue Address
            'ICS'   : RegInfoSt(0x09C, 4, 0x0, ics_bf), # Invalidation Completion Status
            'IECTL' : RegInfoSt(0x0A0, 4, 0x80000000, iectl_bf), # Invalidation Event Control
            'IEDATA': RegInfoSt(0x0A4, 4, 0x0, iedata_bf), # Invalidation Event Data Control
            'IEADDR': RegInfoSt(0x0A8, 4, 0x0, ieaddr_bf), # Invalidation Event Address
            'IEUADDR':RegInfoSt(0x0AC, 4, 0x0, ieuaddr_bf), # Invalidation Event Upper Address
            'IRTA'  : RegInfoSt(0x0B8, 8, 0x0, irta_bf), # Interrupt Remapping Table Address

            # Undefined address registers
            'IOTLB' : RegInfoSt(_undef_reg_off, 8, 0x0, iotlb_bf),
            'IVA'   : RegInfoSt(_undef_reg_off, 8, 0, iva_bf),
            'FRCD'  : RegInfoSt(_undef_reg_off, 16, 0, frcd_bf),
    }

    fr_no_fault                 = 0

    # DMA remapping fault reasons
    fr_no_present_root_entry    = 1
    fr_no_present_context_entry = 2
    fr_invalid_context_entry    = 3
    fr_out_of_guest_memory      = 4
    fr_write_a_read_pte         = 5
    fr_read_a_not_read_pte      = 6
    fr_non_existing_pt_addr     = 7 # pt -- Page table address
    fr_non_existing_rt_addr     = 8 # rt -- root table address
    fr_non_existing_ctp_addr    = 9 # ctp-- context-table pointer
    fr_non_zero_rsvd_re         = 0xA # re -- root entry
    fr_non_zero_rsvd_ce         = 0xB # ce  -- context entry
    fr_non_zero_rsvd_pte        = 0xC # pte -- page table entry
    fr_dma_blocked_for_tt       = 0xD # tt  -- translation type

    # Interrupt remapping fault reasons
    fr_set_rsvd_in_int_req     = 0x20 # int req -- interrupt request
    fr_too_large_int_index     = 0x21
    fr_no_present_irte         = 0x22 # irte -- interrupt remapping table entry
    fr_non_existing_irta       = 0x23 # irta -- interrupt remapping table address
    fr_non_zero_rsvd_irte      = 0x24
    fr_int_blocked_for_mode    = 0x25
    fr_int_blocked_for_veri_f  = 0x26 # veri f -- verification failure

    fault_reason_list = [
        fr_no_present_root_entry,
        fr_no_present_context_entry,
        fr_invalid_context_entry,
        fr_out_of_guest_memory,
        fr_write_a_read_pte,
        fr_read_a_not_read_pte,
        fr_non_existing_pt_addr,
        fr_non_existing_rt_addr,
        fr_non_existing_ctp_addr,
        fr_non_zero_rsvd_re,
        fr_non_zero_rsvd_ce,
        fr_non_zero_rsvd_pte,
        fr_dma_blocked_for_tt,

        fr_set_rsvd_in_int_req,
        fr_too_large_int_index,
        fr_no_present_irte,
        fr_non_existing_irta,
        fr_non_zero_rsvd_irte,
        fr_int_blocked_for_mode,
        fr_int_blocked_for_veri_f,
    ]

    # Memory-resident data structure bitfields
    # Root-entry
    re_bf = Bitfield_LE_Ex({
                    'RSVD'  : (127, 64),
                    'CTP'   : (63, 12), # Context-entry Table Pointer
                    'P'     : (0),      # Present
                })

    # Context-entry
    ce_bf = Bitfield_LE_Ex({
                    'DID'   : (87, 72), # Domain Identifier
                    'AVAIL' : (70, 67), # Available
                    'AW'    : (66, 64), # Address Width
                    'ASR'   : (63, 12), # Address Space Root
                    'ALH'   : (5),      # Address Locality Hint
                    'EH'    : (4),      # Eviction Hint
                    'T'     : (3, 2),   # Translation Type
                    'FPD'   : (1),      # Fault Processing Disable
                    'P'     : (0),      # Present
                })

    # Page-table entry
    pte_bf = Bitfield_LE_Ex({
                    'AVAIL' : (63),     # Available
                    'TM'    : (62),     # Transient Mapping
                    'AVAIL2': (61, 52), # Available 2
                    'ADDR'  : (51, 12), # Address
                    'SNP'   : (11),     # Snoop Behavior
                    'AVAIL3': (10, 8),  # Available 3
                    'SP'    : (7),      # Super Page
                    'AVAIL4': (6, 2),   # Available 4
                    'W'     : (1),      # Write
                    'R'     : (0),      # Read
                })

    # Interrupt remapping table entry
    irte_bf = Bitfield_LE_Ex({
                    'SVT'   : (83, 82), # Source Validation Type
                    'SQ'    : (81, 80), # Source-id Qualifier
                    'SID'   : (79, 64), # Source Identifier
                    'DST'   : (63, 32), # Destination ID
                    'V'     : (23, 16), # Vector
                    'AVAIL' : (11, 8),  # Available
                    'DLM'   : (7, 5),   # Delivery Mode
                    'TM'    : (4),      # Trigger Mode
                    'RH'    : (3),      # Redirection Hint
                    'DM'    : (2),      # Destination Mode
                    'FPD'   : (1),      # Fault Processing Disable
                    'P'     : (0),      # Present
                })

    # Fault record
    fr_bf = Bitfield_LE_Ex({
                    'T'     : (126),    # Type
                    'AT'    : (125, 124), # Address Type
                    'FR'    : (103, 96),  # Fault Reason
                    'SID'   : (79, 64),   # Source Identifier
                    'FI'    : (63, 12),   # Fault Information
                })

    # Compatibility format interrupt request
    compat_int_msg_addr_bf = Bitfield_LE_Ex({
                    'FEE'   : (31, 20), # 0xFEEh
                    'DID'   : (19, 12), # Destination ID
                    'IF'    : (4),      # Interrupt Format (0)
                    'RH'    : (3),      # Redirection Hint
                    'DM'    : (2),      # Destination Mode
                })

    compat_int_msg_data_bf = Bitfield_LE_Ex({
                    'TM'    : (15),     # Trigger Mode
                    'TML'   : (14),     # Trigger Mode Level
                    'DM'    : (10, 8),  # Delivery Mode
                    'V'     : (7, 0),   # Vector
                })

    # Remappable format interrupt request
    remappable_int_msg_addr_bf = Bitfield_LE_Ex({
                    'FEE'   : (31, 20), # 0xFEEh
                    'IH'    : (19, 4),  # Interrupt Handle
                    'SHV'   : (3),      # SubHandle Valid
                })

    # Remappable format interrupt request, VT-d spec
    remappable_int_msg_addr_bf_vtd = Bitfield_LE_Ex({
                    'FEE'   : (31, 20), # 0xFEEh
                    'IH'    : (19, 5),  # Interrupt Handle
                    'IH2'   : (2),      # Interrupt Handle, MSB
                    'SHV'   : (3),      # SubHandle Valid
                })

    remappable_int_msg_data_bf = Bitfield_LE_Ex({
                    'SH'    : (15, 0),  # SubHandle
                })

    # Context cache invalidate descriptor
    cc_inv_desc_bf = Bitfield_LE_Ex({
                    'RSVD'  : (127, 64),
                    'FM'    : (49, 48), # Function Mask
                    'SID'   : (47, 32), # Source ID
                    'DID'   : (31, 16), # Domain ID
                    'G'     : (5, 4),   # Granularity
                    'T'     : (3, 0),   # Type, cc_inv -- 01
                })

    # IOTLB invalidate descriptor
    iotlb_inv_desc_bf = Bitfield_LE_Ex({
                    'ADDR'  : (127, 76),    # Address[63:12]
                    'IH'    : (70),         # Invalidate Hint
                    'AM'    : (69, 46),     # Address Mask
                    'DID'   : (31, 16),     # Domain ID
                    'DR'    : (7),          # Drain Read
                    'DW'    : (6),          # Drain Write
                    'G'     : (5, 4),       # Granularity
                    'T'     : (3, 0),       # Type, iotlb_inv -- 02
                })

    # Device-IOTLB invalidate descriptor
    dev_iotlb_inv_desc_bf = Bitfield_LE_Ex({
                    'ADDR'  : (127, 76),    # Address[63:12]
                    'S'     : (64),         # Size
                    'SID'   : (47, 32),     # Source-ID
                    'MIP'   : (20, 16),     # Max Invalidations Pending
                    'T'     : (3, 0),       # Type, dev_iotlb_inv -- 03
                })

    # Interrupt entry cache invalidate descriptor
    iec_inv_desc_bf = Bitfield_LE_Ex({
                    'RSVD'  : (127, 48),
                    'IIDX'  : (47, 32),     # Interrupt Index
                    'IM'    : (31, 27),     # Interrupt Mask
                    'G'     : (4),          # Granularity
                    'T'     : (3, 0),       # Type, iec_inv -- 04
                })

    # Invalidation Wait Descriptor
    inv_wait_desc_bf = Bitfield_LE_Ex({
                    'SA'    : (127, 66),    # Status Address[63:2]
                    'SD'    : (63, 32),     # Status Data
                    'FN'    : (6),          # Fence Flag
                    'SW'    : (5),          # Status Write
                    'IF'    : (4),          # Interrupt Flag
                    'T'     : (3, 0),       # Type, wait_inv -- 5
                })

    # Some constant bitfield values
    inv_granularity_global  = 1
    inv_granularity_domain  = 2
    inv_granularity_device  = 3
    inv_granularity_page    = 3

    # Delivery mode in the interrupt remapping table entry
    irte_dlm_fixed       = 0
    irte_dlm_lowest_prior= 1
    irte_dlm_smi         = 2
    irte_dlm_nmi         = 4
    irte_dlm_init        = 5
    irte_dlm_ext_int     = 7

    # Trigger mode in the interrupt remapping table entry
    irte_tm_edge         = 0
    irte_tm_level        = 1

    # Destination mode in the interrupt remapping table entry
    irte_dm_physical     = 0
    irte_dm_logical      = 1

    # Invalidate descriptor type
    inv_desc_context     = 1
    inv_desc_iotlb       = 2
    inv_desc_dev_iotlb   = 3
    inv_desc_int_entry   = 4
    inv_desc_wait        = 5

class X58VTdConst:
    _cap_def_val = VTdConst.cap_bf.value(
                            DRD     = 0,
                            DWD     = 1,
                            MAMV    = 9,
                            NFR     = 8,
                            PSI     = 1,
                            SPS     = 0,
                            FRO     = 0x10,
                            ISOCH   = 0,
                            ZLR     = 0,
                            MGAW    = 0x2F,
                            SAGAW   = 0x4,
                            CM      = 0,
                            PHMR    = 1,
                            PLMR    = 1,
                            RWBF    = 0,
                            ND      = 2,
                        )

    _ecap_def_val = VTdConst.ext_cap_bf.value(
                            MHMV    = 0xF,
                            IRO     = 0x20,
                            SC      = 1,
                            PT      = 1,
                            CH      = 1,
                            IR      = 1,
                            DI      = 1,
                            QI      = 1,
                            C       = 0,
                        )

    _customized_reg_info = {
            'CAP'   : VTdConst.RegInfoSt(0x008, 8, _cap_def_val, VTdConst.cap_bf),
            'ECAP'  : VTdConst.RegInfoSt(0x010, 8, _ecap_def_val, VTdConst.ext_cap_bf),
            'CCMD'  : VTdConst.RegInfoSt(0x028, 8, 0, VTdConst.ccmd_bf),
            'IOTLB' : VTdConst.RegInfoSt(0x200, 8, 0,VTdConst.iotlb_bf),
        }

def offset_of(reg_name):
    if list(X58VTdConst._customized_reg_info.keys()).__contains__(reg_name):
        return X58VTdConst._customized_reg_info[reg_name].offset
    elif list(VTdConst.reg_info.keys()).__contains__(reg_name):
        return VTdConst.reg_info[reg_name].offset
    else:
        raise Exception(
            "unknown register name '%s' to retrieve its offset" % reg_name)

def size_of(reg_name):
    if list(X58VTdConst._customized_reg_info.keys()).__contains__(reg_name):
        return X58VTdConst._customized_reg_info[reg_name].size
    elif list(VTdConst.reg_info.keys()).__contains__(reg_name):
        return VTdConst.reg_info[reg_name].size
    elif reg_name.startswith("FRCD"):
        return VTdConst.reg_info["FRCD"].size
    else:
        raise Exception(
            "unknown register name '%s' to retrieve its size" % reg_name)

def default_of(reg_name):
    if list(X58VTdConst._customized_reg_info.keys()).__contains__(reg_name):
        return X58VTdConst._customized_reg_info[reg_name].def_val
    elif list(VTdConst.reg_info.keys()).__contains__(reg_name):
        return VTdConst.reg_info[reg_name].def_val
    else:
        raise Exception("unknown register name '%s' to retrieve "
                        "its default value" % reg_name)

def bitfield_of(reg_name):
    if list(X58VTdConst._customized_reg_info.keys()).__contains__(reg_name):
        return X58VTdConst._customized_reg_info[reg_name].bitfield_obj
    elif list(VTdConst.reg_info.keys()).__contains__(reg_name):
        return VTdConst.reg_info[reg_name].bitfield_obj
    else:
        raise Exception("unknown register name '%s' to retrieve "
                        "its bitfield definition object" % reg_name)

def count_left_1(val, bits = 32):
    cnt = 0
    mask = 1 << (bits - 1)
    while val:
        if (val & mask) == 0:
            break
        cnt += 1
        val <<= 1
    return cnt

def count_left_0(val, bits = 32):
    cnt = 0
    mask = 1 << (bits - 1)
    while val:
        if (val & mask) != 0:
            break
        cnt += 1
        val <<= 1
    return cnt

# Align address 'a' to be on a boundary of b bytes
def align_to(a, b):
    bound_bit = 32 - count_left_0(b)
    stest.expect_true(bound_bit < 31,
        "the boundary of 0x%x-bytes to be aligned to is meaningless" % b)
    masked_bits = (1 << bound_bit) - 1
    return (a + masked_bits) & ~masked_bits

# A simple memory space driver
class MemorySpaceDriver:
    _simics_mem_block_len = 1024

    def __init__(self, mem_space):
        self.mem_iface = mem_space.iface.memory_space

    def read_mem(self, addr, size):
        rem_len   = size
        read_addr = addr
        data_tuple = ()
        while rem_len > 0:
            to_read = min(rem_len, MemorySpaceDriver._simics_mem_block_len)
            data_tuple += self.mem_iface.read(None, read_addr, to_read, 0)
            rem_len    -= to_read
            read_addr  += to_read
        return data_tuple

    def write_mem(self, addr, bytes):
        return self.mem_iface.write(None, addr, bytes, 0)

    def read_value_le(self, addr, size):
        return dev_util.tuple_to_value_le(self.read_mem(addr, size))

    def write_value_le(self, addr, size, value):
        self.write_mem(addr, dev_util.value_to_tuple_le(value, size))

    def read_value_be(self, addr, size):
        return dev_util.tuple_to_value_be(self.read_mem(addr, size))

    def write_value_be(self, addr, size, value):
        self.write_mem(addr, dev_util.value_to_tuple_be(value, size))

# A simple VTd hardware driver
class VTdHwDriver:
    _dma_read  = 0
    _dma_write = 1

    def __init__(self, vtd_hw, vtd_hw_bank_base, mem_space_drv):
        self.vtd_hw = vtd_hw
        self.mem_space_drv = mem_space_drv
        self.vtd_hw_bank_base = vtd_hw_bank_base

    def read_reg(self, reg_name):
        return self.mem_space_drv.read_value_le(
                self.get_reg_addr(reg_name), size_of(reg_name))

    def write_reg(self, reg_name, value):
        return self.mem_space_drv.write_value_le(
                self.get_reg_addr(reg_name), size_of(reg_name), value)

    # Get the offset of invalidate address register
    def get_inv_addr_reg_off(self):
        fields = VTdConst.ext_cap_bf.fields(self.read_reg("ECAP"))
        if PRINT_DEBUG_INFO:
            print("Invalidate address register offset is 0x%x" \
                  % (fields['IRO'] << 4))
        return fields['IRO'] << 4

    def get_frcd_reg_off(self, index):
        fields = VTdConst.cap_bf.fields(self.read_reg("CAP"))
        if index >= fields['NFR']:
            if PRINT_DEBUG_INFO:
                print("number of fault-recording registers is %d" \
                      % fields['NFR'])
            index = fields['NFR'] - 1
        if PRINT_DEBUG_INFO:
            print("Fault recording register %d offset is 0x%x" \
                  % (index, (fields['FRO'] + index) << 4))
        return (fields['FRO'] + index) << 4

    def get_reg_addr(self, reg_name):
        if reg_name == "IVA" or reg_name == "IOTLB":
            off = self.get_inv_addr_reg_off()
            if reg_name == "IOTLB":
                off += 8
        elif reg_name.startswith("FRCD"):
            if reg_name == "FRCD":
                index = 0
            else:
                index = int(reg_name.replace("FRCD", ""))
            off = self.get_frcd_reg_off(index)
        else:
            off = offset_of(reg_name)
        return self.vtd_hw_bank_base + off

    def reset_vtd_hw(self):
        self.vtd_hw.ports.HRESET.signal.signal_raise()

    def get_page_table_levels(self, guest_addr_width):
        if guest_addr_width <= 30:
            levels = 2
        elif guest_addr_width <= 39:
            levels = 3
        elif guest_addr_width <= 48:
            levels = 4
        elif guest_addr_width <= 57:
            levels = 5
        elif guest_addr_width <= 64:
            levels = 6
        else:
            raise Exception("guest address width %d is too large"
                            % guest_addr_width)
        return levels

    def get_page_table_size(self, guest_addr_width, guest_space_size):
        levels = self.get_page_table_levels(guest_addr_width)
        # Give a maximum page table size for a 2GB space
        stest.expect_true(guest_space_size < 0x80000000,
            "get_page_table_size() only know how to compute the size "
            "of a space less than 2GB")
        return (1024 + 2 + levels) * 4096

    def has_capability(self, cap_name):
        cap_fields = VTdConst.cap_bf.fields(self.read_reg("CAP"))
        ecap_fields = VTdConst.ext_cap_bf.fields(self.read_reg("ECAP"))
        if cap_name in ['AFL', 'PLMR', 'PHMR', 'PSI']:
            return cap_fields[cap_name] == 1
        elif cap_name in ['QI', 'IR', 'DI', 'IRO', 'PT']:
            return ecap_fields[cap_name] == 1
        elif cap_name in ['SPS']:
            return cap_fields['SPS'] != 0
        else:
            raise Exception(
                "This capability name '%s' is not implemented now" % cap_name)

    def supported_page_table_levels(self):
        cap_fields = VTdConst.cap_bf.fields(self.read_reg("CAP"))
        levels = []
        bits_val = cap_fields['SAGAW']
        for i in range(5):
            if bits_val & 0x1:
                levels.append(i + 2)
            bits_val = bits_val >> 1
        return levels

    def supported_guest_address_widths(self):
        widths = []
        levels = self.supported_page_table_levels()
        for l in levels:
            widths.append((30, 39, 48, 57, 64)[l - 2])
        return widths

    def enable_dma_remapping(self, to_enable):
        bit_val = (0, 1)[to_enable != 0]
        fields = VTdConst.gcmd_bf.fields(self.read_reg("GSTS"))
        fields['TE'] = bit_val
        # Clear all bits to SET a pointer once
        fields['SFL'] = 0
        fields['SRTP'] = 0
        fields['SIRTP'] = 0
        self.write_reg("GCMD", VTdConst.gcmd_bf.value_ex(fields))

        # Verify the TES bit in the global status register
        fields = VTdConst.gsts_bf.fields(self.read_reg("GSTS"))
        stest.expect_true(fields['TES'] == bit_val,
            "GSTS.TES should be %d after writing %d to GCMD.TE"
            % (bit_val, bit_val))

    def enable_int_remapping(self, to_enable):
        if not self.has_capability('IR'):
            if PRINT_DEBUG_INFO and to_enable != 0:
                print("Cannot enable the interrupt remapping" \
                      "for it's not supported")
            return

        bit_val = (0, 1)[to_enable != 0]
        fields = VTdConst.gcmd_bf.fields(self.read_reg("GSTS"))
        fields['IRE'] = bit_val
        # Clear all bits to SET a pointer once
        fields['SFL'] = 0
        fields['SRTP'] = 0
        fields['SIRTP'] = 0
        self.write_reg("GCMD", VTdConst.gcmd_bf.value_ex(fields))

        # Verify the IRES bit in the global status register
        fields = VTdConst.gsts_bf.fields(self.read_reg("GSTS"))
        stest.expect_true(fields['IRES'] == bit_val,
            "GSTS.IRES should be %d after writing %d to GCMD.IRE"
            % (bit_val, bit_val))

    # Enable or disable the queued invalidation
    def enable_inv_queue(self, to_enable):
        if not self.has_capability('QI'):
            if PRINT_DEBUG_INFO and to_enable != 0:
                print("Cannot enable the invalidation queue" \
                      "for it's not supported")
            return

        bit_val = (0, 1)[to_enable != 0]
        fields = VTdConst.gcmd_bf.fields(self.read_reg("GSTS"))
        fields['QIE'] = bit_val
        # Clear all bits to SET a pointer once
        fields['SFL'] = 0
        fields['SRTP'] = 0
        fields['SIRTP'] = 0
        self.write_reg("GCMD", VTdConst.gcmd_bf.value_ex(fields))

        # Verify the QIES bit in the global status register
        fields = VTdConst.gsts_bf.fields(self.read_reg("GSTS"))
        stest.expect_true(fields['QIES'] == bit_val,
            "GSTS.QIES should be %d after writing %d to GCMD.QIE"
            % (bit_val, bit_val))

        # Clear the queue to 0 if it's to disable the queue
        if to_enable == 0:
            self.write_reg("IQT", 0)
            qh = self.read_reg("IQH")
            stest.expect_true(qh == 0,
                "Hardware should reset queue head to 0 whenever the "
                "queued invalidation is disabled "
                "(refer Intel (r) VT-d spec, page 139)")

    def enable_advanced_fault_log(self, to_enable):
        if not self.has_capability('AFL'):
            if PRINT_DEBUG_INFO and to_enable != 0:
                print("Cannot enable advanced fault logging " \
                      "for it's not supported")
            return

        bit_val = (0, 1)[to_enable != 0]
        fields = VTdConst.gcmd_bf.fields(self.read_reg("GSTS"))
        fields['EAFL'] = bit_val
        # Clear all bits to SET a pointer once
        fields['SFL'] = 0
        fields['SRTP'] = 0
        fields['SIRTP'] = 0
        self.write_reg("GCMD", VTdConst.gcmd_bf.value_ex(fields))

        # Verify the QIES bit in the global status register
        fields = VTdConst.gsts_bf.fields(self.read_reg("GSTS"))
        stest.expect_true(fields['AFLS'] == bit_val,
            "GSTS.AFLS should be %d after writing %d to GCMD.EAFL"
            % (bit_val, bit_val))

    def enable_protected_memory(self, to_enable):
        if ((not self.has_capability('PLMR'))
            and (not self.has_capability('PHMR'))):
            if PRINT_DEBUG_INFO and to_enable != 0:
                print("Cannot enable protected memory region" \
                      "for both high and low are not supported")
            return

        bit_val = (0, 1)[to_enable != 0]
        fields = VTdConst.pmen_bf.fields(self.read_reg("PMEN"))
        fields['EPM'] = bit_val
        self.write_reg("PMEN", VTdConst.pmen_bf.value_ex(fields))

        fields = VTdConst.pmen_bf.fields(self.read_reg("PMEN"))
        stest.expect_true(fields['PRS'] == bit_val,
            "PMEN.PRS should be %d after writing %d to PMEN.EPM"
            % (bit_val, bit_val))

    def enable_fault_event_int(self, to_enable):
        fields = VTdConst.fectl_bf.fields(self.read_reg("FECTL"))
        fields['IM'] = (1, 0)[to_enable != 0] # IM: 1 - to mask, 0 - to enable
        self.write_reg("FECTL", VTdConst.fectl_bf.value_ex(fields))

    # Configure the root-entry table address
    def config_rt_addr(self, rt_addr):
        val = VTdConst.rtaddr_bf.value(RTA = rt_addr >> 12)
        self.write_reg("RTADDR", val)
        fields = VTdConst.gcmd_bf.fields(self.read_reg("GSTS"))
        fields['SRTP'] = 1
        # Clear all other bits to SET a pointer once
        fields['SFL'] = 0
        fields['SIRTP'] = 0
        self.write_reg("GCMD", VTdConst.gcmd_bf.value_ex(fields))

        # Verify the RTPS status bit is set
        fields = VTdConst.gsts_bf.fields(self.read_reg("GSTS"))
        stest.expect_true(fields['RTPS'] == 1,
            "GSTS.RTPS should be set after writing 1 to GCMD.SRTP")

        # Verify the RTADDR is programmed to this address
        fields = VTdConst.rtaddr_bf.fields(self.read_reg("RTADDR"))
        stest.expect_true(fields['RTA'] == (rt_addr >> 12),
            "RTADDR should be read out a new address 0x%x after set" % rt_addr)

        # Globally invalidate the context-cache
        self.inv_context_cache(VTdConst.inv_granularity_global)

        # Globally invalidate the IOTLB
        self.inv_iotlb_cache(VTdConst.inv_granularity_global)

    # Configure the interrupt remapping table address
    def config_irt_addr(self, irt_addr, irte_cnt, extended_int_mode = 0):
        if not self.has_capability('IR'):
            if PRINT_DEBUG_INFO:
                print("Cannot configure the interrupt remapping table " \
                      "address for the interrupt remapping is not supported")
            return

        val = VTdConst.irta_bf.value(IRTA = irt_addr >> 12,
                                     EIME = extended_int_mode,
                                     S = irte_cnt.bit_length() - 1)
        self.write_reg("IRTA", val)

        fields = VTdConst.gcmd_bf.fields(self.read_reg("GSTS"))
        fields['SIRTP'] = 1
        # Clear all other bits to SET a pointer once
        fields['SFL'] = 0
        fields['SRTP'] = 0
        self.write_reg("GCMD", VTdConst.gcmd_bf.value_ex(fields))

        # Verify the IRTPS status bit is set
        fields = VTdConst.gsts_bf.fields(self.read_reg("GSTS"))
        stest.expect_true(fields['IRTPS'] == 1,
            "GSTS.IRTPS should be set after writing 1 to GCMD.SIRTP")

        # Verify the RTADDR is programmed to this address
        fields = VTdConst.irta_bf.fields(self.read_reg("IRTA"))
        stest.expect_true(fields['IRTA'] == (irt_addr >> 12),
            "IRTA should be read out a new address 0x%x after set" % irt_addr)

        # Globally invalidate the interrupt entry cache if existing
        self.inv_int_entry_cache(VTdConst.inv_granularity_global)

    # Configure base address and size of the invalidation queue
    def config_inv_queue(self, qbase, qsize):
        pages = qsize * VTdConst._inv_descriptor_size // VTdConst._page_size
        val = VTdConst.iqa_bf.value(IQA = qbase >> 12,
                                    QS = pages.bit_length() - 1)
        self.write_reg("IQA", val)

    def config_advanced_fault_log(self, log_base, log_size):
        if self.has_capability('AFL'):
            val = VTdConst.aflog_bf.value(
                        FLA = log_base >> 12,
                        FLS = int(math.log(log_size // VTdConst._page_size, 2)),
                    )
            self.write_reg("AFLOG", val)
        else:
            if PRINT_DEBUG_INFO:
                print("Advanced fault logging is not supported " \
                      "on this Intel (r) VT-d implementation")

    def config_protected_memory(self, low_base, low_len, high_base, high_len):
        # Determine the number of reserved bits in the protected memory regs
        if self.has_capability('PLMR'):
            self.write_reg("PLMBASE", (1 << 32) - 1)
            min_size = 1 << (32 - count_left_1(self.read_reg("PLMBASE")))
            # Lower bits of low base must be 0
            stest.expect_true((low_base & (min_size - 1)) == 0,
                "base address 0x%x of low protected memory region "
                "should be aligned to 0x%x boundary" % (low_base, min_size))
            self.write_reg("PLMBASE", low_base)

            self.write_reg("PLMLIMIT", (1 << 32) - 1)
            min_size = 1 << (32 - count_left_1(self.read_reg("PLMLIMIT")))
            # Lower bits of low base must be 0
            stest.expect_true((low_len & (min_size - 1)) == 0,
                "length 0x%x of low protected memory region "
                "should be aligned to 0x%x boundary" % (low_len, min_size))
            self.write_reg("PLMLIMIT", low_base + low_len - 1)
            if PRINT_DEBUG_INFO:
                print("Protected low memory region is: 0x%x ~ 0x%x" \
                      % (low_base, (low_base + low_len)))

        if self.has_capability('PHMR'):
            self.write_reg("PHMBASE", (1 << 64) - 1)
            min_size = 1 << (64 - count_left_1(self.read_reg("PHMBASE"), bits = 64))
            stest.expect_true((high_base & (min_size - 1)) == 0,
                "base address 0x%x of high protected memory region "
                "should be aligned to 0x%x boundary" % (high_base, min_size))
            self.write_reg("PHMBASE", high_base)

            self.write_reg("PHMLIMIT", (1 << 64) - 1)
            min_size = 1 << (64 - count_left_1(
                                    self.read_reg("PHMLIMIT"), bits = 64))
            # Lower bits of low base must be 0
            stest.expect_true((high_len & (min_size - 1)) == 0,
                "length 0x%x of high protected memory region "
                "should be aligned to 0x%x boundary" % (high_len, min_size))
            self.write_reg("PHMLIMIT", high_base + high_len - 1)
            if PRINT_DEBUG_INFO:
                print("Protected high memory region is: 0x%x ~ 0x%x" \
                      % (high_base, high_base + high_len))

    def config_fault_event_int(self, int_msg_addr, int_msg_data):
        self.write_reg("FEADDR", (int_msg_addr >> 2) << 2)
        self.write_reg("FEDATA", int_msg_data)

    # Enqueue an invalidate descriptor
    def enqueue_inv_desc(self, val):
        if not self.has_capability('QI'):
            if PRINT_DEBUG_INFO:
                print("Cannot enqueue the descriptor into the " \
                      "invalidation queue for it's not supported")
            return

        fields = VTdConst.iqa_bf.fields(self.read_reg("IQA"))
        qbase  = fields['IQA'] << 12
        qsize  = int(math.pow(2, fields['QS'])) * 256
        qh     = self.read_reg("IQH") >> 4
        qt     = self.read_reg("IQT") >> 4
        if ((qt + 1) % qsize) == qh:
            raise Exception("Invalidate queue is full")
        self.mem_space_drv.write_value_le(qbase + (qt << 4),
                    VTdConst._inv_descriptor_size, val)
        qt = (qt + 1) % qsize
        self.write_reg("IQT", qt << 4)

    # Invalidate the context-cache globally or locally
    def inv_context_cache(self, granularity, domain_id = 0, device_id = 0,
                          through_descriptor = 0):
        if (granularity != VTdConst.inv_granularity_global
            and granularity != VTdConst.inv_granularity_domain
            and granularity != VTdConst.inv_granularity_device):
            raise Exception("unknown granularity %d in "
                            "invalidating context cache" % granularity)
        if through_descriptor == 0:
            fields = VTdConst.ccmd_bf.fields(self.read_reg("CCMD"))
            fields['CIRG'] = granularity
            if granularity == VTdConst.inv_granularity_domain:
                fields['DID'] = domain_id
            if granularity == VTdConst.inv_granularity_device:
                fields['SID'] = device_id
            fields['ICC'] = 1
            self.write_reg("CCMD", VTdConst.ccmd_bf.value_ex(fields))
            # Verify the ICC bit is cleared by hardware
            fields = VTdConst.ccmd_bf.fields(self.read_reg("CCMD"))
            stest.expect_true(fields['ICC'] == 0,
                "CCMD.ICC should be cleared by hardware "
                "after writing 1 to CCMD.ICC")
        else:
            self.enable_inv_queue(0)
            val = VTdConst.cc_inv_desc_bf.value(
                        FM   = 0,
                        SID  = device_id,
                        DID  = domain_id,
                        G    = granularity,
                        T    = VTdConst.inv_desc_context,
                    )
            self.enqueue_inv_desc(val)
            self.enable_inv_queue(1)

    # Invalidate the IOTLB cache globally or locally
    def inv_iotlb_cache(self, granularity, domain_id = 0, page_addr = 0,
                        through_descriptor = 0):
        if (granularity != VTdConst.inv_granularity_global
            and granularity != VTdConst.inv_granularity_domain
            and granularity != VTdConst.inv_granularity_page):
            raise Exception("unknown granularity %d in "
                            "invalidating IOTLB cache" % granularity)
        if through_descriptor == 0:
            fields = VTdConst.iotlb_bf.fields(self.read_reg("IOTLB"))
            fields['IVT'] = 1
            fields['IIRG'] = granularity
            if granularity == VTdConst.inv_granularity_domain:
                fields['DID'] = domain_id
            elif granularity == VTdConst.inv_granularity_page:
                self.write_reg("IVA", VTdConst.iva_bf.value(
                                        ADDR = page_addr >> 12,
                                        IH   = 0,
                                        AM   = 0))
            self.write_reg("IOTLB", VTdConst.iotlb_bf.value_ex(fields))
            # Verify the IVT bit is cleared by hardware
            fields = VTdConst.iotlb_bf.fields(self.read_reg("IOTLB"))
            stest.expect_true(fields['IVT'] == 0,
                "IOTLB.IVT should be cleared by hardware "
                "after writing 1 to IOTLB.IVT")
        else:
            self.enable_inv_queue(0)
            val = VTdConst.iotlb_inv_desc_bf.value(
                        ADDR = page_addr >> 12,
                        IH   = 0,
                        AM   = 0,
                        DID  = domain_id,
                        DR   = 1,
                        DW   = 1,
                        G    = granularity,
                        T    = VTdConst.inv_desc_iotlb,
                    )
            self.enqueue_inv_desc(val)
            self.enable_inv_queue(1)

    # Invalidate the interrupt entry cache globally or locally
    def inv_int_entry_cache(self, globally, int_index = 0, index_mask = 0):
        self.enable_inv_queue(0)
        val = VTdConst.iec_inv_desc_bf.value(
                            IIDX = int_index,
                            IM   = index_mask,
                            G    = (0, 1)[globally == 0],
                            T    = VTdConst.inv_desc_int_entry,
                        )
        self.enqueue_inv_desc(val)
        self.enable_inv_queue(1)

    # Invalidate the device-IOTLB cache
    def inv_device_iotlb(self, source_addr, source_id,
                         with_size = 0, max_invs_pend = 0):
        self.enable_inv_queue(0)
        val = VTdConst.dev_iotlb_inv_desc_bf.value(
                            ADDR = source_addr >> 12,
                            S    = (0, 1)[with_size != 0],
                            SID  = source_id,
                            MIP  = max_invs_pend,
                            T    = VTdConst.inv_desc_dev_iotlb
                        )
        self.enqueue_inv_desc(val)
        self.enable_inv_queue(1)

    # Wait a list of invalidation descriptor done (just to test wait descriptor)
    def wait_inv_desc_list_done(self, inv_desc_val_list,
                               to_interrupt = 1, to_fence = 0,
                               to_write_status = 0,
                               status_addr = 0, status_data = 0):
        self.enable_inv_queue(0)
        for desc in inv_desc_val_list:
            self.enqueue_inv_desc(desc)
        val = VTdConst.inv_wait_desc_bf.value(
                            SA   = status_addr >> 2,
                            SD   = status_data,
                            FN   = (0, 1)[to_fence != 0],
                            IF   = (0, 1)[to_interrupt != 0],
                            SW   = (0, 1)[to_write_status != 0],
                            T    = VTdConst.inv_desc_wait
                        )
        self.enqueue_inv_desc(val)
        self.enable_inv_queue(1)

    # Issue a message-signaled interrupt to the VTd hardware in the root complex
    def issue_int_message(self, bus_id, dev_id, func_id, msg_addr, msg_data):
        return self.issue_dma_remapping(bus_id, dev_id, func_id, msg_addr,
                                        VTdHwDriver._dma_write, 4,
                                        dev_util.value_to_tuple_le(msg_data, 4))

    # Issue a DMA remapping request in the name of source_id
    #     read_or_write: 0 - read, 1 - write
    def issue_dma_remapping(self, bus_id, dev_id, func_id, addr,
                            read_or_write = _dma_read,
                            rw_len = 0, bytes = ()):
        # Issue the DMA remapping through the test vPCI device
        return tb.issue_dma_remapping(bus_id, dev_id, func_id, addr,
                                      read_or_write, rw_len, bytes)

    # Get and then clear the interrupt data
    # return tuple format: (dest_cpu_id, vector, trigger_mode,
    #                       destination_mode, delivery_mode)
    # if vector == 0, then it means no interrupt since last calling of it
    def get_and_clear_int_data(self):
        # An ugly code here to refer objects belonging to my parent object
        int_data_dic = simics.conf_attribute_t.copy(tb.apic_bus.current_interrupt)
        tb.apic_bus.current_interrupt = {}
        if int_data_dic != {}:
            return (int_data_dic['dest'],
                    int_data_dic['vect'],
                    int_data_dic['trig-mode'],
                    int_data_dic['dest-mode'],
                    int_data_dic['deliv-mode'])
        else:
            return (0, 0, 0, 0, 0)

    # Prepare the multi-level page table for a domain in a continuous area
    #     space_size-- space size of guest software
    #     levels    -- levels of the page table, 2 to 6
    #     base_addr -- base address of the continuous area to be used by the PT
    #     length    -- length of the continuous area
    def prepare_domain_page_table(self, space_size, levels, base_addr, length):
        page_size   = VTdConst._page_size
        pte_size    = VTdConst._pte_size
        pte_bf      = VTdConst.pte_bf

        # Begin constructing the page table from lowest-level page entry
        tabled_space = space_size # Size of the space pointed by this level table
        pte_addr     = base_addr  # Address where this level PTE resides
        phy_addr     = 0 # No physical page mapped at a domain page now
        for l in range(levels):
            page_cnt = (tabled_space + page_size - 1) // page_size
            if page_cnt == 0:
                raise Exception("page count should not be 0 to page a space")
            first_pte   = pte_addr
            this_phy    = phy_addr
            for e in range(page_cnt):
                val = pte_bf.value(SP = 0, SNP = 0, W = 0, R = 0, TM = 0,
                                   ADDR = (this_phy >> 12))
                self.mem_space_drv.write_value_le(pte_addr, pte_size, val)
                pte_addr += pte_size
                if l > 0:
                    this_phy += page_size
            if PRINT_DEBUG_INFO:
                print(("level %d page table: %d entries started from 0x%x, "
                      "points 0x%x physical space stared from 0x%x"
                  % (l, page_cnt, first_pte, tabled_space, phy_addr)))
            tabled_space = page_cnt * pte_size
            phy_addr = first_pte
            if l == (levels - 1):
                if page_cnt > 1:
                    raise Exception("the uppermost page directory "
                                    "should have only one entry")
                pte_addr -= pte_size # Back to address of last PTE
            else:
                # Advance to the next page
                pte_addr = ((pte_addr + page_size - 1) >> 12) << 12
        return pte_addr

    # Map a guest page to specified host address through filling a page entry
    #     table_root  -- address of the page table root
    #     levels      -- levels of the page table, 2 to 6
    #     guest_addr  -- address of the page in the guest memory space
    #     host_addr   -- host address of the physical page
    #     is_super    -- whether this page is a super page
    def map_guest_page_to_host(self, table_root, levels,
                               guest_addr, host_addr,
                               is_super = 0, can_read = 1, can_write = 1):
        pte_size    = VTdConst._pte_size
        pte_bf      = VTdConst.pte_bf
        off_mask    = (1 << 9) - 1

        level = levels
        pte_base = table_root
        pte_addr = table_root
        while level > 0:
            rshift_bits = 12 + (level - 1) * 9
            pte_off = ((guest_addr >> rshift_bits) & off_mask) << 3
            pte_addr = pte_base + pte_off
            if PRINT_DEBUG_INFO:
                print("PTE address: 0x%x" % pte_addr)
            pte_val = self.mem_space_drv.read_value_le(pte_addr, pte_size)
            pte_base = (pte_bf.fields(pte_val)['ADDR']) << 12
            # Update the R/W bit to request read/write permission
            fields = pte_bf.fields(pte_val)
            fields['R'] = (0, 1)[can_read != 0]
            fields['W'] = (0, 1)[can_write != 0]
            self.mem_space_drv.write_value_le(
                pte_addr, pte_size, pte_bf.value_ex(fields))
            level -= 1
        fields = pte_bf.fields(pte_val)
        fields['ADDR'] = host_addr >> 12
        fields['R'] = (0, 1)[can_read != 0]
        fields['W'] = (0, 1)[can_write != 0]
        fields['SP'] = (0, 1)[is_super != 0]
        self.mem_space_drv.write_value_le(pte_addr, pte_size, pte_bf.value_ex(fields))

    # Switch to a domain specified by its address space root
    def switch_domain(self, context_root):
        # Check whether pointed table pointed by current root is a valid domain
        re_size = VTdConst._root_entry_size
        val = self.read_reg("RTADDR")
        rt_addr = VTdConst.rtaddr_bf.fields(val)['RTA'] << 12
        val = self.mem_space_drv.read_value_le(rt_addr, re_size)
        fields = VTdConst.re_bf.fields(val)
        if fields['P'] == 1 and fields['CTP'] != 0:
            if PRINT_DEBUG_INFO:
                print("a valid domain at 0x%x to be left" \
                      % (fields['CTP'] << 12))
            self.inv_context_cache(VTdConst.inv_granularity_global)
            self.inv_iotlb_cache(VTdConst.inv_granularity_global)
        else:
            if PRINT_DEBUG_INFO:
                print("no valid domain to be left")

        if context_root == (fields['CTP'] << 12):
            if PRINT_DEBUG_INFO:
                print("new domain to switch is same as current pointed one")
            return

        # Replace the CTP bitfields to be new root
        fields['CTP'] = context_root >> 12
        fields['P'] = 1
        self.mem_space_drv.write_value_le(
                rt_addr, re_size, VTdConst.re_bf.value_ex(fields))

class ApicBus(pyobj.ConfObject):
    '''A pseudo object with apic_bus interface to test APIC'''
    def _initialize(self):
        super()._initialize()
        self.last_paras = {}

    class apic_bus(pyobj.Interface):
        def interrupt(self, dest_mode, delivery_mode,
                            level_assert, trigger_mode, vector, destination):
            self._up.last_paras['dest-mode'] = dest_mode
            self._up.last_paras['deliv-mode'] = delivery_mode
            self._up.last_paras['level'] = level_assert
            self._up.last_paras['trig-mode'] = trigger_mode
            self._up.last_paras['vect'] = vector
            self._up.last_paras['dest'] = destination
            return simics.Apic_Bus_Accepted

    class current_interrupt(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'D'
        def getter(self):
            return self._up.last_paras

        def setter(self, val):
            self._up.last_paras = val

class VTdTestBench:
    # Memory space constants
    _main_mem_base         = 0x00000000
    _main_mem_length       = 0x80000000 # 2GB memory
    _vtd_hw_bank_base      = 0xF0000000 # 4KB

    # Scratch memory space constants
    _scratch_re_base       = 0x0000
    _scratch_ce_base       = 0x0008

    # PCI device number constants
    _vtd_dev_num = 1

    def __init__(self):

        objs = [] # all objects to create

        clk = simics.pre_conf_object('clock', 'clock')
        clk.freq_mhz = 1000
        objs += [clk]

        ram_image = simics.pre_conf_object('ram_image', 'image')
        ram_image.size = VTdTestBench._main_mem_length
        objs += [ram_image]

        ram = simics.pre_conf_object('ram', 'ram')
        ram.image = ram_image
        objs += [ram]

        mem_space = simics.pre_conf_object('mem_space', 'memory-space')
        conf_space = simics.pre_conf_object('conf_space', 'memory-space')
        io_space = simics.pre_conf_object('io_space', 'memory-space')
        bridge = simics.pre_conf_object('bridge', 'x58_dmi')
        pci_bus = simics.pre_conf_object('pci_bus', 'pcie-bus')
        pci_bus.memory_space = mem_space
        pci_bus.conf_space = conf_space
        pci_bus.io_space = io_space
        pci_bus.bridge = bridge
        pci_bus.pci_devices = []
        bridge.pci_bus = pci_bus
        objs += [mem_space, conf_space, io_space, pci_bus, bridge]

        # Pseudo APIC bus to catch the interrupts from VTd hardware
        apic_bus = simics.pre_conf_object('apic_bus', 'ApicBus')
        objs += [apic_bus]

        vtd = simics.pre_conf_object('vtd', 'x58_remap_unit0')
        vtd.apic_bus = apic_bus
        vtd.memory_space = mem_space
        objs += [vtd]

        pci_bus.upstream_target = vtd

        # A simple vPCI device to send the DMA read/write to the VT-d hardware
        pci_dev = simics.pre_conf_object('pci_dev', 'simple_pcie_device')
        pci_dev.pci_bus = pci_bus
        objs += [pci_dev]

        mem_space.map = [
            [VTdTestBench._main_mem_base,    ram, 0, 0, VTdTestBench._main_mem_length],
            [VTdTestBench._vtd_hw_bank_base, [vtd, 'vtd'], 0, 0, VTdConst._reg_space_size],
            ]

        for o in objs:
            o.queue = clk


        simics.SIM_add_configuration(objs, None)

        self.vtd = simics.SIM_get_object('vtd')
        self.pci_dev = simics.SIM_get_object('pci_dev')
        self.pci_bus = simics.SIM_get_object('pci_bus')
        self.apic_bus = simics.SIM_get_object('apic_bus')

        self.mem_space = simics.SIM_get_object('mem_space')
        self.scratch_mem = dev_util.Memory()
        self.mem_space_drv = MemorySpaceDriver(self.mem_space)
        self.vtd_hw_drv = VTdHwDriver(self.vtd, self._vtd_hw_bank_base, self.mem_space_drv)

        simics.SIM_set_log_level(self.pci_dev, 4)
        simics.SIM_set_log_level(self.vtd, 4)

        # Memory management variables
        self.permanent_base = VTdTestBench._main_mem_base
        self.permanent_len  = VTdTestBench._main_mem_length // 8
        self.dynamic_base   = self.permanent_base + self.permanent_len
        self.dynamic_len    = VTdTestBench._main_mem_length // 2
        self.permanent_ptr  = self.permanent_base
        self.dynamic_ptr    = self.dynamic_base

    # Allocate a permanent memory area for such page tables
    def alloc_permanent_mem(self, length, align_size = 0):
        if align_size <= 0:
            align_size = length
        cur_ptr = align_to(self.permanent_ptr, align_size)
        if (cur_ptr + length) >= self.permanent_base + self.permanent_len:
            raise Exception("permanent memory to be allocated from 0x%x to "
                    "0x%x will exceed pre-allocated region from 0x%x to 0x%x"
                    % (cur_ptr, cur_ptr + length, self.permanent_base,
                     self.permanent_baase + self.permanent_len))
        self.permanent_ptr = cur_ptr + length
        return cur_ptr

    # Allocate a dynamic memory area for such remapping pages
    def alloc_dynamic_mem(self, length):
        # Align dynamic pointer to the required length
        cur_ptr = align_to(self.dynamic_ptr, length)
        if (cur_ptr + length) >= self.dynamic_base + self.dynamic_len:
            raise Exception("dynamic memory to be allocated from 0x%x to 0x%x "
                  "will exceed pre-allocated region from 0x%x to 0x%x"
                  % (cur_ptr, cur_ptr + length, self.dynamic_base,
                     self.dynamic_base + self.dynamic_len))
        self.dynamic_ptr = cur_ptr + length
        return cur_ptr

    def reset_test_bench_status(self):
        self.permanent_ptr = self.permanent_base
        self.dynamic_ptr   = self.dynamic_base

    def get_vtd_bank_base(self):
        return VTdTestBench._vtd_hw_bank_base

    def map_pci_device(self, device, dev_id, func_id,):
        m = []
        # first unmap device
        for p in self.pci_bus.pci_devices:
            if p[2] != device:
                m.append(p)
        # now add new map
        m += [[dev_id, func_id, device]]
        self.pci_bus.pci_devices = m
        # disconnect the device from the bus to clear cached bus-id
        device.pci_bus = None
        device.pci_bus = self.pci_bus

    # Issue a DMA remapping request through the test vPCI device
    def issue_dma_remapping(self, bus_id, dev_id, func_id, addr,
                            read_or_write = VTdHwDriver._dma_read,
                            rw_len = 0, bytes = ()):
        stest.expect_true(bus_id == 0, "can only handle bus_id == 0, only one bus connected")
        self.map_pci_device(self.pci_dev, dev_id, func_id)
        # Enable the 'Bus Master Enable' bit of the PCI device directly
        self.pci_dev.pci_config_command = 0x4
        self.pci_dev.address = addr
        self.pci_dev.size = rw_len
        if read_or_write == VTdHwDriver._dma_read:
            try:
                # tuple again to evaluate the expression
                return simics.conf_attribute_t.copy(self.pci_dev.data)
            except:
                return ()
        else:
            try:
                self.pci_dev.data = tuple(bytes)
                return tuple(bytes)
            except:
                return ()

def gen_int_req_handle(pci_bus_id, device_id, func_id):
    if func_id == 0:
        sh_valid = 0
        subhandle = 0
        handle = (pci_bus_id << 8) + device_id
    else:
        sh_valid = 1
        subhandle = func_id
        handle = (pci_bus_id << 8) + device_id
    return (handle, sh_valid, subhandle)

def gen_source_id(pci_bus_id, device_id, func_id):
    assert pci_bus_id < 0x100 and device_id < 0x20 and func_id < 0x8
    return (pci_bus_id << 8) + (device_id << 3) + func_id




tb            = VTdTestBench()
vtd_hw_drv    = tb.vtd_hw_drv
mem_space_drv = tb.mem_space_drv
