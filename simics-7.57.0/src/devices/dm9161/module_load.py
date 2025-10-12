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


import cli
import nic_common

def get_info(obj):
    return (nic_common.get_phy_info(obj))

def get_status(obj):
    return (nic_common.get_phy_status(obj))

def define_new_commands(classname):
    cli.new_info_command(classname, get_info)
    cli.new_status_command(classname, get_status)

define_new_commands("dm9161")
