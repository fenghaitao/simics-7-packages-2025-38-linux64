# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

simics_add_module(simics-uefi
  CLASSES simics-uefi
  SOURCES simics-uefi.dml module_load.py
  SIMICS_API latest
)
target_link_libraries(simics-uefi
  PRIVATE dml-lib
)

get_property(dmlc_flags GLOBAL PROPERTY SIMICS_DMLC_FLAGS)
list(APPEND dmlc_flags --nowarn=WEXPERIMENTAL)
set_target_properties(simics-uefi
  PROPERTIES SIMICS_DMLC_FLAGS "${dmlc_flags}"
)

add_subdirectory(test)
