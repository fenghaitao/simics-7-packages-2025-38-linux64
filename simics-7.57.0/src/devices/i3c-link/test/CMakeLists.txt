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
  simics_add_test(1-read)
  simics_add_test(10-comp)
  simics_add_test(100-no-slaves)
  simics_add_test(101-order)
  simics_add_test(11-legacy-i2c)
  simics_add_test(2-write)
  simics_add_test(3-direct-write)
  simics_add_test(4-broadcast)
  simics_add_test(5-daa)
  simics_add_test(6-hot-join)
  simics_add_test(7-ibi-delayed)
  simics_add_test(7-ibi)
  simics_add_test(8-secondary-master)
  simics_add_test(bus-broadcast-write)
  simics_add_test(bus-daa)
  simics_add_test(bus-direct-message)
  simics_add_test(bus-hard-reset)
  simics_add_test(bus-hot-join)
  simics_add_test(bus-ibi-delayed)
  simics_add_test(bus-ibi)
  simics_add_test(bus-known-address)
  simics_add_test(bus-legacy)
  simics_add_test(bus-secondary-master)
  simics_add_test(i3c-cable-comp-test)
  simics_add_test(i3c-cable-with-bus)
  simics_add_test(i3c-cable)
endif()
