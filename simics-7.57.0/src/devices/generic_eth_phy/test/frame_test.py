# Test sending frames

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


import stest
import dev_util
import simics
import conf
# SIMICS-21543
conf.sim.deprecation_level = 0

def test_phy_transmit(phy_class):
    class Ieee_802_3_mac_v3(dev_util.Iface):
        iface = "ieee_802_3_mac_v3"
        def __init__(self):
            self.avail = []
            self.status = []
            self.frames = []
        def tx_bandwidth_available(self, sim_obj, addr):
            self.avail.append(addr)
        def receive_frame(self, sim_obj, addr, frame, crc_ok):
            self.frames.append((addr, frame, crc_ok))
        def link_status_changed(self, sim_obj, phy, status):
            pass

    class EthernetCommon(dev_util.Iface):
        iface = "ethernet_common"
        def __init__(self):
            self.frames = []
        def frame(self, sim_obj, frame, crc_status):
            self.frames.append((frame, crc_status))

    mac = dev_util.Dev([Ieee_802_3_mac_v3])
    ep = dev_util.Dev([EthernetCommon])
    clock = simics.pre_conf_object('clock', 'clock')
    clock.freq_mhz = 1000
    phy = simics.pre_conf_object('phy', phy_class)
    phy.queue = clock
    phy.mac = mac.obj
    phy.link = ep.obj
    simics.SIM_add_configuration([clock, phy], None)
    phy, clock = conf.phy, conf.clock

    # Abbreviations
    def send_frame(phy, frame, replace_crc):
        return phy.iface.ieee_802_3_phy_v3.send_frame(frame, replace_crc)
    def check_bandwidth(phy):
        return phy.iface.ieee_802_3_phy_v3.check_tx_bandwidth()

    def test_send_frame(frame, replace_crc):
        stest.expect_equal(send_frame(phy, frame, replace_crc), 0)
        stest.expect_equal(
            ep.ethernet_common.frames,
            [(frame,
              [simics.Eth_Frame_CRC_Unknown, simics.Eth_Frame_CRC_Match][replace_crc])])
        ep.ethernet_common.frames = []

    phy.tx_bandwidth = 0
    for frame in (b'', b'zelenka'):
        for replace_crc in range(2):
            test_send_frame(frame, replace_crc)

    def test_bandwidth_limit(tx_bandwidth, frame, loopback, phy_addr,
                             reject_test):
        '''Bandwidth limit is obeyed, and the MAC is notified when
        bandwidth becomes available.'''
        phy.tx_bandwidth = tx_bandwidth
        phy.address = phy_addr
        stest.expect_equal(check_bandwidth(phy), 1)
        stest.expect_equal(send_frame(phy, frame, 1), 0)
        ep.ethernet_common.frames = []

        delay = int(clock.freq_mhz * 1000000 * len(frame) * 8
                    / tx_bandwidth) if tx_bandwidth else 0

        # in cycles
        if delay:
            simics.SIM_continue(delay - 2)
            # reject_test is either be None or a function that shall
            # trigger a tx_bandwidth_available() call when bandwidth
            # becomes available
            if reject_test:
                reject_test()
            stest.expect_equal(mac.ieee_802_3_mac_v3.avail, [])
            stest.expect_equal(ep.ethernet_common.frames, [])
            simics.SIM_continue(3)
            stest.expect_equal(mac.ieee_802_3_mac_v3.avail,
                               [phy_addr] if reject_test else [])
            mac.ieee_802_3_mac_v3.avail = []

        # After the delay, it's OK to send again
        stest.expect_equal(check_bandwidth(phy), 1)
        stest.expect_equal(send_frame(phy, frame, 1), 0)
        stest.expect_equal(len(ep.ethernet_common.frames), 1)
        # clean up to prepare for the next iteration
        simics.SIM_continue(delay + 1)

    Mbit = 1000000
    for tx_bandwidth in [0, 10*Mbit, 100*Mbit, 1000*Mbit]:
        for frame in [b'', b'a' * 11, b'b' * 173]:
            for loopback in [False, True]:
                for phy_addr in [42, 333333]:
                    for reject_test in [
                            lambda: stest.expect_equal(send_frame(
                                phy, b'x', 1), -1),
                            lambda: stest.expect_equal(check_bandwidth(phy), 0),
                            lambda: (send_frame(phy, b'x', 1),
                                     check_bandwidth(phy)),
                            None]:
                        test_bandwidth_limit(tx_bandwidth, frame, loopback,
                                             phy_addr, reject_test)

    def test_receive_frame(address, frame, crc_status):
        phy.address = address
        phy.iface.ethernet_common.frame(frame, crc_status)
        stest.expect_equal(mac.ieee_802_3_mac_v3.frames,
                           [(address, frame,
                             {simics.Eth_Frame_CRC_Mismatch: 0,
                              simics.Eth_Frame_CRC_Match: 1}[crc_status])])
        mac.ieee_802_3_mac_v3.frames = []

    for frame in [b'', b'foo']:
        for crc_status in [simics.Eth_Frame_CRC_Match,
                           simics.Eth_Frame_CRC_Mismatch]:
            for address in [0, 33]:
                test_receive_frame(address, frame, crc_status)

    def test_delete_object():
        '''Bandwidth limit is obeyed, and the MAC is notified when
        bandwidth becomes available.'''
        frame = b'x' * 64
        phy.tx_bandwidth = tx_bandwidth = 100*Mbit
        stest.expect_equal(send_frame(phy, frame, 1), 0)
        ep.ethernet_common.frames = []

        delay = int(clock.freq_mhz * 1000000 * len(frame) * 8
                    / tx_bandwidth)

        simics.SIM_continue(delay - 2)

        stest.expect_equal(send_frame(phy, b'x', 1), -1) # no bandwidth

        stest.expect_equal(mac.ieee_802_3_mac_v3.avail, [])
        stest.expect_equal(ep.ethernet_common.frames, [])

        # Suddenly DELETE the phy!
        simics.SIM_delete_object(phy)

        simics.SIM_continue(3)

        stest.expect_equal(mac.ieee_802_3_mac_v3.avail, [])
        mac.ieee_802_3_mac_v3.avail = []

    test_delete_object()
