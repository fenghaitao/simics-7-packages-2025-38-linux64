# -*- Makefile -*-

# © 2019 Intel Corporation
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

MODULE_CLASSES = riscv-clint riscv-plic
MODULE_CLASSES += riscv_clint riscv_plic # legacy aliases

SRC_FILES = riscv-interrupt-controllers.c
SRC_FILES += clint.dml
SRC_FILES += plic.dml

PYTHON_FILES = module_load.py simics_start.py

EXTRA_MODULE_VPATH := riscv-common

SIMICS_API := latest
THREAD_SAFE = yes

include $(MODULE_MAKEFILE)
