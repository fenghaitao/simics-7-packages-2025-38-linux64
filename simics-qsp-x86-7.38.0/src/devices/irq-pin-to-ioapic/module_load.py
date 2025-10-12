# © 2025 Intel Corporation
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

device_name = 'irq_pin_to_ioapic'

def get_info(obj):
    irq2pin = [ f'IRQ {n} - >IOAPIC Pin {m}' for n,m in zip(range(len(obj.irq_to_ioapic_pin)), obj.irq_to_ioapic_pin)]
    irqtype = [ f'IRQ {n} {"edge" if m else "level"}' for n,m in zip(range(len(obj.irq_is_edge_triggered)), obj.irq_is_edge_triggered)]
    return [(None,[('IOAPIC', obj.to_ioapic),
                   ('Input IRQ to IOAPIC pin map', irq2pin),
                   ('Input IRQ type', irqtype),
                  ])]

def get_status(obj):
    pirq = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    pirqstate = [ f'PIRQ{n}={m}' for n,m in zip(pirq, obj.irq_level)]
    return [(None,[('PIRQ[A-H] level', pirqstate)])]

cli.new_info_command(device_name, get_info)
cli.new_status_command(device_name, get_status)
