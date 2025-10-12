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


# s-lan-rx-single-queue.py
# tests the packet receiving with single queue
# of Gigabit LAN Controller in ICH9

from tb_lan import *

tb.lan.log_level = 1

def do_test():
    lan_drv.reset_mac()

    rd_addr = RX_DESC_BASE

    # Select the parameters of the test ethernet frame
    eth_frame = TestData.tcp_pkt
    frame_db = tuple_to_db(tuple(eth_frame))
    frame_len = len(eth_frame)
    phy_addr = PHY_ADDRESS
    crc_ok = 0

    tb.prepare_to_rx_packet()

    lan_drv.config_mac_addr(0, tuple(eth_frame[0:6]))

    # Enable the receive function and enable the store-bad-packet option
    tb.write_value_le(addr_of("RCTL"), bits_of("RCTL"),
                      IchLanConst.rctl_bf.value(EN = 1, SBP = 1))

    # Enable the  interrupt
    tb.write_reg('IMS', IchLanConst.ims_bf.value(RXTO = 1, RXDMTO = 1))

    # Verify ICR
    icr = tb.read_reg('ICR')
    expect( icr, 0, "ICR value before RX")

    # Let the PHY send a frame to the MAC
    tb.lan.iface.ieee_802_3_mac.receive_frame(phy_addr, frame_db, crc_ok)

    # Check the frame is stored into the buffer by the MAC
    tb.scratch_pad_mem_write(SCRATCH_RD_BASE,
                             tb.read_mem(rd_addr, ICH9_LAN_RD_LEN))

    expect(tb.rd_layout.LENGTH, frame_len, "Ethernet frame length")
    expect(tb.rd_layout.STATUS0.PIF, 1, "the frame passed in-exact filter")
    expect(tb.rd_layout.STATUS0.EOP, 1, "this buffer is the end of the frame")
    expect(tb.rd_layout.STATUS0.DD, 1, "descriptor is done")
    expect(tb.rd_layout.ERRORS.CE, 1, "CRC error due to no CRC in this frame")

    simics.SIM_continue( 10 )

    # Verify correct interrupts generated
    icr = tb.read_reg('ICR')
    expect(icr, IchLanConst.icr_bf.value(INT_ASS = 1, RXTO = 1, RXDMTO = 0),
           "ICR value after RX (INT_ASS, RXDMTO and RXTO set)")

do_test()
