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


from cli import (
    new_info_command,
    new_status_command,
)

def status_info(obj):
    return [
        (None,
         [("CPU core", obj.attr.executor),
          ("Number of cycles CPU core is ahead", obj.attr.catch_up_cycles)])]

# At present, we provide the same information in status and info
new_info_command("async-bridge", status_info)
new_status_command("async-bridge", status_info)
