# © 2012 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import dev_util,stest
from configuration import *
from common import MiiRegister

loopback_bf = dev_util.Bitfield_LE({'reset' : 15,
                                    'loopback' : 14,
                                    'ss_lsb' : 13,
                                    'an_enable' : 12,
                                    'power_down' : 11,
                                    'isolate' : 10,
                                    'restart_an' : 9,
                                    'duplex_mode' : 8,
                                    'collision_test' : 7,
                                    'ss_msb' : 6,
                                    'unidir_en' : 5,
                                    'reserved' : (4, 0)})

rev_buff = []

def loopback_test(phy_class):
    class Ieee_802_3_mac_v3(dev_util.Iface):
        iface = "ieee_802_3_mac_v3"
        def receive_frame(self, sim_obj, addr, frame, crc_ok):
            global rev_buff
            rev_buff.append((frame, crc_ok))
        def link_status_changed(self, sim_obj, phy, status):
            pass

    def send_frame(phy, frame, replace_crc):
        return phy.iface.ieee_802_3_phy_v3.send_frame(frame, replace_crc)

    mac = dev_util.Dev([Ieee_802_3_mac_v3])
    clock = pre_conf_object('clock', 'clock')
    clock.freq_mhz = 1000
    phy = pre_conf_object('phy', phy_class)
    phy.queue = clock
    phy.mac = mac.obj
    SIM_add_configuration([clock, phy], None)
    phy, clock = conf.phy, conf.clock
    SIM_set_log_level(phy, 4)
    phy.tx_bandwidth = 0
    MiiRegister(phy, 0, loopback_bf).write(loopback = 1)

    global rev_buff

    for frame, replace_crc in zip((b'', b'zelenka'), (0, 1)):
        stest.expect_equal(send_frame(phy, frame, replace_crc), 0,
                           'Send frame')
        SIM_continue(50)
        crc_status = replace_crc
        stest.expect_equal(rev_buff, [(frame, crc_status)],
                           'Recv frame')
        rev_buff = []

loopback_test('generic_eth_phy')
