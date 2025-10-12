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

# sample-device-* modules ship with CTest by default as an example; but they
# are not expected to run by default in a user's project. User can opt-in (and
# run these tests) by copying the module to the project and modify this
# if-statement; or set the flag in their configuration
if(SIMICS_ENABLE_TESTS_FROM_PACKAGES)
  simics_add_test(sample-device-python-confclass)
endif()
