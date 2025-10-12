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


import cli

def no_info(obj):
    "Function to not return any info at all for a device"
    return []

def bus_status(obj):
    return [('Connected devices', [(d.name, i) for d, i, im, subs
                                   in obj.connected_devices])]

cli.new_info_command('firewire_bus', no_info)
cli.new_status_command('firewire_bus', bus_status)
