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


# test RTC NVRAM behavior for bug 16524

import rtc_nvram as test
import common

(rtc, _, _) = common.create_config()

nvram = test.AttrAccess(rtc, 'registers_nvram')
vram = test.AttrAccess(rtc, 'registers_volatile_ram')
ctrl = test.AttrAccess(rtc, 'registers_ram_ctrl')
assert len(nvram) == 114
test.run_test(nvram, vram, ctrl, 0xE, 'registers')
