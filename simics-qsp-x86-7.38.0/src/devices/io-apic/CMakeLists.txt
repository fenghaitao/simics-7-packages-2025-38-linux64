# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

# skip-cmake-conversion

# io-apic.cc is not currently distributed
if(SIMICS_REPO_ROOT)
  simics_add_module(io-apic
    CLASSES io-apic
    INTERFACES ioapic
    SOURCES io-apic.cc io-apic.h module_load.py
    INIT_LOCAL
    SIMICS_API latest
  )
  add_compile_definitions(DEVICE_IS_LITTLE_ENDIAN )
else()
  add_library(io-apic-imports INTERFACE)
  target_include_directories(io-apic-imports INTERFACE .)
  add_library(io-apic::imports ALIAS io-apic-imports)
  add_library(io-apic::includes ALIAS io-apic-imports)
endif()
