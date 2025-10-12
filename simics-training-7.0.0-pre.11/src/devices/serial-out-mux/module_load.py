# © 2020 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


##
## Module loading and info/status commands for the serial mux out device
##
import cli

class_name = 'serial-out-mux'

# info command prints static information
def get_info(obj):
    return [("Configuration",
             [("Original target",obj.original_target),
              ("Mux target",obj.mux_target)])]

# status command prints dynamic information
def get_status(obj):
    return []

cli.new_info_command(class_name, get_info)
cli.new_status_command(class_name, get_status)

class_name = 'serial-out-mux-p'

# info command prints static information
def get_info_p(obj):
    return [("Configuration",
             [("Original target",obj.original_target),
              ("Mux target",obj.mux_target)])]

# status command prints dynamic information
def get_status_p(obj):
    return []

cli.new_info_command(class_name, get_info_p)
cli.new_status_command(class_name, get_status_p)

class_name = 'serial-out-mux-serial-in'

def nothing_here(obj):
    return [(None, [("Nothing here yet", "Sorry!")])]

cli.new_info_command(class_name, nothing_here)
cli.new_status_command(class_name, nothing_here)


