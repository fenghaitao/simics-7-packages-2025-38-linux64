# © 2023 Intel Corporation
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
  simics_add_test(dual-parallel-tests)
  simics_add_test(is25wp256-tests)
  simics_add_test(m25p05-tests)
  simics_add_test(m25p10-tests)
  simics_add_test(m25p128-tests)
  simics_add_test(m25p16-tests)
  simics_add_test(m25p20-tests)
  simics_add_test(m25p32-tests)
  simics_add_test(m25p40-tests)
  simics_add_test(m25p64-tests)
  simics_add_test(m25p80-tests)
  simics_add_test(m25pe40-tests)
  simics_add_test(mx66l2g45g-tests)
  simics_add_test(n25q00aa-tests)
  simics_add_test(n25q032-tests)
  simics_add_test(n25q256a-tests)
  simics_add_test(s25sl12801-tests)
  simics_add_test(sector-lock)
  simics_add_test(spi-nogpm)
  simics_add_test(w25qxx-tests)
endif()
