# © 2022 Intel Corporation
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
import sample_device_with_external_lib_common

# Create an instance of the device to test
dev = sample_device_with_external_lib_common.create_sample_device_with_external_lib()

# Simple test to ensure the external lib is working as expected
trigger = dev_util.Register_BE(dev.bank.regs, 0x0, 8)

t_1 = 0x12345678
t_2 = 0x90ABCDEF
trigger.write( (t_1 << 32) + t_2 )
stest.expect_equal(trigger.read(), (t_2 << 32) + t_1, 'Incorrect value manipulation by device.')
