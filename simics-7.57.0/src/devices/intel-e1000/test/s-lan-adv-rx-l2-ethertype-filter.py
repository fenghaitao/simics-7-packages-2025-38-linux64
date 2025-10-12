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


# s-lan-rx-l2-ethertype-filter.py
# tests the receive-side L2 ethernet type filter function

# Tested data flow:
# Input packet --> L2 ethertype filter --> Physical queue

from tb_lan import *

tb.lan.log_level = 4

def do_test(queue):
    lan_drv.reset_mac()

    rd_cnt  = RX_DESC_LEN // BASE_PKT_BUF_SIZE

    tb.adv_prepare_to_rx_packet(rd_cnt = rd_cnt, queue = queue)

    # Configure the MAC address of this LAN
    lan_drv.config_mac_addr(0, tuple(TestData.tcp_pkt[0:6]))

    # Configure multiple receive queue command register
    tb.write_reg("MRQC", IchLanConst.mrqc_bf.value(MRQE = 0))

    tb.write_reg("RXCSUM", IchLanConst.rxcsum_bf.value(PCSD = 1))

    tb.write_reg("ETQF%d" % queue,
                 IchLanConst.etqf_bf.value(FILTER_ENABLE = 1,
                                           ETYPE = 0x0800,
                                           RX_QUEUE = queue,
                                           QUEUE_ENABLE = 1))

    rbuf_addr = RX_BUF_BASE

    # Select the parameters of the test ethernet frame
    frame_len = len(TestData.tcp_pkt)
    eth_frame = [0x00 for i in range(frame_len)]
    eth_frame[0:frame_len] = TestData.tcp_pkt
    crc_ok = 1 # Avoid checking the checksum

    frame_db = tuple_to_db(tuple(eth_frame))
    phy_addr = PHY_ADDRESS

    # Enable the extended status
    tb.write_reg("RFCTL", IchLanConst.rfctl_bf.value(EXSTEN = 1))

    # Enable the receive function and enable the store-bad-packet option
    tb.write_reg("RCTL", IchLanConst.rctl_bf.value(EN = 1, SBP = 1))

    # Let the PHY send a frame to the MAC
    tb.lan.iface.ieee_802_3_mac.receive_frame(phy_addr, frame_db, crc_ok)

    # Check the frame is stored into the buffer by the MAC
    expect_list(list(tb.read_mem(rbuf_addr, frame_len)), list(eth_frame),
                "received Ethernet frame")

do_test(0)
do_test(1)
