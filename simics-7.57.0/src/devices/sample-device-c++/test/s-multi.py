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

# Create many objects and set the register
for i in range(10):
    dev1 = SIM_create_object('sample_device_cxx_bank_by_code', 'dut' + str(i * 2), [])
    dev1.bank.b[0].r[0] = i
    dev2 = SIM_create_object('sample_device_cxx_bank_by_data',
                             'dut' + str(i * 2 + 1), [])
    dev2.bank.b[0].r[1] = i

# Verify the register value
for i in range(10):
    stest.expect_equal(getattr(conf, 'dut' + str(i * 2)).bank.b[0].r[0], i)
    stest.expect_equal(getattr(conf, 'dut' + str(i * 2 + 1)).bank.b[0].r[1], i)
