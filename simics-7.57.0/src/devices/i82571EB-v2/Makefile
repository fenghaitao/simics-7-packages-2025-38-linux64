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

NIC_MODEL = i82571EB

DEVICES = $(NIC_MODEL)

MODULE_CLASSES :=  i82571EB_v2

SRC_FILES := $(addsuffix .dml, $(subst _,-,$(DEVICES)))

MODULE_CFLAGS =

EXTRA_MODULE_VPATH += intel-e1000 dml-lib

PYTHON_FILES := module_load.py

THREAD_SAFE = yes
SIMICS_API = 6

include $(MODULE_MAKEFILE)
