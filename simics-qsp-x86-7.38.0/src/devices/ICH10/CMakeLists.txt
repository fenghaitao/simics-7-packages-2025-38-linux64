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

# skip-cmake-conversion

simics_add_module(ICH10
  CLASSES ich10_lpc
          ich10_sata_f2
          ich10_sata_f5
          ich10_thermal
          ich10_smbus
          ich10_smbus_i2c_v2
          ich10_usb_uhci
          ich10_usb_ehci
          ich10_bridge
          ich10_hpe_timer
          ich10_timer
          ich10_rtc
          ich10_spi
          ich10_cf9
  SOURCES lpc.dml
          sata-f2.dml
          sata-f5.dml
          thermal.dml
          smbus.dml
          smbus-i2c-v2.dml
          usb-uhci.dml
          usb-ehci.dml
          bridge.dml
          hpe-timer.dml
          timer.dml
          rtc.dml
          spi.dml
          cf9.dml
          module_load.py
  SIMICS_API 6
)
simics_copy_python_files(ICH10 FROM ICH FILES ich_commands.py)
target_link_libraries(ICH10
  PRIVATE ICH ICH__lpc ICH__sata io-apic::imports ide::imports serial-interrupt-interface::imports sata-ahci dml-lib
)
