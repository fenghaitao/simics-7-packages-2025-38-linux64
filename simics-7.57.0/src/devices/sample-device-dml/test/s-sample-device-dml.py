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


import dev_util
import conf
import stest

SIM_run_command("log-level 4")
# Create an instance of the device to test
SIM_add_configuration([pre_conf_object('dev1', 'sample_device_dml')], None)
dev = conf.dev1

# Add register definitions for the device's registers
r1 = dev_util.Register_LE(dev.bank.regs, 0)

# Test that the device behaves as expected
# This is a really simple device and we just check that reads from its register
# returns the expected value
stest.expect_equal(r1.read(), 42)

# Verify that the saved variable behaves as expected
dev.iface.sample.simple_method(0)
stest.expect_equal(r1.read(), 43)
