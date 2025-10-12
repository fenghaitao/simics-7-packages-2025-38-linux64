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

dut1 = SIM_create_object("sample_device_cxx_interface", "dut1", [])

stest.expect_equal(dut1.signal_raised, False)
dut1.iface.signal.signal_raise()
stest.expect_equal(dut1.signal_raised, True)
dut1.iface.signal.signal_lower()
stest.expect_equal(dut1.signal_raised, False)

dut2 = SIM_create_object("sample_device_cxx_user_interface", "dut2", [])

stest.expect_equal(dut2.simple_method_cnt, 0)
dut2.iface.sample.simple_method(0)
stest.expect_equal(dut2.simple_method_cnt, 1)
dut2.iface.sample.simple_method(-1)
stest.expect_equal(dut2.simple_method_cnt, 2)

dut3 = SIM_create_object("sample_device_cxx_interface_c", "dut3", [])

stest.expect_equal(dut3.signal_raised, False)
dut3.iface.signal.signal_raise()
stest.expect_equal(dut3.signal_raised, True)
dut3.iface.signal.signal_lower()
stest.expect_equal(dut3.signal_raised, False)

dut4 = SIM_create_object("sample_device_cxx_interface_with_custom_info", "dut4", [])

stest.expect_equal(dut4.signal_raised, False)
dut4.iface.signal.signal_raise()
stest.expect_equal(dut4.signal_raised, True)
dut4.iface.signal.signal_lower()
stest.expect_equal(dut4.signal_raised, False)
