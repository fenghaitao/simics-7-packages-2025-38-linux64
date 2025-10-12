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

simics_add_module(simple-broken-device-valgrind
  CLASSES simple_broken_device_valgrind
  SOURCES simple-broken-device-valgrind.dml
  SIMICS_API latest
)

set_target_properties(simple-broken-device-valgrind PROPERTIES EXCLUDE_FROM_ALL TRUE)
