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


import cli
import conf

cls = 'simics-uefi'

# .info command returns data reported in PCIe capabilities
def info_cmd(obj):
    return [(None,
             [("Package numbers", obj.package_data),
              ("Selected video mode", obj.video_mode)])]

# .status command returns number of accesses to capabilities
def status_cmd(obj):
    return [(None,
             [("Accesses", obj.caps_accesses),
              ("Detected video modes", obj.detected_video_modes)
             ])]

cli.new_info_command(cls, info_cmd)
cli.new_status_command(cls, status_cmd)
