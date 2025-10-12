# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# s-vtd-protect-mem.py

from vtd_tb import (tb, vtd_hw_drv)
import stest

size = 0x1000000
low_base = tb.main_mem_base + tb.main_mem_length // 8
high_base = tb.main_mem_base + tb.main_mem_length - size

vtd_hw_drv.config_protected_memory(low_base, size, high_base, size)
vtd_hw_drv.enable_protected_memory(1)
vtd_hw_drv.enable_dma_remapping(False)

for offs in (-1, 0, size - 1, size):
    protected = offs >= 0 and offs < size
    for base in (low_base, high_base):
        read_addr = base + offs
        data = vtd_hw_drv.issue_dma_remapping(
            0, 0, 0, read_addr, vtd_hw_drv.dma_read, 1)
        if protected:
            stest.expect_false(data, f"{hex(read_addr)} not protected")
            vtd_hw_drv.enable_protected_memory(0)
            data = vtd_hw_drv.issue_dma_remapping(
                0, 0, 0, read_addr, vtd_hw_drv.dma_read, 1)
            vtd_hw_drv.enable_protected_memory(1)

        stest.expect_true(data, f"{hex(read_addr)} incorrectly protected")
