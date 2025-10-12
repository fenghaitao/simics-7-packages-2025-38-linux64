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

class_name = 'i_multi_writer_output'

#
# ------------------------ info -----------------------
#

def get_info(obj):
    return [("",
             [("Supported number of writers", obj.max_writers_attr),
              ("Connected to ", obj.console)])]

def get_status(obj):
    rv = []
    cnt = 0
    for bg_col, fg_col, stall_cyc in zip(obj.bg_colors, obj.fg_colors, obj.stall_cycles):
        rv.append((f"Writer {cnt}",
             [("Background color ID", bg_col),
              ("Foreground color ID", fg_col),
              ("Stall cycles ", stall_cyc)]))
        cnt +=1
    return rv

cli.new_info_command(class_name, get_info)
cli.new_status_command(class_name, get_status)
