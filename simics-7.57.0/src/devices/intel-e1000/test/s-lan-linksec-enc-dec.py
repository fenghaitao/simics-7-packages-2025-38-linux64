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


# s-lan-linksec-enc-dec.py
# tests the LinkSec(MACsec) encryption in TX and decryption in RX

# Tested data flow:
#   plaintext packet -> upper protocol -> TX -> LinkSec encryption
#   -> ciphertext packet -> PHY -> RX -> LinkSec decryption -> plaintext packet

from tb_lan import *

tb.lan.log_level = 1

# Input parameters:
#     key: secret key
#     pkt: packet, including DA, SA, ether-type
#     sa:  secure association
#     an:  association number
#     pn:  packet number
#     pi:  port identifier
def do_test(key, pkt, sa, an, pn, pi):
    lan_drv.reset_mac()
    if sa > 1:
        sa = 1
    src_mac = pkt[6:12]

    lan_drv.config_lstx_mode(IchLanConst.LSEC_TX_MODE_ENC)
    # Configure the source MAC address and port ID in TX/RX
    lan_drv.config_lstx_smac_addr_pi(src_mac, pi)
    # Configure the TX keys for SA0 or SA1
    lan_drv.config_lstxsa_key(sa, key)
    # Configure TX association numbers for SA0 or SA1
    lan_drv.config_lstxsa_an(sa, an)
    # Configure TX packet numbers for SA0 or SA1
    lan_drv.config_lstxsa_pn(sa, pn)
    # Select the current SA
    lan_drv.select_sa(sa)
    # Store the packet in the memory and construct a TX descriptor
    tb.prepare_tx_packet(pkt, legacy_td = 0)

    tb.phy.recv_pkt = []
    # Enable TX
    lan_drv.enable_tx(1)

    # Continue a delta time
    simics.SIM_continue(1)

    # Store the output encrypted ethernet frame in the PHY
    out_len = len(tb.phy.recv_pkt[0])
    recv_pkt = [0x00 for i in range(out_len)]
    recv_pkt[0:out_len] = tb.phy.recv_pkt[0][0:out_len]

    # Check the "ILSec" bit in TCP/IP data descriptor is set
    d_td_addr = TX_DESC_BASE + ICH9_LAN_C_TD_LEN
    tb.scratch_pad_mem_write(
        SCRATCH_D_TD_BASE, tb.read_mem(d_td_addr, ICH9_LAN_D_TD_LEN))

    # Check the SecTAG parameters are as expected
    tb.scratch_pad_mem_write(SCRATCH_MACSEC_SECTAG_BASE, recv_pkt[12:28])
    expect_hex(tb.sectag_layout.ETYPE, MACsecConst.ether_type,
               "MACsec (802.1AE) Ethernet type")
    expect(tb.sectag_layout.TCI_AN.V,  0, "SecTAG version number")
    expect(tb.sectag_layout.TCI_AN.ES, 0, "SecTAG end station")
    expect(tb.sectag_layout.TCI_AN.SC, 1, "SecTAG secure channel")
    expect(tb.sectag_layout.TCI_AN.SCB,0, "SecTAG single copy broadcast")
    expect(tb.sectag_layout.TCI_AN.E,  1, "SecTAG encrypted")
    expect(tb.sectag_layout.TCI_AN.C,  1, "SecTAG changed text")
    expect(tb.sectag_layout.TCI_AN.AN, an,"SecTAG association number")
    expect(tb.sectag_layout.SL.SL,     0, "SecTAG short length")
    expect(tb.sectag_layout.PN,        pn,"SecTAG packet number")
    expect(tb.sectag_layout.SMA,       dev_util.tuple_to_value_be(src_mac),
                                          "SecTAG source MAC address")
    expect(tb.sectag_layout.PI,        pi,"SecTAG port identifier")

    # Select SA for the AN in the RX direction
    lan_drv.config_lsrxan_sa(an, sa)

    # Configure the RX key for the SA
    lan_drv.config_lsrxsa_key(sa, key)

    # Configure RX source MAC address and port ID for an association number
    lan_drv.config_lsrxan_smac_addr_pi(an, src_mac, pi)

    # Configure the PN for the SA
    lan_drv.config_lsrxsa_pn(sa, pn)

    # Prepare the RX buffer and descriptor to receive the packet
    tb.prepare_to_rx_packet()

    # Configure the MAC address
    lan_drv.config_mac_addr(0, tuple(recv_pkt[0:6]))

    # Enable LinkSec RX to be in decrypt and check integrity mode
    lan_drv.config_lsrx_mode(IchLanConst.LSEC_RX_MODE_STRICT)

    # Enable the RX
    lan_drv.enable_rx(1)

    # Send a frame to ICH10 MAC through the PHY
    tb.lan.iface.ieee_802_3_mac.receive_frame(
        PHY_ADDRESS, tuple_to_db(tuple(recv_pkt)), 1)

    # Get the decrypted frame and check it with original packet
    dec_pkt = list(tb.read_mem(RX_BUF_BASE, len(pkt)))
    expect_list(dec_pkt, pkt, "encrypted-then-decrypted packet")



do_test(TestData.test_key, TestData.tcp_pkt, sa = 1, an = 2, pn = 3, pi = 4)
do_test(TestData.test_key, TestData.tcp_pkt, sa = 0, an = 3, pn = 0, pi = 0)
