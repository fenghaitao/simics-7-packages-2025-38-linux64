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


# s-lan-rx-checksum-offloading.py
# tests the receive checksum offloading in the Gigabit LAN Controller in ICH9

from tb_lan import *

tb.lan.log_level = 1

def finish_test(expect_value):
    # Examine the IP header checksum offloading passes the comparison
    tb.scratch_pad_mem_write(SCRATCH_RD_BASE,
                             tb.read_mem(RX_DESC_BASE, ICH9_LAN_RD_LEN))
    expect(tb.rd_layout.STATUS0.IPCS, expect_value["ipcs"],
           "IPv4 header checksum calculated on the packet")
    expect(tb.rd_layout.ERRORS.IPE, expect_value["ipe"],
           "no error in calculating IPv4 header checksum on the packet")

    expect(tb.rd_layout.STATUS0.TCPCS, expect_value["tcpcs"],
           "TCPCS flag not set on the packet")

    expect(tb.rd_layout.STATUS0.UDPCS, expect_value["udpcs"],
           "UDP checksum calculation on the TCP packet")

    expect(tb.rd_layout.ERRORS.TCPE, expect_value["tcpe"],
           "no error in calculating TCP/UDP checksum on the packet")

def prepare_test(eth_frame):
    # Reset the MAC
    lan_drv.reset_mac()

    # Let the MAC do the IP header checksum offloading
    tb.write_value_le(addr_of("RXCSUM"), bits_of("RXCSUM"),
                      IchLanConst.rxcsum_bf.value(IPOFLD = 1,
                                                  TUOFLD = 1,
                                                  PCSS = 14))
    tb.prepare_to_rx_packet()

    lan_drv.config_mac_addr(0, eth_frame[0:6])
    frame_db = tuple_to_db(tuple(eth_frame))
    phy_addr = PHY_ADDRESS
    crc_ok = 0

    # Enable the RX
    lan_drv.config_rx_option(store_bad_packet = 1)
    lan_drv.enable_rx(1)

    return (frame_db, phy_addr, crc_ok)

def do_test(tcp_udp = 1, ipv = 4, zero_udp_cs = False):

    # Configure the MAC address of this LAN
    if ipv == 4:
        if tcp_udp:
            eth_frame = TestData.tcp_pkt[0:]
        else:
            eth_frame = ( TestData.udp_pkt[0:],
                          TestData.udp_pkt_cs_is_0[0:])[zero_udp_cs]
    elif ipv == 6:
        if tcp_udp:
            eth_frame = TestData.tcp_pkt_ipv6[0:]
        else:
            eth_frame = ( TestData.udp_pkt_ipv6[0:],
                          TestData.udp_pkt_ipv6_cs_is_0[0:])[zero_udp_cs]

    expect_value = {
        "ipcs"  : 1,
        "ipe"   : 0,
        "tcpcs" : 1,
        "udpcs" : (1,0)[tcp_udp],
        "tcpe"  : 0,
    }

    (frame_db, phy_addr, crc_ok) =  prepare_test(eth_frame)
    # Send a TCP packet to the MAC
    tb.lan.iface.ieee_802_3_mac.receive_frame(phy_addr, frame_db, crc_ok)

    finish_test(expect_value)

    if (zero_udp_cs and  tcp_udp == 0):
        # Fix eth frame checksum
        eth_frame[-4:] = ( [0xba, 0x60, 0xcb, 0xca],
                           [0xdd, 0x9e, 0xfb, 0xc0]) [ipv == 6]

        expect_value["tcpe"] = (0,1) [ipv == 6]
        udp_cs_offset = (udp_tucso, udp_v6_tucso) [ipv == 6]
        eth_frame[udp_cs_offset: udp_cs_offset + 2] = [0x00,0x00]
        (frame_db, phy_addr, crc_ok) =  prepare_test(eth_frame)
        # Send a TCP packet to the MAC
        tb.lan.iface.ieee_802_3_mac.receive_frame(phy_addr, frame_db, crc_ok)

        finish_test(expect_value)


do_test(tcp_udp = 1)
do_test(tcp_udp = 0)
do_test(tcp_udp = 0, zero_udp_cs = True)
do_test(tcp_udp = 1, ipv = 6)
do_test(tcp_udp = 0, ipv = 6)
do_test(tcp_udp = 0, ipv = 6, zero_udp_cs = True)
