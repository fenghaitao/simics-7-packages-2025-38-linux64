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


# s-lan-rx-addr-filter.py
# tests the address filtering of received packets
# in the Gigabit LAN Controller in ICH9

from tb_lan import *

tb.lan.log_level = 1

ETH_BC_ADDR = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
ETH_MC_ADDR = [0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
ETH_UC_ADDR = [0x00, 0x02, 0x03, 0x04, 0x05, 0x06]

def do_test(mac_addr, to_enable):
    lan_drv.reset_mac()

    tb.prepare_to_rx_packet()

    rd_addr = RX_DESC_BASE

    # Configure the MAC address of this LAN
    enable_broadcast_accept = 0
    enable_multicast_promisc = 0
    enable_unicast_promisc = 0
    eth_frame = TestData.tcp_pkt[0:]
    eth_frame[0:6] = mac_addr

    if (mac_addr == ETH_BC_ADDR):
        enable_broadcast_accept = to_enable
    elif (mac_addr == ETH_MC_ADDR):
        enable_multicast_promisc = to_enable
    else:
        enable_unicast_promisc = to_enable
        # Configure the ICH9 MAC to a different address
        new_mac = mac_addr[0:]
        new_mac[5] += 1
        lan_drv.config_mac_addr(0, new_mac)

    # Select the parameters of the test ethernet frame
    frame_db = tuple_to_db(tuple(eth_frame))
    frame_len = len(eth_frame)
    phy_addr = PHY_ADDRESS
    crc_ok = 0

    # Enable the store-bad-packet option
    lan_drv.config_rx_option(store_bad_packet = 1,
                             enable_broadcast_accept = enable_broadcast_accept,
                             enable_multicast_promisc = enable_multicast_promisc,
                             enable_unicast_promisc = enable_unicast_promisc,
                             )

    # Enable the receive function
    lan_drv.enable_rx(1)

    # Let the PHY send a frame to the MAC
    tb.lan.iface.ieee_802_3_mac.receive_frame(phy_addr, frame_db, crc_ok)

    # Check the frame is stored into the buffer by the MAC
    tb.scratch_pad_mem_write(SCRATCH_RD_BASE,
                             tb.read_mem(rd_addr, ICH9_LAN_RD_LEN))

    if to_enable:
        expect(tb.rd_layout.LENGTH, frame_len, "Ethernet frame length")
        expect(tb.rd_layout.STATUS0.PIF, 0,
               "the frame is not passed in-exact filter")
        expect(tb.rd_layout.STATUS0.EOP, 1,
                "this buffer is the end of the frame")
        expect(tb.rd_layout.STATUS0.DD, 1, "descriptor is done")
        expect(tb.rd_layout.ERRORS.CE, 1,
                "CRC error due to no CRC in this frame")
    else:
        expect(tb.rd_layout.STATUS0.DD, 0, "descriptor is un-touched")


do_test(ETH_BC_ADDR, 1) # Broadcast, enable it
do_test(ETH_BC_ADDR, 0) # Broadcast, disable it

do_test(ETH_MC_ADDR, 1) # Multicast, enable it
do_test(ETH_MC_ADDR, 0) # Multicast, disable it

do_test(ETH_UC_ADDR, 1) # Unicast, enable it
do_test(ETH_UC_ADDR, 0) # Unicast, disable it
