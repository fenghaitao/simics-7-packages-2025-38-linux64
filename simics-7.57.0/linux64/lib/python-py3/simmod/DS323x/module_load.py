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
import simics

def get_info(obj):
    return [("Time",
             [("RTC Time", obj.base_rtc_time)]),
            ("I2C Address",
             [("The device " + obj.name +
               " is listening to addresses", [obj.address * 2, obj.address * 2 + 1])]),
            ("Address Info",
             [("Address Range", obj.address_range),
              ("Address Mode", obj.address_mode)])]

cli.new_info_command('DS323x', get_info)

def get_status(obj):
    import time
    (y, mon, d, h, min, s) = time.gmtime(obj.current_rtc_time)[:6]
    return [(None,
             [("Current RTC Time",
               "%02d-%02d-%02d %02d:%02d:%02d"
               % (y, mon, d, h, min, s))])]

cli.new_status_command('DS323x', get_status)

#
# -------------------- set-date-time --------------------
#

def set_date_time_cmd(obj, year, month, mday, hour, minute, second,
                      binary, bcd):

    # TODO: add support for binary/bcd flags

    import calendar
    try:
        obj.base_rtc_time = calendar.timegm(
            (year, month, mday, hour, minute, second))
    except:
        raise cli.CliError("Could not set time")

cli.new_command("set-date-time", set_date_time_cmd,
            [cli.arg(cli.range_t(1970, 2037, "1970..2037"), "year"),
             cli.arg(cli.range_t(1, 12, "1..12"), "month"),
             cli.arg(cli.range_t(1, 31, "1..31"), "mday"),
             cli.arg(cli.range_t(0, 23, "0..23"), "hour"),
             cli.arg(cli.range_t(0, 59, "0..59"), "minute"),
             cli.arg(cli.range_t(0, 59, "0..59"), "second"),
             cli.arg(cli.flag_t, "-binary"), cli.arg(cli.flag_t, "-bcd")],
            short = "set date and time",
            cls = 'DS323x',
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
    import time
    (y, mon, d, h, min, s) = time.gmtime(obj.current_rtc_time)[:6]
    print("Time: %02d-%02d-%02d %02d:%02d:%02d" % (y, mon, d, h, min, s))

cli.new_command("get-date-time", get_date_time_cmd,
            [],
            short = "get date and time",
            cls = 'DS323x',
            doc = """
Return the date and time of the realtime clock.<br/>
""")
