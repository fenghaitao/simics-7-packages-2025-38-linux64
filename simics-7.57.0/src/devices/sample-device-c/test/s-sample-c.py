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


# Sample tests for sample-device-c

import stest

# Create sample the device
c_dev = SIM_create_object('sample-device-c', 'sample_dev_c')

def test_device():
    # Check that value is read correct.
    for val in (0, 10, 73):
        c_dev.attr.value = val
        stest.expect_equal(c_dev.attr.value, val)

    # Check that simple_method outputs log.
    simple_method = c_dev.iface.sample.simple_method
    stest.expect_log(simple_method, (1,), log_type = "info")

test_device()

print("All tests passed.")
