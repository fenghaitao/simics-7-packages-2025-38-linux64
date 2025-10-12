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


from cli import new_info_command, new_status_command

def info(obj):
    return [(None,
             [("Memory", obj.attr.target_mem),
              ("Interrupt target", obj.attr.intr_target)])]

def status(obj):
    sg = "Yes" if obj.attr.regs_DMA_control & (1 << 27) else "No"
    c_int = "Enabled" if obj.attr.regs_DMA_control & (1 << 29) else "Disabled"
    enabled = "Yes" if obj.attr.regs_DMA_control & (1 << 31) else "No"
    return [ (None,
              [("Throttle", obj.attr.throttle),
               ("DMA enabled", enabled),
               ("Completion Interrupt", c_int),
               ("Scatter-gather transfer", sg),
               ("DMA source addr", "0x%x" % obj.attr.regs_DMA_source),
               ("DMA destination addr", "0x%x" % obj.attr.regs_DMA_dest)])]

new_info_command("sample_dma_device", info)
new_status_command("sample_dma_device", status)
