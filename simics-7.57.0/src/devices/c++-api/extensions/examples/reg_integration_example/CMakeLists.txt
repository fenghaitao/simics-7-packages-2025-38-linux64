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

simics_add_module(SampleDevice
    CLASSES SampleDevice
    SOURCES sample_device.cpp regs.cpp module_load.py
    INIT_LOCAL
    SIMICS_API latest
)
 
target_include_directories(SampleDevice PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../../../src) 

target_link_libraries(SampleDevice
    PRIVATE Simics::C++
    PRIVATE Simics::C++::SME::includes
)
 
add_subdirectory(test EXCLUDE_FROM_ALL)

if(NOT TARGET build_all_sme_unit_tests)
  add_custom_target(build_all_sme_unit_tests)
endif()
add_dependencies(build_all_sme_unit_tests SampleDevice)

