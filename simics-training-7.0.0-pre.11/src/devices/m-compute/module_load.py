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

class_names = ['m_compute',
               'm_compute_threaded',
               'm_compute_dummy',
               'm_compute_threaded_dummy']

#
# ------------------------ info -----------------------
#

def get_info(obj):
    # Return information about the setup of the compute unit
    return [("Setup",
            [("Memory space for descriptors and results", obj.local_memory),
             ("Operation time per pixel (ps)", obj.pixel_compute_time),
             ("Target for completion signal", obj.operation_done)]),
             ("Model properties",
             [("Threaded implementation", obj.is_threaded),])]

#
# ------------------------ status -----------------------
#

def get_status(obj):
    # Current status
    return []

for class_name in class_names:
    cli.new_info_command(class_name, get_info)
    cli.new_status_command(class_name, get_status)

