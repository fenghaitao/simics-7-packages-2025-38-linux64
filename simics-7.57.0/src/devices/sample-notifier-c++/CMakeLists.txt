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

simics_add_module(sample-notifier-c++
  CLASSES sample_notifier_cc
  SOURCES sample-notifier.cc module_load.py
  INIT_LOCAL
)
target_link_libraries(sample-notifier-c++
  PRIVATE Simics::C++
)
# Set rpath to libstdc++
if(NOT WIN32)
  set_target_properties(sample-notifier-c++ PROPERTIES BUILD_RPATH $ORIGIN/../sys/lib)
endif()
add_subdirectory(test)
