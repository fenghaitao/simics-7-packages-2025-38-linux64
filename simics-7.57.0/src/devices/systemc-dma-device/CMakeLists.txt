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

# This does not build the Simics module, but rather provide a target depends
# on by another module

add_library(systemc-dma-device INTERFACE)
target_sources(systemc-dma-device INTERFACE dma-device.cc)
target_include_directories(systemc-dma-device INTERFACE .)
