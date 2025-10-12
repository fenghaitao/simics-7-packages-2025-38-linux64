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
    new_info_command,
    new_status_command,
)
import nic_common
import sim_commands

#
# ---------------------- info ----------------------
#

def get_info(obj):
    return (sim_commands.get_pci_info(obj) +
            nic_common.get_nic_info(obj))



#
# --------------------- status ---------------------
#

def get_status(obj):
    csrs = obj.csrs
    return ([(None,
             [("Bus mode (CSR0)", "0x%0.8x" % csrs[0]),
              ("Transmit poll demand (CSR1)", "0x%0.8x" % csrs[1]),
              ("Receive poll demand (CSR2)", "0x%0.8x" % csrs[2]),
              ("Receive list base address (CSR3)", "0x%0.8x" % csrs[3]),
              ("Transmit list base address (CSR4)", "0x%0.8x" % csrs[4]),
              ("Status (CSR5)", "0x%0.8x" % csrs[5]),
              ("Operation mode (CSR6)", "0x%0.8x" % csrs[6]),
              ("Interrupt enable (CSR7)", "0x%0.8x" % csrs[7]),
              ("Missed frames and overflow counter (CSR8)", "0x%0.8x" % csrs[8]),
              ("Boot ROM serial, ROM MII, (CSR9)", "0x%0.8x" % csrs[9])])
             ] +
            sim_commands.get_pci_status(obj) +
            nic_common.get_nic_status(obj))

def register_commands(device_name):
    nic_common.new_nic_commands(device_name)
    new_info_command(device_name, get_info)
    new_status_command(device_name, get_status)
