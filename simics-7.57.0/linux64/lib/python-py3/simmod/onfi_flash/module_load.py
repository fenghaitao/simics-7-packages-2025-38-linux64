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

def get_info(obj):
    return [(None,
             [("Blocks", obj.blocks),
              ("Pages per block", obj.pages_per_block),
              ("Data bytes per page", obj.data_bytes_per_page),
              ("Spare bytes per page", obj.spare_bytes_per_page),
              ("Bus width", "%d bits" % (obj.bus_width)),
              ("ID bytes", " ".join(["0x%02x" % x for x in obj.id_bytes])),
              ("Status byte", "0x%02x" % obj.status_byte)])]

def get_status(obj):
    return [(None,
             [("Command latch enable pin",
               "high" if obj.command_latch_enable else "low"),
              ("Address latch enable pin",
               "high" if obj.address_latch_enable else "low"),
              ("Write protect pin", "high" if obj.write_protect else "low")])]

new_info_command('onfi_flash', get_info)
new_status_command('onfi_flash', get_status)
