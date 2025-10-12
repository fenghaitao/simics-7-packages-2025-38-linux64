# -*- Makefile -*-

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

# NOTE: remap-unit *must* be listed before core or else init_as_subobject
#       will fail to locate the x58-remap-unit class when registering x58-core
DEVICES = remap-unit \
          core \
          dmi \
          ioxapic \
          pcie-port \
          pcie-port-acs \
          qpi-port \
          qpi-arch

CLASSES = $(addprefix x58-, $(DEVICES))
FILES = $(addsuffix .dml, $(DEVICES))

MODULE_CLASSES := $(CLASSES)

PYTHON_FILES = module_load.py
SRC_FILES := $(FILES)

MODULE_CFLAGS += -Wno-array-bounds
DMLC_FLAGS += --nowarn=WEXPERIMENTAL

EXTRA_MODULE_VPATH += io-apic:dml-lib

THREAD_SAFE = yes
SIMICS_API = latest


include $(MODULE_MAKEFILE)
