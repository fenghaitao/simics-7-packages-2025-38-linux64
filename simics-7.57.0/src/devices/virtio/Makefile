# -*- Makefile -*-

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

MODULE_CLASSES :=
MODULE_CLASSES += virtio_mmio_blk
MODULE_CLASSES += virtio_mmio_net
MODULE_CLASSES += virtio_mmio_fs
MODULE_CLASSES += virtio-mmio-entropy
MODULE_CLASSES += virtio_pcie_blk
MODULE_CLASSES += virtio_pcie_net
MODULE_CLASSES += virtio_pcie_fs
MODULE_CLASSES += virtio-pcie-sriov-blk

SRC_FILES :=
SRC_FILES += virtio-mmio-blk.dml
SRC_FILES += virtio-mmio-net.dml
SRC_FILES += virtio-mmio-fs.dml
SRC_FILES += virtio-mmio-entropy.dml
SRC_FILES += virtio-pcie-blk.dml
SRC_FILES += virtio-pcie-net.dml
SRC_FILES += virtio-pcie-fs.dml
SRC_FILES += virtio-pcie-sriov-blk.dml

PYTHON_FILES = module_load.py

EXTRA_MODULE_VPATH += dml-lib virtiofs-fuse

SIMICS_API := latest
THREAD_SAFE := yes


ifeq ($(MODULE_MAKEFILE),)
$(error Make sure you compile your module from the project directory)
else
include $(MODULE_MAKEFILE)
endif
