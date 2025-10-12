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

def get_connected_devices(obj):
    addr_and_dev = sorted((a, o.name) for (o, a) in obj.devices)
    return ("Connected devices", ["0x%02x: %s" % (addr, name)
                                  for (addr, name) in addr_and_dev])

def get_info(obj):
    return [(None, [get_connected_devices(obj)])]

cli.new_info_command('mii-management-bus', get_info)

def get_status(obj):
    return []

cli.new_status_command('mii-management-bus', get_status)
