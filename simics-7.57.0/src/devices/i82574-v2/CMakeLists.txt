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

simics_add_module(i82574-v2
  CLASSES i82574_v2
  SOURCES i82574.dml module_load.py
  SIMICS_API 6
)
target_link_libraries(i82574-v2
  PRIVATE intel-e1000::imports dml-lib
)
add_subdirectory(test)
