# © 2014 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import dev_util
import conf
import stest
import ieee_802_15_4_probe_common

transmit_counter = 0
receive_counter = 0

def snooper_func(user_data, probe, to_side, frame, rssi,
                 channel_page, channel_number, crc_status):
    global transmit_counter
    global receive_counter

    simics.SIM_log_info(1, probe, 0, "snooper_func called")

    if to_side == 0: # transmit
        simics.SIM_log_info(1, probe, 0, "transmit_counter increased")
        transmit_counter += 1
    else: # receive
        simics.SIM_log_info(1, probe, 0, "receive_counter increased")
        receive_counter += 1

[probes, devs, links] = ieee_802_15_4_probe_common.create_ieee_802_15_4_probe()

simics.SIM_run_command('log-level 1')
probes[0].iface.ieee_802_15_4_probe.attach_snooper(snooper_func, None)
probes[1].iface.ieee_802_15_4_probe.attach_snooper(snooper_func, None)

simics.SIM_run_command('%s.set-rssi %s 5' % (devs[0].name, devs[1].name))

stest.expect_equal(transmit_counter, 0)
stest.expect_equal(receive_counter, 0)
devs[0].ep.iface.ieee_802_15_4_link.transmit(b"abcd", 0, 0, 0)
simics.SIM_run_command('run-seconds 1')
stest.expect_equal(transmit_counter, 1)
stest.expect_equal(receive_counter, 1)
