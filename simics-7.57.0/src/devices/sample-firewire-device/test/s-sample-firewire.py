# © 2013 Intel Corporation
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
import dev_util as du

# Create an instance of the sample firewire device and a clock.
clock = SIM_create_object('clock', 'clock', freq_mhz=100)
firewire_dev = SIM_create_object('sample_firewire_device', 'firewire_dev',
                                 [['queue', clock]])

fw_iface = firewire_dev.iface.firewire_device

node_id = du.Register_BE(firewire_dev.bank.firewire_config_registers, 8, 4,
                         du.Bitfield_BE({'bus_id'    : (0, 9),
                                         'offset_id' : (10, 15)}, bits = 32))

# Test a bus reset to the firewire device
def test_reset(offset_id):
    fw_iface.reset(offset_id, 0, [])
    stest.expect_equal(node_id.offset_id, offset_id)

test_reset(1)

# Write you tests here
