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

add_subdirectory(mock)

if (CC_API_UNITTESTS_ENABLED)

include(gtest.cmake)

add_executable(cc-api-unittest
  test_after.cc
  test_after_bank.cc
  test_attr_value.cc
  test_attribute.cc
  test_attribute_getter.cc
  test_attribute_traits.cc
  test_attribute_type_string.cc
  test_bank.cc
  test_bank_access.cc
  test_bank_instrumentation_subscribe_connection.cc
  test_bank_port.cc
  test_bank_templates.cc
  test_bank_type.cc
  test_common_types.cc
  test_conf_object.cc
  test_conf_class.cc
  test_connect.cc
  test_connect_template.cc
  test_event.cc
  test_field.cc
  test_field_templates.cc
  test_field_type.cc
  test_get_interface.cc
  test_hierarchical_object.cc
  test_hierarchical_object_name.cc
  test_log.cc
  test_mappable_conf_object.cc
  test_port.cc
  test_register.cc
  test_register_templates.cc
  test_register_type.cc
  test_utility.cc)

# Define a function to set compiler options and link options
function(set_gcc_options target)
  if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    # make sure we don't use implicit type conversions
    target_compile_options(${target} PRIVATE -Wconversion)
    # link with static libs so test binary can run through CTest without
    # patching LD_LIBRARY_PATH
    if(WIN32)
      target_link_options(${target} PRIVATE -static -static-libgcc -static-libstdc++)
    endif()
  endif()
endfunction()

set_gcc_options(cc-api-unittest)
target_link_libraries(cc-api-unittest
  PRIVATE simics-cc-api::stubbed simics-api-stubs GTest::gtest_main)

# https://cmake.org/cmake/help/git-stage/module/GoogleTest.html
include(GoogleTest)
gtest_discover_tests(cc-api-unittest
  TEST_PREFIX src/devices/c++-api/unittest/
  DISCOVERY_MODE PRE_TEST)

# NOTE: order never changes between runs of the same binary *unless* you run
# the binary directly passing the `--gtest_shuffle` flag

# The decoration test *must* be run in a separate binary as it depends on the
# order in which conf-class.h header is included for the decoration to take
# effect.
add_executable(cc-api-unittest-decorate
  test_conf_class_decorate_class.cc)
set_gcc_options(cc-api-unittest-decorate)
target_link_libraries(cc-api-unittest-decorate
  PRIVATE simics-cc-api::stubbed simics-api-stubs GTest::gtest_main)
add_dependencies(cc-api-unittest cc-api-unittest-decorate)

gtest_discover_tests(cc-api-unittest-decorate
  TEST_PREFIX src/devices/c++-api/unittest/
  DISCOVERY_MODE PRE_TEST)

endif()
