# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import dataclasses

from enum import Enum

import cli
import table
import json

class Mode(Enum):
    RM_RESUME = 0
    RM_STEP_OVER = 1
    RM_STEP_INTO = 2
    RM_STEP_OVER_LINE = 3
    RM_STEP_INTO_LINE = 4
    RM_STEP_OUT = 5
    RM_REVERSE_RESUME = 6
    RM_REVERSE_STEP_OVER = 7
    RM_REVERSE_STEP_INTO = 8
    RM_REVERSE_STEP_OVER_LINE = 9
    RM_REVERSE_STEP_INTO_LINE = 10
    RM_REVERSE_STEP_OUT = 11
    RM_STEP_OVER_RANGE = 12
    RM_STEP_INTO_RANGE = 13
    RM_REVERSE_STEP_OVER_RANGE = 14
    RM_REVERSE_STEP_INTO_RANGE = 15
    RM_UNTIL_ACTIVE = 16
    RM_REVERSE_UNTIL_ACTIVE = 17

class Command(Enum):
    Command_Nothing = 0
    Command_Forward = 1
    Command_Into = 2
    Command_Over = 3
    Command_Out = 4
    Command_Instruction_Into = 5
    Command_Instruction_Over = 6
    Command_Until_Active = 7

@dataclasses.dataclass
class Stat:
    """This class must match the order and types of the data entries in the
    tcf.stepping_statistics attribute."""
    mode: int
    command: int
    origin_pc: int
    resulting_pc: int
    ctx_id: str
    peer: str
    cache_misses: int
    cache_miss_info: list
    cache_miss_time: int
    real_time: int
    sim_time: int
    address_to_line: int
    find_symbol_by_addr: int

    @classmethod
    def get_field_names(cls):
        return [field.name for field in dataclasses.fields(cls)]

    @classmethod
    def verify_fields(cls, fields):
        for field in fields:
            assert field in cls.get_field_names(), (
                f"Unknown field '{field}'")

    @classmethod
    def non_counter_fields(cls):
        return ["mode", "command", "origin_pc", "resulting_pc", "ctx_id",
                "cache_miss_info", "peer"]

    @classmethod
    def counter_fields(cls):
        return set(cls.get_field_names()) - set(cls.non_counter_fields())

    @classmethod
    def time_fields(cls):
        return ["cache_miss_time", "real_time", "sim_time"]

    @classmethod
    def on_by_default(cls, f):
        return f not in ["command", "cache_miss_info"]

    def _repr_cache_miss_info(self, val):
        res = ""
        for (i, (n, cnt)) in enumerate(val):
            if i > 0:
                res += ","
            res += f"{n}={cnt}"
        return res

    @classmethod
    def get_printable_field_name(cls, field):
        if field == "real_time":
            return f"{field} (us)"
        elif field == "cache_miss_time":
            return f"{field} (us)"
        elif field == "sim_time":
            return f"{field} (ps)"
        return field

    def get_printable_field_value(self, field):
        value = getattr(self, field)
        if field == "mode":
            return Mode(value).name
        elif field == "command":
            return Command(value).name
        elif field in ("origin_pc", "resulting_pc"):
            return hex(value)
        elif field in ("ctx_id", "peer"):
            return value
        elif field == "cache_miss_info":
            return self._repr_cache_miss_info(value)
        assert field in Stat.counter_fields()
        return value

    def __repr__(self):
        fields = []
        for field in self.get_field_names():
            value = getattr(self, field)
            printable_value = self.get_printable_field_value(field)
            if printable_value != value:
                fields.append(f"{field}={printable_value} ({value})")
            else:
                fields.append(f"{field}={value}")
        return f"{self.__class__.__name__}({', '.join(fields)})"

def summarize(countable):
    return [sum(column) for column in zip(*countable)]

def is_statistics_enabled(tcf):
    return tcf.stepping_statistics_enabled

def enable_statistics(tcf):
    tcf.stepping_statistics_enabled = True

def disable_statistics(tcf):
    tcf.stepping_statistics_enabled = False

def clear_statistics(tcf):
    tcf.stepping_statistics = []

def get_statistics(tcf, printable=False, **field_args):
    Stat.verify_fields(field_args.keys())
    enabled = [x for x in field_args if field_args[x]]
    rows = []
    for (step_info, counters) in tcf.stepping_statistics:
        stat = Stat(*(step_info + counters))
        rows.append([stat.get_printable_field_value(x) if (
            printable) else getattr(stat, x) for x in enabled])
    return rows

def register():
    class Format:
        @classmethod
        def field_to_arg(cls, field):
            return field.replace("_", "-")

    def sub_cmd_status(tcf):
        status = "enabled" if is_statistics_enabled(tcf) else "disabled"
        return cli.command_verbose_return(
            value=status, message=f"Stepping statistics is {status}")

    def sub_cmd_enable_disable(tcf, enable):
        already = enable == is_statistics_enabled(tcf)
        enable_msg = "enabled" if enable else "disabled"
        if already:
            msg = f"Stepping statistics is already {enable_msg}."
        else:
            msg = f"Stepping statistics is now {enable_msg}."
            if enable:
                enable_statistics(tcf)
            else:
                disable_statistics(tcf)
        return cli.command_verbose_return(value=enable, message=msg)

    def sub_cmd_enable(tcf):
        return sub_cmd_enable_disable(tcf, True)

    def sub_cmd_disable(tcf):
        return sub_cmd_enable_disable(tcf, False)

    def sub_cmd_clear(tcf):
        clear_statistics(tcf)
        return cli.command_verbose_return(
            value=[], message="Stepping statistics has been cleared")

    def sub_cmd_show(tcf, *field_args):
        fields = Stat.get_field_names()
        enabled = dict(zip(fields, field_args))
        data = get_statistics(tcf, printable=True, **enabled)
        if not data:
            return
        cols = []
        for field in [x for x in fields if enabled[x]]:
            col = [(table.Column_Key_Name, Stat.get_printable_field_name(field))]
            if field not in Stat.non_counter_fields():
                col.append((table.Column_Key_Footer_Sum, True))
            if field in Stat.time_fields():
                col.append((table.Column_Key_Int_Radix, 10))
            cols.append(col)
        props = [(table.Table_Key_Columns, cols)]
        tbl = table.Table(props, data)
        msg = tbl.to_string(rows_printed=0) if data else ""
        print(msg)

    def stepping_statistics_cmd(tcf, sub_cmd_arg, *fields):
        sub_cmd = sub_cmd_arg[2]
        if sub_cmd == '-status':
            return sub_cmd_status(tcf)
        elif sub_cmd == '-enable':
            return sub_cmd_enable(tcf)
        elif sub_cmd == '-disable':
            return sub_cmd_disable(tcf)
        elif sub_cmd == '-clear':
            return sub_cmd_clear(tcf)
        elif sub_cmd == '-show':
            sub_cmd_show(tcf, *fields)
        else:
            assert False

    action_args = [cli.arg(
        (cli.flag_t, cli.flag_t, cli.flag_t, cli.flag_t, cli.flag_t),
        ("-status", "-enable", "-disable", "-clear", "-show"), "1", "-show")]
    field_args = [
        cli.arg(cli.bool_t(), Format.field_to_arg(x), "?",
                Stat.on_by_default(x))
        for x in Stat.get_field_names()]
    cli.new_unsupported_command(
        "stepping-statistics", "internals", stepping_statistics_cmd,
        args=action_args + field_args,
        cls = "tcf-agent",
        short = "control and show stepping statistics",
        doc = """
For internal use.

Control statistics collection using <tt>-enable</tt> and <tt>-disable</tt>, and
use <tt>-status</tt> to get the current enable status.

The <arg>ctx-id</arg> argument is used to specify what context to collect
stats for.

Use <tt>-clear</tt> to clear current statistics.

Use <tt>-show</tt> to show current stats.

The following arguments control what statistics to show:
<ul>
    <li><arg>cache-misses</arg></li>
    <li><arg>mode</arg></li>
    <li><arg>peer</arg></li>
    <li><arg>resulting-pc</arg></li>
    <li><arg>address-to-line</arg></li>
    <li><arg>cache-miss-time</arg></li>
    <li><arg>cache-miss-info</arg></li>
    <li><arg>command</arg></li>
    <li><arg>find-symbol-by-addr</arg></li>
    <li><arg>origin-pc</arg></li>
    <li><arg>real-time</arg></li>
    <li><arg>sim-time</arg></li>
</ul>

These arguments can be set to TRUE or FALSE, leaving an argument unset will
use it's default value.
""")

    cli.new_unsupported_command(
        "save-stepping-statistics", "internals", save_stepping_statistics_cmd,
        args=[cli.arg(cli.filename_t(), 'output')],
        cls = "tcf-agent",
        short = "save stepping statistics as .json",
        doc="""
        For internal use.

        Save stepping statistics from stepping-statistics command in
        a .json file given by <arg>output</arg>.""")


def save_stepping_statistics_cmd(tcf, output):
    fields = Stat.get_field_names()
    rows = []
    for (step_info, counters) in tcf.stepping_statistics:
        rows.append(step_info + counters)

    with open(output, "w") as f:
        json.dump({"fields": fields, "statistics": rows}, f, indent=4)
