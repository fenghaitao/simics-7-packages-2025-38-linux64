# -*- Makefile ; coding: utf-8 -*-

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

# Simics module makefile

MODULE_CLASSES = sample_dma_device_cpp

SRC_FILES= sample-dma-device.cc
PYTHON_FILES = module_load.py

THREAD_SAFE = yes
SIMICS_API := latest

# set this as we use the Simics C++ Device API v2
USE_CC_API = 2
# This feature requires C++17
USE_CC_MODELING_API = yes

# Set rpath to libstdc++
ifeq ($(HOST_TYPE),linux64)
MODULE_LDFLAGS = -Wl,-rpath,'$$ORIGIN/../sys/lib'
endif

include $(MODULE_MAKEFILE)
