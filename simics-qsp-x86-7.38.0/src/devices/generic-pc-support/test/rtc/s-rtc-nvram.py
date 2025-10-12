# © 2025 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# test RTC NVRAM behavior for bug 16524

import sys
sys.path.append('../../../DS12887/test') # Modify this if running from project

from rtc_tb import *
import rtc_nvram as test

nvram = test.AttrAccess(tb.rtc, 'rtc_ram')
vram = test.AttrAccess(tb.rtc, 'rtc_volatile_ram')
ctrl = test.AttrAccess(tb.rtc, 'rtc_ram_ctrl')
assert len(nvram) == 242
test.run_test(nvram, vram, ctrl, 0xE, 'rtc')
