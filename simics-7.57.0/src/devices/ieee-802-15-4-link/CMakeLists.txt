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

simics_add_module(ieee-802-15-4-link
  CLASSES ieee_802_15_4_link_impl ieee_802_15_4_link_endpoint
  COMPONENTS ieee_802_15_4_link
  SOURCES ieee-802-15-4-link.c ieee_802_15_4_common.py module_load.py
  INIT_LOCAL
  SIMICS_API latest
)
target_link_libraries(ieee-802-15-4-link
  PRIVATE ieee-802-15-4-interfaces::includes devices-common devices-common-crc
)
target_link_libraries(ieee-802-15-4-link
  PRIVATE link
)
add_subdirectory(test)
