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
##
## module-load.py for the toggle model
##
## Define the custom info and status commands
## 
import cli

class_name = 'p_toggle'


#
# ------------------------ info -----------------------
#

def get_info(obj):
    return [("Location", 
             [("X", obj.x),
               ("Y", obj.y)]),
            ("Size", 
             [("Width", obj.width),
               ("Height", obj.height)]),
            ("Connections",
              [("Output image",obj.output_image),
               ("Toggle state receiver",obj.output)])]



cli.new_info_command(class_name, get_info)

#
# ------------------------ status -----------------------
#

def get_status(obj):
    return [("Toggle state", 
             [("State", "On" if obj.toggle_state else "Off")])]

cli.new_status_command(class_name, get_status)
