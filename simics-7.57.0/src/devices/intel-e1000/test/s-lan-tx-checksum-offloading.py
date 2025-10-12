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


# s-lan-tx-checksum-offloading.py
# tests the checksum offloading by the TCP/IP context transmit descriptor
# in the Gigabit LAN Controller in ICH9

from tb_lan import *

tb.lan.log_level = 1
tb.mem.log_level = 1

def do_test(ipv, tup, enable_vlan, enable_delay, payload_len, seg_size):

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

    # Prepare the context for this TCP/IP checksum offloading
    tb.c_td_layout.IPCSS        = tcp_ipcss
    tb.c_td_layout.IPCSO        = tcp_ipcso
    tb.c_td_layout.IPCSE        = tcp_ipcse
    tb.c_td_layout.TUCSS        = TestData.tucs_offsets[ipv][tup]["TUCSS"]
    tb.c_td_layout.TUCSE        = TestData.tucs_offsets[ipv][tup]["TUCSE"]
    tb.c_td_layout.TUCSO        = TestData.tucs_offsets[ipv][tup]["TUCSO"]
    tb.c_td_layout.TUCMD.PAYLEN = payload_len
    tb.c_td_layout.TUCMD.DTYP   = ICH9_LAN_TCP_IP_C_TD_TYPE
    tb.c_td_layout.TUCMD.DEXT   = 1
    tb.c_td_layout.TUCMD.TSE    = 0 # Disable the TCP segmentation
    tb.c_td_layout.TUCMD.IDE    = enable_delay
    tb.c_td_layout.TUCMD.RS     = 1
    tb.c_td_layout.TUCMD.IP     = (1, 0)[ipv == "ipv4"]
    tb.c_td_layout.TUCMD.TCP    = (0, 1)[tup == "tcp"]
    tb.c_td_layout.HDRLEN       = 0 #TestData.get_pkt_hdr_len(ipv4_ipv6, tcp_udp, enable_vlan)
    tb.write_mem(next_td,
        tuple(tb.scratch_pad_mem_read(SCRATCH_C_TD_BASE, ICH9_LAN_C_TD_LEN)))
    next_td += ICH9_LAN_C_TD_LEN

    # Prepare a packet header prototype in the transmit buffer
    tbuf_addr = TX_BUF_BASE
    # We exclude the CRC, since that will be appended because IFCS==1
    eth_pkt = ( (TestData.udp_pkt, TestData.tcp_pkt)
               ,(TestData.udp_pkt_ipv6, TestData.tcp_pkt_ipv6)
              ) [ipv == "ipv6"][tup == "tcp"]

    pkt_len = len(eth_pkt)-4
    pkt = [0x00 for i in range(pkt_len)]
    pkt[0:pkt_len] = eth_pkt[0:pkt_len]
    if ipv == "ipv4":
        pkt[tb.c_td_layout.IPCSO: tb.c_td_layout.IPCSO + 2] = [0x00, 0x00]
        if tup == "tcp":
            pkt[tb.c_td_layout.TUCSO: tb.c_td_layout.TUCSO + 2] = [0xad, 0x2b]
        else:
            pkt[tb.c_td_layout.TUCSO: tb.c_td_layout.TUCSO + 2] = [0x47, 0x23]

    tb.write_mem(tbuf_addr, tuple(pkt))
    tb.d_td_layout.ADDR         = tbuf_addr
    tb.d_td_layout.DCMD.DTYP    = 1
    tb.d_td_layout.DCMD.DEXT    = 1
    tb.d_td_layout.DCMD.DTALEN  = len(pkt)
    tb.d_td_layout.DCMD.RS      = 1
    tb.d_td_layout.DCMD.VLE     = enable_vlan
    tb.d_td_layout.DCMD.IDE     = enable_delay
    tb.d_td_layout.DCMD.IFCS    = 1
    tb.d_td_layout.DCMD.EOP     = 1
    tb.d_td_layout.POPTS.TXSM   = 1
    tb.d_td_layout.POPTS.IXSM   = 1
    tb.write_mem(next_td,
        tuple(tb.scratch_pad_mem_read(SCRATCH_D_TD_BASE, ICH9_LAN_D_TD_LEN)))
    next_td += ICH9_LAN_D_TD_LEN

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

    # Continue a delta time
    simics.SIM_continue(10)

    # Check the frame is stored into the buffer by the MAC
    tb.scratch_pad_mem_write(SCRATCH_C_TD_BASE,
                             tb.read_mem(td_base, ICH9_LAN_C_TD_LEN))
    expect(tb.c_td_layout.STA.DD, 1, "descriptor done in the descriptor status")
    tb.scratch_pad_mem_write(SCRATCH_D_TD_BASE,
                             tb.read_mem(td_base + ICH9_LAN_TD_LEN, ICH9_LAN_D_TD_LEN))
    expect(tb.d_td_layout.STA.DD, 1, "descriptor done in the descriptor status")
    # Compare the packets excluding the CRC

    expect_list(tb.phy.recv_pkt[0][0:pkt_len], eth_pkt[0:pkt_len],
                "Ethernet packet transmitted to the PHY")

    simics.SIM_continue(int(delay_cycles - 1))


for (ipv4_ipv6, tcp_udp, enable_vlan, enable_delay, payload_len, seg_size) in (
        (ipv4_ipv6, tcp_udp, enable_vlan, enable_delay, payload_len, seg_size)
            for ipv4_ipv6 in ("ipv4", "ipv6")
            for tcp_udp in ("tcp", "udp")
            for enable_vlan in (0, ) #, 1)
            for enable_delay in (0, 1)
            for payload_len in (8000, )
            for seg_size in (1500, )):
    do_test(ipv4_ipv6, tcp_udp, enable_vlan, enable_delay, payload_len, seg_size)
