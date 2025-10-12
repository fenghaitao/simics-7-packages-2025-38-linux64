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


from common import *
from stest import expect_equal

# Test the set address request
def set_addr_test(bReq = 0, wVal = 0):
    tablet.device_state = 2
    set_transfer_data(bReq = bReq, wVal = wVal)
    expect_equal(tablet.device_address, wVal)
    expect_equal(tablet.device_state, 1)

# Test the set configuration request
def set_conf_test(bReq = 0, wVal = 0):
    tablet.device_state = 1
    # The bConfigurationValue in the configuration descriptors is 1.
    # Now use the wValue to select it.
    set_transfer_data(bReq = bReq, wVal = wVal)
    expect_equal(tablet.device_state, 2)

set_addr_test(bReq = 5, wVal = 0xff)
set_conf_test(bReq = 9, wVal = 1)
