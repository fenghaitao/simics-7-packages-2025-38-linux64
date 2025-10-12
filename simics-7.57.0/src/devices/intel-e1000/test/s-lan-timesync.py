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


# s-lan-timesync.py
# tests the TimeSync stamping in RX/TX

# Tested data flow:

from tb_lan import *

tb.lan.log_level = 1

cur_cycle = 0

def get_cur_stamp():
    cur_stamp = cur_cycle * 1000.0 / sys_timer_mhz
    cur_stamp = (cur_stamp * 0.048 / 6) * 125.0
    return int(cur_stamp)

def test_tm_tx():
    global cur_cycle

    lan_drv.reset_mac()

    random_cycles = 123456789
    simics.SIM_continue(random_cycles)
    cur_cycle += random_cycles
    # Store the packet in the memory and construct a TX descriptor
    tb.prepare_tx_packet(TestData.tcp_pkt, legacy_td = 0, time_stamp = 1)

    # Construct a packet with timestamp to let ICH10 ethernet to TX
    tb.phy.recv_pkt = []

    # Enable time-stamp TX
    lan_drv.enable_tm_tx(1)

    # Enable TX, packet gets timestamped and sent immediately
    lan_drv.enable_tx(1)

    # Check the timestamp
    fields = IchLanConst.tsynctxctl_bf.fields(tb.read_reg('TSYNCTXCTL'))
    expect(fields['TXTT'], 1, "TX time stamp valid")
    stamp = (tb.read_reg('TXSTMPH') << 32) + tb.read_reg('TXSTMPL')
    expect(stamp, get_cur_stamp(), "time stamp stamped on the TX frame")
    fields = IchLanConst.tsynctxctl_bf.fields(tb.read_reg('TSYNCTXCTL'))
    expect(fields['TXTT'], 0, "TX time stamp valid cleared")

# Possible combinations of layer and ptp_ver and msg_t:
#    -- General msg V1 on Layer 4 (msg_t = 1)
#    -- Event msg V1 on Layer 4 (msg_t = 2)
#    -- V2 on Layer 2
#    -- General msg V2 on Layer 4 (msg_t = 1)
#    -- Event msg V2 on Layer 4 (msg_t = 2)
def test_tm_rx(layer = 2, ptp_ver = 2, msg_t = 1):
    global cur_cycle

    lan_drv.reset_mac()

    random_cycles = 0x987654321
    simics.SIM_continue(random_cycles)
    cur_cycle += random_cycles

    if ptp_ver != 2 and ptp_ver != 1:
        assert 0
    if layer != 2 and layer != 4:
        assert 0
    if msg_t != 1 and msg_t != 2:
        assert 0

    v1_control = 0x11
    v2_msg_id  = 0x22
    src_id = int.from_bytes(b'googl?', 'big')
    seq_id = 0xFFFF

    # Duplicate the tcp packet in test data
    ptp_len = pkt_len = len(TestData.udp_pkt)
    if ptp_len < (14 + 20 + 8 + 36):
        ptp_len = 78
    ptp_pkt = [0x00 for i in range(ptp_len)]
    ptp_pkt[0:pkt_len] = TestData.udp_pkt[0:pkt_len]
    # Construct the PTP message in the scratch
    if ptp_ver == 1:
        tb.ptp_v1_layout.VER_PTP = 1
        tb.ptp_v1_layout.CTRL   = v1_control
        tb.ptp_v1_layout.SRC_UUID = src_id
        tb.ptp_v1_layout.SEQ_ID = seq_id
        ptp_msg = tb.scratch_pad_mem_read(
                SCRATCH_PTP_V1_BASE, SCRATCH_PTP_V1_LEN)
    else:
        tb.ptp_v2_layout.MSG_ID = v2_msg_id
        tb.ptp_v2_layout.VER_PTP = 2
        tb.ptp_v2_layout.SRC_UUID = src_id
        tb.ptp_v2_layout.SEQ_ID = seq_id
        ptp_msg = tb.scratch_pad_mem_read(
                SCRATCH_PTP_V2_BASE, SCRATCH_PTP_V2_LEN)
    # Construct a PTP frame on input layer
    if layer == 2:
        ptp_pkt[12:14] = PtpConst.ether_type.to_bytes(2, 'big')
        ptp_pkt[14:50] = ptp_msg
    else:
        if msg_t == 1:
            ptp_pkt[36:38] = PtpConst.udp_general_port.to_bytes(2, 'big')
        else:
            ptp_pkt[36:38] = PtpConst.udp_event_port.to_bytes(2, 'big')
        ptp_pkt[42:78] = ptp_msg

    # Send an ethernet frame to the PHY
    tb.prepare_to_rx_packet()
    lan_drv.config_mac_addr(0, tuple(ptp_pkt[0:6]))
    lan_drv.enable_tm_rx(1, v1_ctrl = v1_control, v2_msg_id = v2_msg_id)
    lan_drv.enable_rx(1)
    tb.lan.iface.ieee_802_3_mac.receive_frame(
        PHY_ADDRESS, tuple_to_db(tuple(ptp_pkt)), 1)

    # Check the timestamp in RX
    fields = IchLanConst.tsyncrxctl_bf.fields(tb.read_reg('TSYNCRXCTL'))
    expect(fields['RXTT'], 1, "RX time stamp valid")
    stamp = (tb.read_reg('RXSTMPH') << 32) + tb.read_reg('RXSTMPL')
    expect(stamp, get_cur_stamp(), "time stamp stamped on the RX frame")
    fields = IchLanConst.tsyncrxctl_bf.fields(tb.read_reg('TSYNCRXCTL'))
    expect(fields['RXTT'], 0, "RX time stamp valid cleared")
    expect_hex(tb.read_reg('RXSATRL'), src_id & ((1 << 32) - 1),
        "source uuid low 32-bit")
    fields = IchLanConst.rxsatrh_bf.fields(tb.read_reg('RXSATRH'))
    expect_hex(fields['SRCIDH'], src_id >> 32, "source uuid high 16-bit")
    expect_hex(fields['SEQID'], seq_id, "sequence id")

def do_test():
    test_tm_tx()
    test_tm_rx(layer = 4, ptp_ver = 1)
    test_tm_rx(layer = 4, ptp_ver = 1, msg_t = 2)
    test_tm_rx(layer = 4)
    test_tm_rx(layer = 4, msg_t = 2)

do_test()
