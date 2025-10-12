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
  simics_add_test(accept-smaller-read-writes)
  simics_add_test(add-flash-model)
  simics_add_test(all-flashes)
  simics_add_test(amd-8x-8-bit-partial)
  simics_add_test(amd-8x-8-bit)
  simics_add_test(amd-ignore-cmd-address)
  simics_add_test(amd-protection-bits-1)
  simics_add_test(amd-repeated-sector-erase)
  simics_add_test(amd-sector-erase-per-chip)
  simics_add_test(amd-single-16-bit-8-bit-bus)
  simics_add_test(amd-single-16-bit-complex-accesses)
  simics_add_test(amd-single-16-bit)
  simics_add_test(amd-single-8-bit)
  simics_add_test(big-endian-intel-2x-16-bit-32-bit-bus)
  simics_add_test(bug-10869)
  simics_add_test(bug-17529)
  simics_add_test(bug-21451)
  simics_add_test(bug-8693)
  simics_add_test(intel-4x-16-bit-32-bit-bus-partial)
  simics_add_test(intel-p30-64-byte-write-buffer)
  simics_add_test(intel-sector-lock-down)
  simics_add_test(intel-single-16-bit-8-bit-bus)
  simics_add_test(intel-single-16-bit)
endif()
