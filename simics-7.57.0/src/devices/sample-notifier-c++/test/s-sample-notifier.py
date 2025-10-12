# © 2023 Intel Corporation
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

dut = SIM_create_object('sample_notifier_cc', 'dut')
stest.expect_equal(dut.notifier_count, 0)

# Raise the reset signal on dut will trigger the notification send to itself
with stest.expect_log_mgr(dut, log_type="info", regex="Hey, I"):
    dut.iface.signal.signal_raise()
    dut.iface.signal.signal_lower()
stest.expect_equal(dut.notifier_count, 1)
