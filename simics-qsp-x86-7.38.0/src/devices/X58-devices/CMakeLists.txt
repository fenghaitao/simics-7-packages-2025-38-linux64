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

simics_add_module(X58-devices
  CLASSES x58-core x58-dmi x58-ioxapic x58-pcie-port x58-pcie-port-acs x58-qpi-arch x58-qpi-port x58-remap-unit
  # NOTE: remap-unit.dml *must* come before core.dml to satisfy order dependency
  SOURCES remap-unit.dml core.dml dmi.dml ioxapic.dml pcie-port.dml pcie-port-acs.dml qpi-arch.dml qpi-port.dml module_load.py
  SIMICS_API latest
)
target_link_libraries(X58-devices
  PRIVATE io-apic::imports dml-lib
)

get_property(dmlc_flags GLOBAL PROPERTY SIMICS_DMLC_FLAGS)
list(APPEND dmlc_flags --nowarn=WEXPERIMENTAL)
set_target_properties(X58-devices  # qpi-arch.dml
  PROPERTIES SIMICS_DMLC_FLAGS "${dmlc_flags}"
)

add_subdirectory(test)
