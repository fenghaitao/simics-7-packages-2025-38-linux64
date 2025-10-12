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

MODULE_CLASSES = eth-hub-link eth-hub-link-endpoint			\
                 eth-cable-link eth-cable-link-endpoint			\
                 eth-switch-link eth-switch-link-endpoint		\
                 eth-link-snoop-endpoint eth-switch-link-snoop-endpoint

MODULE_COMPONENTS = ethernet_hub ethernet_cable ethernet_switch	\
		    ethernet_vlan_switch

# Set rpath to liblink
MODULE_LDFLAGS = -llink -Wl,-rpath,'$$ORIGIN/../bin'

EXTRA_MODULE_VPATH = common

SRC_FILES = common.c eth-hub-link.c eth-cable-link.c \
	    eth-switch-link.c crc.c
PYTHON_FILES = module_load.py simics_start.py
SIMICS_API := latest
THREAD_SAFE=yes

include $(MODULE_MAKEFILE)
