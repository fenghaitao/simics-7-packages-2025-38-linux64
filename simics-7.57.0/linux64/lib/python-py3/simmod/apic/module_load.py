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

#
# ------------------------ info -----------------------
#

def get_info(obj):
    return [ (None,
              [ ("Connected on bus", obj.apic_bus),
                ("APIC id", obj.apic_id),
                ("CPU", obj.cpu) ]) ]

new_info_command('apic', get_info)

def get_status(obj):
    ia32_apic_base = obj.apicbase_msr
    lvt_timer = obj.lvt_timer
    lvt_lint0 = obj.lvt_lint0
    lvt_lint1 = obj.lvt_lint1
    lvt_error = obj.lvt_error
    lvt_perf_counter = obj.lvt_performance_counter

    delivery_mode = ("Fixed", "Reserved", "SMI", "Reserved", "NMI", "INIT", "Reserved", "ExtINT")
    timer_mode = ("One-shot", "Periodic", "TSC-deadline")

    requested = [i for (i, (_, r, _)) in enumerate(obj.status) if r != 0]
    in_service = [i for (i, (_, _, s)) in enumerate(obj.status) if s != 0]

    return [ ("Mode",
              [ ("Processor is BSP",
                 "True" if ia32_apic_base & 0x100 else "False"),
                ("APIC", "Enabled" if ia32_apic_base & 0x800 else "Disabled"),
                ("x2APIC mode",
                 "Enabled" if ia32_apic_base & 0x400 else "Disabled"),
                ("MMIO base", hex(ia32_apic_base & 0xffffffffffff0000)) ]),
             ("LVT Timer",
              [ ("Mode", timer_mode[(lvt_timer >> 17) & 0x3]),
                ("Mask", "Masked" if lvt_timer & 0x10000 else "Not masked"),
                ("Delivery status",
                 "Send pending" if lvt_timer & 0x1000 else "Idle"),
                ("Vector", lvt_timer & 0xff) ]),
             ("LVT LINT0",
              [ ("Mode", "Periodic" if lvt_lint0 & 0x20000 else "One-shot"),
                ("Mask", "Masked" if lvt_lint0 & 0x10000 else "Not masked"),
                ("Trigger", "Level" if lvt_lint0 & 0x8000 else "Edge"),
                ("Remote IRR", "1" if lvt_lint0 & 0x4000 else "0"),
                ("Input polarity", "1" if lvt_lint0 & 0x2000 else "0"),
                ("Delivery status",
                 "Send pending" if lvt_lint0 & 0x1000 else "Idle"),
                ("Delivery mode", delivery_mode[(lvt_lint0 >> 8) & 0x7]),
                ("Vector", lvt_lint0 & 0xff) ]),
             ("LVT LINT1",
              [ ("Mode", "Periodic" if lvt_lint1 & 0x20000 else "One-shot"),
                ("Mask", "Masked" if lvt_lint1 & 0x10000 else "Not masked"),
                ("Trigger", "Level" if lvt_lint1 & 0x8000 else "Edge"),
                ("Remote IRR", "1" if lvt_lint1 & 0x4000 else "0"),
                ("Input polarity", "1" if lvt_lint1 & 0x2000 else "0"),
                ("Delivery status",
                 "Send pending" if lvt_lint1 & 0x1000 else "Idle"),
                ("Delivery mode", delivery_mode[(lvt_lint1 >> 8) & 0x7]),
                ("Vector", lvt_lint1 & 0xff) ]),
             ("LVT Error",
              [ ("Mask", "Masked" if lvt_error & 0x10000 else "Not masked"),
                ("Delivery status",
                 "Send pending" if lvt_error & 0x1000 else "Idle"),
                ("Vector", lvt_error & 0xff) ]),
             ("LVT Performance Counter",
              [ ("Mask",
                 "Masked" if lvt_perf_counter & 0x10000 else "Not masked"),
                ("Delivery status",
                 "Send pending" if lvt_perf_counter & 0x1000 else "Idle"),
                ("Vector", lvt_perf_counter & 0xff) ]),
             ("IRQ Status",
              [ ("Requested", " ".join(str(x) for x in requested)),
                ("In Service", " ".join(str(x) for x in in_service))])]

new_status_command('apic', get_status)

def get_apic_bus_info(obj):
    return [ (None,
              [ ("Connected APIC(s)", obj.apics),
                ("I/O-APIC", obj.ioapic) ]) ]

new_info_command('apic-bus', get_apic_bus_info)

def get_apic_bus_status(obj):
    return []

new_status_command('apic-bus', get_apic_bus_status)
