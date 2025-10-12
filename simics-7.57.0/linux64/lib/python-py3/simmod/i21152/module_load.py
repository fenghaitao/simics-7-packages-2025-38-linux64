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
    get_last_loaded_module,
    new_info_command,
    new_status_command,
)
import sim_commands

device_name = get_last_loaded_module()

# cross 32-bit reads not supported
def read_config(obj, offset, size):
    reg = offset // 4
    off = (offset % 4) * 8
    return (obj.config_registers[reg] >> off) & ((1 << size * 8) - 1)

def get_info(obj):
    return (sim_commands.get_pci_info(obj) +
            [(None,
              [ ("Secondary Bus", obj.secondary_bus)]),
             ("Bridge information",
              [ ("Primary Bus Number", "0x%x" % read_config(obj, 0x18, 1)),
                ("Secondary Bus Number", "0x%x" % read_config(obj, 0x19, 1)),
                ("Subordinate Bus Number", "0x%x" % read_config(obj, 0x1a, 1))]),
             ("Memory setup",
              [ ("IO Base", "0x%x" % ((read_config(obj, 0x30, 2) << 16)
                                      | (read_config(obj, 0x1c, 1) << 8))),
                ("IO Limit", "0x%x" % ((read_config(obj, 0x32, 2) << 16)
                                       | (read_config(obj, 0x1d, 1) << 8)))]),
             (None,
              [ ("Memory Base", "0x%x" % (read_config(obj, 0x20, 2) << 16)),
                ("Memory Limit", "0x%x" % (read_config(obj, 0x22, 2) << 16))]),
             (None,
              [ ("Prefetchable Base", "0x%x" % ((read_config(obj, 0x28, 4) << 32)
                                                | (read_config(obj, 0x24, 2) << 16))),
                ("Prefetchable Limit", "0x%x" % ((read_config(obj, 0x2c, 4) << 32)
                                                 | (read_config(obj, 0x26, 2) << 16)))])])


def get_status(obj):
    return sim_commands.get_pci_status(obj)

new_info_command(device_name, get_info)
new_status_command(device_name, get_status)
