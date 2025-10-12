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

message(CHECK_START "Setting up Google Test")

# Google Test: http://google.github.io/googletest/
include(FetchContent)
FetchContent_Declare(
  googletest
  GIT_REPOSITORY https://github.com/google/googletest.git
  GIT_TAG f8d7d77c06936315286eb55f8de22cd23c188571  # 1.14.0
)
# For Windows: Prevent overriding the parent project's compiler/linker settings
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

# TODO(ah): figure out how to use PkgConfig with FetchContent

# GTest is a bit stupid and relies on undefined macros causing warnings causing
# errors due to -Werror=undef
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
  target_compile_options(gtest PRIVATE -Wno-undef)
  target_compile_options(gtest_main PRIVATE -Wno-undef)
  target_compile_options(gmock PRIVATE -Wno-undef)
  target_compile_options(gmock_main PRIVATE -Wno-undef)
endif()

message(CHECK_PASS "done")
