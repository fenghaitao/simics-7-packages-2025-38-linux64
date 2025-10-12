# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from cli import (
    get_last_loaded_module,
    new_info_command,
    new_status_command,
)
import nic_common

device_name = get_last_loaded_module()

register_names = ["Control",
                  "Status",
                  "PHY Identifier",
                  "PHY Identifier",
                  "Auto-Negotiation Advertisement",
                  "Link Partner Ability",
                  "Auto-Negotiation Expansion",
                  "Next Page Transmit",
                  "Link Partner Next Page",
                  "1000BASE-T Control",
                  "1000BASE-T Status",
                  "Reserved",
                  "Reserved",
                  "Reserved",
                  "Reserved",
                  "Extended Status",
                  "PHY Specific Control",
                  "PHY Specific Status",
                  "Interrupt Enable",
                  "Interrupt Status",
                  "Extended PHY Specific Control",
                  "Receive Error Counter",
                  "Extended Address",
                  "Global Status",
                  "LED Control",
                  "Manual LED Override",
                  "Extended Control 2",
                  "Extended Status",
                  "Cable Tester Status",
                  "Extended Address",
                  "Calibration",
                  "Reserved"]

#
# ---------------------- info ----------------------
#

def get_info(obj):
    return []

#
# --------------------- status ---------------------
#

def get_status(obj):
    register_values = ["0x%04x" % x for x in obj.registers]
    return [("MII Management Register Set", zip(register_names, register_values))]

nic_common.new_nic_commands(device_name)
new_info_command(device_name, get_info)
new_status_command(device_name, get_status)
