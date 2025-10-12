# © 2024 Intel Corporation
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

dut = SIM_create_object("sample_device_cxx_port_use_port", "dut_use_port", [])

stest.expect_equal(dut.state, 0)
dut.port.sample[0].iface.signal.signal_raise()
stest.expect_equal(dut.state, 1)
dut.port.sample[1].iface.signal.signal_raise()
stest.expect_equal(dut.state, 3)
dut.port.sample[0].iface.signal.signal_lower()
stest.expect_equal(dut.state, 2)
dut.port.sample[1].iface.signal.signal_lower()
stest.expect_equal(dut.state, 0)

dut = SIM_create_object(
    "sample_device_cxx_port_use_confobject", "dut_use_confobject", [])

stest.expect_equal(dut.port.sample.raised, False)
dut.port.sample.iface.signal.signal_raise()
stest.expect_equal(dut.port.sample.raised, True)
dut.port.sample.iface.signal.signal_lower()
stest.expect_equal(dut.port.sample.raised, False)
