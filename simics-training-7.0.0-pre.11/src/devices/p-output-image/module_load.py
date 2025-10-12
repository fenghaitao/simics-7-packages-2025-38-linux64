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
## Define the info and status commands for the module. 
## 

import cli

class_name = 'p_output_image'

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
            ("Images",
              [("list",obj.images)])]

cli.new_info_command(class_name, get_info)

#
# ------------------------ status -----------------------
#

def get_status(obj):
    return [("State",
             [("Last image set (index number)", obj.last_set_level)])]

cli.new_status_command(class_name, get_status)
