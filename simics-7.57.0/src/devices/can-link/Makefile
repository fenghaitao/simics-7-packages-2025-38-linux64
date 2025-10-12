# -*- Makefile -*-

# © 2016 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

# Simics module makefile

MODULE_CLASSES = can_link_impl can_endpoint
MODULE_COMPONENTS = can_link

# Set rpath to liblink
MODULE_LDFLAGS = -llink -Wl,-rpath,'$$ORIGIN/../bin'

SRC_FILES = can-link.c
PYTHON_FILES = module_load.py

MODULE_CFLAGS =
EXTRA_MODULE_VPATH := can-interface
SIMICS_API := latest
THREAD_SAFE:=yes

ifeq ($(MODULE_MAKEFILE),)
$(error Make sure you compile your module from the project directory)
else
include $(MODULE_MAKEFILE)
endif
