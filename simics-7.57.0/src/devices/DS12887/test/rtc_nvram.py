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

import stest
import dev_util

def run_test(nvram, vram, ctrl, ram_addr, bank):
    NVRAM_OFFSET = 3
    VRAM_OFFSET = 7

    ram_size = len(nvram)

    assert 111 < ram_size
    for n in (0, 3, 7, 18, 45, 97, 111, ram_size - 1):
        # Check that set + (read and get) works as expected (set value
        # can be 'get' or 'read' back) when volatile RAM is disabled
        ram_val = (n + NVRAM_OFFSET) & 0xFF
        nvram[n] = ram_val

        ram_reg = dev_util.Register(getattr(nvram.rtc.bank, bank), n + ram_addr, size = 1)

        stest.expect_equal(nvram[n], ram_val)
        stest.expect_equal(ram_reg.read(), ram_val)

        # Check that write + (read and get) works as expected (written
        # value can be 'get' or 'read' back) when volatile RAM is
        # disabled
        ram_val = ~ram_val & 0xFF
        ram_reg.write(ram_val)

        stest.expect_equal(ram_reg.read(), ram_val)
        stest.expect_equal(ram_reg.read(), ram_val)

        # Write to NV-RAM should pass through to volatile RAM
        stest.expect_equal(nvram[n], ram_val)

        # Setting volatile RAM should not effect NV-RAM.
        vram_val = (n + VRAM_OFFSET) & 0xFF
        vram[n] = vram_val

        stest.expect_equal(ram_reg.read(), ram_val)
        stest.expect_equal(nvram[n], ram_val)

        ctrl[n] = 1 # Read values from volatile

        # What we set, we get (for vram)
        stest.expect_equal(vram[n], vram_val)

        # Setting NV-RAM should not effect the volatile storage
        nvram[n] = ram_val
        stest.expect_equal(vram[n], vram_val)
        stest.expect_different(vram[n], ram_val)

        stest.expect_equal(nvram[n], ram_val)
        stest.expect_equal(ram_reg.read(), vram_val)

        # Write updates both NV-RAM and volatile RAM
        vram_val = ~vram_val & 0xFF
        ram_reg.write(vram_val)

        stest.expect_equal(ram_reg.read(), vram_val)
        stest.expect_equal(vram[n], vram_val)
        stest.expect_equal(nvram[n], vram_val)

class AttrAccess:
    def __init__(self, rtc, attr_name):
        self.rtc = rtc
        self.attr = attr_name

    def __getitem__(self, n):
        return getattr(self.rtc, self.attr)[n]

    def __setitem__(self, n, v):
        l = getattr(self.rtc, self.attr)
        l[n] = v
        setattr(self.rtc, self.attr, l)

    def __len__(self):
        return len(getattr(self.rtc, self.attr))
