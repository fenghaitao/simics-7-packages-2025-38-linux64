# © 2024 Intel Corporation
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
import simics

simics.SIM_load_module('i-processor-id-atom')

class_name = 'i_processor_id_router'

#
# ------------------------ info -----------------------
#

def get_info(obj):
    return [("",
             [("Target for transactions with IDs", obj.memory_space_with_id),
              ("Target for transactions without IDs", obj.memory_space_without_id)])]

# same for both
cli.new_info_command(class_name, get_info)
cli.new_status_command(class_name, get_info)
