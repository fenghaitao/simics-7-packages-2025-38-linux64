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


import cli

class_name = "simics_nvme_controller"


def get_info(obj):
    info = []
    for i, ns_size in enumerate(obj.namespace_sizes):
        info.append((f"Namespace {i + 1} size", ns_size))
    return [("", info)]


def get_status(obj):
    total_ns_size = sum(obj.namespace_sizes)
    unallocated_ns_space = obj.disk_size - total_ns_size
    info = [
        ("Unallocated namespace space", unallocated_ns_space)
    ]
    return [("", info)]


cli.new_info_command(class_name, get_info)
cli.new_status_command(class_name, get_status)
