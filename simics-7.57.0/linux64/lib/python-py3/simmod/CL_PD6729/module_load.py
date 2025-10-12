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

def get_info(obj):
    # FIXME: add device specific info
    return (sim_commands.get_pci_info(obj))

def get_status(obj):
    # FIXME: add device specific status
    return (sim_commands.get_pci_status(obj))

new_info_command(device_name, get_info)
new_status_command(device_name, get_status)
