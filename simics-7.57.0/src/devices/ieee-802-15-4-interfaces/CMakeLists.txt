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

simics_add_module(ieee-802-15-4-interfaces
  INTERFACES ieee_802_15_4_link ieee_802_15_4_control ieee_802_15_4_receiver ieee_802_15_4_probe
  SOURCES ieee-802-15-4-interfaces.h
  SIMICS_API latest
)
