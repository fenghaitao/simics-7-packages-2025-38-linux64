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


# s-lan-tx-legacy-mode.py
# tests the packet transmitting by the legacy transmit descriptor
# in the Gigabit LAN Controller in ICH9

from tb_lan import *

tb.lan.log_level = 1
tb.mem.log_level = 1

def do_test():
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
    tx_pkt = TestData.tcp_pkt
    pkt_len = len(tx_pkt)
    delay_cnt = 888
    # Add 1 to carry in the decimal to one cycle
    delay_cycles = delay_cnt * ICH9_LAN_DELAY_UNIT_IN_US * sys_timer_mhz + 1

    # Prepare the transmit buffer and descriptor
    tbuf_addr = TX_BUF_BASE
    tb.write_mem(tbuf_addr, tuple(tx_pkt))
    td_addr = TX_DESC_BASE
    td_cnt  = ICH9_LAN_MIN_L_TD_CNT
    tb.l_td_layout.BUFADDR  = tbuf_addr
    tb.l_td_layout.LENGTH   = pkt_len
    tb.l_td_layout.CMD.EOP  = 1
    tb.l_td_layout.CMD.RS   = 1
    tb.l_td_layout.CMD.IDE  = 1 # Enable the delay interrupt to get a notify

    tb.write_mem(td_addr,
        tuple(tb.scratch_pad_mem_read(SCRATCH_L_TD_BASE, ICH9_LAN_L_TD_LEN)))

    # Configure the address of the transmit descriptor
    tb.write_value_le(addr_of("TDBAL0"),  bits_of("TDBAL0"), td_addr)
    tb.write_value_le(addr_of("TDBAH0"),  bits_of("TDBAH0"), 0)
    tb.write_value_le(addr_of("TDLEN0"),  bits_of("TDLEN0"), td_cnt * ICH9_LAN_L_TD_LEN)
    tb.write_value_le(addr_of("TDH0"),  bits_of("TDH0"), 0)
    tb.write_value_le(addr_of("TDT0"),  bits_of("TDT0"), 1)

    # Configure the MAC address of this LAN
    lan_drv.config_mac_addr(0, tx_pkt[6:12])

    # Enable the TXDW interrupt
    tb.write_value_le(addr_of('IMS'), bits_of('IMS'),
                                      IchLanConst.ims_bf.value(TXDW = 1))

    tb.pci.irq_level = 0
    tb.phy.recv_pkt = []

    # Enable the transmit function and enable the store-bad-packet option
    tb.write_value_le(addr_of("TCTL"), bits_of("TCTL"),
                      IchLanConst.tctl_bf.value(EN = 1))

    # Continue a delta time
    simics.SIM_continue(1)

    # Check the frame is stored into the buffer by the MAC
    tb.scratch_pad_mem_write(SCRATCH_L_TD_BASE,
                             tb.read_mem(td_addr, ICH9_LAN_L_TD_LEN))
    expect(tb.l_td_layout.STA.DD, 1, "descriptor done in the descriptor status")

    # Examine the received frame in the PHY
    expect_list(tb.phy.recv_pkt, [tx_pkt],
                "Ethernet packet transmitted to the PHY")

    simics.SIM_continue(int(delay_cycles - 1))
    expect(tb.pci.irq_level, 1, "one interrupt generated from the ICH9 LAN")


do_test()
