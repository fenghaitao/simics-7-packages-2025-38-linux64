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

MODULE_CLASSES = ieee_802_15_4_link_impl ieee_802_15_4_link_endpoint
MODULE_COMPONENTS = ieee_802_15_4_link

# Set rpath to liblink
MODULE_LDFLAGS = -llink -Wl,-rpath,'$$ORIGIN/../bin'

SRC_FILES = ieee-802-15-4-link.c crc.c
SIMICS_API := latest
THREAD_SAFE := yes
EXTRA_MODULE_VPATH := ieee-802-15-4-interfaces common
PYTHON_FILES = module_load.py ieee_802_15_4_common.py

include $(MODULE_MAKEFILE)
