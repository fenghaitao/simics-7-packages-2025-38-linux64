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


# tb_lan.py
# testbench of ICH8/9/10 ethernet controller

import pyobj
import simics
import cli_impl
import stest
import dev_util
import conf
import os, sys
sys.path.append(os.path.join(".."))
from . import pcibus

sys_timer_mhz   = 14.18

SIM_MEM_BLOCK_LEN   = 1024

# Main memory division
MAIN_RAM_BASE       = 0x80000000
MAIN_RAM_SIZE       = 0x1000000

RX_DESC_BASE        = MAIN_RAM_BASE
RX_DESC_LEN         = 0x80000
TX_DESC_BASE        = RX_DESC_BASE + RX_DESC_LEN
TX_DESC_LEN         = 0x80000

RX_BUF_BASE         = MAIN_RAM_BASE + 0x100000
RX_BUF_LEN          = 0x100000
TX_BUF_BASE         = RX_BUF_BASE  + RX_BUF_LEN
TX_BUF_LEN          = 0x100000

ICH9_LAN_REG_BASE   = 0x100000
ICH9_LAN_REG_LEN    = 0x10000

ICH9_PCI_CONF_BASE  = 0x200000
ICH9_PCI_CONF_LEN   = 0x100

SPI_FLASH_BASE      = 0x300000
SPI_FLASH_LEN       = 0x1000 # 4KB

ICH9_LAN_DELAY_UNIT_IN_US   = 1.024

# Packet buffer size
MAX_PKT_BUF_SIZE    = 9018
BASE_PKT_BUF_SIZE   = 2048 # default setting of ICH9 yields this size
PAGE_SIZE           = 4096
PAGE_MASK           = ~((1 << 12) - 1)

# ICH9 LAN controller receive parameters
ICH9_LAN_RD_LEN     = 16
ICH9_LAN_MIN_RD_CNT = 8 # Minimum 128-byte to fill a cache line
ICH9_MAC_ADDR_0     = 0x200909021200

# Transmit parameters
ICH9_LAN_TD_LEN     = 16
ICH9_LAN_MIN_TD_CNT = 8 # Minimum 128-byte to fill a cache line
ICH9_LAN_L_TD_LEN   = ICH9_LAN_TD_LEN
ICH9_LAN_MIN_L_TD_CNT= ICH9_LAN_MIN_TD_CNT # Minimum 128-byte to fill a cache line
ICH9_LAN_C_TD_LEN   = ICH9_LAN_TD_LEN
ICH9_LAN_D_TD_LEN   = ICH9_LAN_TD_LEN
ICH9_LAN_TCP_IP_C_TD_TYPE   = 0x0
ICH9_LAN_DATA_C_TD_TYPE     = 0x1


# Scratch pad memory division
SCRATCH_RD_BASE     = 0x00
SCRATCH_RD_LEN      = 16
SCRATCH_EX_RD_BASE  = SCRATCH_RD_BASE + SCRATCH_RD_LEN
SCRATCH_EX_RD_LEN   = 16
SCRATCH_L_TD_BASE   = SCRATCH_EX_RD_BASE + SCRATCH_EX_RD_LEN
SCRATCH_L_TD_LEN    = ICH9_LAN_L_TD_LEN
SCRATCH_C_TD_BASE   = SCRATCH_L_TD_BASE + SCRATCH_L_TD_LEN
SCRATCH_C_TD_LEN    = ICH9_LAN_C_TD_LEN
SCRATCH_D_TD_BASE   = SCRATCH_C_TD_BASE + SCRATCH_C_TD_LEN
SCRATCH_D_TD_LEN    = ICH9_LAN_D_TD_LEN
SCRATCH_MACSEC_SECTAG_BASE   = SCRATCH_D_TD_BASE + SCRATCH_D_TD_LEN
SCRATCH_MACSEC_SECTAG_LEN    = 16
SCRATCH_PTP_V1_BASE = SCRATCH_MACSEC_SECTAG_BASE + SCRATCH_MACSEC_SECTAG_LEN
SCRATCH_PTP_V1_LEN  = 36
SCRATCH_PTP_V2_BASE = SCRATCH_PTP_V1_BASE + SCRATCH_PTP_V1_LEN
SCRATCH_PTP_V2_LEN  = 36
SCRATCH_SRD_BASE    = SCRATCH_PTP_V2_BASE + SCRATCH_PTP_V2_LEN
SCRATCH_SRD_LEN     = 32

# PHY parameters
PHY_ADDRESS         = 0x01  # Address of attached external PHY

# TCP/IP protocol constants
eth_hdr_len             = 14
eth_sip_v4_off          = 26 # Source IP, IPv4
eth_dip_v4_off          = 30 # Destination IP, IPv4
eth_sport_v4_off        = 34 # Source TCP/UDP port, IPv4
eth_dport_v4_off        = 36 # Destination TCP/UDP port, IPv4

eth_sip_v6_off          = 22 # Source IP, IPv6
eth_dip_v6_off          = 38 # Destination IP, IPv6
eth_sport_v6_off        = 54 # Source TCP/UDP port, IPv6
eth_dport_v6_off        = 56 # Destination TCP/UDP port, IPv6

tcp_ipcso               = 24 # IPv4 checksum offset
tcp_ipcss               = 14 # IPv4 checksum start
tcp_ipcse               = 33 # IPv4 checksum ending
tcp_tucso               = 50 # TCP/IPv4 checksum offset
tcp_tucss               = 34 # TCP/IPv4 checksum start
tcp_tucse               = 0  # TCP/IPv4 checksum ending
tcp_v6_tucso            = 70 # TCP/IPv6 checksum offset
tcp_v6_tucss            = 54 # TCP/IPv6 checksum start
tcp_v6_tucse            = 0  # TCP/IPv6 checksum ending
udp_v6_tucso            = 60 # UPD/IPv6 checksum offset
udp_tucso               = 40 # UDP/IPv4 checksum offset

# Advanced descriptor types
ADV_DESC_ONE_BUFFER                   = 1
ADV_DESC_HEADER_SPLIT                 = 2
ADV_DESC_REPLICATE_ALWAYS             = 3
ADV_DESC_REPLICATE_LARGE_PKT_ONLY     = 4
ADV_DESC_SPLIT_ALWAYS_USE_HEADER_BUF  = 5

class Bitfield_LE_Ex(dev_util.Bitfield_LE):
    def __init__(self, fields, ones=0):
        dev_util.Bitfield_LE.__init__(self, fields, ones)

    def value_ex(self, dict):
        value = 0
        for key in dict:
            (start, stop) = self.field_ranges[key]

            if not (0 <= dict[key] and dict[key] < (1 << (stop + 1 - start))):
                raise RangeError("Value to large for bitfield '%s'." % key,
                                 (dict[key], 0, (2 << (stop - start)) - 1))

            # Insert field into final value
            value |= dict[key] << start
        return value | self.ones

class MACsecConst:
    ether_type = 0x88E5
    sectag_tci_an_bf = dev_util.Bitfield_BE({
                        'V'     : 0,
                        'ES'    : 1,
                        'SC'    : 2,
                        'SCB'   : 3,
                        'E'     : 4,
                        'C'     : 5,
                        'AN'    : (6, 7),
                       }, bits = 8)

    sectag_sl_bf    = dev_util.Bitfield_BE({
                        'SL'    : (2, 7),
                       }, bits = 8)

class PtpConst:
    ether_type = 0x88F7
    udp_event_port = 319
    udp_general_port = 320

class TestData:
    tcp_pkt = [
                # Ethernet header
                0x00, 0x13, 0x72, 0xe1, 0x37, 0x59,
                0x00, 0x14, 0x78, 0x41, 0xc8, 0x54,
                0x08, 0x00, # Ethernet type/length

                # IP header, 20-byte
                0x45, 0x00, # IPv4, 20-byte header
                0x00, 0x34, # Total length, 52-byte, 32-byte data
                0xac, 0x7d, # Identification
                0x40, 0x00, # Flag, fragment offset
                0x77,       # TTL, Time-To-Live
                0x06,       # Protocol, 6 = TCP
                0xaa, 0x41, # Checksum, at offset 24
                0x3d, 0x87, 0xad, 0x8d, # Source IP
                0xc0, 0xa8, 0x01, 0x48, # Destination IP

                # TCP header, 20-byte
                0x21, 0x99, # Source port
                0x80, 0xd0, # Destination Port
                0x0a, 0x0b, 0x71, 0xf4,     # TX sequence
                0xc7, 0x59, 0xac, 0xc9,     # RX sequence
                0x80, 0x10, # Flags
                0xff, 0x33, # Window
                0xe0, 0x8b, # Checksum, at offset 50
                0x00, 0x00, # Urgent pointer

                # TCP options
                0x01, 0x01, # NOP * 2
                0x08, 0x0a, # Option: Timestamp
                0x01, 0x70, 0x06, 0x0d, # Timestamp
                0x00, 0x5f, 0x4f, 0x90, # Timestamp echo

                # Ethernet frame cs
                0x00, 0x00, 0x00, 0x00  # dummy value
              ]

    udp_pkt = [
                # Ethernet header, 14 bytes
                0x00, 0x14, 0x78, 0x41, 0xc8, 0x54,
                0x00, 0x13, 0x72, 0xe1, 0x37, 0x59,
                0x08, 0x00,

                # IP header, 20 bytes
                0x45, 0x00,
                0x00, 0x2e, 0x01, 0xf1, 0x40, 0x00,
                0x3f, 0x11, 0xf2, 0xd6,
                0xc0, 0xa8, 0x01, 0x48,
                0x7b, 0x7d, 0x09, 0x8a,

                # UDP header, 8 bytes
                0x80, 0x01, 0x07, 0x22,
                0x00, 0x1a, 0x88, 0x9b,

                # Payload data, 18 bytes
                0xa9, 0x03,
                0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00,

                # Ethernet frame cs
                0x00, 0x00, 0x00, 0x00  # dummy value
              ]


    udp_pkt_cs_is_0 = [
                # Ethernet header, 14 bytes
                0x00, 0x17, 0xa0, 0x00, 0x00, 0x01,
                0x00, 0x17, 0xa0, 0x00, 0x00, 0x00,
                0x08, 0x00,

                # IP header, 20 bytes
                0x45, 0x00, 0x00, 0x48, 0xd6, 0x3e,
                0x40, 0x00, 0x40, 0x11, 0x4f, 0x8a,
                0x0a, 0x0a, 0x00, 0x64, 0x0a, 0x0a,
                0x00, 0x65,

                # UDP header, 8 bytes
                0xb5, 0xe8, 0x1b, 0xd3, 0x00, 0x34,
                0xff, 0xff,

                # Payload data
                0x5f, 0x74, 0x65, 0x73, 0x74, 0x5f,
                0x7a, 0x65, 0x72, 0x6f, 0x5f, 0x75,
                0x64, 0x70, 0x5f, 0x76, 0x34, 0x5f,
                0x5f, 0x5f, 0x21, 0x21, 0x21, 0x21,
                0x5f, 0x5f, 0x39, 0x39, 0x00, 0x20,
                0x00, 0x20, 0x00, 0x20, 0x00, 0x20,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x60, 0x5c,

                # Ethernet frame cs
                0x2d, 0xbf, 0x53, 0x40
    ]


    udp_pkt_ipv6 = [
                # Ethernet frame header
                0x33, 0x33, 0x00, 0x01, 0x00, 0x02, 0x00,
                0x17, 0xa0, 0x00, 0x00, 0x00, 0x86, 0xdd,
                0x60, 0x05,

                # IPv6 header
                0x1e, 0x2b, 0x00, 0x32, 0x11, 0x01, 0xfe,
                0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x02, 0x17, 0xa0, 0xff, 0xfe, 0x00, 0x00,
                0x00, 0xff, 0x02, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x01, 0x00, 0x02,

                # UDP header
                0x02, 0x22, # src port
                0x02, 0x23, # dst port
                0x00, 0x32, # len
                0x1a, 0x42, # udp checksum

                # data (DHCPv6)
                0x0b, 0x8b, 0x7c, 0x30, 0x00, 0x06, 0x00,
                0x0a, 0x00, 0x17, 0x00, 0x18, 0x00, 0x38,
                0x00, 0x1f, 0x00, 0x0e, 0x00, 0x01, 0x00,
                0x0e, 0x00, 0x02, 0x00, 0x00, 0xab, 0x11,
                0x8c, 0x3a, 0x7f, 0x47, 0x95, 0xe9, 0x67,
                0xe3, 0x00, 0x08, 0x00, 0x02, 0x05, 0x8a,

                # Ethernet frame checksum
                0xdc, 0xaf, 0x1f, 0x5d
    ]

    udp_pkt_ipv6_cs_is_0 = [
                # Ethernet frame header
                0x00, 0x17, 0xa0, 0x00, 0x00, 0x01, 0x00,
                0x17, 0xa0, 0x00, 0x00, 0x00, 0x86, 0xdd,

                # IPv6 header
                0x60, 0x09, 0x58, 0x3c, 0x00, 0x3e, 0x11,
                0x40, 0xfe, 0x80, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x02, 0x17, 0xa0, 0xff, 0xfe,
                0x00, 0x00, 0x00, 0xfe, 0x80, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x02, 0x17, 0xa0,
                0xff, 0xfe, 0x00, 0x00, 0x01,

                # UDP header
                0xe9, 0xc3, # srt port
                0x04, 0xd2, # dst port
                0x00, 0x3e, # len
                0xff, 0xff, # udp checksum

                # Data
                0x5f, 0x5f, 0x54, 0x45, 0x53, 0x54, 0x5f, 0x55,
                0x44, 0x50, 0x5f, 0x69, 0x70, 0x76, 0x36, 0x5f,
                0x7a, 0x65, 0x72, 0x6f, 0x5f, 0x63, 0x68, 0x65,
                0x63, 0x6b, 0x73, 0x75, 0x6d, 0x5f, 0x5f, 0x74,
                0x65, 0x73, 0x74, 0x74, 0x65, 0x73, 0x74, 0x5f,
                0x31, 0x31, 0x31, 0x31, 0x31, 0x31, 0x31, 0x31,
                0x00, 0x70, 0x15, 0x5b, 0x3a, 0x30,

                # Ethernet frame checksum
                0x5b, 0x13, 0xed, 0xd2
    ]

    tcp_pkt_ipv6 = [
                # Ethernet frame header
                0x00, 0x17, 0xa0, 0x00, 0x00, 0x00,
                0x00, 0x17, 0xa0, 0x00, 0x00, 0x01,
                0x86, 0xdd,

                # IPv6 header
                0x60, 0x06, 0x0a, 0x99, 0x00, 0x28,
                0x06, 0x40, 0xfe, 0x80, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x02, 0x17,
                0xa0, 0xff, 0xfe, 0x00, 0x00, 0x01,
                0xfe, 0x80, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x02, 0x17, 0xa0, 0xff,
                0xfe, 0x00, 0x00, 0x00,

                # TCP header
                0xeb, 0x12,                         # src port
                0x15, 0xb3,                         # dst port
                0xe9, 0x13, 0x6f, 0x38, 0x00, 0x00,
                0x00, 0x00, 0xa0, 0xc2, 0x70, 0x80,
                0xc0, 0x79,                         # TCP checksum
                0x00, 0x00, 0x02, 0x04, 0x05, 0xa0,
                0x04, 0x02, 0x08, 0x0a, 0x31, 0x6b,
                0x4c, 0xa9, 0x00, 0x00, 0x00, 0x00,
                0x01, 0x03, 0x03, 0x09,

                # Ethernet frame checksum
                0xc1, 0x79, 0x71, 0x2d,
    ]

    tucs_offsets = {
        "ipv4": {
            "tcp": {
                "TUCSS": tcp_tucss,
                "TUCSE": tcp_tucse,
                "TUCSO": tcp_tucso
            },
            "udp": {
                "TUCSS": tcp_tucss,
                "TUCSE": tcp_tucse,
                "TUCSO": udp_tucso
            }
        },
        "ipv6": {
            "tcp": {
                "TUCSS": tcp_v6_tucss,
                "TUCSE": tcp_v6_tucse,
                "TUCSO": tcp_v6_tucso
            },
            "udp": {
                "TUCSS": tcp_v6_tucss,
                "TUCSE": tcp_v6_tucse,
                "TUCSO": udp_v6_tucso
            }
        }
    }

    # Test keys for AES-GCM cipher suite
    test_key = list(map(ord,
        ['i', ' ', 'l', 'o', 'v', 'e', ' ', 'v',
         'i', 'r', 't', 'u', 't', 'e', 'c', 'h']))

    @staticmethod
    def get_pkt_hdr_len(ipv4_ipv6, tcp_udp, enable_vlan):
        mac_len = 14
        if enable_vlan:
            mac_len = 18 # FIXME: 18???
        if ipv4_ipv6 == "ipv4":
            if tcp_udp == "tcp":
                return (mac_len + 20 + 20)
            else:
                return (mac_len + 20 + 8)
        else:
            if tcp_udp == "tcp":
                return (mac_len + 40 + 40) # FIXME: 40???, 40???
            else:
                return (mac_len + 40 + 8)

    @staticmethod
    def gen_pkt_hdr(ipv4_ipv6, tcp_udp, enable_vlan):
        mac_len = 14
        mac_hdr = TestData.tcp_pkt[0:mac_len]
        ip_hdr = []
        xp_hdr = []
        if enable_vlan:
            mac_hdr = mac_hdr + [0x00, 0x00, 0x00, 0x00]
        if ipv4_ipv6 == "ipv4":
            if tcp_udp == "tcp":
                ip_hdr = TestData.tcp_pkt[14:34]
                xp_hdr = TestData.tcp_pkt[34:54]
            else:
                ip_hdr = TestData.udp_pkt[14:34]
                xp_hdr = TestData.udp_pkt[34:42]
        else:
            assert 0
        return mac_hdr + ip_hdr + xp_hdr

class IchLanConst:
    LSEC_TX_MODE_DISABLE    = 0
    LSEC_TX_MODE_ADD_INTG   = 1
    LSEC_TX_MODE_ENC        = 2

    LSEC_RX_MODE_DISABLE    = 0
    LSEC_RX_MODE_CHECK      = 1
    LSEC_RX_MODE_STRICT     = 2
    LSEC_RX_MODE_DROP       = 3

    # Time stamp constants
    TM_RX_TYPE_V2_ON_L2     = 0
    TM_RX_TYPE_V1_ON_L4     = 1
    TM_RX_TYPE_V2_ALL       = 2
    TM_RX_TYPE_ALL          = 4
    TM_RX_TYPE_V2_EVENT     = 5

    general_reg_info = {
                    'CTRL'      :   (0x00000, 4, 0x201),
                    'STATUS'    :   (0x00008, 4, 0x800002a3),
                    'STRAP'     :   (0x0000C, 4, 0x0),
                    'EEC'       :   (0x00010, 4, 0x0),
                    'CTRL_EXT'  :   (0x00018, 4, 0x0),
                    'MDIC'      :   (0x00020, 4, 0x0),
                    'FEXTNVM'   :   (0x00028, 4, 0x0),
                    'FEXT'      :   (0x0002C, 4, 0x0),
                    'BUSNUM'    :   (0x00038, 4, 0xc8),
                    'FCTTV'     :   (0x00170, 4, 0x0),
                    'FCRTV'     :   (0x05F40, 4, 0x0),
                    'LEDCTL'    :   (0x00E00, 4, 0x0),
                    'EXTCNF_CTRL':  (0x00F00, 4, 0x0),
                    'EXTCNF_SIZE':  (0x00F08, 4, 0x0),
                    'PHY_CTRL'  :   (0x00F10, 4, 0x0),
                    'PCIANACFG' :   (0x00F18, 4, 0x0),
                    'PBA'       :   (0x01000, 4, 0xe0008),
                    'PBS'       :   (0x01008, 4, 0x18),
                }

    receive_reg_info = {
                    'RCTL'      :   (0x00100, 4, 0x0),
                    'ERT'       :   (0x02008, 4, 0x0),
                    'FCRTL'     :   (0x02160, 4, 0x0),
                    'FCRTH'     :   (0x02168, 4, 0x0),
                    'PSRCTL'    :   (0x02170, 4, 0x00040402),
                    'RDBAL0'    :   (0x02800, 4, 0x0),
                    'RDBAH0'    :   (0x02804, 4, 0x0),
                    'RDLEN0'    :   (0x02808, 4, 0x0),
                    'RDH0'      :   (0x02810, 4, 0x0),
                    'RDT0'      :   (0x02818, 4, 0x0),
                    'RDTR'      :   (0x02820, 4, 0x0),
                    'RXDCTL'    :   (0x02828, 4, 0x0),
                    'RADV'      :   (0x0282C, 4, 0x0),
                    'RDBAL1'    :   (0x02900, 4, 0x0),
                    'RDBAH1'    :   (0x02904, 4, 0x0),
                    'RDLEN1'    :   (0x02908, 4, 0x0),
                    'RDH1'      :   (0x02910, 4, 0x0),
                    'RDT1'      :   (0x02918, 4, 0x0),
                    'RSRPD'     :   (0x02C00, 4, 0x0),
                    'RAID'      :   (0x02C08, 4, 0x0),
                    'CPUVEC'    :   (0x02C10, 4, 0x0),
                    'RXCSUM'    :   (0x05000, 4, 0x0),
                    'RFCTL'     :   (0x05008, 4, 0x0),
                    'MTA0'      :   (0x05200, 4, 0x0),
                    'RAL0'      :   (0x05400, 4, 0x0),
                    'RAH0'      :   (0x05404, 4, 0x0),
                    'SHRAL0'    :   (0x05438, 4, 0x0),
                    'SHRAH0'    :   (0x0543C, 4, 0x0),
                    'MRQC'      :   (0x05818, 4, 0x0),
                    'RSSIM'     :   (0x05864, 4, 0x0),
                    'RSSIR'     :   (0x05868, 4, 0x0),
                    'RETA'      :   (0x05C00, 1, 0x0),
                    'RSSRK'     :   (0x05C80, 1, 0x0),
                    'SRRCTL0'   :   (0x0280c, 4, 0x0),
                    'SRRCTL1'   :   (0x0290c, 4, 0x0),
                    'PSRTYPE01' :   (0x05480, 4, 0x0),
                }

    transmit_reg_info = {
                    'TCTL'      :   (0x00400, 4, 0x2003f0f8),
                    'TIPG'      :   (0x00410, 4, 0x0),
                    'AIT'       :   (0x00458, 4, 0x0),
                    'TDBAL0'    :   (0x03800, 4, 0x0),
                    'TDBAH0'    :   (0x03804, 4, 0x0),
                    'TDLEN0'    :   (0x03808, 4, 0x0),
                    'TDH0'      :   (0x03810, 4, 0x0),
                    'TDT0'      :   (0x03818, 4, 0x0),
                    'TIDV'      :   (0x03820, 4, 0x0),
                    'TXDCTL0'   :   (0x03828, 4, 0x0),
                    'TADV'      :   (0x0382c, 4, 0x0),
                    'TARC0'     :   (0x03840, 4, 0x400),
                    'TDBAL1'    :   (0x03900, 4, 0x0),
                    'TDBAH1'    :   (0x03904, 4, 0x0),
                    'TDLEN1'    :   (0x03908, 4, 0x0),
                    'TDH1'      :   (0x03910, 4, 0x0),
                    'TDT1'      :   (0x03918, 4, 0x0),
                    'TXDCTL1'   :   (0x03928, 4, 0x0),
                    'TARC1'     :   (0x03940, 4, 0x400),
                }

    linksec_reg_info = {
                    # TX registers
                    'LSECTXCAP' :   (0x0B000, 4, 0x9),
                    'LSECTXCTRL':   (0x0B004, 4, 0xFFFFFF20),
                    'LSECTXSCL' :   (0x0B008, 4, 0x0),
                    'LSECTXSCH' :   (0x0B00C, 4, 0x0),
                    'LSECTXSA'  :   (0x0B010, 4, 0x0),
                    'LSECTXPN0' :   (0x0B018, 4, 0x0),
                    'LSECTXPN1' :   (0x0B01C, 4, 0x0),
                    'LSECTXKEY00':  (0x0B020, 4, 0x0),
                    'LSECTXKEY01':  (0x0B024, 4, 0x0),
                    'LSECTXKEY02':  (0x0B028, 4, 0x0),
                    'LSECTXKEY03':  (0x0B02C, 4, 0x0),
                    'LSECTXKEY10':  (0x0B030, 4, 0x0),
                    'LSECTXKEY11':  (0x0B034, 4, 0x0),
                    'LSECTXKEY12':  (0x0B038, 4, 0x0),
                    'LSECTXKEY13':  (0x0B03C, 4, 0x0),

                    # RX registers
                    'LSECRXCAP' :   (0x0B300, 4, 0x81),
                    'LSECRXCTRL':   (0x0B304, 4, 0xB0),
                    'LSECRXSCL0':   (0x0B3D0, 4, 0x0),
                    'LSECRXSCL1':   (0x0B3D4, 4, 0x0),
                    'LSECRXSCL2':   (0x0B3D8, 4, 0x0),
                    'LSECRXSCL3':   (0x0B3DC, 4, 0x0),
                    'LSECRXSCH0':   (0x0B3E0, 4, 0x0),
                    'LSECRXSCH1':   (0x0B3E4, 4, 0x0),
                    'LSECRXSCH2':   (0x0B3E8, 4, 0x0),
                    'LSECRXSCH3':   (0x0B3EC, 4, 0x0),
                    'LSECRXSA0' :   (0x0B310, 4, 0x0),
                    'LSECRXSA1' :   (0x0B314, 4, 0x0),
                    'LSECRXSA2' :   (0x0B318, 4, 0x0),
                    'LSECRXSA3' :   (0x0B31C, 4, 0x0),
                    'LSECRXSA4' :   (0x0B320, 4, 0x0),
                    'LSECRXSA5' :   (0x0B324, 4, 0x0),
                    'LSECRXSA6' :   (0x0B328, 4, 0x0),
                    'LSECRXSA7' :   (0x0B32C, 4, 0x0),
                    'LSECRXSAPN0' : (0x0B330, 4, 0x0),
                    'LSECRXSAPN1' : (0x0B334, 4, 0x0),
                    'LSECRXSAPN2' : (0x0B338, 4, 0x0),
                    'LSECRXSAPN3' : (0x0B33C, 4, 0x0),
                    'LSECRXSAPN4' : (0x0B340, 4, 0x0),
                    'LSECRXSAPN5' : (0x0B344, 4, 0x0),
                    'LSECRXSAPN6' : (0x0B348, 4, 0x0),
                    'LSECRXSAPN7' : (0x0B34C, 4, 0x0),
                    'LSECRXKEY00' : (0x0B350, 4, 0x0),
                    'LSECRXKEY01' : (0x0B354, 4, 0x0),
                    'LSECRXKEY02' : (0x0B358, 4, 0x0),
                    'LSECRXKEY03' : (0x0B35C, 4, 0x0),
                    'LSECRXKEY10' : (0x0B360, 4, 0x0),
                    'LSECRXKEY11' : (0x0B364, 4, 0x0),
                    'LSECRXKEY12' : (0x0B368, 4, 0x0),
                    'LSECRXKEY13' : (0x0B36C, 4, 0x0),
                    'LSECRXKEY20' : (0x0B370, 4, 0x0),
                    'LSECRXKEY21' : (0x0B374, 4, 0x0),
                    'LSECRXKEY22' : (0x0B378, 4, 0x0),
                    'LSECRXKEY23' : (0x0B37C, 4, 0x0),
                    'LSECRXKEY30' : (0x0B380, 4, 0x0),
                    'LSECRXKEY31' : (0x0B384, 4, 0x0),
                    'LSECRXKEY32' : (0x0B388, 4, 0x0),
                    'LSECRXKEY33' : (0x0B38C, 4, 0x0),
                }

    timesync_reg_info = {
                    'SYSTIML'     : (0x0B600, 4, 0x0),
                    'SYSTIMH'     : (0x0B604, 4, 0x0),
                    'TIMINCA'     : (0x0B608, 4, 0x0),
                    'TIMADJL'     : (0x0B60C, 4, 0x0),
                    'TIMADJH'     : (0x0B610, 4, 0x0),

                    'TSYNCTXCTL'  : (0x0B614, 4, 0x0),
                    'TXSTMPL'     : (0x0B618, 4, 0x0),
                    'TXSTMPH'     : (0x0B61C, 4, 0x0),

                    'TSYNCRXCTL'  : (0x0B620, 4, 0x0),
                    'RXSTMPL'     : (0x0B624, 4, 0x0),
                    'RXSTMPH'     : (0x0B628, 4, 0x0),
                    'RXSATRL'     : (0x0B62C, 4, 0x0),
                    'RXSATRH'     : (0x0B630, 4, 0x0),
                    'RXCFGL'      : (0x0B634, 4, 0xF788), # It's a BE16
                    'RXUDP'       : (0x0B638, 4, 0x1903), # It's a BE16
                }

    interrupt_reg_info = {
                    'ICR'       :   (0x000c0, 4, 0x0), # Interrupt Cause Read
                    'ITR'       :   (0x000c4, 4, 0x0),
                    'ICS'       :   (0x000c8, 4, 0x0),
                    'IMS'       :   (0x000d0, 4, 0x0),
                    'IMC'       :   (0x000d8, 4, 0x0),
                    'IAM'       :   (0x000E0, 4, 0x0),
                }

    stat_reg_info = {
                    'CRCERRS'   :   (0x04000, 4, 0x0),
                    'RXERRC'    :   (0x0400C, 4, 0x0),
                    'GPRC'      :   (0x04074, 4, 0x0),
                    'GPTC'      :   (0x04080, 4, 0x0),
                }

    filter_reg_info = {
                    'ETQF0'     :   (0x05cb0, 4, 0x0),
                    'ETQF1'     :   (0x05cb4, 4, 0x0),
                }

    reg_info_list = [general_reg_info, receive_reg_info, transmit_reg_info,
                     linksec_reg_info, timesync_reg_info, interrupt_reg_info,
                     stat_reg_info, filter_reg_info]

    reg_names =  (list(general_reg_info.keys())
                + list(receive_reg_info.keys())
                + list(transmit_reg_info.keys())
                + list(linksec_reg_info.keys())
                + list(timesync_reg_info.keys())
                + list(interrupt_reg_info.keys())
                + list(stat_reg_info.keys())
                + list(filter_reg_info.keys()))

    # Bitfield definitions
    mdic_bf = Bitfield_LE_Ex({
                    'E'         : 31,       # Error
                    'I'         : 29,       # Interrupt Enable
                    'R'         : 28,       # Ready Bit
                    'OP'        : (27, 26), # Opcode
                    'PHYADDR'   : (25, 21), # PHY Address
                    'REGADDR'   : (20, 16), # PHY Register Address
                    'DATA'      : (15, 0),  # Data
                   })

    ctrl_bf = Bitfield_LE_Ex({
                    'VME'         : 30,       # VLAN Mode Enable
    })

    rctl_bf = Bitfield_LE_Ex({
                    'FLXBUF'    : (30, 27),
                    'SECRC'     : 26,
                    'BSEX'      : 25,
                    'PMCF'      : 23,
                    'BSIZE'     : (17, 16),
                    'BAM'       : 15,
                    'MO'        : (13, 12),
                    'DTYP'      : (11, 10), # 00 -- Legacy, 01 - Packet split
                    'RDMTS'     : (9, 8),
                    'LPE'       : 5,
                    'MPE'       : 4,
                    'UPE'       : 3,
                    'SBP'       : 2,
                    'EN'        : 1,
                   })

    srrctl_bf = Bitfield_LE_Ex({
            'DROP_EN'        : 31,
            'DESCTYPE'       : (27, 25),
            'RDMTS'          : (24, 20),
            'BSIZEHEADER'    : (11, 8),
            'BSIZEPACKET'    : (6, 0),
            })

    rfctl_bf = Bitfield_LE_Ex({
                    'EXSTEN'    : 15,
                    'IPFRSP_DIS': 14,
                    'ACKD_DIS'  : 13,
                    'ACKDIS'    : 12,
                    'NFS_VER'   : (9, 8),
                    'NFSR_DIS'  : 7,
                    'NFSW_DIS'  : 6,
                    'ISCSI_DWC' : (5, 1),
                    'ISCSI_DIS' : 0,
                   })

    psrctl_bf = Bitfield_LE_Ex({
                    'BSIZE0'    : (6, 0),    # Receive buffer size for buffer 0
                    'BSIZE1'    : (13, 8),   # Receive buffer size for buffer 1
                    'BSIZE2'    : (21, 16),  # Receive buffer size for buffer 2
                    'BSIZE3'    : (29, 24),  # Receive buffer size for buffer 3
                   })

    rx_status_bf = Bitfield_LE_Ex({
                    'PIF'       : 7, # Passed In-Exact Filter
                    'IPCS'      : 6, # IPv4 Checksum Calculated on Packet
                    'TCPCS'     : 5, # TCP Checksum Calculated on Packet
                    'UDPCS'     : 4, # UDP Checksum Calculated on Packet
                    'VP'        : 3, # Packet is 802.1q
                    'EOP'       : 1, # End-of-Packet
                    'DD'        : 0, # Descriptor Done
                   })

    ex_rx_status_bf = Bitfield_LE_Ex({
                    'RXE'       : 31, # Rx Data Error
                    'IPE'       : 30, # IPv4 Checksum Error
                    'TCPE'      : 29, # TCP/UDP Checksum Error
                    'CE'        : 24, # CRC Error or Alignment Error

                    'ACK'       : 15, # ACK Packet Identification
                    'UDPV'      : 10, # Valid UDP XSUM
                    'IPIDV'     : 9,  # IP Identification Valid
                    'TST'       : 8,  # Time Stamp Taken
                    'PIF'       : 7,  # Passed In-Exact Filter
                    'IPCS'      : 6,  # IPv4 Checksum Calculated on Packet
                    'TCPCS'     : 5,  # TCP Checksum Calculated on Packet
                    'UDPCS'     : 4,  # UDP Checksum Calculated on Packet
                    'VP'        : 3,  # Packet is 802.1q
                    'EOP'       : 1,  # End of Packet
                    'DD'        : 0,  # Descriptor Done
                   })

    rx_error_bf = Bitfield_LE_Ex({
                    'RXE'       : 7, # RX Data Error
                    'IPE'       : 6, # IPv4 Checksum Error
                    'TCPE'      : 5, # TCP/UDP Checksum Error
                    'CE'        : 0, # CRC Error or Alignment Error
                   })

    # Split receive descriptor header status bitfield
    srd_header_st_bf = Bitfield_LE_Ex({
                    'HLEN'      : (9, 0),   # Header Length
                    'HDRSP'     : 15,       # Header split
                   })

    mrq_bf = Bitfield_LE_Ex({
                    'Q'         : (12, 8), # Queue Index
                    'RT'        : (3, 0),  # RSS Type
                   })


    rah_bf = Bitfield_LE_Ex({
                    'AV'        : 31,       # Address Valid
                    'VIND'      : 18,       # VMDq Output Index
                    'ASEL'      : (17, 16), # Address Select
                    'RAH'       : (15, 0),  # Receive Address High
                   })

    rxcsum_bf = Bitfield_LE_Ex({
                    'PCSD'      : 13,     # Packet Checksum Disable
                    'IPPCSE'    : 12,     # IP Payload Checksum Enable
                    'TUOFLD'    : 9,      # TCP Checksum Off-load Enable
                    'IPOFLD'    : 8,      # IP Checksum Off-load Enable
                    'PCSS'      : (7, 0), # Packet Checksum Start
                   })

    linksec_bf = Bitfield_LE_Ex({
                    'LSECE'     : (6, 5), # LinkSec Error Code
                    'SAINDX'    : (3, 1), # SA Index
                    'LSECH'     : 0,      # LinkSec Valid
                   })

    # Filtering registers
    mrqc_bf = Bitfield_LE_Ex({
                    'RFE'       : (21, 16), # RSS Field Enable
                    'MRQE'      : (1, 0),   # Multiple Receive Queues Enable
                   })

    rssim_bf = Bitfield_LE_Ex({
                    'RIM'       : (31, 0), # RSS Interrupt Mask
                   })

    rssir_bf = Bitfield_LE_Ex({
                    'RIR'       : (31, 0), # RSS Interrupt Request
                   })


    # Transmit relating bitfields
    l_td_cmd_bf = Bitfield_LE_Ex({
                    'IDE'       : 7, # Interrupt Delay Enable
                    'VLE'       : 6, # VLAN Packet Enable
                    'DEXT'      : 5, # Extension
                    'RS'        : 3, # Report Status
                    'IC'        : 2, # Insert Checksum
                    'IFCS'      : 1, # Insert FCS
                    'EOP'       : 0, # End-of-Packet
                   })

    l_td_sta_bf = Bitfield_LE_Ex({
                    'RSV'       : (7, 3), # Reserved
                    'LC'        : 2, # Late Collision
                    'EC'        : 1, # Excess Collision
                    'DD'        : 0, # Descriptor Done
                   })


    l_td_special_bf = Bitfield_LE_Ex({
                    'PRI'       : (15, 13), # User Priority
                    'CFI'       : 12,       # Canonical Form Indicator
                    'VLAN'      : (11, 0),  # VLAN Identifier
                   })

    # Context transmit descriptor bitfields
    c_td_tucmd_bf = Bitfield_LE_Ex({
                    'IDE'       : 31,       # Interrupt Delay Enable
                    'SNAP'      : 30,
                    'DEXT'      : 29,       # Descriptor Extension
                    'RS'        : 27,       # Report Status
                    'TSE'       : 26,       # TCP Segmentation Enable
                    'IP'        : 25,       # Packet Type(IPv4 = 1b, IPv6 = 0b)
                    'TCP'       : 24,       # Packet Type(TCP = 1b)
                    'DTYP'      : (23, 20),
                    'PAYLEN'    : (19, 0),
                   })

    c_td_sta_bf = Bitfield_LE_Ex({
                    'DD'        : 0,        # Descriptor Done
                   })

    # TCP/IP data descriptor bitfields
    d_td_cmd_bf = Bitfield_LE_Ex({
                    'IDE'       : 31,
                    'VLE'       : 30,       # VLAN Enable
                    'DEXT'      : 29,
                    'ILSec'     : 28,       # Includes LinkSec encapsulation and LinkSec processing
                    'RS'        : 27,
                    'TSE'       : 26,
                    'IFCS'      : 25,       # Insert IFCS
                    'EOP'       : 24,       # End-Of-Packet
                    'DTYP'      : (23, 20),
                    'DTALEN'    : (19, 0),
                   })

    d_td_sta_bf = Bitfield_LE_Ex({
                    'TS'        : 4,        # Time Stamp
                    'DD'        : 0,        # Descriptor Done
                   })

    d_td_popts_bf = Bitfield_LE_Ex({
                    'TXSM'      : 1,        # Insert TCP/UDP Checksum
                    'IXSM'      : 0,        # Insert IP Checksum
                   })


    tctl_bf = Bitfield_LE_Ex({
                    'RRTHRESH'  : (30, 29), # Read Request Threshold
                    'RTLC'      : 24,       # Re-transmit on Late Collision
                    'SWXOFF'    : 22,       # Software XOFF Transmission
                    'COLD'      : (21, 12), # Collision Distance
                    'CT'        : (11, 4),  # Collision Threshold
                    'PSP'       : (3),      # Pad Short Packets
                    'EN'        : (1),      # Transmit Enable
                   })

    tidv_bf = Bitfield_LE_Ex({
                    'FDP'       : 31,       # Flush Partial Description Block
                    'IDV'       : (15, 0),  # Interrupt Delay Value
                   })

    ims_bf = Bitfield_LE_Ex({
                    'TXQE'      : 1,        # Transmit Queue Empty
                    'TXDW'      : 0,        # Transmit Descriptor Written Back
                    'RXTO'      : 7,        # Receive Timer Interrupt
                    'RXDMTO'    : 4,        # Receive Desc Min Threshold
                    })

    icr_bf = Bitfield_LE_Ex({
                    'TXQE'      : 1,        # Transmit Queue Empty
                    'TXDW'      : 0,        # Transmit Descriptor Written Back
                    'RXTO'      : 7,        # Receive Timer Interrupt
                    'RXDMTO'    : 4,        # Receive Desc Min Threshold
                    'INT_ASS'   : 31,       # Interrupt Asserted
                    })

    # LinkSec register bitfields
    lsectxctrl_bf = Bitfield_LE_Ex({
                    'LSTXEN'    : (1, 0),   # LinkSec TX Enable
                    'PNID'      : (2),      # PN Increase Disabled
                    'AISCI'     : (5),      # Always Include SCI
                    'PNTRH'     : (31, 8),  # PN Exhaustion Threshold
                   })

    lsecrxctrl_bf = Bitfield_LE_Ex({
                    'LSRXEN'    : (3, 2),   # LinkSec RX Enable
                    'PPLSH'     : (6),      # Post LinkSec Header
                    'RP'        : (7),      # Replay Protect
                   })

    lsectxsch_bf = Bitfield_LE_Ex({
                    'SecYH'     : (15, 0),  # MAC Address SecY High
                    'PI'        : (31, 16), # Port Identifier
                   })

    lsectxsa_bf = Bitfield_LE_Ex({
                    'AN0'       : (1, 0),   # Association Number 0
                    'AN1'       : (3, 2),   # Association Number 1
                    'SelSA'     : (4),      # SA Select
                    'ActSA'     : (5),      # Active SA
                   })

    lsecrxsch_bf = Bitfield_LE_Ex({
                    'MAH'       : (15, 0),  # MAC Address SecY High
                    'PI'        : (31, 16), # Port Identifier
                   })

    lsecrxsa_bf = Bitfield_LE_Ex({
                    'AN'        : (1, 0),   # Association Number
                    'SAV'       : (2),      # SA Valid
                    'FRR'       : (3),      # Frame Received
                    'Retired'   : (4),      # Retired
                   })

    # TimeSync register bitfields
    tsynctxctl_bf = Bitfield_LE_Ex({
                    'TXTT'      : (0),      # TX time stamp valid
                    'EN'        : (4),      # Enable TX timestamp
                   })

    tsyncrxctl_bf = Bitfield_LE_Ex({
                    'RXTT'      : (0),      # RX time stamp valid
                    'TYPE'      : (3, 1),   # Type of packets to timestamp
                    'EN'        : (4),      # Enable RX timestamp
                   })
    rxsatrh_bf = Bitfield_LE_Ex({
                    'SRCIDH'    : (15, 0),  # Source UUID high 16-bit
                    'SEQID'     : (31, 16), # Sequence ID
                   })

    rxcfgl_bf  = Bitfield_LE_Ex({
                    'PTPL2'     : (15, 0),  # PTP L2 Ether Type
                    'V1'        : (23, 16), # V1 control to time stamp
                    'V2'        : (31, 24), # V2 message ID to time stamp
                   })

    timinca_bf = Bitfield_LE_Ex({
                    'IV'        : (23, 0),  # Increment value
                    'IP'        : (31, 24), # Increment period
                   })


    etqf_bf = Bitfield_LE_Ex({
                    'QUEUE_ENABLE'  : (31), # Queue Enable
                    'TIME_STAMP'    : (30), # IEEE1588 Time Stamp
                    'IMMEDIATE_INTERRUPT' : (29), # Immediate Interrupt
                    'FILTER_ENABLE' : (26), # Filter Enable
                    'ETYPE_LENGTH_ENABLE' : (25), # Ethernet Type Length Enable
                    'ETYPE_LENGTH'  : (24, 20), # Ethernet Type Length
                    'RX_QUEUE'      : (19, 16), # Queue Index
                    'ETYPE'         : (15, 0),  # Ethernet Type
                   })


def offset_of(reg_name):
    for info in IchLanConst.reg_info_list:
        if reg_name in info:
            return info[reg_name][0]
    assert 0

def addr_of(reg_name):
    return ICH9_LAN_REG_BASE + offset_of(reg_name)

def size_of(reg_name):
    for info in IchLanConst.reg_info_list:
        if reg_name in info:
            return info[reg_name][1]
    assert 0

def bits_of(reg_name):
    return 8 * size_of(reg_name)

def default_of(reg_name):
    for info in IchLanConst.reg_info_list:
        if reg_name in info:
            return info[reg_name][2]
    assert 0

class Phy_8256x(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()
        self.pkt_cnt = 0
        self.recv_pkt = []

    class ieee_802_3_phy_v2(pyobj.Interface):
        def send_frame(self, buf, replace_crc):
            self._up.recv_pkt.append(db_to_list(buf))
            return 0 # The frame was sent to the link

        def check_tx_bandwidth(self):
            #print "check_tx_bandwidth: "
            return 1 # There're some bandwidth

        def add_mac(self, mac):
            print("add_mac: ")

        def del_mac(self, mac):
            print("del_mac: ")

        def add_mac_mask(self, mac, mask):
            print("add_mac_mask: ")

        def del_mac_mask(self, mac, mask):
            print("del_mac_mask: ")

        def set_promiscous_mode(self, enable):
            print("set_promiscous_mode: ")

    class recv_pkt(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = '[[i*]*]'
        def getter(self):
            return self._up.recv_pkt
        def setter(self, val):
            self._up.recv_pkt = val


class Mii_8256x(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()
        self.mii_frame_cnt = 0
        self.r_phy = 0
        self.r_reg = 0
        self.r_val = 0
        self.w_phy = 0
        self.w_reg = 0
        self.w_val = 0

    class mii_management(pyobj.Interface):
        def serial_access(self, data_in, clock):
            return 0

        def read_register(self, phy, reg):
            self._up.r_phy = phy
            self._up.r_reg = reg
            return self._up.r_val

        def write_register(self, phy, reg, value):
            self._up.w_phy = phy
            self._up.w_reg = reg
            self._up.w_val = value

    class read_phy(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.r_phy
        def setter(self, val):
            self._up.r_phy = val

    class read_reg(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.r_reg
        def setter(self, val):
            self._up.r_reg = val

    class read_val(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.r_val
        def setter(self, val):
            self._up.r_val = val

    class write_phy(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.w_phy
        def setter(self, val):
            self._up.w_phy = val

    class write_reg(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.w_reg
        def setter(self, val):
            self._up.w_reg = val

    class write_val(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.w_val
        def setter(self, val):
            self._up.w_val = val

class IchLanDriver:
    def __init__(self, tb, ich9_lan_base):
        self.tb = tb
        self.base = ich9_lan_base
        tb.jumbo_frames_supported = True
        tb.rss_multi_processors_supported = True

    def reset_mac(self):
        self.tb.lan.ports.HRESET.signal.signal_raise()
        self.tb.set_bus_master_enabled()

    # Configure the MAC address
    def config_mac_addr(self, queue, addr_tuple):
        mac_addr = int.from_bytes(addr_tuple, 'little')
        self.tb.write_reg("RAL%d" % queue, mac_addr & ((1 << 32) - 1))
        rah_val = IchLanConst.rah_bf.value(RAH = mac_addr >> 32, AV = 1)
        self.tb.write_reg("RAH%d" % queue, rah_val)

    # Configure the working mode of LinkSec TX
    def config_lstx_mode(self, mode):
        self.tb.write_reg("LSECTXCTRL",
                     IchLanConst.lsectxctrl_bf.value(LSTXEN = mode))

    # Configure the working mode of LinkSec RX
    def config_lsrx_mode(self, mode):
        self.tb.write_reg("LSECRXCTRL",
                     IchLanConst.lsecrxctrl_bf.value(LSRXEN = mode))

    # Configure LinkSec TX SCI source MAC address and port identifier
    def config_lstx_smac_addr_pi(self, addr_tuple, pi_val):
        mac_addr = int.from_bytes(addr_tuple, 'big')
        self.tb.write_reg("LSECTXSCL", mac_addr & ((1 << 32) - 1))
        sch_val = IchLanConst.lsectxsch_bf.value(SecYH = mac_addr >> 32, PI = pi_val)
        self.tb.write_reg("LSECTXSCH", sch_val)

    # Configure LinkSec RX SCI source MAC address and port identifier for an AN
    def config_lsrxan_smac_addr_pi(self, an, addr_tuple, pi_val):
        mac_addr = int.from_bytes(addr_tuple, 'big')
        self.tb.write_reg("LSECRXSCL%d" % an, mac_addr & ((1 << 32) - 1))
        sch_val = IchLanConst.lsecrxsch_bf.value(MAH = mac_addr >> 32, PI = pi_val)
        self.tb.write_reg("LSECRXSCH%d" % an, sch_val)

    # Configure the ring of the receive descriptor
    def config_rd_ring(self, rd_base, rd_cnt,
                       queue = 0, descsize = ICH9_LAN_RD_LEN):
        self.tb.write_reg("RDBAL%d" % queue, rd_base)
        self.tb.write_reg("RDBAH%d" % queue, 0)
        self.tb.write_reg("RDLEN%d" % queue, rd_cnt * descsize)
        self.tb.write_reg("RDH%d" % queue, 0)
        self.tb.write_reg("RDT%d" % queue, rd_cnt * descsize)

    # Configure the ring of the transmit descriptor
    def config_td_ring(self, td_base, td_cnt):
        self.tb.write_reg("TDBAL0", td_base)
        self.tb.write_reg("TDBAH0", 0)
        self.tb.write_reg("TDLEN0", td_cnt * ICH9_LAN_TD_LEN)
        self.tb.write_reg("TDH0", 0)
        self.tb.write_reg("TDT0", td_cnt)

    # Configure the receive options
    def config_rx_option(self, store_bad_packet = 0,
                               enable_broadcast_accept = 0,
                               enable_multicast_promisc = 0,
                               enable_unicast_promisc = 0,
                               desc_type = 0):
        self.tb.update_reg("RCTL",
                           SBP = store_bad_packet,
                           BAM = enable_broadcast_accept,
                           MPE = enable_multicast_promisc,
                           UPE = enable_unicast_promisc,
                           DTYP = desc_type)

    # Configure LinkSec TX Key for a secure association
    def config_lstxsa_key(self, sa, key_byte_list):
        if len(key_byte_list) < 16:
            assert 0
        if sa > 0:
            addr = addr_of('LSECTXKEY10')
        else:
            addr = addr_of('LSECTXKEY00')

        for i in range(16):
            self.tb.write_value_le(addr, 8, key_byte_list[i])
            addr = addr + 1

    # Configure LinkSec TX association number for a secure association
    def config_lstxsa_an(self, sa, an):
        if sa > 0:
            self.tb.update_reg('LSECTXSA', AN1 = an)
        else:
            self.tb.update_reg('LSECTXSA', AN0 = an)

    # Configure LinkSec TX packet number for a secure association
    def config_lstxsa_pn(self, sa, pn):
        if sa > 0:
            reg_name = 'LSECTXPN1'
        else:
            reg_name = 'LSECTXPN0'
        self.tb.write_reg(reg_name, pn)

    # Select SA0 or SA1
    def select_sa(self, sa):
        if sa > 0:
            sa = 1
        self.tb.update_reg('LSECTXSA', SelSA = sa)

    # Configure the SA for an association number in RX direction
    def config_lsrxan_sa(self, an, sa):
        if an > 3 or sa > 1:
            assert 0
        rxsa_val = IchLanConst.lsecrxsa_bf.value(AN = an, SAV = 1)
        self.tb.write_reg('LSECRXSA%d' % sa, rxsa_val)

    # Configure LinkSec RX Key for a secure association
    def config_lsrxsa_key(self, sa, key_byte_list):
        if len(key_byte_list) < 16 or sa > 1:
            assert 0
        if sa > 0:
            addr = addr_of('LSECRXKEY10')
        else:
            addr = addr_of('LSECRXKEY00')

        for i in range(16):
            self.tb.write_value_le(addr, 8, key_byte_list[i])
            addr = addr + 1

    # Configure LinkSec RX packet number for a secure association
    def config_lsrxsa_pn(self, sa, pn):
        if sa > 0:
            reg_name = 'LSECRXSAPN1'
        else:
            reg_name = 'LSECRXSAPN0'
        self.tb.write_reg(reg_name, pn)

    def enable_rx(self, to_enable):
        self.tb.update_reg("RCTL", EN = to_enable)

    def enable_tx(self, to_enable):
        self.tb.update_reg("TCTL", EN = to_enable)

    def enable_tm_tx(self, to_enable):
        val = self.tb.read_reg('TIMINCA')
        if val == 0:
            self.init_tm_incremental(6, 125) # See 8256x-SDM page 101

        self.tb.update_reg('TSYNCTXCTL', EN = to_enable)

    def enable_tm_rx(self, to_enable, type = IchLanConst.TM_RX_TYPE_ALL, v1_ctrl = 0, v2_msg_id = 0):
        val = self.tb.read_reg('TIMINCA')
        if val == 0:
            self.init_tm_incremental(6, 125) # See 8256x-SDM page 101

        self.tb.update_reg('RXCFGL',
                           V1 = v1_ctrl,
                           V2 = v2_msg_id)

        self.tb.update_reg('TSYNCRXCTL',
                           EN = to_enable,
                           TYPE = type)

    def init_tm_incremental(self, inc_period, inc_value):
        self.tb.update_reg('TIMINCA',
                           IP = inc_period,
                           IV = inc_value)

# Simple memory operation collection
class MemoryOperator:
    def __init__(self, mem_space):
        self.mem_iface = mem_space.iface.memory_space

    def read_mem(self, addr, size):
        rem_len   = size
        read_addr = addr
        data_tuple = ()
        while rem_len > 0:
            to_read = min(rem_len, SIM_MEM_BLOCK_LEN)
            data_tuple += self.mem_iface.read(None, read_addr, to_read, 0)
            rem_len    -= to_read
            read_addr  += to_read
        return data_tuple

    def write_mem(self, addr, bytes):
        rem_len    = len(bytes)
        write_addr = addr
        index      = 0
        while rem_len > 0:
            to_write = min(rem_len, SIM_MEM_BLOCK_LEN)
            self.mem_iface.write(None, write_addr,
                                 bytes[index:index + to_write], 0)
            rem_len    -= to_write
            index      += to_write
            write_addr += to_write

    def read_value_le(self, addr, bits):
        return int.from_bytes(self.read_mem(addr, bits // 8), 'little')

    def write_value_le(self, addr, bits, value):
        self.write_mem(addr, tuple(value.to_bytes(bits // 8, 'little')))

    def read_reg_le(self, reg_name):
        return self.read_value_le(addr_of(reg_name), bits_of(reg_name))

    def write_reg_le(self, reg_name, reg_val):
        return self.write_value_le(addr_of(reg_name), bits_of(reg_name), reg_val)

class ConfRegs(pyobj.ConfObject):
    class d25p(pyobj.Attribute):
        """The d25p register"""
        attrtype = 'i'
        def _initialize(self):
            self.val = 1
        def getter(self):
            return self.val
        def setter(self, val):
            self.val = val % 2**32
    class cs_conf(pyobj.Port):
        class int_register(pyobj.Interface):
            def read(self, num):
                return self._top.d25p.val if num == 0x3118 else 0

class TestBench:
    def __init__(self, instantiate_lan_device_func, use_legacy_pci_library=True):
        self.use_legacy_pci_library = use_legacy_pci_library
        self.spi_flashes = []
        self.flash_images = []

        # Bus clock
        clk = simics.pre_conf_object('sys_timer_clk', 'clock')
        clk.freq_mhz = sys_timer_mhz
        simics.SIM_add_configuration([clk], None)
        self.sys_clk = conf.sys_timer_clk

        # Main memory and its image
        img = simics.pre_conf_object('main_img', 'image')
        img.size = MAIN_RAM_SIZE
        main_ram = simics.pre_conf_object('main_ram', 'ram')
        main_ram.image = img
        simics.SIM_add_configuration([img, main_ram], None)
        self.main_ram_image = conf.main_img
        self.main_ram = conf.main_ram

        # Memory-spaces
        mem = simics.pre_conf_object('mem', 'memory-space')
        simics.SIM_add_configuration([mem], None)
        self.mem = conf.mem
        self.mem_op = MemoryOperator(self.mem)

        self.io_space = simics.SIM_create_object('memory-space', 'io_space')
        self.conf_space = simics.SIM_create_object('memory-space',
                                                   'conf_space', [])

        # PCI bus
        if use_legacy_pci_library:
            self.pci = simics.SIM_create_object('PCIBus', 'pci',
                                                [['memory', self.mem],
                                                ['io', self.io_space],
                                                ['conf', self.conf_space]])
        else:
            self.pci = simics.SIM_create_object('fake_upstream_target', 'pci',
                                                [['memory', self.mem],
                                                ['io', self.io_space],
                                                ['conf', self.conf_space]])

        # Flash storage ram and its image
        img = simics.pre_conf_object('flash_img', 'image')
        img.size = SPI_FLASH_LEN
        ram = simics.pre_conf_object('flash_ram', 'ram')
        ram.image = img
        simics.SIM_add_configuration([img, ram], None)
        self.flash_image = conf.flash_img
        self.flash_ram = conf.flash_ram
        self.flash_ram.queue = self.sys_clk

        # Pseudo 8256x PHY
        self.phy = simics.SIM_create_object('Phy_8256x', 'phy')

        # Pseudo 8256x MII
        self.mii = simics.SIM_create_object('Mii_8256x', 'mii')

        # AES-GCM cryptographic engine
        aes = simics.pre_conf_object('aes_eng', 'crypto_engine_aes')
        simics.SIM_add_configuration([aes], None)
        self.aes_eng = conf.aes_eng

        # Chipset Config register
        self.lpc = simics.SIM_create_object('ConfRegs', 'lpc')

        # Instantiate the given MAC controller
        instantiate_lan_device_func(self)
        self.lan = conf.lan

        self.mem.map += [
                          [MAIN_RAM_BASE,       self.main_ram,
                                    0, 0, MAIN_RAM_SIZE],
                          [ICH9_LAN_REG_BASE,   [self.lan, "csr"],
                                    0, 0, ICH9_LAN_REG_LEN],
                        ]

        if use_legacy_pci_library:
            self.mem.map += [
                          [ICH9_PCI_CONF_BASE,  [self.lan, "pci_config"],
                                    0, 0, ICH9_PCI_CONF_LEN],
            ]
        else:
            self.mem.map += [
                          [ICH9_PCI_CONF_BASE,  [self.lan, "pcie_config"],
                                    0, 0, ICH9_PCI_CONF_LEN],
            ]

        # The scratch-pad memory
        self.scratch_pad_mem = simics.SIM_create_object("sparse-memory", "scratch_pad_mem")

        # LAN receive descriptor layout
        self.rd_layout = dev_util.Layout_LE(self.scratch_pad_mem,
                        SCRATCH_RD_BASE,
                        {'BUFADDR'  :   (0, 8),
                         'LENGTH'   :   (8, 2),
                         'PKTCSUM'  :   (10, 2),
                         'STATUS0'  :   (12, 1, IchLanConst.rx_status_bf),
                         'ERRORS'   :   (13, 1, IchLanConst.rx_error_bf),
                         'VLANTAG'  :   (14, 2)
                        })
        self.rd_layout.clear()

        # LAN split receive descriptor layout
        self.srd_layout = dev_util.Layout_LE(self.scratch_pad_mem,
                        SCRATCH_SRD_BASE,
                        {'MRQ'      :   (0, 4, IchLanConst.mrq_bf),
                         'IPID'     :   (4, 2), # IP Identification
                         'PKTCSUM'  :   (6, 2), # Packet Checksum
                         'EXSTATUS' :   (8, 4, IchLanConst.ex_rx_status_bf),
                         'LENGTH0'  :   (12, 2),
                         'VLANTAG'  :   (14, 2),
                         'HDRST'    :   (16, 2, IchLanConst.srd_header_st_bf), # Header Status
                         'LENGTH1'  :   (18, 2),
                         'LENGTH2'  :   (20, 2),
                         'LENGTH3'  :   (22, 2),
                         'RSVD'     :   (24, 8),
                        })
        self.srd_layout.clear()

        # LAN extended receive descriptor layout
        self.ex_rd_layout = dev_util.Layout_LE(self.scratch_pad_mem,
                        SCRATCH_EX_RD_BASE,
                        {'MRQ'      :   (0, 3, IchLanConst.mrq_bf),
                         'LINKSEC'  :   (3, 1, IchLanConst.linksec_bf),
                         'RSSHASH'  :   (4, 4),
                         'EXSTATUS' :   (8, 4, IchLanConst.ex_rx_status_bf),
                         'LENGTH'   :   (12, 2),
                         'VLANTAG'  :   (14, 2),
                        })

        self.ex_rd_layout.clear()

        # LAN advanced receive descriptor layout
        self.adv_rd_read_layout = dev_util.Layout_LE(
            self.scratch_pad_mem, SCRATCH_EX_RD_BASE, {
                'word0' : (0, 8, dev_util.Bitfield_LE({
                            'PACKET_BUFFER'  : (63, 0)
                            })),
                'word1' : (8, 8, dev_util.Bitfield_LE({
                            'HEADER_BUFFER'  : (63, 0)
                            }))
                }
            )

        self.adv_rd_read_layout.clear()

        # LAN advanced receive descriptor layout
        self.adv_rd_layout = dev_util.Layout_LE(
            self.scratch_pad_mem, SCRATCH_EX_RD_BASE, {
                'word0' : (0, 8, dev_util.Bitfield_LE({
                            # These 2 are overlaid with RSS hash
                            'PKTCSUM'  :   (63, 48), # Packet Checksum
                            'IPID'     :   (47, 32), # IP Identification
                            'SPH'      :   31,
                            'HDR_LEN'  :   (30, 21),
                            'PKT_TYPE' :   (16, 4),
                            'RSS_TYPE' :   (3, 0)
                            })),
                'word1' : (8, 8, dev_util.Bitfield_LE({
                            'VLANTAG'  :   (63, 48),
                            'PKT_LEN'  :   (47, 32),
                            'RXE'    : 31,
                            'IPE'    : 30,
                            'L4E'    : 29,
                            'SECERR' : (28, 27),
                            'HB0'    : 23,
                            'LB'     : 18,
                            'SECP'   : 17,
                            'TS'     : 16,
                            'STRIPCRC' : 12,
                            'LLINT'  : 11,
                            'UDPV'   : 10,
                            'VEXT'   : 9,
                            'PIF'    : 7,
                            'IPCS'   : 6,
                            'L4I'    : 5,
                            'UDPCS'  : 4,
                            'VP'     : 3,
                            'EOP'    : 1,
                            'DD'     : 0
                            }))
                }
            )

        self.adv_rd_layout.clear()

        # LAN legacy transmit descriptor layout
        self.l_td_layout = dev_util.Layout_LE(self.scratch_pad_mem,
                        SCRATCH_L_TD_BASE,
                        {'BUFADDR'  :   (0, 8),
                         'LENGTH'   :   (8, 2),
                         'CSO'      :   (10, 1), # Checksum Offset
                         'CMD'      :   (11, 1, IchLanConst.l_td_cmd_bf),
                         'STA'      :   (12, 1, IchLanConst.l_td_sta_bf),
                         'CSS'      :   (13, 1), # Checksum Start
                         'SPECIAL'  :   (14, 2, IchLanConst.l_td_special_bf),
                        })
        self.l_td_layout.clear()

        # LAN TCP/IP context descriptor layout
        self.c_td_layout = dev_util.Layout_LE(self.scratch_pad_mem,
                        SCRATCH_C_TD_BASE,
                        {'IPCSS'    :   (0, 1),
                         'IPCSO'    :   (1, 1),
                         'IPCSE'    :   (2, 2),
                         'TUCSS'    :   (4, 1),
                         'TUCSO'    :   (5, 1),
                         'TUCSE'    :   (6, 2),
                         'TUCMD'    :   (8, 4, IchLanConst.c_td_tucmd_bf),
                         'STA'      :   (12, 1, IchLanConst.c_td_sta_bf),
                         'HDRLEN'   :   (13, 1),
                         'MSS'      :   (14, 2)
                        })
        self.c_td_layout.clear()

        # LAN TCP/IP data descriptor layout
        self.d_td_layout = dev_util.Layout_LE(self.scratch_pad_mem,
                        SCRATCH_D_TD_BASE,
                        {'ADDR'     :   (0, 8),     # Data Buffer Address
                         'DCMD'     :   (8, 4, IchLanConst.d_td_cmd_bf), # Descriptor Command
                         'STA'      :   (12, 1, IchLanConst.d_td_sta_bf), # TCP/IP Status
                         'POPTS'    :   (13, 1, IchLanConst.d_td_popts_bf), # Packet Option Field
                         'VLAN'     :   (14, 2), # VLAN field
                        })
        self.d_td_layout.clear()

        # Advanced context descriptor layout
        self.adv_c_td_layout = dev_util.Layout_LE(
            self.scratch_pad_mem, SCRATCH_C_TD_BASE, {
                'word0' : (0, 8, dev_util.Bitfield_LE({
                            'IPSEC_SA_IDX' : (39, 32),
                            'VLAN'         : (31, 16),
                            'MACLEN'       : (15, 9),
                            'IPLEN'        : (8, 0)
                            })),
                'word1' : (8, 8, dev_util.Bitfield_LE({
                            'MSS'          : (63, 48),
                            'L4LEN'        : (47, 40),
                            'IDX'          : (38, 36),
                            'DEXT'         : 29,
                            'DTYP'         : (23, 20),
                            'ENCRYPT'      : 14,
                            'IPSEC_TYPE'   : 13,
                            'L4T'          : (12, 11),
                            'IPV4'         : 10,
                            'SNAP'         : 9,
                            'IPSEC_ESP_LEN' : (8, 0)
                            }))
                }
            )

        self.adv_c_td_layout.clear()

        # Advanced data descriptor layout
        self.adv_d_td_layout = dev_util.Layout_LE(
            self.scratch_pad_mem, SCRATCH_D_TD_BASE, {
                'word0' : (0, 8, dev_util.Bitfield_LE({
                            'BUFADDR'  :   (63, 0),
                            })),
                'word1' : (8, 8, dev_util.Bitfield_LE({
                            'PAYLEN' :   (63, 46),
                            'IPSEC'  : 42,
                            'TXSM'   : 41,
                            'IXSM'   : 40,
                            'CC'     : 39,
                            'IDX'    : (38, 36),
                            'DD'     : 32,
                            'TSE'    : 31,
                            'VLE'    : 30,
                            'DEXT'   : 29,
                            'RS'     : 27,
                            'IFCS'   : 25,
                            'EOP'    : 24,
                            'DTYP'   : (23, 20),
                            'MAC'    : (19, 18),
                            'DTALEN' : (15, 0)
                            }))
                }
            )

        self.adv_d_td_layout.clear()

        # MACsec SecTAG layout
        self.sectag_layout = dev_util.Layout_BE(self.scratch_pad_mem,
                        SCRATCH_MACSEC_SECTAG_BASE,
                        {'ETYPE'    :   (0, 2),
                         'TCI_AN'   :   (2, 1, MACsecConst.sectag_tci_an_bf),
                         'SL'       :   (3, 1, MACsecConst.sectag_sl_bf),
                         'PN'       :   (4, 4),
                         'SMA'      :   (8, 6),
                         'PI'       :   (14, 2),
                        })
        self.sectag_layout.clear()

        # PTP V1 message header layout
        self.ptp_v1_layout = dev_util.Layout_BE(self.scratch_pad_mem,
                        SCRATCH_PTP_V1_BASE,
                        {'VER_PTP'  :   (0, 2),
                         'VER_NET'  :   (2, 2),
                         'SUB_DOM'  :   (4, 16),
                         'TYPE'     :   (20, 1),
                         'SCT'      :   (21, 1), # Source Communication Technology
                         'SRC_UUID' :   (22, 6),
                         'SRC_PID'  :   (28, 2), # Source Port ID
                         'SEQ_ID'   :   (30, 2), # Sequence ID
                         'CTRL'     :   (32, 1),
                         'RSVD'     :   (33, 1),
                         'FLAGS'    :   (34, 2),
                        })
        self.ptp_v1_layout.clear()

        # PTP V2 message header layout
        self.ptp_v2_layout = dev_util.Layout_BE(self.scratch_pad_mem,
                        SCRATCH_PTP_V2_BASE,
                        {'MSG_ID'   :   (0, 1),
                         'VER_PTP'  :   (1, 1),
                         'VES_LEN'  :   (2, 2),  # Vessage Length
                         'SUB_DOM'  :   (4, 1),  # Subdomain Number
                         'RSVD1'    :   (5, 1),
                         'FLAGS'    :   (6, 2),
                         'CORR_NS'  :   (8, 6), # Correction NS
                         'CORR_SUB' :   (14, 2),# Correction Sub NS
                         'RSVD2'    :   (16, 4),
                         'RSVD3'    :   (20, 1),
                         'SCT'      :   (21, 1), # Source Communication Technology
                         'SRC_UUID' :   (22, 6),
                         'SRC_PID'  :   (28, 2), # Source Port ID
                         'SEQ_ID'   :   (30, 2), # Sequence ID
                         'CTRL'     :   (32, 1),
                         'LMP'      :   (33, 1), # Log Message Period
                         'RSVD4'    :   (34, 2),
                        })
        self.ptp_v2_layout.clear()


    # Shortcuts to memory operations
    def read_mem(self, addr, size):
        return self.mem_op.read_mem(addr, size)
    def write_mem(self, addr, bytes):
        return self.mem_op.write_mem(addr, bytes)
    def read_value_le(self, addr, bits):
        return self.mem_op.read_value_le(addr, bits)
    def write_value_le(self, addr, bits, value):
        return self.mem_op.write_value_le(addr, bits, value)
    def read_reg(self, reg_name):
        return self.mem_op.read_reg_le(reg_name)
    def write_reg(self, reg_name, value):
        return self.mem_op.write_reg_le(reg_name, value)

    def scratch_pad_mem_write(self, addr, data):
        t = simics.transaction_t(write=True, data=bytes(data))
        exc = simics.SIM_issue_transaction(self.scratch_pad_mem, t, addr)
        if exc != simics.Sim_PE_No_Exception:
            raise simics.SimExc_Memory


    def scratch_pad_mem_read(self, addr, n):
        t = simics.transaction_t(read=True, size=n)
        exc = simics.SIM_issue_transaction(self.scratch_pad_mem, t, addr)
        if exc != simics.Sim_PE_No_Exception:
            raise simics.SimExc_Memory
        return t.data

    # Special operation to update the fields of a register
    def update_reg(self, reg_name, **new_fields):
        val = self.read_reg(reg_name)
        bf = getattr(IchLanConst, reg_name.lower() + "_bf")
        fields = bf.fields(val)
        #print "val=",val,"fields=",fields,"new_fields=",new_fields
        fields.update(new_fields)
        new_val = bf.value_ex(fields)
        #print "fields=",fields,"new_val=",new_val
        self.write_reg(reg_name, new_val)

    # Clear the receive buffer in the memory
    def clear_rx_buf(self, off = RX_BUF_BASE, len = RX_BUF_LEN):
        for i in range(len // SIM_MEM_BLOCK_LEN):
            self.write_mem(off, tuple([0x00 for j in range(SIM_MEM_BLOCK_LEN)]))
            off += SIM_MEM_BLOCK_LEN

    # Clear the receive descriptor buffer in the memory
    def clear_rx_desc_buf(self, off = RX_DESC_BASE,
                          len = 256 * 16):
        self.write_mem(off, tuple([0x00 for j in range(len)]))

    # Clear the transmit buffer in the memory
    def clear_tx_buf(self):
        off = TX_BUF_BASE
        for i in range(TX_BUF_LEN // SIM_MEM_BLOCK_LEN):
            self.write_mem(off, tuple([0x00 for j in range(SIM_MEM_BLOCK_LEN)]))
            off += SIM_MEM_BLOCK_LEN

    # Clear the transmit descriptor buffer in the memory
    def clear_tx_desc_buf(self):
        off = TX_DESC_BASE
        for i in range(TX_DESC_LEN // SIM_MEM_BLOCK_LEN):
            self.write_mem(off, tuple([0x00 for j in range(SIM_MEM_BLOCK_LEN)]))
            off += SIM_MEM_BLOCK_LEN

    # Prepare TX buffer and descriptor for one or more packets
    # at specified address
    #   queue:        TX queue 0 or 1
    #   with_notfiy:  enable the delay interrupt to get a notify
    def prepare_tx_packet(self, tx_pkt, tbuf_addr = TX_BUF_BASE,
                          td_addr = TX_DESC_BASE, queue = 0, with_notify = 1,
                          legacy_td = 1, time_stamp = 0, ifcs = 0):
        # Store the packet into the memory buffer
        self.write_mem(tbuf_addr, tuple(tx_pkt))
        td_cnt = ICH9_LAN_MIN_TD_CNT
        next_td = td_addr

        if legacy_td == 0:
            # Prepare the context for this TCP/IP segmentation
            ipv4_ipv6 = "ipv4"
            tcp_udp = "tcp"
            enable_vlan = 0
            hdr_len = TestData.get_pkt_hdr_len(ipv4_ipv6, tcp_udp, enable_vlan)
            payload_len = len(tx_pkt) - hdr_len
            self.c_td_layout.TUCMD.PAYLEN = payload_len
            self.c_td_layout.TUCMD.DTYP   = ICH9_LAN_TCP_IP_C_TD_TYPE
            self.c_td_layout.TUCMD.DEXT   = 1
            self.c_td_layout.TUCMD.TSE    = 0 # Disable the TCP segmentation
            self.c_td_layout.TUCMD.IDE    = with_notify
            self.c_td_layout.TUCMD.RS     = 1
            self.c_td_layout.TUCMD.IP     = (0, 1)[ipv4_ipv6 == "ipv6"]
            self.c_td_layout.TUCMD.TCP    = (0, 1)[tcp_udp == "tcp"]
            self.c_td_layout.HDRLEN       = hdr_len
            self.c_td_layout.MSS          = 0
            self.write_mem(next_td,
                tuple(self.scratch_pad_mem_read(SCRATCH_C_TD_BASE, ICH9_LAN_C_TD_LEN)))
            next_td += ICH9_LAN_C_TD_LEN

        # Construct the TX descriptor in scratch pad
        if legacy_td:
            self.l_td_layout.BUFADDR  = tbuf_addr
            self.l_td_layout.LENGTH   = len(tx_pkt)
            self.l_td_layout.CMD.EOP  = 1
            self.l_td_layout.CMD.RS   = 1
            self.l_td_layout.CMD.IDE  = with_notify
            self.l_td_layout.CMD.IFCS = ifcs
            self.write_mem(next_td,
                tuple(self.scratch_pad_mem_read(SCRATCH_L_TD_BASE, ICH9_LAN_L_TD_LEN)))
            next_td += ICH9_LAN_L_TD_LEN
        else:
            self.d_td_layout.ADDR         = tbuf_addr
            self.d_td_layout.DCMD.TSE     = 0
            self.d_td_layout.DCMD.DTYP    = 1
            self.d_td_layout.DCMD.DEXT    = 1
            self.d_td_layout.DCMD.DTALEN  = len(tx_pkt)
            self.d_td_layout.DCMD.RS      = 1
            self.d_td_layout.DCMD.VLE     = 0
            self.d_td_layout.DCMD.IDE     = with_notify
            self.d_td_layout.DCMD.EOP     = 1
            self.d_td_layout.STA.TS       = time_stamp
            self.d_td_layout.DCMD.IFCS    = ifcs
            self.write_mem(next_td,
                tuple(self.scratch_pad_mem_read(SCRATCH_D_TD_BASE, ICH9_LAN_D_TD_LEN)))
            next_td += ICH9_LAN_D_TD_LEN

        # Configure the address of the transmit descriptor
        self.write_reg('TDBAL%d' % queue, td_addr)
        self.write_reg('TDBAH%d' % queue, 0)
        self.write_reg('TDLEN%d' % queue, td_cnt * ICH9_LAN_L_TD_LEN)
        self.write_reg('TDH%d' % queue, 0)
        self.write_reg('TDT%d' % queue, (2, 1)[legacy_td])

        # Configure the transmit interrupt delay value
        if with_notify:
            delay_cnt = 888
            # Add 1 to carry in the decimal to one cycle
            delay_cycles = (
                delay_cnt * ICH9_LAN_DELAY_UNIT_IN_US * sys_timer_mhz + 1)
#            self.write_reg('TIDV',
#                           IchLanConst.tidv_bf.value(IDV = delay_cnt, FDP = 1))

        # Configure the MAC address of this LAN
        mac_addr = int.from_bytes(tx_pkt[6:12], 'little')
        rah_val = IchLanConst.rah_bf.value(RAH = mac_addr >> 32, AV = 1)
        self.write_reg('RAL%d' % queue, mac_addr & ((1 << 32) - 1))
        self.write_reg('RAH%d' % queue, rah_val)

        # Enable the TXDW interrupt
        self.write_reg('IMS', IchLanConst.ims_bf.value(TXDW = 1))

        return delay_cycles

    # Prepare RX buffer and descriptor to receive packets from network
    #   queue:        RX queue 0 or 1
    #   split_rd:     whether to use split receive descriptor
    #   buf_cnt:      buffer count to contain packet portions in a split
    #   buf_size:     buffer size in the unit of KB
    def prepare_to_rx_packet(self, rbuf_addr = RX_BUF_BASE,
            buf_len = RX_BUF_LEN, rd_addr = RX_DESC_BASE,
            rd_cnt = ICH9_LAN_MIN_RD_CNT, queue = 0,
            split_rd = 0, buf_cnt = 4, buf_size = 4):

        self.clear_rx_buf(rbuf_addr, buf_len)

        desc_size = (SCRATCH_SRD_LEN, ICH9_LAN_RD_LEN)[split_rd == 0]
        self.clear_rx_desc_buf(rd_addr, rd_cnt * desc_size)

        # Prepare the receive descriptor(s) in the memory
        for i in range(rd_cnt):
            if split_rd:
                pad_addr = SCRATCH_SRD_BASE
                buf_addr = rbuf_addr + i * buf_cnt * (buf_size << 10)
                self.srd_layout.clear()
                for j in range(buf_cnt):
                    self.scratch_pad_mem_write(
                        pad_addr,
                        buf_addr.to_bytes(8, 'little'))
                    pad_addr += 8
                    buf_addr += (buf_size << 10)
                self.write_mem(rd_addr + i * SCRATCH_SRD_LEN,
                               tuple(self.scratch_pad_mem_read(
                            SCRATCH_SRD_BASE, SCRATCH_SRD_LEN)))
            else:
                self.rd_layout.clear()
                self.rd_layout.BUFADDR = rbuf_addr + i * (buf_size << 10)
                self.rd_layout.LENGTH = 0
                self.write_mem(rd_addr + i * ICH9_LAN_RD_LEN,
                               tuple(self.scratch_pad_mem_read(
                            SCRATCH_RD_BASE, ICH9_LAN_RD_LEN)))

        # Configure the address of the receive descriptor
        self.write_reg("RDBAL%d" % queue, rd_addr)
        self.write_reg("RDBAH%d" % queue, 0)
        self.write_reg("RDLEN%d" % queue, rd_cnt * desc_size)
        self.write_reg("RDH%d" % queue, 0)
        self.write_reg("RDT%d" % queue, rd_cnt - 1)

        if split_rd:
            self.update_reg("RFCTL", EXSTEN = 1)

    # Prepare RX buffer and descriptor to receive packets from network
    #   queue:        RX queue
    #   buf_cnt:      buffer count to contain packet portions in a split
    #   desc_type:    descriptor type
    #   head_buf_size: header buffer size in the unit of 64 bytes
    #   buf_size:     buffer size in the unit of KB
    def adv_prepare_to_rx_packet(self, rbuf_addr = RX_BUF_BASE,
            buf_len = RX_BUF_LEN, rd_addr = RX_DESC_BASE,
            rd_cnt = ICH9_LAN_MIN_RD_CNT, queue = 0,
            desc_type = 1, head_buf_size = 4, buf_size = 2):

        self.clear_rx_buf(rbuf_addr, buf_len)

        # Clear the receive descriptors in memory
        rd_len = rd_cnt * 16
        self.write_mem(rd_addr, tuple([0x00 for j in range(rd_len)]))

        # Prepare the receive descriptors in memory
        pad_addr = SCRATCH_EX_RD_BASE
        head_addr = rbuf_addr
        buf_addr = rbuf_addr + (head_buf_size << 6)
        self.adv_rd_layout.clear()
        if desc_type == 1:
            self.scratch_pad_mem_write(pad_addr,
                                       head_addr.to_bytes(8, 'little'))
        else:
            self.scratch_pad_mem_write(pad_addr,
                                       buf_addr.to_bytes(8, 'little'))
            self.scratch_pad_mem_write(pad_addr + 8,
                                       head_addr.to_bytes(8, 'little'))

        self.write_mem(rd_addr, tuple(self.scratch_pad_mem_read(
                    SCRATCH_EX_RD_BASE, SCRATCH_SRD_LEN)))

        # Configure the address of the receive descriptor
        self.write_reg("RDBAL%d" % queue, rd_addr)
        self.write_reg("RDBAH%d" % queue, 0)
        self.write_reg("RDLEN%d" % queue, rd_cnt * ICH9_LAN_RD_LEN)
        self.write_reg("RDH%d" % queue, 0)
        self.write_reg("RDT%d" % queue, rd_cnt - 1)

        # Set up descriptor type and buffer lengths
        self.write_reg("SRRCTL%d" % queue, IchLanConst.srrctl_bf.value(
                BSIZEPACKET = buf_size, # Kbytes
                BSIZEHEADER = head_buf_size, # *64 bytes
                DESCTYPE = desc_type
                ))

    def set_bus_master_enabled(self):
        if self.use_legacy_pci_library:
            self.lan.pci_config_command = 0x4  # BME
        else:
            self.pcie_config.command.write(dev_util.READ, m=1)


#tb = TestBench('ICH10')
#lan_drv = IchLanDriver(tb, ICH9_LAN_REG_BASE)

def gen_eth_frame(da, sa, type, length):
    eth_frame = list((i * 113) & 0xFF for i in range(length))

    # Prepare the destination address and type
    eth_frame[0:6] = list(dev_util.value_to_tuple_be(da, 6))
    eth_frame[6:12] = list(dev_util.value_to_tuple_be(sa, 6))
    eth_frame[12:14] = list(dev_util.value_to_tuple_be(type, 2))
    return eth_frame

def tuple_to_db(t):
    return bytes(t)

def db_to_list(db):
    return list(db)


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
