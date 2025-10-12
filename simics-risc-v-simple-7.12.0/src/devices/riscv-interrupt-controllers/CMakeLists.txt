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

simics_add_module(riscv-interrupt-controllers
  CLASSES riscv-clint riscv-plic riscv_clint riscv_plic
  SOURCES clint.dml plic.dml riscv-interrupt-controllers.c module_load.py simics_start.py
  INIT_LOCAL
  SIMICS_API latest
)
target_link_libraries(riscv-interrupt-controllers
  PRIVATE riscv-common
)
add_subdirectory(test)
