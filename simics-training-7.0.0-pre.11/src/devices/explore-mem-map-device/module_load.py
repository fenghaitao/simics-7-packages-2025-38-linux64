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
## Module loading and info/status commands for the device used to explore the memory map
##
import cli

class_name = 'explore-mem-map-device'

#
# ------------------------ info -----------------------
#

def get_info(obj):
    # USER-TODO: Return something useful here
    return []

cli.new_info_command(class_name, get_info)

#
# ------------------------ status -----------------------
#

def get_status(obj):
    # USER-TODO: Return something useful here
    return []

cli.new_status_command(class_name, get_status)
