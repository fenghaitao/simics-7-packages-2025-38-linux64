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

# Load the Simics mock library target
add_subdirectory(${SIMICS_BASE_DIR}/src/devices/c++-api/unittest/mock simics-mock)

# Setup GTest
if (DEFINED ENV{GTEST_ROOT})
    # https://cmake.org/cmake/help/git-stage/module/GoogleTest.html
    find_package(GTest REQUIRED PATHS $ENV{GTEST_ROOT}/$ENV{GTEST_VER})
    include(GoogleTest)
else()
    message(STATUS "Fetching Google Test ...")

    # Google Test: http://google.github.io/googletest/
    include(FetchContent)
    FetchContent_Declare(
        googletest
        GIT_REPOSITORY https://github.com/google/googletest.git
        GIT_TAG b796f7d44681514f58a683a3a71ff17c94edb0c1  # 1.13.0
    )
    if (WIN32)
        # For Windows: Prevent overriding the parent project's compiler/linker settings
        set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
    endif (WIN32)

    FetchContent_MakeAvailable(googletest)
    include(GoogleTest)
    
    #message(STATUS "Setting up Google Test ... done")
endif()

# Macro setup for adding support for a target
# To use: add_simics_gtest(TARGET_NAME)
macro(add_simics_gtest target)

    # Generic libraries
    target_link_libraries(${target}
        PRIVATE -lpthread
        PRIVATE -lstdc++
    )

    # GTest Setup
    # Includes
    target_include_directories(${target}
        PRIVATE ${GTEST_INCLUDE_DIRS}
    )
    
    # GTest link libraries
    target_link_libraries(${target}
        PRIVATE GTest::gtest_main
    )

    # Simics Stub Setup
    target_link_libraries(${target}
#        PRIVATE simics-api-stubs
        PRIVATE simics-cc-api::stubbed
        PRIVATE simics-api-stubs
    )

endmacro()

#
# Local Variables:
# mode: C++
# c-basic-offset: 4
# eval: (c-set-style "linux" t)
# indent-tabs-mode: nil
# tab-width: 8
# fill-column: 120
# End:
#
# vim: et:sw=4:ts=8:si:cindent:cino=\:0,g0,(0:
#
