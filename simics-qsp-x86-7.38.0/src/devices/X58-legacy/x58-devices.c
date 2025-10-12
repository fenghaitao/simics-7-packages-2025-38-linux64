/*
  © 2021 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <simics/device-api.h>

void
init_local()
{
        /* Register class-aliases for the old-style names, with underscore,
           pointing to variants of the devices using legacy PCIe libraries */
        SIM_register_class_alias("x58_dmi", "x58-dmi-legacy");
        SIM_register_class_alias("x58_core_f0", "x58-core-f0-legacy");
        SIM_register_class_alias("x58_core_f1", "x58-core-f1-legacy");
        SIM_register_class_alias("x58_core_f2", "x58-core-f2-legacy");
        SIM_register_class_alias("x58_core_f3", "x58-core-f3-legacy");
        SIM_register_class_alias("x58_ioxapic", "x58-ioxapic-legacy");
        SIM_register_class_alias("x58_qpi_port0_f0", "x58-qpi-port0-f0-legacy");
        SIM_register_class_alias("x58_qpi_port0_f1", "x58-qpi-port0-f1-legacy");
        SIM_register_class_alias("x58_qpi_port1_f0", "x58-qpi-port1-f0-legacy");
        SIM_register_class_alias("x58_qpi_port1_f1", "x58-qpi-port1-f1-legacy");
        SIM_register_class_alias("x58_pcie_port", "x58-pcie-port-legacy");
        SIM_register_class_alias("x58_remap_dispatcher", "x58-remap-dispatcher-legacy");
        SIM_register_class_alias("x58_remap_unit0", "x58-remap-unit0-legacy");
        SIM_register_class_alias("x58_remap_unit1", "x58-remap-unit1-legacy");
        SIM_register_class_alias("x58_qpi_ncr_f0", "x58-qpi-ncr-f0-legacy");
        SIM_register_class_alias("x58_qpi_sad_f1", "x58-qpi-sad-f1-legacy");
}
