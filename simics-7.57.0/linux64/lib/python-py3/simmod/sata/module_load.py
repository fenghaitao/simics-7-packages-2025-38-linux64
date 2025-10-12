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

def sata_get_info(obj):
    return [ (None,
              [ ("Host adaptor", obj.hba),
                ("IDE drive", obj.master),
                ("Interrupt delay", obj.interrupt_delay) ] ) ]

def sata_get_status(obj):
    return [ (None,
              [("LBA mode", obj.lba_mode),
                ] ) ]

new_info_command("sata", sata_get_info)
new_status_command("sata", sata_get_status)
