#                                                              -*- Makefile -*-

# © 2018 Intel Corporation
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
#
# Simics module makefile for the "serial out mux" device used in the
# model builder labs.  It has a variant with a port
# 

MODULE_CLASSES = serial-out-mux serial-out-mux-p serial-out-mux-serial-in
SRC_FILES = serial-out-mux-port.c serial-out-mux.c init.c

PYTHON_FILES = module_load.py

MODULE_CFLAGS =

SIMICS_API := 6
THREAD_SAFE:=yes

COMPILE_PYC = 0

ifeq ($(MODULE_MAKEFILE),)
$(error Make sure you compile your module from the project directory)
else
include $(MODULE_MAKEFILE)
endif
