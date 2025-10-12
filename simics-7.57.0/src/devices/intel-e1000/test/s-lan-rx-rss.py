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


# s-lan-rx-rss.py
# tests the receive-side scaling function
# of the gigabit LAN controller in ICH9/10

# Tested data flow:
# Input packet --> RSS hash --> 32-bit hash value in Rx descriptor
#                           --> Redirection table --> Target processor
#                                                 --> Physical queue

from tb_lan import *

tb.lan.log_level = 1

# RSS verification suite, from "Intel I/O Controller Hub 8/9/10 and
# 82566/82567/82562V Software Developer's Manual", Revision 1.8, Page 55
rss_rk = [
            0x6d, 0x5a, 0x56, 0xda, 0x25, 0x5b, 0x0e, 0xc2,
            0x41, 0x67, 0x25, 0x3d, 0x43, 0xa3, 0x8f, 0xb0,
            0xd0, 0xca, 0x2b, 0xcb, 0xae, 0x7b, 0x30, 0xb4,
            0x77, 0xcb, 0x2d, 0xa3, 0x80, 0x30, 0xf2, 0x0c,
            0x6a, 0x42, 0xb7, 0x3b, 0xbe, 0xac, 0x01, 0xfa,
        ]

rss_ipv4_para = [
    # Destination IP, destination port,
    #   source IP, source port,
    #       hash in "IPv4 only",
    #           hash in "IPv4 with TCP"
    [161, 142, 100, 80, 0x6, 0xE6,
        66, 9, 149, 187, 0xA, 0xEA,
            0x323E8FC2,
                0x51CCC178],
    [65, 69, 140, 83, 0x12, 0x83,
        199, 92, 111, 2, 0x37, 0x96,
            0xD718262A,
                0xC626B0EA],
    [12, 22, 207, 184, 0x94, 0x88,
        24, 19, 198, 95, 0x32, 0x62,
            0xD2D0A5DE,
                0x5C2B394A],
    [209, 142, 163, 6, 0x8, 0xA9,
        38, 27, 205, 30, 0xBC, 0x64,
            0x82989176,
                0xAFC7327F],
    [202, 188, 127, 2, 0x5, 0x17,
        153, 39, 163, 191, 0xAC, 0xDB,
            0x5D1809C5,
                0x10E828A2],
]

rss_ipv6_para = [
    # Destination IP, destination port,
    #   source IP, source port,
    #       hash in "IPv6 only",
    #           hash in "IPv6 with TCP"

    # The first para combination seems to have some printing error
    #[0x3F, 0xFE, 0x25, 0x01, 0x2, 0x00, 0x1F, 0xFF, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x7, 0x6, 0xE6,
    #    0x3F, 0xFE, 0x25, 0x01, 0x2, 0x00, 0x0, 0x3, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1, 0xA, 0xEA,
    #        0x2CC18CD5,
    #            0x40207D3D],
    [0xFF, 0x02, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1, 0x12, 0x83,
        0x3F, 0xFE, 0x5, 0x01, 0x0, 0x8, 0x0, 0x0, 0x2, 0x60, 0x97, 0xFF, 0xFE, 0x40, 0xEF, 0xAB, 0x37, 0x96,
            0x0F0C461C,
                0xDDE51BBF],
    [0xFE, 0x80, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x2, 0x00, 0xF8, 0xFF, 0xFE, 0x21, 0x67, 0xCF, 0x94, 0x88,
        0x3F, 0xFE, 0x19, 0x00, 0x45, 0x45, 0x0, 0x3, 0x2, 0x00, 0xF8, 0xFF, 0xFE, 0x21, 0x67, 0xCF, 0xAC, 0xDB,
            0x4B61E985, 0x02D1FEEF],
]

rss_tcpipv4_hash    = 0
rss_ipv4_hash       = 1
rss_tcpipv6_hash    = 2
rss_ipv6ex_hash     = 3
rss_ipv6_hash       = 4

def do_test(hash_func, queue, processor):
    lan_drv.reset_mac()

    tb.clear_rx_buf()

    tb.prepare_to_rx_packet(rd_cnt = RX_DESC_LEN // BASE_PKT_BUF_SIZE,
                            buf_size = BASE_PKT_BUF_SIZE // 1024,
                            queue = queue)

    lan_drv.config_mac_addr(0, tuple(TestData.tcp_pkt[0:6]))

    # Configure multiple receive queue command register
    tb.write_reg("MRQC", IchLanConst.mrqc_bf.value(RFE = (1 << hash_func), MRQE = 1))
    tb.write_reg("RXCSUM", IchLanConst.rxcsum_bf.value(PCSD = 1))

    # Configure RSS random key
    for i in range(len(rss_rk)):
        tb.write_value_le(addr_of("RSSRK") + i, bits_of("RSSRK"), rss_rk[i])

    rd_addr = RX_DESC_BASE
    rbuf_addr = RX_BUF_BASE
    if hash_func == rss_tcpipv4_hash or hash_func == rss_ipv4_hash:
        para_cnt = len(rss_ipv4_para)
    else:
        para_cnt = len(rss_ipv6_para)
    for para_i in range(para_cnt):
        if hash_func == rss_tcpipv4_hash or hash_func == rss_ipv4_hash:
            test_para = rss_ipv4_para[para_i]
        else:
            test_para = rss_ipv6_para[para_i]
        # Select the parameters of the test ethernet frame
        frame_len = len(TestData.tcp_pkt)
        eth_frame = [0x00 for i in range(frame_len)]
        eth_frame[0:frame_len] = TestData.tcp_pkt
        if hash_func == rss_tcpipv4_hash or hash_func == rss_ipv4_hash:
            eth_frame[eth_dip_v4_off:eth_dip_v4_off + 4] = test_para[0:4]
            eth_frame[eth_dport_v4_off:eth_dport_v4_off + 2] = test_para[4:6]
            eth_frame[eth_sip_v4_off:eth_sip_v4_off + 4] = test_para[6:10]
            eth_frame[eth_sport_v4_off:eth_sport_v4_off + 2] = test_para[10:12]
            crc_ok = 0
        else:
            eth_frame[12] = 0x86
            eth_frame[13] = 0xDD # Ethernet type = 0x86DD to say it's IPv6
            eth_frame[14] = 0x60 # IP version is 6
            eth_frame[20] = 0x6  # Next header is TCP(6)
            eth_frame[eth_dip_v6_off:eth_dip_v6_off + 16] = test_para[0:16]
            eth_frame[eth_dport_v6_off:eth_dport_v6_off + 2] = test_para[16:18]
            eth_frame[eth_sip_v6_off:eth_sip_v6_off + 16] = test_para[18:34]
            eth_frame[eth_sport_v6_off:eth_sport_v6_off + 2] = test_para[34:36]
            crc_ok = 1 # Avoid in checking the checksum
        frame_db = tuple_to_db(tuple(eth_frame))
        phy_addr = PHY_ADDRESS

        # Configure RSS interrupt mask register
        tb.write_reg("RSSIM", 0xFFFFFFFF)

        # Configure redirection table register to route packet to expected queue
        if hash_func == rss_tcpipv4_hash:
            hash_val = test_para[13]
        elif hash_func == rss_ipv4_hash:
            hash_val = test_para[12]
        elif hash_func == rss_tcpipv6_hash:
            hash_val = test_para[37]
        elif hash_func == rss_ipv6_hash:
            hash_val = test_para[36]
        reta_ptr = hash_val & 0x7F

        # Route all packets to queue 0 and processor 0
        for i in range(128):
            tb.write_value_le(addr_of("RETA") + i, bits_of("RETA"), 0)

        # Route the specific packet to the selected queue/cpu
        tb.write_value_le(addr_of("RETA") + reta_ptr, bits_of("RETA"),
                          reta_bf.value(QI = queue, CI = processor))


        # Enable the extended status
        tb.write_reg("RFCTL", IchLanConst.rfctl_bf.value(EXSTEN = 1))
        # Enable the receive function and enable the store-bad-packet option
        tb.write_reg("RCTL", IchLanConst.rctl_bf.value(EN = 1, SBP = 1))

        # Let the PHY send a frame to the MAC
        tb.lan.iface.ieee_802_3_mac.receive_frame(phy_addr, frame_db, crc_ok)

        # Check the frame is stored into the buffer by the MAC
        expect_list(list(tb.read_mem(rbuf_addr, frame_len)), list(eth_frame),
                    "received Ethernet frame")

        # Check the receive descriptor status
        tb.scratch_pad_mem_write(SCRATCH_EX_RD_BASE,
                                 tb.read_mem(rd_addr, ICH9_LAN_RD_LEN))
        expect_hex(tb.ex_rd_layout.RSSHASH, hash_val, "RSS hash value")
        expect(tb.ex_rd_layout.MRQ.RT, hash_func + 1, "RSS hash function")

        # Check the target processor
        if tb.rss_multi_processors_supported:
            expect(tb.read_reg("CPUVEC"), 1 << processor,
                   "RSS target processor")

        rd_addr += ICH9_LAN_RD_LEN
        rbuf_addr += BASE_PKT_BUF_SIZE

# IPv6Ext is no more sense than IPv6 but needs more complex test packets
for hash_func in [rss_tcpipv4_hash, rss_ipv4_hash, rss_tcpipv6_hash, rss_ipv6_hash]:
    do_test(hash_func, 0, 0)
    do_test(hash_func, 1, 0)
    if tb.rss_multi_processors_supported:
        do_test(hash_func, 1, 7)
