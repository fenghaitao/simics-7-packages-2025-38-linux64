# -*- makefile -*-

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

MODULE_CLASSES = pcie-downstream-port pcie-downstream-port-legacy
SRC_FILES = pcie-downstream-port-device.dml pcie-downstream-port-legacy-device.dml

PYTHON_FILES = module_load.py simics_start.py

SIMICS_API := 6
THREAD_SAFE := yes
DMLC_FLAGS += --nowarn=WEXPERIMENTAL # vect in 1.4 is experimental

ifeq ($(MODULE_MAKEFILE),)
$(error Make sure you compile your module from the project directory)
else
include $(MODULE_MAKEFILE)
endif
