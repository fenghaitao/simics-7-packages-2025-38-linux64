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

simics_add_module(sample-pcie-ats-device
    CLASSES sample-pcie-ats-endpoint sample-pcie-root-complex-ats sample-pcie-ats-prs-dma
    SOURCES endpoint-atc.dml root-complex-ats.dml endpoint-dma.dml
    SIMICS_API latest
)
simics_add_sanitizers(sample-pcie-ats-device)

target_link_libraries(sample-pcie-ats-device PRIVATE dml-lib)

add_subdirectory(test)
