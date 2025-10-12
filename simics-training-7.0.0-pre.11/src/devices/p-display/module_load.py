# © 2022 Intel Corporation
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

class_name = 'p_display'

#
# ------------------------ info -----------------------
#

def get_info(obj):
    return [("Display unit configuration",
             [("Connected graphics console", obj.console),
              ("Display width (px)", obj.width),
              ("Display height (px)", obj.height),
              ])]


cli.new_info_command(class_name, get_info)

#
# ------------------------ status -----------------------
#

def get_status(obj):
    return [("Current state", [("No current state to report","")])]
cli.new_status_command(class_name, get_status)

#
# Add more commands here, using cli.new_command()
#
