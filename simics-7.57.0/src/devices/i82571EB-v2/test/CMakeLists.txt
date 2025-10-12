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

if(SIMICS_ENABLE_TESTS_FROM_PACKAGES)
  simics_add_test(lan-checkpoint)
  simics_add_test(lan-eeprom)
  simics_add_test(lan-map-spi-flash)
  simics_add_test(lan-mii)
  simics_add_test(lan-rx-addr-filter)
  simics_add_test(lan-rx-checksum-offloading)
  simics_add_test(lan-rx-rss)
  simics_add_test(lan-rx-single-queue)
  simics_add_test(lan-rx-split)
  simics_add_test(lan-stat)
  simics_add_test(lan-tx-checksum-offloading)
  simics_add_test(lan-tx-legacy-td)
  simics_add_test(lan-tx-segmentation)
endif()
