#                                                              -*- Makefile -*-
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

MODULE_CLASSES = p_button
SRC_FILES = p-button.dml
PYTHON_FILES = module_load.py

SIMICS_API := 6
THREAD_SAFE := yes

EXTRA_MODULE_VPATH += p-control-button-interface  p-image-properties-interface

COMPILE_PYC = 0

ifeq ($(MODULE_MAKEFILE),)
$(error Make sure you compile your module from the project directory)
else
include $(MODULE_MAKEFILE)
endif
