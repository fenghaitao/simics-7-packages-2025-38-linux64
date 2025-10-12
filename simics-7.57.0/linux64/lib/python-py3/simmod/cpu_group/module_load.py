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

from cli import new_info_command

def get_info(obj):
    return [("Connected processors",
             [(str(i), obj.cpu_list[i].name)
              for i in range(len(obj.cpu_list))])]

new_info_command("cpu-group", get_info)
