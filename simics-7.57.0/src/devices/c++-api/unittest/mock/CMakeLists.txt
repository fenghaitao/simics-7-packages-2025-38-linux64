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

# The stubs should not honor CMAKE_LIBRARY_OUTPUT_DIRECTORY, that would just be
# confusing. The shared library is for internal purposes and it's path should
# be propagated to the user through CMake mechanisms (meaning that the location
# is irrelevant).

if(NOT TARGET simics-api-stubs)
    set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}")
    # We turned this into a SHARED library in
    # 08bf479344fe633e4d6c90ae760f23a1307a987d to avoid some problems with weak
    # symbols when stubs was used outside of the C++ API unittests ; but on
    # Windows the problem is reversed and we need to build a static or else we
    # will have problems locating the DLL (and STATIC works just fine so far).
    if(WIN32)
      add_library(simics-api-stubs STATIC)
    else()
      add_library(simics-api-stubs SHARED)
    endif()
    target_sources(simics-api-stubs PRIVATE stubs.cc)
    target_include_directories(simics-api-stubs PUBLIC .)
    target_link_libraries(simics-api-stubs PRIVATE simics-cc-api::stubbed)
endif()
