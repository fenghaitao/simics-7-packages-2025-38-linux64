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

modname = "DS12887"

# Access functions for the NVRAM

def nvram_read(obj, offset):
    return obj.registers_nvram[offset - 14]

def nvram_write(obj, offset, value):
    nvram_values = obj.registers_nvram
    nvram_values[offset - 14] = value
    obj.registers_nvram = nvram_values

# CMOS checksum calculation

def cmos_checksum(obj):
    sum = 0
    for i in range(0x10, 0x2e):
        sum = sum + nvram_read(obj, i)
    nvram_write(obj, 0x2e, (sum >> 8) & 0xff)
    nvram_write(obj, 0x2f, sum & 0xff)

# Optionally convert value to bcd format, depending on the DM bit
def reg_value(obj, value):
    if nvram_read(obj, 11) & 0x4:
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

def set_date_time_cmd(obj, year, month, mday, hour, minute, second,
                      binary, bcd):
    if binary:
        obj.registers_a = obj.registers_a | 0x4
    elif bcd:
        obj.registers_a = obj.registers_a & ~0x4

    try:
        obj.time = "%02d-%02d-%02d %02d:%02d:%02d" % (year % 100, month, mday,
                                                      hour, minute, second)
    except:
        raise cli.CliError("Could not set time")
    # TODO: Set century if stored in CMOS

cli.new_command("set-date-time", set_date_time_cmd,
            [cli.arg(cli.range_t(1970, 2037, "1970..2037"), "year"),
             cli.arg(cli.range_t(1, 12, "1..12"), "month"),
             cli.arg(cli.range_t(1, 31, "1..31"), "mday"),
             cli.arg(cli.range_t(0, 23, "0..23"), "hour"),
             cli.arg(cli.range_t(0, 59, "0..59"), "minute"),
             cli.arg(cli.range_t(0, 59, "0..59"), "second"),
             cli.arg(cli.flag_t, "-binary"), cli.arg(cli.flag_t, "-bcd")],
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
    print("Time: %s" % obj.time)

cli.new_command("get-date-time", get_date_time_cmd,
            [],
            short = "get date and time",
            cls = modname,
            doc = """
Return the date and time of the realtime clock.<br/>
""")

#
# ------------------------ info -----------------------
#

def get_info(obj):
    return [ (None,
              [ ("IRQ device", obj.irq_dev),
                ("IRQ number", obj.irq_level) ]) ]

cli.new_info_command(modname, get_info)

def get_status(obj):
    try:
        rega = obj.registers_a
        regb = obj.registers_b
        regc = obj.registers_c
        regd = obj.registers_d
        frequencies = [0, 256, 128, 8192, 4096, 2048, 1024, 512, 256, 128, 64, 32, 16, 8, 4, 2]
    except Exception as msg:
        print("Problem reading attributes from device: %s" % msg)
        return []

    return [ (None,
              [ ("Register A", "0x%02x" % rega),
                ("UIP", "%d" % (1 if rega & 0x80 else 0)),
                ("DV", (rega >> 4) & 0x07),
                ("RS", "%d => %d Hz" % (rega & 0x0f, frequencies[rega & 0x0f])),
                ("Register B", "0x%02x" % regb),
                ("SET", 1 if regb & 0x80 else 0),
                ("PIE", 1 if regb & 0x40 else 0),
                ("AIE", 1 if regb & 0x20 else 0),
                ("UIA", 1 if regb & 0x10 else 0),
                ("SQWE", 1 if regb & 0x08 else 0),
                ("DM", 1 if regb & 0x04 else 0),
                ("12/24", 1 if regb & 0x02 else 0),
                ("DSE", 1 if regb & 0x01 else 0),
                # note, the C registers may not be updated in case of polling
                ("Register C", "0x%02x" % regc),
                ("IRQF", 1 if regc & 0x80 else 0),
                ("PF", 1 if regc & 0x40 else 0),
                ("AF", 1 if regc & 0x20 else 0),
                ("UF", 1 if regc & 0x10 else 0),
                ("Register D", "0x%02x" % regd),
                ("VRT", 1 if regd & 0x80 else 0) ]),
             ("Date and Time Registers",
              [ ("Sec", "0x%02x" % obj.registers_seconds),
                ("Min", "0x%02x" % obj.registers_minutes),
                ("Hour", "0x%02x" % obj.registers_hours),
                ("Day", "0x%02x" % obj.registers_day_of_the_week),
                ("Date", "0x%02x" % obj.registers_date_of_the_month),
                ("Month", "0x%02x" % obj.registers_month),
                ("Year", "0x%02x" % obj.registers_year) ]),
             ("Alarm Registers",
              [ ("Sec", "0x%02x" % obj.registers_seconds_alarm),
                ("Min", "0x%02x" % obj.registers_minutes_alarm),
                ("Hour", "0x%02x" % obj.registers_hours_alarm) ])]

cli.new_status_command(modname, get_status)
