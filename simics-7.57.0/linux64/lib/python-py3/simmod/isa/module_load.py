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
    return [ ("Connections",
              [ ("Legacy PIC", obj.pic),
                ("I/O-APIC", obj.ioapic) ]),
             ("IRQ to I/O-APIC pin assignment",
              [("IRQ %d" % i, "Pin %d" % obj.irq_to_pin[i]) for i in range(len(obj.irq_to_pin))]) ]

def get_status(obj):
    return [ ("IRQ status",
              [("IRQ %d" % i, "active" if obj.irq_status[i] else "inactive")
               for i in range(len(obj.irq_status))]) ]

new_info_command('ISA', get_info)
new_status_command('ISA', get_status)
