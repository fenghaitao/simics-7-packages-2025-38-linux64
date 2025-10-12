# -*- Makefile -*-

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

#
# Sample makefile for the DML device: "empty-dml-device"
# See Simics Model Builder User's Guide for more details on what to put here.
#

MODULE_CLASSES = i82559
SRC_FILES = i82559.dml
PYTHON_FILES = module_load.py

THREAD_SAFE = yes
SIMICS_API := 6

EXTRA_MODULE_VPATH += dml-lib

ifeq ($(MODULE_MAKEFILE),)
$(error Make sure you compile your module from the project directory)
else
include $(MODULE_MAKEFILE)
endif
