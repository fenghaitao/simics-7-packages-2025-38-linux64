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

# Expected TOC in lba and msf mode, must match that of the simple_cd_test_file
lba_toc = (0, 18, 1, 1, 0, 20, 1, 0, 0, 0, 0, 0, 0, 20, 170, 0, 0, 0, 0, 182)
msf_toc = (0, 18, 1, 1, 0, 20, 1, 0, 0, 0, 2, 0, 0, 20, 170, 0, 0, 0, 4, 32)
(cdrom, wrapper) = create_with_test_wrapper(simple_cd_test_file)
cdrom.iface.cdrom_media.insert()

wrapper.read_toc_msf = False
toc = wrapper.read_toc
stest.expect_equal(toc, lba_toc)

wrapper.read_toc_msf = True
toc = wrapper.read_toc
stest.expect_equal(toc, msf_toc)

# Simple sanity check, byte (0,1) in the TOC is the length, i.e., 18
stest.expect_equal(lba_toc[1], len(lba_toc) - 2)
