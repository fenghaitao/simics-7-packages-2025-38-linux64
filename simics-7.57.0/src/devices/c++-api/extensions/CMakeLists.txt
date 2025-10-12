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

#
# Basic/minimal setup with GCC and Ninja:
#
#   cmake -S . -B bt -G Ninja -DCMAKE_BUILD_TYPE=Debug
#   cmake --build bt
#
# To learn more, see official documentation:
#   https://cmake.org/cmake/help/latest/index.html
#   https://cmake.org/cmake/help/latest/guide/tutorial/index.html
# and this nice tutorial:
#   https://cliutils.gitlab.io/modern-cmake/
# and this list of do's and dont's
#   https://gist.github.com/mbinna/c61dbb39bca0e4fb7d1f73b0d66a4fd1
#

# In general, newer is better but a minimum of 3.20 is required
cmake_minimum_required(VERSION 3.20)

# Include check compiler flag
include(CheckCXXCompilerFlag)

# Setup default C and C++ standards (change as you see fit)
# NOTE: this must be done *before* call to project() below
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Setup project; customize to your liking
project(Simics_Project LANGUAGES C CXX ASM)

# Enable CTest support early so BUILD_TESTING is defined for all modules
include(CTest)

# Add the SME library. This is the line you need to use the library.
# We do it early to ensure our local SME is preferred over the SME
# release that comes with Simics (and which would be included
# when the Simics package is found)
add_subdirectory(src)

# Load Simics from the Base package associated with the current project
find_file(project_paths_file .project-properties/project-paths
          REQUIRED NO_DEFAULT_PATH PATHS ${CMAKE_CURRENT_SOURCE_DIR})
file(STRINGS "${project_paths_file}" project_paths)
foreach(line ${project_paths})
  if(line MATCHES "^simics-root: (.*)")
    set(SIMICS_BASE_DIR "${CMAKE_MATCH_1}")
  endif()
endforeach()
find_package(Simics REQUIRED CONFIG PATHS ${SIMICS_BASE_DIR}/cmake ${SIMICS_BASE_DIR}/../cmake)

# Put anything you want below OR into the config-user.cmake. The benefit of
# using the config-user.cmake is that you can pass --force flag to
# project-setup when upgrading Simics Base and not risk overwriting local
# configuration.
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/config-user.cmake)
  include(${CMAKE_CURRENT_SOURCE_DIR}/config-user.cmake)
endif()

# Add unit tests but exclude it from the ALL target
add_subdirectory(unittests EXCLUDE_FROM_ALL)

# Add the example but exclude them from the ALL target
add_subdirectory(examples EXCLUDE_FROM_ALL)

# Add sub directory for documentation, this is only local
# so we can build and to test it out locally before
# it goes to the release area
# Simics release build 'should' find our toc.json
# and build for Simics released documentation
add_subdirectory(doc-src EXCLUDE_FROM_ALL)
