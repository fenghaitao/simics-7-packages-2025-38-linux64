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


from cli import (
    new_info_command,
    new_status_command,
)

def get_info(obj):
    return [ (None,
              [ ("Memory object", obj.memory)])]

dma_type = ('verify', 'write', 'read', 'illegal')
dma_mode = ('demand', 'single', 'block', 'cascade')

def get_counter_status(obj, i, j):
    return [("Masked", "yes" if obj.mask[i][j] else "no"),
            ("Page Address", "0x%x" % obj.page_addr[i][j]),
            ("Base Address", "0x%x" % obj.base_addr[i][j]),
            ("Current Address", "0x%x" % obj.current_addr[i][j]),
            ("Base Count", "0x%x" % obj.base_count[i][j]),
            ("Current Count", "0x%x" % obj.current_count[i][j]),
            ("Direction", "down" if obj.dec_address[i][j] else "up"),
            ("Reset at TC", "yes" if obj.auto_init[i][j] else "no"),
            ("DMA Type", dma_type[obj.dma_type[i][j]]),
            ("DMA Mode", dma_mode[obj.dma_mode[i][j]]),
            ("Request Reg", obj.request[i][j]),
            ("Terminal Count", obj.tc[i][j])]

def get_status(obj):
    stat = []
    for i in (0, 1):
        stat += [("Controller %d" % i,
                  [("Enabled", "no" if obj.disabled[i] else "yes"),
                   ("Flip-Flop", obj.flip_flop[i]),
                   ("Page Size", "0x%x" % obj.page_size[i])])]
    for i in (0, 1):
        for j in range(4):
            stat += [("Controller %d Channel %d" % (i, j),
                      get_counter_status(obj, i, j))]
    return stat

new_info_command('i8237x2', get_info)
new_status_command('i8237x2', get_status)
