# -*- Makefile -*-

# © 2017 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

MODULE_CLASSES = gml_link_impl gml_link_endpoint
MODULE_COMPONENTS = gml_link

# Set rpath to liblink
MODULE_LDFLAGS = -llink -Wl,-rpath,'$$ORIGIN/../bin'

EXTRA_MODULE_VPATH = generic-message-interfaces

SRC_FILES = gml-link.c
PYTHON_FILES = module_load.py
SIMICS_API := latest
THREAD_SAFE=yes

include $(MODULE_MAKEFILE)
