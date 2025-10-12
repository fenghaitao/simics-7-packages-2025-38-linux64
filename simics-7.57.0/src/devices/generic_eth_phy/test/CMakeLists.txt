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
  simics_add_test(bug19050)
  simics_add_test(bug25131)
  simics_add_test(frames-c)
  simics_add_test(frames-dml)
  simics_add_test(link-status-propagation)
  simics_add_test(loopback)
  simics_add_test(mii-regs)
  simics_add_test(restart-auto-negotiation)
endif()
