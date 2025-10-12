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

simics_add_module(signal-link
  CLASSES signal_link_impl signal_link_endpoint
  COMPONENTS signal_link
  SOURCES signal-link.c module_load.py
  INIT_LOCAL
  SIMICS_API latest
)
target_link_libraries(signal-link
  PRIVATE link
)
add_subdirectory(test)
