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
import sim_commands

def get_info(obj):
    return [ (None, [
        ("PHY object", obj.phy),
        ] ) ] + sim_commands.get_pci_info(obj)

def get_status(obj):
    return sim_commands.get_pci_status(obj)

cli.new_info_command('i82559', get_info)
cli.new_status_command('i82559', get_status)
