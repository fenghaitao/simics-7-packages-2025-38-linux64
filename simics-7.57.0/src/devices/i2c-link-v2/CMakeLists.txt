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

simics_add_module(i2c-link-v2
  CLASSES i2c-link-impl i2c-link-endpoint i2c_wire
  COMPONENTS i2c_link_v2
  SOURCES i2c-link-v2.c i2c-wire.dml module_load.py simics_start.py
  INIT_LOCAL
  SIMICS_API latest
)
target_link_libraries(i2c-link-v2
  PRIVATE link
)

if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/test)
  add_subdirectory(test)
endif()
