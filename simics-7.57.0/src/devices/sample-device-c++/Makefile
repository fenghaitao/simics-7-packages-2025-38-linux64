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

MODULE_CLASSES = \
    sample_device_cxx_after \
    sample_device_cxx_after_bank \
    sample_device_cxx_attribute_class_attribute \
    sample_device_cxx_attribute_class_member_method \
    sample_device_cxx_attribute_class_member_variable \
    sample_device_cxx_attribute_custom_method \
    sample_device_cxx_attribute_global_method \
    sample_device_cxx_attribute_nested_stl_container \
    sample_device_cxx_attribute_pseudo \
    sample_device_cxx_attribute_specialized_converter \
    sample_device_cxx_bank_by_code \
    sample_device_cxx_bank_by_data \
    sample_device_cxx_class_with_init_class \
    sample_device_cxx_class_without_init_class \
    sample_device_cxx_class_without_init_local \
    sample_device_cxx_connect \
    sample_device_cxx_connect_to_descendant \
    sample_device_cxx_connect_map_target \
    sample_device_cxx_event \
    sample_device_cxx_interface \
    sample_device_cxx_interface_c \
    sample_device_cxx_interface_with_custom_info \
    sample_device_cxx_logging \
    sample_device_cxx_port_use_confobject \
    sample_device_cxx_port_use_port \
    sample_device_cxx_user_interface

SRC_FILES= \
    init.c \
    sample-after-bank.cc \
    sample-after.cc \
    sample-attribute.cc \
    sample-bank-by-code.cc \
    sample-bank-by-data.cc \
    sample-class.cc \
    sample-connect.cc \
    sample-event.cc \
    sample-interface.cc \
    sample-interface-c.cc \
    sample-logging.cc \
    sample-port.cc \
    solve-methods-collision.cc
PYTHON_FILES = module_load.py
EXTRA_MODULE_VPATH := sample-interface

THREAD_SAFE = yes
SIMICS_API := latest

# set this as we use the Simics C++ Device API v2
USE_CC_API = 2
# This feature requires C++17
USE_CC_MODELING_API = yes

# Set rpath to libstdc++
ifeq ($(HOST_TYPE),linux64)
MODULE_LDFLAGS = -Wl,-rpath,'$$ORIGIN/../sys/lib'
endif

include $(MODULE_MAKEFILE)
