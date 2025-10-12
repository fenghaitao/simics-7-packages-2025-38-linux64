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

# Simics module makefile

SIMICS_API := latest
THREAD_SAFE:=yes

MODULE_CLASSES = sample_device_mixed

SRC_FILES = sample-device-mixed.dml \
            sample-device-mixed.c \
            sample-device-mixed-c++.cc
PYTHON_FILES := module_load.py

DMLC_FLAGS = 

# Use g++ as linker since the module contains C++ code
CCLD := $(CXX)

# Set rpath to libstdc++
ifeq ($(HOST_TYPE),linux64)
MODULE_LDFLAGS = -Wl,-rpath,'$$ORIGIN/../sys/lib'
endif

include $(MODULE_MAKEFILE)

sample-device-mixed.d: sample-device-mixed-dml.h
sample-device-mixed-c++.d: sample-device-mixed-dml.h
