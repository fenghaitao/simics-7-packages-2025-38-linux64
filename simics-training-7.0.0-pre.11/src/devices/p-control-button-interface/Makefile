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

# IFACE_FILES should list all .h files that should be used to produce
# Python support for its interfaces and structs. If you do not want
# any Python support, you should remove the entire Makefile.
IFACE_FILES := p-control-button-interface.h

SIMICS_API := 6
THREAD_SAFE := yes

ifeq ($(MODULE_MAKEFILE),)
$(error Make sure you compile your module from the project directory)
endif

include $(MODULE_MAKEFILE)
