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

simics_add_module(eth-links
  CLASSES eth-hub-link eth-hub-link-endpoint eth-cable-link eth-cable-link-endpoint eth-switch-link eth-switch-link-endpoint eth-link-snoop-endpoint eth-switch-link-snoop-endpoint
  COMPONENTS ethernet_hub ethernet_cable ethernet_switch ethernet_vlan_switch
  SOURCES common.c eth-cable-link.c eth-hub-link.c eth-switch-link.c module_load.py simics_start.py
  INIT_LOCAL
  SIMICS_API latest
)
target_link_libraries(eth-links
  PRIVATE devices-common devices-common-crc link
)
add_subdirectory(test)
