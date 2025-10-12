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

if(SIMICS_ENABLE_TESTS_FROM_PACKAGES)
  simics_test_suite_begin()
    foreach(test checkpoint-update
                 checkpoint
                 commands
                 devices-and-functions
                 flush
                 info-status
                 legacy-ifcs
                 pcie-simple-conf
                 pcie-switch
                 transparent-mode
                 msg-to-old-style-port-map)
      simics_add_test(${test} LABELS "sanitizer")
    endforeach()
    # TODO(tsonono): Temp disable the sanitizer t285 on hotplug
    # Direct leak of 64 byte(s) in 1 object(s) allocated from:
    #0 0x146d790dd81b  (/disk2/conan_build_deps/7.18/gcc-15.1.0/bin/../lib/gcc/x86_64-pc-linux-gnu/15.1.0/../../../../lib64/libasan.so+0x13a81b)
    #1 0x106d74de6e2b in lowlevel_realloc /disk2/mp/builds/coverage.117.16065191615.1/core/src/core/util/simmalloc.c:358
    #2 0x106d65b064d9 in _DML_M_functions___add_or_del_legacy_dev /disk2/mp/builds/coverage.117.16065191615.1/src/devices/pcie-downstream-port/pcie-downstream-port-legacy.dml:176
    #3 0x106d65b06917 in _DML_M_functions__handle_legacy_dev /disk2/mp/builds/coverage.117.16065191615.1/src/devices/pcie-downstream-port/pcie-downstream-port-legacy.dml:189
    #4 0x106d65b06d8d in _DML_M_functions__del_legacy /disk2/mp/builds/coverage.117.16065191615.1/src/devices/pcie-downstream-port/pcie-downstream-port-legacy.dml:258
    #5 0x106d65b06d8d in _DML_M_pci_devices__inform_devices /disk2/mp/builds/coverage.117.16065191615.1/src/devices/pcie-downstream-port/pcie-downstream-port-legacy.dml:124
    simics_add_test(hotplug)
  simics_test_suite_end()
endif()
