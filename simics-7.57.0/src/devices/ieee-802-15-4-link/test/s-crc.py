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


import simics
import dev_util
import stest
import common

simics.SIM_run_command("log-level 1")

[devs, eps, link] = common.create_test_bench()

simics.SIM_run_command('%s.set-rssi %s 5' % (devs[0].name, devs[1].name))

for dev in devs:
    stest.expect_equal(dev.received_frames_count, 0)

# Send message from Node 0 to Node 1 with IEEE_802_15_4_Frame_CRC_Match
devs[0].ep.iface.ieee_802_15_4_link.transmit(b"abcd", 0, 0, 0)
simics.SIM_continue(5)
stest.expect_equal(devs[1].received_frames_count, 1,
                   "The frame should have been received.")

# Send message from Node 0 to Node 1 with IEEE_802_15_4_Frame_CRC_Mismatch
devs[1].received_frames_count = 0
devs[1].lost_frames_count = 0
devs[0].ep.iface.ieee_802_15_4_link.transmit(b"abcd", 0, 0, 1)
simics.SIM_continue(5)
stest.expect_equal(devs[1].received_frames_count, 0,
                   "The frame should have been lost.")
stest.expect_equal(devs[1].lost_frames_count, 0,
                   "Receiver node should not be aware of the lost frame.")

# Send message from Node 0 to Node 1 with IEEE_802_15_4_Frame_CRC16_Unknown
devs[1].received_frames_count = 0
devs[1].lost_frames_count = 0
frame = b'\x01\x02\x03\x04\x05\x06\x07' # incorrect CRC
devs[0].ep.iface.ieee_802_15_4_link.transmit(frame, 0, 0, 2)
simics.SIM_continue(5)
stest.expect_equal(devs[1].received_frames_count, 0,
                   "The frame should have been lost.")
stest.expect_equal(devs[1].lost_frames_count, 0,
                   "Receiver node should not be aware of the lost frame.")

# Send message from Node 0 to Node 1 with IEEE_802_15_4_Frame_CRC16_Unknown
devs[1].received_frames_count = 0
frame = b'\x01\x02\x03\x04\x05\x06\x07\x9e\xd2' # correct CRC
devs[0].ep.iface.ieee_802_15_4_link.transmit(frame, 0, 0, 2)
simics.SIM_continue(5)
stest.expect_equal(devs[1].received_frames_count, 1,
                   "The frame should have been received.")

# Send message from Node 0 to Node 1 with IEEE_802_15_4_Frame_CRC32_Unknown
devs[1].received_frames_count = 0
frame = b'\x01\x02\x03\x04\x05\x06\x07' # incorrect CRC
devs[0].ep.iface.ieee_802_15_4_link.transmit(frame, 0, 0, 3)
simics.SIM_continue(5)
stest.expect_equal(devs[1].received_frames_count, 0,
                   "The frame should have been lost.")
stest.expect_equal(devs[1].lost_frames_count, 0,
                   "Receiver node should not be aware of the lost frame.")

devs[1].received_frames_count = 0
frame = b'\x01\x02\x03\x04\x05\x06\x07\x88\x68\xe4\x70' # correct CRC
devs[0].ep.iface.ieee_802_15_4_link.transmit(frame, 0, 0, 3)
simics.SIM_continue(5)
stest.expect_equal(devs[1].received_frames_count, 1,
                   "The frame should have been received.")
