# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

simics_add_module(virtio
  CLASSES virtio_mmio_blk virtio_mmio_net virtio_mmio_fs virtio-mmio-entropy virtio_pcie_blk virtio_pcie_net virtio_pcie_fs virtio-pcie-sriov-blk
  SOURCES virtio-mmio-blk.dml virtio-mmio-entropy.dml virtio-mmio-fs.dml virtio-mmio-net.dml virtio-pcie-blk.dml virtio-pcie-fs.dml virtio-pcie-net.dml virtio-pcie-sriov-blk.dml module_load.py
  SIMICS_API latest
)
target_link_libraries(virtio
  PRIVATE dml-lib
  PRIVATE virtiofs-fuse::imports
)

add_subdirectory(test)

simics_add_sanitizers(virtio)
