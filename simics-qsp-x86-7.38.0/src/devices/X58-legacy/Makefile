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

DEVICES = dmi \
          core_f0 \
          core_f1 \
          core_f2 \
          core_f3 \
          ioxapic \
          qpi_port0_f0 \
          qpi_port0_f1 \
          qpi_port1_f0 \
          qpi_port1_f1 \
          pcie_port \
          remap_dispatcher \
          remap_unit0 \
          remap_unit1 \
          qpi_ncr_f0 \
          qpi_sad_f1

ALIASES = $(addprefix x58_, $(DEVICES))
CLASSES = $(addprefix x58-, $(addsuffix -legacy,$(subst _,-,$(DEVICES))))
FILES = $(addsuffix .dml, $(subst _,-,$(DEVICES)))

MODULE_CLASSES := $(CLASSES) $(ALIASES)

PYTHON_FILES = module_load.py simics_start.py
SRC_FILES := x58-devices.c
SRC_FILES += $(FILES)

EXTRA_MODULE_VPATH += io-apic:dml-lib

THREAD_SAFE = yes
SIMICS_API = 6


include $(MODULE_MAKEFILE)
