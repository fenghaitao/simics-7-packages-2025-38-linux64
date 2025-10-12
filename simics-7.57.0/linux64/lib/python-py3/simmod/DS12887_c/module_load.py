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
    CliError,
    arg,
    flag_t,
    get_last_loaded_module,
    new_command,
    new_info_command,
    new_status_command,
    range_t,
    )
from simics import *

# shared source
modname = get_last_loaded_module()

def cmos_checksum(obj):
    sum = 0
    for i in range(0x10, 0x2e):
        sum = sum + obj.nvram[i]
    # write checksum
    obj.nvram[0x2e] = (sum >> 8) & 0xff
    obj.nvram[0x2f] = sum & 0xff

def reg_value(obj, value):
    if obj.nvram[11] & 0x4:
        # binary
        return value
    else:
        #bcd
        hi = value // 10
        lo = value - (hi * 10)
        return hi << 4 | lo

#
# -------------------- set-date-time --------------------
#

def set_date_time_cmd(obj, year, month, mday, hour, minute, second, binary, bcd):
    if binary:
        obj.nvram[11] = obj.nvram[11] | 4
    elif bcd:
        obj.nvram[11] = obj.nvram[11] & ~0x4

    if modname == "DS17485":
        # For DS17485 only, has a dedicated register for century
        obj.nvram_bank1[0x48 - 0x40] = year // 100
    else:
        # Century is usually stored in CMOS
        obj.nvram[0x32] = reg_value(obj, year // 100)
        # TODO: only update CMOS checksum after changing century on x86?
        cmos_checksum(obj)

    try:
        obj.year = year
        obj.month = month
        obj.mday = mday
        obj.hour = hour
        obj.minute = minute
        obj.second = second
    except Exception as y:
        raise CliError("Error setting time in " + modname + " device: %s" % y)

new_command("set-date-time", set_date_time_cmd,
            [arg(range_t(1990, 2037, "1990..2037"), "year"),
             arg(range_t(1, 12, "1..12"), "month"),
             arg(range_t(1, 31, "1..31"), "mday"),
             arg(range_t(0, 23, "0..23"), "hour"),
             arg(range_t(0, 59, "0..59"), "minute"),
             arg(range_t(0, 59, "0..59"), "second"),
             arg(flag_t, "-binary"), arg(flag_t, "-bcd")],
            short = "set date and time",
            cls = modname,
            doc = """
Set the date and time of the realtime clock. Both <arg>month</arg> and
<arg>mday</arg> start counting at one while <arg>hour</arg>,
<arg>minute</arg> and <arg>second</arg>, start at zero.
The <arg>year</arg> argument should be in the full four-digit format.

The <cmd>&lt;x86-component&gt;.cmos-init</cmd> command must be issued before
this command, unless the simulation was started from a checkpoint.

The <tt>-binary</tt> and <tt>-bcd</tt> flags can be used to
specify the format of the register values. Default is to use BCD, but
some systems use a binary format without checking the binary/BCD status
bit in register B.
""")



#
# -------------------- get-date-time --------------------
#

def get_date_time_cmd(obj):
    print("Time: %04d-%02d-%02d %02d:%02d:%02d" % (
        obj.year, obj.month,obj.mday,
        obj.hour, obj.minute, obj.second))

new_command("get-date-time", get_date_time_cmd,
            [],
            short = "get date and time",
            cls = modname,
            doc = """
Return the date and time of the real-time clock.<br/>
""")

#
# ------------------------ info -----------------------
#

def get_info(obj):
    return [ (None,
              [ ("IRQ device", obj.irq_dev),
                ("IRQ number", obj.irq_level) ]) ]

new_info_command(modname, get_info)

def get_status(obj):
    try:
        rega = obj.nvram[10]
        regb = obj.nvram[11]
        regc = obj.nvram[12]
        regd = obj.nvram[13]
        rsus = obj.period_in_us
    except Exception as msg:
        print("Problem reading attributes from device: %s" % msg)
        return []

    return [ (None,
              [ ("Register A", "0x%x" % rega),
                ("UIP", "%d" % (1 if rega & 0x80 else 0)),
                ("DV", (rega >> 4) & 7),
                ("RS", "%d => %d us" % (rega & 0x0f, rsus[rega & 0x0f])),
                ("Register B", "0x%x" % regb),
                ("SET", 1 if regb & 0x80 else 0),
                ("PIE", 1 if regb & 0x40 else 0),
                ("AIE", 1 if regb & 0x20 else 0),
                ("UIA", 1 if regb & 0x10 else 0),
                ("SQWE", 1 if regb & 0x08 else 0),
                ("DM", 1 if regb & 0x04 else 0),
                ("12/24", 1 if regb & 0x02 else 0),
                ("DSE", 1 if regb & 0x01 else 0),
                # note, the C registers may not be updated in case of polling
                ("Register C", "0x%x" % regc),
                ("IRQF", 1 if regc & 0x80 else 0),
                ("PF", 1 if regc & 0x40 else 0),
                ("AF", 1 if regc & 0x20 else 0),
                ("UF", 1 if regc & 0x10 else 0),
                ("Register D", "0x%x" % regd),
                ("VRT", 1 if regd & 0x80 else 0) ]),
             ("Date and Time Registers",
              [ ("Sec", "0x%02x" % obj.nvram[0]),
                ("Min", "0x%02x" % obj.nvram[2]),
                ("Hour", "0x%02x" % obj.nvram[4]),
                ("Day", "0x%02x" % obj.nvram[6]),
                ("Date", "0x%02x" % obj.nvram[7]),
                ("Month", "0x%02x" % obj.nvram[8]),
                ("Year", "0x%02x" % obj.nvram[9]) ]),
             ("Alarm Registers",
              [ ("Sec", "0x%02x" % obj.nvram[1]),
                ("Min", "0x%02x" % obj.nvram[3]),
                ("Hour", "0x%02x" % obj.nvram[5]) ])]

new_status_command(modname, get_status)

def nvram_update_hap_handler(arg, obj, index, old_value, new_value):
    count = SIM_step_count(obj)
    print("%s [%d]=%s (old value %s)" % (count, index, new_value, old_value))

def trace_nvram_cmd(obj):
    SIM_hap_add_callback("RTC_Nvram_Update", nvram_update_hap_handler, obj)

new_command("trace-nvram", trace_nvram_cmd,
            [],
            type  = ["Tracing"],
            short = "trace nvram updates",
            cls = modname,
            doc = """
Trace all nvram updates.<br/>
""")
