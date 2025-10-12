# INTEL CONFIDENTIAL

# © 2022 Intel Corporation
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

apic_class_name     = 'x2apic_v2'
apic_bus_class_name = 'apic_bus_v2'

def apic_get_info(obj):
    return [ (None,
              [ ("Connected on bus", obj.apic_bus),
                ("APIC id", obj.apic_id),
                ("CPU", obj.cpu) ]) ]

def apic_get_status(obj):
    ia32_apic_base = obj.bank.apic_regs.IA32_APIC_BASE_MSR
    lvt_cmci  = obj.bank.apic_regs.LVT_CMCI
    lvt_timer = obj.bank.apic_regs.LVT_Timer
    lvt_lint0 = obj.bank.apic_regs.LVT_LINT0
    lvt_lint1 = obj.bank.apic_regs.LVT_LINT1
    lvt_error = obj.bank.apic_regs.LVT_Error
    lvt_perf_counter = obj.bank.apic_regs.LVT_Performance

    delivery_mode = ("Fixed", "Reserved", "SMI", "Reserved", "NMI", "INIT", "Reserved", "ExtINT")
    timer_mode = ("One-shot", "Periodic", "TSC-deadline")

    isrs = obj.bank.apic_regs.ISR
    isrs_as_bit_string = ''.join([ format(e,'032b')[::-1] for e in isrs ])
    irrs = obj.bank.apic_regs.IRR
    irrs_as_bit_string = ''.join([ format(e,'032b')[::-1] for e in irrs ])

    requested  = [i for (i , r ) in enumerate(irrs_as_bit_string) if r != '0']
    in_service = [i for (i , r ) in enumerate(isrs_as_bit_string) if r != '0']

    return [ ("Mode",
              [ ("Processor is BSP",
                 "True" if ia32_apic_base & 0x100 else "False"),
                ("APIC", "Enabled" if ia32_apic_base & 0x800 else "Disabled"),
                ("x2APIC mode",
                 "Enabled" if ia32_apic_base & 0x400 else "Disabled"),
                ("MMIO base", hex(ia32_apic_base & 0xffffffffffff0000)) ]),
             ("LVT CMCI",
              [ ("Mask", "Masked" if lvt_cmci & 0x10000 else "Not masked"),
                ("Delivery status", "Send pending" if lvt_cmci & 0x1000 else "Idle"),
                ("Vector", lvt_cmci & 0xff) ]),
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

def apic_bus_get_info(obj):
    return [ (None,
              [ ("Connected APIC(s)", obj.apics),
                ("I/O-APIC(s)", obj.ioapics),
                ("PIC", obj.pic),
                ("Forward APIC bus", obj.fwd_apic_bus)])]

def apic_bus_get_status(obj):
    return [ (None,
              [ ("Message", "This status output is intentionally empty.")])]


cli.new_info_command(apic_class_name, apic_get_info)
cli.new_info_command(apic_bus_class_name, apic_bus_get_info)

cli.new_status_command(apic_class_name, apic_get_status)
cli.new_status_command(apic_bus_class_name, apic_bus_get_status)
