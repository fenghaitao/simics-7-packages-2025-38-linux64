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

set(CLASSES
  x58_core_f0
  x58_core_f1
  x58_core_f2
  x58_core_f3
  x58_dmi
  x58_ioxapic
  x58_pcie_port
  x58_qpi_ncr_f0
  x58_qpi_port0_f0
  x58_qpi_port0_f1
  x58_qpi_port1_f0
  x58_qpi_port1_f1
  x58_qpi_sad_f1
  x58_remap_dispatcher
  x58_remap_unit0
  x58_remap_unit1
)
set(LEGACY)
foreach(c ${CLASSES})
  string(REPLACE "_" "-" l ${c})
  list(APPEND LEGACY ${l}-legacy)
endforeach()

simics_add_module(X58-legacy
  CLASSES ${CLASSES} ${LEGACY}
  SOURCES core-f0.dml core-f1.dml core-f2.dml core-f3.dml dmi.dml ioxapic.dml pcie-port.dml qpi-ncr-f0.dml qpi-port0-f0.dml qpi-port0-f1.dml qpi-port1-f0.dml qpi-port1-f1.dml qpi-sad-f1.dml remap-dispatcher.dml remap-unit0.dml remap-unit1.dml x58-devices.c module_load.py simics_start.py
  SIMICS_API 6
  INIT_LOCAL
)
target_link_libraries(X58-legacy
  PRIVATE io-apic::imports dml-lib
)
