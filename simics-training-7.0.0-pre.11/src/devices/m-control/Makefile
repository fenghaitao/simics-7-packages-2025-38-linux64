#                                                              -*- Makefile -*-

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


#----------------------------------------------------------------------------------
# Simics module makefile for the control device
#

# Two classes: one with stall feature, one without 
#
MODULE_CLASSES = m_control m_control_stall
SRC_FILES = m-control.dml m-control-stall.dml  
PYTHON_FILES = module_load.py

SIMICS_API := 6
THREAD_SAFE := yes

COMPILE_PYC = 0

# Extra for PCIe 
EXTRA_MODULE_VPATH += dml-lib

# For interface towards the compute unit
EXTRA_MODULE_VPATH += m-compute-control-interface


ifeq ($(MODULE_MAKEFILE),)
$(error Make sure you compile your module from the project directory)
else
include $(MODULE_MAKEFILE)
endif
