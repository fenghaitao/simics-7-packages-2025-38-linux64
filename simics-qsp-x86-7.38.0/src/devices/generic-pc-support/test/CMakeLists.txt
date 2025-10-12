# © 2025 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

function(add_all_local_tests)
  file(GLOB py_tests ${CMAKE_CURRENT_SOURCE_DIR}/s-*.py)

  foreach(T ${py_tests})
    get_filename_component(TFILE ${T} NAME)
    string(REGEX REPLACE "(s-)(.*)(.py)" "\\2" TNAME ${TFILE})
    message(TRACE "Adding test ${TNAME}")
    cmake_path(GET CMAKE_CURRENT_FUNCTION_LIST_DIR PARENT_PATH NS)
    get_filename_component(NS ${NS} NAME)
    simics_add_test(${TNAME} NAMESPACE ${NS})
  endforeach()
endfunction()

if(SIMICS_ENABLE_TESTS_FROM_PACKAGES)
add_subdirectory(cf9)
add_subdirectory(hpet)
add_subdirectory(rtc)
simics_add_test(cf8-cfc)
simics_add_test(pci-upstream-dispatcher)
endif()

