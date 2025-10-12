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


import stest
from cdrom_common import *
import os

# Perform a very simple read-block test. Read all blocks and verify
# that the sum of bytes matches a known good value.
exp_block_sum = {
    16: 45276,
    17: 34357,
    18: 536,
    20: 30,
    22: 30,
    24: 31,
    26: 31,
    28: 8616,
    29: 1500,
    30: 16677,
    31: 7124 }

(cdrom, wrapper) = create_with_test_wrapper(simple_cd_test_file)
cdrom.iface.cdrom_media.insert()

capacity = cdrom.iface.cdrom_media.capacity()

for lba in range(capacity):
    wrapper.read_block_lba = lba
    block = wrapper.read_block
    stest.expect_equal(sum(block), exp_block_sum.get(lba, 0))


stest.untrap_log('error')
wrapper.read_block_lba = capacity
block = wrapper.read_block
# Need to access block to trigger attribute access
stest.expect_exception(stest.expect_different, (block, 0), SimExc_Attribute)
