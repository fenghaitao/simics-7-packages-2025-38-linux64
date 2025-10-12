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

MODULE_CLASSES = i3c_link_impl i3c_link_endpoint	\
		 i3c_cable_impl i3c_cable_endpoint	\
		 i3c_bus i3c_wire i2c_to_i3c_adapter
MODULE_COMPONENTS = i3c_cable i3c_link

# Set rpath to liblink
MODULE_LDFLAGS = -llink -Wl,-rpath,'$$ORIGIN/../bin'

SRC_FILES = i3c-link.c i3c-cable.c i3c-link-common.c \
            i2c-to-i3c-adapter.dml i3c-bus.dml i3c-wire.dml
PYTHON_FILES = module_load.py

DMLC_FLAGS += --nowarn=WEXPERIMENTAL

SIMICS_API := latest
THREAD_SAFE := yes

include $(MODULE_MAKEFILE)
