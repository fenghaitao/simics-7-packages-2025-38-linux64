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

if(NOT TARGET simics-cc-mod-ext-api-includes)
  # Only the includes (useful when splitting a module in OBJECTS and MODULE)
  add_library(simics-cc-mod-ext-api-includes INTERFACE IMPORTED GLOBAL)
  add_library(Simics::C++::SME::includes ALIAS simics-cc-mod-ext-api-includes)
  target_include_directories(simics-cc-mod-ext-api-includes INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
    ${CMAKE_CURRENT_LIST_DIR}/../dependencies
  )
endif()
