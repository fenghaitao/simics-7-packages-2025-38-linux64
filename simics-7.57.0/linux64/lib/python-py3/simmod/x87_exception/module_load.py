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
    return [ (None,
              [ ("Target processor", obj.ignne_target),
                ("Interrupt device", obj.irq_dev),
                ("Interrupt level", obj.irq_level) ] ) ]

def get_status(obj):
    return [ (None,
              [ ("FERR# line", "asserted" if obj.ferr_status else "deasserted"),
                ("IGNNE# line",
                 "asserted" if obj.ignne_status else "deasserted"),
                ("Interrupt request",
                 "active" if obj.irq_status else "inactive") ] ) ]

new_info_command('x87_exception', get_info)
new_status_command('x87_exception', get_status)
