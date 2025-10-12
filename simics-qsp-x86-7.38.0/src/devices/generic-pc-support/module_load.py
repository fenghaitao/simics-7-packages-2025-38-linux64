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
from cli import (new_command, arg, range_t, flag_t)

def set_date_time_cmd(obj, year, month, mday, hour, minute, second,
                      binary, bcd):
    if binary:
        obj.rtc_reg_a = obj.rtc_reg_a | 0x4
    elif bcd:
        obj.rtc_reg_a = obj.rtc_reg_a & ~0x4

    try:
        obj.time = "%02d-%02d-%02d %02d:%02d:%02d" % (year % 100, month, mday,
                                                      hour, minute, second)
    except:
        raise cli.CliError("Could not set time")

new_command("set-date-time", set_date_time_cmd,
            [arg(range_t(1970, 2037, "1970..2037"), "year"),
             arg(range_t(1, 12, "1..12"), "month"),
             arg(range_t(1, 31, "1..31"), "mday"),
             arg(range_t(0, 23, "0..23"), "hour"),
             arg(range_t(0, 59, "0..59"), "minute"),
             arg(range_t(0, 59, "0..59"), "second"),
             arg(flag_t, "-binary"), arg(flag_t, "-bcd")],
            short = "set date and time",
            cls = "generic_rtc",
            doc = """
Set the date and time of the realtime clock. Both <arg>month</arg> and
<arg>mday</arg> start counting at one while <arg>hour</arg>,
<arg>minute</arg> and <arg>second</arg>, start at zero.
The <arg>year</arg> argument should be in the full four-digit format.

The <cmd>&lt;x86-component&gt;.cmos-init</cmd> command must be issued before
this command, unless the simulation was started from a checkpoint.

The <tt>-binary</tt> and <tt>-bcd</tt> flags can be used to specify the format
of the register values. Default is to use BCD, but some systems use a binary
format without checking the binary/BCD status bit in register B.
""")

device_name = 'minimal_acpi_support'

def get_info_mas(obj):
    return [(None,[('CPUs',obj.cpus)])]

def get_status_mas(obj):
    return [(None,[('SMI pin raised',obj.cpus_smi_state)])]

cli.new_info_command(device_name, get_info_mas)
cli.new_status_command(device_name, get_status_mas)

device_name = 'cf9_handler'

def get_info_cf9(obj):
    return [(None,[('Reset signal target',obj.reset_signal),
                   ('Init signal target',obj.init_signal)])]

def get_status_cf9(obj):
    return [(None,[('Status','Intentionally empty.')])]

cli.new_info_command(device_name, get_info_cf9)
cli.new_status_command(device_name, get_status_cf9)

device_name = 'pci_cf8_cfc_handler'

def get_info_cf8(obj):
    return [(None,[('Downstream target',obj.downstream_target)])]

def get_status_cf8(obj):
    return [(None,[('Status','Intentionally empty.')])]

cli.new_info_command(device_name, get_info_cf8)
cli.new_status_command(device_name, get_status_cf8)

device_name = 'generic_hpet'

def get_info_hpet(obj):
    bdfs = [(n, hex(bdf)) for n, bdf in zip(range(len(obj.bdf_for_memory_space_msi)), obj.bdf_for_memory_space_msi)]
    return [("", [("Number of timers", ((obj.regs_gcap_id >> 8) & 0x1F) + 1),
                   ("Connected APIC", obj.intc_apic),
                   ("MSI memory space", obj.memory_space),
                   ("MSI transaction target", obj.msi_transaction_tgt),
                   ("BDF use as requester ID for MSI", bdfs),
                  ])]

def get_status_hpet(obj):
    num = ((obj.regs_gcap_id >> 8) & 0x1F) + 1
    st = []
    for i in range(num):
        v = []
        if obj.regs_tim_conf[i] & (1 << 2):
            v.append("Enabled")
        else:
            v.append("Disabled")
        if (obj.regs_tim_conf[i] & (1 << 14)):
            v.append("FSB")
            x = obj.regs_fsb_int_rout[i]
            v.append("[0x%x @ 0x%08x]" % (x & 0xffffffff, (x >> 32)))
        else:
            if (obj.regs_tim_conf[i] & (1 << 1)):
                v.append("Level")
            else:
                v.append("Edge")
            if i < 2 and (obj.regs_gen_conf & (1 << 1)):
                route = "Legacy IRQ[%s]" % ("0/2", "8")[i]
            else:
                route = "IRQ[%d]" % ((obj.regs_tim_conf[i] >> 9) & 0x1f)
            v.append(route)
        if obj.regs_tim_conf[i] & (1 << 8):
            v.append("32-bit")
        if obj.regs_tim_conf[i] & (1 << 6):
            v.append("VAL-SET-CONF")
        if obj.regs_tim_conf[i] & (1 << 3):
            v.append("Periodic")
        st.append(("Timer%d" % i, " ".join(v)))

    cmp = []
    for i in range(num):
        v = []
        mask = 0xffffffff
        if (obj.regs_tim_conf[i] & 0x120) == 0x20:
            mask = 0xffffffffffffffff
        v.append("0x%x" % (obj.regs_tim_comp[i] & mask))
        if obj.regs_tim_conf[i] & (1 << 3):
            period = float(obj.regs_tim_period[i] * (obj.regs_gcap_id >> 32))
            if period != 0:
                freq = 1e15 / period
                v.append("  (periodic @ %.2f Hz)" % freq)
            else:
                v.append("  PERIOD = 0")
        elif obj.regs_tim_conf[i] & (1 << 2):
            val = (obj.regs_tim_comp[i] - obj.regs_running_main_cnt) & mask
            ms = 1e-12 * float(val * (obj.regs_gcap_id >> 32))
            v.append("  (expires in %.3f ms)" % ms)
        cmp.append(("Timer%d" % i, " ".join(v)))

    gst = [
        ('State', ("Halted", "Running")[obj.regs_gen_conf & 1]),
        ]

    v , q = [], []
    for i in range(num):
        sbit = (obj.regs_gintr_sta & (1 << i))
        if sbit:
            v.append("Timer%d" % i)

        pin = obj.regs_irq_pins[i]
        valid, apic, i8259 = (pin >> 16) & 1, (pin & 0xff), (pin >> 8) & 0xff
        if valid:
            if apic == i8259:
                q.append("IRQ[%d]" % (apic))
            else:
                q.append("IRQ[%d/%d]" % (i8259, apic))

    gst.append(("Status", " ".join(v)))
    gst.append(("IRQ Pins", " ".join(q)))
    gst.append(('Counter', "0x%x" % obj.regs_running_main_cnt))

    return [("Configuration", st),
            ("State", gst),
            ("Comparators", cmp),
            ]

cli.new_info_command(device_name, get_info_hpet)
cli.new_status_command(device_name, get_status_hpet)

device_name = 'generic_rtc'

def get_info_rtc(obj):
    addr = 0x70
    rtc_info = [("RTC base address", "0x%x" % addr)]
    return [(None, rtc_info)]

def get_status_rtc(obj):
    bcd_binary_tuple = ("BCD", "Binary")
    hours_tuple = ("12H", "24H")
    rtc_status = [("RTC current time", obj.time),
                  ("RTC hours format", hours_tuple[(obj.rtc_reg_b >> 1) & 0x1]),
                  ("RTC data Mode",
                        bcd_binary_tuple[(obj.rtc_reg_b >> 2) & 0x1]),
                 ]
    return [(None, rtc_status)]

cli.new_info_command(device_name, get_info_rtc)
cli.new_status_command(device_name, get_status_rtc)

device_name = 'pci_upstream_dispatcher'

def get_info_dispatcher(obj):
    return [(None,[('Default remap unit', obj.default_remapping_unit),
                   ('GFX remap unit', obj.gfx_remapping_unit),
                   ('GFX objects', obj.gfx_objs),
                   ('Legacy PCI interrupt target', obj.interrupt)])]

def get_status_dispatcher(obj):
    return [(None,[('Status','Intentionally empty.')])]

cli.new_info_command(device_name, get_info_dispatcher)
cli.new_status_command(device_name, get_status_dispatcher)
