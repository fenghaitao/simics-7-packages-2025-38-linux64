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

class_names = ['virtio_mmio_blk', 'virtio_mmio_net', 'virtio_pcie_blk',
               'virtio_pcie_net', 'virtio_mmio_fs', 'virtio_pcie_fs',
               'virtio-mmio-entropy', 'virtio-pcie-sriov-blk']

#
# ------------------------ info -----------------------
#

def get_info(obj):
    return []

for class_name in class_names:
    cli.new_info_command(class_name, get_info)

#
# ------------------------ status -----------------------
#

def get_status(obj):
    return []

for class_name in class_names:
    cli.new_status_command(class_name, get_status)
