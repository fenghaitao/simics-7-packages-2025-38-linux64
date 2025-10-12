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

MODULE_CLASSES = generic_spi_flash M25Pxx
SRC_FILES = generic-spi-flash.c generic-spi-flash.dml
PYTHON_FILES = module_load.py

DMLC_FLAGS += --nowarn=WEXPERIMENTAL

SIMICS_API = latest
THREAD_SAFE = yes

include $(MODULE_MAKEFILE)
