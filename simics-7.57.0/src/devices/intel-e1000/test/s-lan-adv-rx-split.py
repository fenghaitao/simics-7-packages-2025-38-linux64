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


# s-adv-lan-rx-split.py
# tests the header split packet receiving of gigabit LAN Controller

from tb_lan import *

tb.lan.log_level = 1

# Construct a packet to split
short_len = len(TestData.tcp_pkt)
short_pkt = TestData.tcp_pkt

pkt1_len = 1500
pkt1 = [(i & 0xFF) for i in range(pkt1_len)]
pkt1[0:short_len] = TestData.tcp_pkt[0:short_len]

def do_test(pkt, descriptor_type, expected_split_length):
    print("do_test ", descriptor_type, expected_split_length)
    lan_drv.reset_mac()
    pkt_len   = len(pkt)
    buf_start = RX_BUF_BASE
    head_buf_size = 256
    buf_size  = 4096
    rd_start  = RX_DESC_BASE
    lan_drv.config_rx_option(desc_type = 1)

    tb.adv_prepare_to_rx_packet(rbuf_addr = buf_start, rd_addr = rd_start,
                                desc_type = descriptor_type,
                                head_buf_size = (head_buf_size >> 6),
                                buf_size = (buf_size >> 10) )
    lan_drv.config_mac_addr(0, tuple(pkt[0:6]))
    lan_drv.enable_rx(1)

    # Set up split types
    tb.write_reg("PSRTYPE01", 0x0007fffe)

    tb.lan.iface.ieee_802_3_mac.receive_frame(
        PHY_ADDRESS, tuple_to_db(tuple(pkt)), 1)

    # Check the write-back descriptor status
    tb.scratch_pad_mem_write(SCRATCH_EX_RD_BASE,
                             tb.read_mem(rd_start, SCRATCH_EX_RD_LEN))

    header_length = tb.adv_rd_layout.word0.HDR_LEN
    payload_length = tb.adv_rd_layout.word1.PKT_LEN

    expect(tb.adv_rd_layout.word0.SPH, 1, "Packet split performed")
    expect(header_length, expected_split_length, "Split header length")
    expect(payload_length, pkt_len - header_length, "Payload length")

    # Compare stored packet with input packet
    head_addr = buf_start
    buf_addr = buf_start + head_buf_size
    read_pkt = []
    read_pkt += list(tb.read_mem(head_addr, header_length))
    read_pkt += list(tb.read_mem(buf_addr, payload_length))
    expect_list(read_pkt, pkt, "stored packet")


do_test(pkt1, ADV_DESC_SPLIT_ALWAYS_USE_HEADER_BUF, 66)
