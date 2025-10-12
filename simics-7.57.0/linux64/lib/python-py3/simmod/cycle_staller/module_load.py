# © 2016 Intel Corporation
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

class_name = 'cycle_staller'

# info command prints static information
def get_info(obj):
    return []

# status command prints dynamic information
def get_status(obj):
    return [("Stall info",
             [(clock.name, "total = %10d, left = %10d" % (total, stall))
              for (clock, total, stall) in obj.stall_info])]

cli.new_info_command(class_name, get_info)
cli.new_status_command(class_name, get_status)
