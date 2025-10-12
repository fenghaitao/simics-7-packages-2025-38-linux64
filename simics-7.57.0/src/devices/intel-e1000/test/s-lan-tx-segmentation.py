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


# s-lan-tx-segmentation.py
# tests the TCP/UDP segmentation by the TCP/IP context transmit descriptor
# in the Gigabit LAN Controller in ICH9

from tb_lan import *

tb.lan.log_level = 1
tb.mem.log_level = 1

def do_test(ipv4_ipv6, tcp_udp, enable_vlan, enable_delay, seg_size, payload_distribution):
    lan_drv.reset_mac()

    # Clear the transmit buffer in the memory
    off = TX_BUF_BASE
    for i in range(TX_BUF_LEN // SIM_MEM_BLOCK_LEN):
        tb.write_mem(off, tuple([0x00 for j in range(SIM_MEM_BLOCK_LEN)]))
        off += SIM_MEM_BLOCK_LEN

    # Clear the transmit descriptor buffer in the memory
    off = TX_DESC_BASE
    for i in range(TX_DESC_LEN // SIM_MEM_BLOCK_LEN):
        tb.write_mem(off, tuple([0x00 for j in range(SIM_MEM_BLOCK_LEN)]))
        off += SIM_MEM_BLOCK_LEN

    # Select the parameters of the ethernet frame to be transmitted
    delay_cnt = 888
    delay_cycles = delay_cnt * ICH9_LAN_DELAY_UNIT_IN_US * sys_timer_mhz + 1

    td_base = TX_DESC_BASE
    next_td = td_base
    td_cnt  = ICH9_LAN_MIN_L_TD_CNT
    hdr_len = TestData.get_pkt_hdr_len(ipv4_ipv6, tcp_udp, enable_vlan)
    pkt_hdr = TestData.gen_pkt_hdr(ipv4_ipv6, tcp_udp, enable_vlan)
    payload_len = 0
    for i in range(len(payload_distribution)):
        payload_len += payload_distribution[i]
    pkt_data = [i & 0xFF for i in range(payload_len)]

    # Prepare the context for this TCP/IP segmentation
    tb.c_td_layout.TUCMD.PAYLEN = payload_len
    tb.c_td_layout.TUCMD.DTYP   = ICH9_LAN_TCP_IP_C_TD_TYPE
    tb.c_td_layout.TUCMD.DEXT   = 1
    tb.c_td_layout.TUCMD.TSE    = 1 # Enable the TCP segmentation
    tb.c_td_layout.TUCMD.IDE    = enable_delay
    tb.c_td_layout.TUCMD.RS     = 1
    tb.c_td_layout.TUCMD.IP     = (0, 1)[ipv4_ipv6 == "ipv4"]
    tb.c_td_layout.TUCMD.TCP    = (0, 1)[tcp_udp == "tcp"]
    tb.c_td_layout.HDRLEN       = hdr_len
    tb.c_td_layout.MSS          = seg_size
    tb.write_mem(next_td,
        tuple(tb.scratch_pad_mem_read(SCRATCH_C_TD_BASE, ICH9_LAN_C_TD_LEN)))
    next_td += ICH9_LAN_C_TD_LEN

    # Prepare the transmit descriptors as the count required by td_to_use
    tbuf_addr = TX_BUF_BASE
    td_to_use = len(payload_distribution)
    data_off = 0
    for i in range(td_to_use):
        data_cnt = payload_distribution[i]
        to_write = pkt_data[data_off:(data_off + data_cnt)]
        if i == 0:
            to_write = pkt_hdr + to_write
        tb.write_mem(tbuf_addr, tuple(to_write))
        tb.d_td_layout.ADDR         = tbuf_addr
        tb.d_td_layout.DCMD.IFCS    = 1
        tb.d_td_layout.DCMD.TSE     = 1
        tb.d_td_layout.DCMD.DTYP    = 1
        tb.d_td_layout.DCMD.DEXT    = 1
        tb.d_td_layout.DCMD.DTALEN  = len(to_write)
        tb.d_td_layout.DCMD.RS      = 1
        tb.d_td_layout.DCMD.VLE     = enable_vlan
        tb.d_td_layout.DCMD.IDE     = enable_delay
        tb.d_td_layout.DCMD.EOP     = (0, 1)[i == (td_to_use - 1)]
        tb.write_mem(next_td,
            tuple(tb.scratch_pad_mem_read(SCRATCH_D_TD_BASE, ICH9_LAN_D_TD_LEN)))

        next_td += ICH9_LAN_D_TD_LEN
        tbuf_addr = (tbuf_addr + len(to_write) + PAGE_SIZE - 1) & PAGE_MASK
        data_off += data_cnt

    # Configure the address of the transmit descriptor
    tb.write_value_le(addr_of("TDBAL0"),  bits_of("TDBAL0"), td_base)
    tb.write_value_le(addr_of("TDBAH0"),  bits_of("TDBAH0"), 0)
    tb.write_value_le(addr_of("TDLEN0"),  bits_of("TDLEN0"),
                      td_cnt * ICH9_LAN_TD_LEN)
    tb.write_value_le(addr_of("TDH0"),  bits_of("TDH0"), 0)
    tb.write_value_le(addr_of("TDT0"),  bits_of("TDT0"),
                      (next_td - td_base) // ICH9_LAN_TD_LEN)

    # Configure the transmit interrupt delay value
    tidv_val = IchLanConst.tidv_bf.value(IDV = delay_cnt, FDP = 1)
    tb.write_value_le(addr_of("TIDV"), bits_of("TIDV"), tidv_val)

    tb.phy.recv_pkt = []

    # Enable the transmit function
    tb.write_value_le(addr_of("TCTL"), bits_of("TCTL"),
                      IchLanConst.tctl_bf.value(EN = 1))

    # Continue cycles enough for MAC to send out all the segments
    simics.SIM_continue(int((payload_len + 1500)* 8 * 0.1 * sys_timer_mhz))

    # Check the frame is stored into the buffer by the MAC
    tb.scratch_pad_mem_write(SCRATCH_C_TD_BASE,
                             tb.read_mem(td_base, ICH9_LAN_C_TD_LEN))
    expect(tb.c_td_layout.STA.DD, 1, "descriptor done in the descriptor status")
    tb.scratch_pad_mem_write(SCRATCH_D_TD_BASE,
                             tb.read_mem(td_base + ICH9_LAN_TD_LEN, ICH9_LAN_D_TD_LEN))
    expect(tb.d_td_layout.STA.DD, 1, "descriptor done in the descriptor status")

    # Examine the received segmented frames in the PHY
    # (the -4 is for the FCS)
    segments = payload_len // seg_size
    if payload_len % seg_size > 0:
        segments += 1
    expect(len(tb.phy.recv_pkt), segments,
               "segment count after segmentation by MAC")
    for i in range(segments):
        recv = tb.phy.recv_pkt[i]
        ex_len = seg_size + hdr_len
        if i == segments - 1:
            ex_len = hdr_len + payload_len - seg_size * (segments - 1)
        elif tcp_udp == 'tcp':
            tctrl = dev_util.tuple_to_value_be(recv[46:48])
            expect((tctrl >> 3) & 1, 0, 'Cleared PSH')
            expect(tctrl & 1, 0, 'Cleared FIN')
        expect(len(recv)-4, ex_len,
            "length of segmented TCP/UDP packet transmitted to the PHY")
        expect_list(recv[hdr_len:ex_len-4],
                    pkt_data[(i * seg_size):(i * seg_size + ex_len - hdr_len)-4],
                    "segmented TCP/UDP packet data")

    tb.pci.irq_level = 0
    simics.SIM_continue(int(delay_cycles - 1))
    #expect(tb.pci.irq_level, 1, "one interrupt generated from the ICH9 LAN")


for (ipv4_ipv6, tcp_udp, enable_vlan, enable_delay, seg_size,
     payload_distribution) in (
        (ipv4_ipv6, tcp_udp, enable_vlan, enable_delay, seg_size,
         payload_distribution)
            for ipv4_ipv6 in ("ipv4", ) #"ipv6")
            for tcp_udp in ("tcp", "udp")
            for enable_vlan in (0, ) #1)
            for enable_delay in (0, ) #1)
            for seg_size in (1500, )
            for payload_distribution in (
                                        [8000],
                                        [1500],
                                        [800],
                                        [0, 8000],
                                        [1000, 7000],
                                        [0, 3000, 3000, 2000],
                                       )):
    #print "tcp/udp: ", tcp_udp, "distribution: ", payload_distribution
    do_test(ipv4_ipv6, tcp_udp, enable_vlan, enable_delay, seg_size,
            payload_distribution)
