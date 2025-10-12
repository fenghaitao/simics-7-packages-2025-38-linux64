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

def get_info(obj):
    return [(None,
             [('Mask', '0x%x' % obj.address_mask)])]

def get_status(obj):
    return []

cli.new_info_command('bitmask-translator', get_info)
cli.new_status_command('bitmask-translator', get_status)
