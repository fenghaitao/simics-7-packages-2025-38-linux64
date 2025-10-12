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

simics_add_module(sample-pcie-shim
  COMPONENTS sample_pcie_switch_shim_comp
             sample_pcie_endpoint_shim_comp
  CLASSES pcie-shim-stub
          pcie-endpoint-shim-frontend
          pcie-port-shim-frontend
          sample-pcie-external-connection
  SOURCES pcie-shim.cc
          pcie-shim-stub.cc
          pcie-external-connection.cc
          pcie-endpoint-shim-frontend.dml
          pcie-port-shim-frontend.dml
          init.c
          sample_pcie_shim_comp.py
          module_load.py
  SIMICS_API latest
  INIT_LOCAL
)
target_link_libraries(sample-pcie-shim
  PRIVATE dml-lib Simics::C++
)

add_library(sample-pcie-shim-lib STATIC pcie-shim.cc)
target_link_libraries(sample-pcie-shim-lib
  PUBLIC Simics::C++
)
# Set rpath to libstdc++
if(NOT WIN32)
  set_target_properties(sample-pcie-shim-lib PROPERTIES BUILD_RPATH $ORIGIN/../sys/lib)
endif()
target_include_directories(sample-pcie-shim-lib INTERFACE .)
