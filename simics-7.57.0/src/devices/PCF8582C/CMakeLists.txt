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

simics_add_module(PCF8582C
  CLASSES PCF8582C
  SOURCES PCF8582C.c PCF8582C.dml
  SIMICS_API 6  # using old api
  INIT_LOCAL
)
target_link_libraries(PCF8582C
  PRIVATE devices-common
)
