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


# s-lan-rx-split.py
# tests the split packet receiving of gigabit LAN Controller

from tb_lan import *

tb.lan.log_level = 1

# Construct a long packet to scatter among four split buffers
short_len = len(TestData.tcp_pkt)
short_pkt = TestData.tcp_pkt

pkt2_len = 1500
long_pkt2 = [(i & 0xFF) for i in range(pkt2_len)]
long_pkt2[0:short_len] = TestData.tcp_pkt[0:short_len]

pkt3_len = 6000
long_pkt3 = [(i & 0xFF) for i in range(pkt3_len)]
long_pkt3[0:short_len] = TestData.tcp_pkt[0:short_len]

pkt4_len = 9000
long_pkt4 = [(i & 0xFF) for i in range(pkt4_len)]
long_pkt4[0:short_len] = TestData.tcp_pkt[0:short_len]

def do_test(pkt, buf_cnt):
    print("do_test ", buf_cnt)
    lan_drv.reset_mac()
    pkt_len   = len(pkt)
    buf_start = RX_BUF_BASE
    buf_size  = 4096
    rd_start  = RX_DESC_BASE
    lan_drv.config_rx_option(desc_type = 1)

    tb.prepare_to_rx_packet(rbuf_addr = buf_start, rd_addr = rd_start,
        split_rd = 1, buf_cnt = buf_cnt, buf_size = (buf_size >> 10) )
    lan_drv.config_mac_addr(0, tuple(pkt[0:6]))
    lan_drv.enable_rx(1)

    # Allow long packets
    if pkt_len > 1500:
        rctl = tb.read_reg("RCTL")
        rctl |= IchLanConst.rctl_bf.value(LPE=1)
        tb.write_reg("RCTL", rctl )

    # Set buffer3 size to 2048
    psrctl = tb.read_reg("PSRCTL")
    psrctl &= ~IchLanConst.psrctl_bf.value(BSIZE3=0x3f)
    psrctl |= IchLanConst.psrctl_bf.value(BSIZE3=0x02)
    tb.write_reg("PSRCTL", psrctl )

    tb.lan.iface.ieee_802_3_mac.receive_frame(
        PHY_ADDRESS, tuple_to_db(tuple(pkt)), 1)

    # Compare stored packet with input packet
    index = 0
    buf_addr = buf_start
    def_split_len = [256, 4096, 4096, 2048]
    split_len = [0, 0, 0, 0]
    read_pkt = []
    for i in range(buf_cnt):
        read_len = pkt_len - index
        split_len[i] = def_split_len[i]
        if read_len > split_len[i]:
            read_len = split_len[i]
        read_pkt += list(tb.read_mem(buf_addr, read_len))
        buf_addr += buf_size
        index += read_len
        if index == pkt_len:
            break
    expect_list(read_pkt, pkt[0:index], "stored packet")

    # Check the write-back descriptor status
    tb.scratch_pad_mem_write(SCRATCH_SRD_BASE,
            tb.read_mem(rd_start, SCRATCH_SRD_LEN))
    exp_len0 = split_len[0]
    if exp_len0 > pkt_len:
        exp_len0 = pkt_len
    expect(tb.srd_layout.LENGTH0, exp_len0,
           "count of bytes written to buffer 0")
    exp_len1 = pkt_len - exp_len0
    if exp_len1 > split_len[1]:
        exp_len1 = split_len[1]
    expect(tb.srd_layout.LENGTH1, exp_len1,
           "count of bytes written to buffer 1")
    exp_len2 = pkt_len - exp_len1 - exp_len0
    if exp_len2 > split_len[2]:
        exp_len2 = split_len[2]
    expect(tb.srd_layout.LENGTH2, exp_len2,
           "count of bytes written to buffer 2")
    exp_len3 = pkt_len - exp_len2 - exp_len1 - exp_len0
    if exp_len3 > split_len[3]:
        exp_len3 = split_len[3]
    expect(tb.srd_layout.LENGTH3, exp_len3,
           "count of bytes written to buffer 3")
    expect(tb.srd_layout.HDRST.HLEN, 0, "no header split")
    expect(tb.srd_layout.HDRST.HDRSP, 0, "no header split")
    expect(tb.srd_layout.EXSTATUS.DD, 1, "descriptor done")

if tb.jumbo_frames_supported:
    do_test(long_pkt4, 4)
    do_test(long_pkt3, 3)

do_test(long_pkt2, 2)
do_test(short_pkt, 1)
