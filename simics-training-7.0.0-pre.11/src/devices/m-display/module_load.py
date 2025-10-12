# © 2021 Intel Corporation
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

class_name = 'm_display'

#
# ------------------------ info -----------------------
#

def get_info(obj):
    return [("Display unit configuration",
             [("Connected graphics console", obj.console),
              ("Memory space for local memory", obj.local_memory),
              ])]


cli.new_info_command(class_name, get_info)

#
# ------------------------ status -----------------------
#

def get_status(obj):
    return [("Last display order",
             [("Display width (px)", obj.bank.regs.width),
              ("Display height (px)", obj.bank.regs.height),
              ("Max iterations", obj.bank.regs.max_iter),
              ("Iteration (results) data address", hex(obj.bank.regs.iter_data_addr)),
              ("Color table address", hex(obj.bank.regs.color_table_addr)),
              ])]
cli.new_status_command(class_name, get_status)

#
# Add more commands here, using cli.new_command()
#
