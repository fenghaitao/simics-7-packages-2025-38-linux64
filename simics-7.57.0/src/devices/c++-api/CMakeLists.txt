# © 2022 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

if(NOT TARGET Simics::C++)

# Only the includes (useful when splitting a moduel in OBJECTS and MODULE)
add_library(simics-cc-api-includes INTERFACE IMPORTED GLOBAL)
add_library(Simics::C++::includes ALIAS simics-cc-api-includes)
target_include_directories(simics-cc-api-includes INTERFACE
  .
  $<TARGET_PROPERTY:SIMICS_GENERATED_CC_ROOT>/$<TARGET_PROPERTY:SIMICS_API>
)

# Objects are re-used for the libraries below
add_library(simics-cc-api-objects OBJECT
  after.cc
  bank.cc
  bank-instrumentation-subscribe-connection.cc
  conf-class.cc
  conf-object.cc
  event.cc
  field.cc
  fmt/format.cc
  hierarchical-object.cc
  register.cc
  utility.cc
)
add_library(simics-cc-api::objects ALIAS simics-cc-api-objects)
if(NOT CMAKE_CXX_COMPILER_ID STREQUAL "MSVC")
  target_compile_options(simics-cc-api-objects PRIVATE
    -Wall          # Enable common warnings
    -Wconversion)  # make sure we don't use implicit type conversions
endif()
target_link_libraries(simics-cc-api-objects
  PUBLIC Simics::includes Simics::C++::includes)

# The static library used by modules that either:
#  do not want to use Simics memory management; or
#  do not want to bring in Simics::Simics deps (e.g. unittests)
add_library(simics-cc-api-stub STATIC)
add_library(Simics::C++::no-mm ALIAS simics-cc-api-stub)
add_library(simics-cc-api::stubbed ALIAS simics-cc-api-stub)
target_link_libraries(simics-cc-api-stub PUBLIC
  simics-cc-api-objects
)

# The static library used by all other modules via Simics::C++ target
add_library(simics-cc-api STATIC overload-new-and-delete.cc)
add_library(Simics::C++ ALIAS simics-cc-api)
target_link_libraries(simics-cc-api PUBLIC
  simics-cc-api-objects
)
target_link_libraries(simics-cc-api INTERFACE
  Simics::Simics
  stdc++
)

# add the SME library
add_subdirectory(extensions/src)

endif()
