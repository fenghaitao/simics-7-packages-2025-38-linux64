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

# Use the 6 API since this device still uses temporal_state
SIMICS_API := 6
THREAD_SAFE=yes

MODULE_CLASSES = DS12887

SRC_FILES = DS12887.dml
PYTHON_FILES = module_load.py

include $(MODULE_MAKEFILE)
