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

simics_add_module(standard-pcie-switch
    CLASSES  standard-pcie-switch
    SOURCES switch.dml module_load.py
    SIMICS_API latest
)
simics_add_sanitizers(standard-pcie-switch)

target_link_libraries(standard-pcie-switch PRIVATE dml-lib)
