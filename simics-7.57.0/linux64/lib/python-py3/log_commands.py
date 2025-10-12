# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import codecs
import datetime
import contextlib
import enum
import io
import os
import re
import unittest
import pprint

import cli
import simics
import conf

from simics import (
    SIM_VERSION_5,
    SIM_VERSION_6,

    SIM_object_iterator,
)

from cli import (
    arg,
    filename_t,
    flag_t,
    int_t,
    obj_t,
    str_t,
    uint_t,
    new_command,
    CliError,
    command_quiet_return,
    command_return,
    number_str,
    print_columns,
    get_completions,
)

from sim_commands import (
    conf_class_expander,
    format_log_line,
    internal_classes,
    y_or_ies,
)

# Set this variable to force a value of the real-time value in logs.
forced_real_time_value = None

class LogFormatType(enum.Enum):
    log = 0
    trace = 1
    trace_obj = 2

class LogFormatString:
    __slots__ = ('fmt', 'used_chars', 'curly_fmt')
    def __init__(self, fmt, used_chars):
        self.fmt = fmt
        self.used_chars = used_chars
        def convert(grp):
            return f'{{{grp[1]}}}'
        self.curly_fmt = re.sub(
            '[%]([a-z])', convert, self.fmt)

    def __str__(self):
        return pprint.pformat({
            'fmt': self.fmt,
            'used_chars': self.used_chars,
            'curly_fmt': self.curly_fmt})

    def __repr__(self):
        return self.__str__()

class Logger_info:
    __slots__ = (
        '_custom_format',
        '_disassembly',
        '_include_group',
        '_include_level',
        '_pico_seconds',
        '_real_time',
        '_time_stamp',
        'console',
        'cached_default_formats',
        'file',
        'file_name',
        'chars_for_log',
        'chars_for_trace',
        'chars_for_trace_with_obj',
        'format_for_log',
        'format_for_trace',
        'format_for_trace_with_obj',
    )

    ch_to_attr = {
        'd': 'disassembly',
        'g': 'include_group',
        'l': 'include_level',
        'm': None,
        'o': None,
        'p': 'pico_seconds',
        'r': 'real_time',
        't': None,
        'v': 'time_stamp'
    }

    ch_not_in_trace_obj = ['g', 'l']
    ch_not_in_trace = ch_not_in_trace_obj + ['o']

    def __init__(self, copy_from=None):
        for (name, default_value) in [
                ('_custom_format', None),
                ('cached_default_formats', {}),
                ('_disassembly', False),
                ('_include_group', False),
                ('_include_level', False),
                ('_pico_seconds', False),
                ('_real_time', False),
                ('_time_stamp', False),
                ('console', True),
                ('file_name', None),
                ('file', None)]:
            value = default_value if copy_from is None else getattr(
                copy_from, name)
            setattr(self, name, value)
        self.update_formats()

    @classmethod
    def is_valid_format(cls, fmt):
        valid_chars = cls.used_ch_in_format(fmt, True)
        if not valid_chars:
            return f"No valid format characters in '{fmt}'"
        invalid_chars = cls.used_ch_in_format(fmt, False)
        if invalid_chars:
            return 'Invalid specifiers: ' + ', '.join(invalid_chars)
        if fmt.endswith('%'):
            return f"Invalid format '{fmt}'"
        return None

    @classmethod
    def used_ch_in_format(cls, fmt, valid):
        """Returns a list of the [in]valid format characters used in 'fmt'."""
        prefix = '' if valid else '^'
        chars = ''.join([f'{prefix}{x}' for x in cls.ch_to_attr])
        regexp = f'%([{chars}])'
        return sorted(set(re.findall(regexp, fmt)))

    def get_cli_format(self):
        '''Returns the log format that will be presented to the user in
        log-setup.'''
        if self.custom_format is not None:
            return self.custom_format
        return "default"

    def strip_characters(self, fmt, characters):
        for ch in characters:
            ch_formatters = []
            ch_formatters.append(f'%{ch}')
            for ch_fmt in ch_formatters:
                fmt = fmt.replace(ch_fmt, '')
        return fmt

    @classmethod
    def default_fmt_attrs(cls):
        """Returns a list with attributes that affect the default format."""
        return [attr for (ch, attr) in cls.ch_to_attr.items() if (
            (attr is not None))]

    def enabled_characters(self, enabled):
        """Returns the characters which are disabled by attrs."""
        return [ch for (ch, attr) in self.ch_to_attr.items() if (
            (attr in self.default_fmt_attrs())
            and (getattr(self, attr) is enabled))]

    def inherent_default_characters(self, log_format_type):
        """Returns a list of characters that are always present
        in the default format string of the given format type."""
        if log_format_type == LogFormatType.log:
            chars = 'otm'
        elif log_format_type == LogFormatType.trace:
            chars = 'tm'
        elif log_format_type == LogFormatType.trace_obj:
            chars = 'otm'
        return list(chars)

    @property
    def custom_format(self):
        return self._custom_format

    @custom_format.setter
    def custom_format(self, value):
        self._custom_format = value
        self.update_formats()

    @property
    def disassembly(self):
        return self._disassembly

    @disassembly.setter
    def disassembly(self, value):
        self._disassembly = value
        self.update_formats()

    @property
    def include_group(self):
        return self._include_group

    @include_group.setter
    def include_group(self, value):
        self._include_group = value
        self.update_formats()

    @property
    def include_level(self):
        return self._include_level

    @include_level.setter
    def include_level(self, value):
        self._include_level = value
        self.update_formats()

    @property
    def pico_seconds(self):
        return self._pico_seconds

    @pico_seconds.setter
    def pico_seconds(self, value):
        self._pico_seconds = value
        self.update_formats()

    @property
    def real_time(self):
        return self._real_time

    @real_time.setter
    def real_time(self, value):
        self._real_time = value
        self.update_formats()

    @property
    def time_stamp(self):
        return self._time_stamp

    @time_stamp.setter
    def time_stamp(self, value):
        self._time_stamp = value
        self.update_formats()

    def default_fmt_key(self, log_format_type, enabled_chars):
        return log_format_type.name + ''.join(sorted(enabled_chars))

    def get_default_format(self, log_format_type):
        enabled_chars = set(self.enabled_characters(True)
                            + self.inherent_default_characters(log_format_type))
        key = self.default_fmt_key(log_format_type, enabled_chars)
        if key in self.cached_default_formats:
            return self.cached_default_formats[key]
        if log_format_type is LogFormatType.log:
            disabled_chars = []
        if log_format_type is LogFormatType.trace:
            disabled_chars = self.ch_not_in_trace
        if log_format_type is LogFormatType.trace_obj:
            disabled_chars = self.ch_not_in_trace_obj
        valid_chars = set(enabled_chars) - set(disabled_chars)

        def is_present(chars):
            return set(list(chars)).issubset(valid_chars)

        parts = []
        for (s, cond) in [
                ('[', True),
                ('%o', is_present('o')),
                (' ', is_present('ot')),
                ('%t', is_present('t')),
                (' ', is_present('g')),
                ('%g', is_present('g')),
                (' ', is_present('l')),
                ('%l', is_present('l')),
                (']', True),
                (' ', is_present('v')),
                ('%v', is_present('v')),
                (' ', is_present('r')),
                ('%r', is_present('r')),
                (' ', is_present('p')),
                ('%p', is_present('p')),
                ('%d', is_present('d')),
                (' ', is_present('m')),
                ('%m', is_present('m'))]:
            if cond:
                parts.append(s)
        result = ''.join(parts)
        self.cached_default_formats[key] = result
        return result

    def update_formats(self):
        default_fmt = self.custom_format is None
        if default_fmt:
            fmt_log = self.get_default_format(LogFormatType.log)
            fmt_trace = self.get_default_format(LogFormatType.trace)
            fmt_trace_obj = self.get_default_format(LogFormatType.trace_obj)
        else:
            fmt_log = self.custom_format
            fmt_trace = self.strip_characters(
                fmt_log, self.ch_not_in_trace)
            fmt_trace_obj = self.strip_characters(
                fmt_log, self.ch_not_in_trace_obj)
        formats = []
        for fmt in [fmt_log, fmt_trace, fmt_trace_obj]:
            used_chars = Logger_info.used_ch_in_format(fmt, True)
            formats.append(LogFormatString(fmt, used_chars))

        (self.format_for_log,
         self.format_for_trace,
         self.format_for_trace_with_obj) = formats

    def __str__(self):
        return pprint.pformat({k: getattr(self, k) for k in self.__slots__})

def format_log(decorate, log_format, obj, log_type, msg, log_level, group_ids):
    new_values = {}
    cobj = None
    if not set(['d', 'p', 'v']).isdisjoint(set(log_format.used_chars)):
        cobj = get_cycle_object_for_timestamps()
    for ch in log_format.used_chars:
        if ch == 'd':
            d = ''
            if (cobj and hasattr(cobj.iface, "processor_info_v2")
                and cobj.iface.processor_cli.get_disassembly):
                (_, disas_str) = cobj.iface.processor_cli.get_disassembly(
                    "v", cobj.iface.processor_info_v2.get_program_counter(),
                    0, None)
                d = f"({disas_str})" if decorate else disas_str
            new_values['d'] = d
        elif ch == 'g':
            g = ''
            if obj and obj.log_groups:
                groups = []
                idx = 0
                while group_ids:
                    if group_ids & 1:
                        groups.append(obj.log_groups[idx])
                    idx += 1
                    group_ids >>= 1
                g = ', '.join(groups)
            new_values['g'] = g
        elif ch == 'l':
            new_values['l'] = '' if log_level is None else str(log_level)
        elif ch == 'm':
            new_values['m'] = msg
        elif ch == 'o':
            new_values['o'] = obj.name if obj else ''
        elif ch == 'p':
            p = ''
            if cobj:
                p_seconds = simics.SIM_cycle_count(cobj.vtime.ps)
                ps_str = f"{number_str(p_seconds, radix=10)}"
                p = f"{{{ps_str} ps}}" if decorate else ps_str
            new_values['p'] = p
        elif ch == 'r':
            if forced_real_time_value is not None:
                r = forced_real_time_value
            else:
                now = datetime.datetime.now()
                r = "{0}".format(now.strftime("%H:%M:%S.%f")[:-2])
            r = f"[{r}]" if decorate else r
            new_values['r'] = r
        elif ch == 't':
            new_values['t'] = log_type
        elif ch == 'v':
            v = ''
            if cobj:
                time_stamp = f"{cobj.name}"
                if hasattr(cobj.iface, "processor_info"):
                    proc_iface = cobj.iface.processor_info
                    pc = proc_iface.get_program_counter()
                    time_stamp += f" 0x{pc:x}"
                cycles = cobj.iface.cycle.get_cycle_count()
                time_stamp += f" {number_str(cycles, radix=10)}"
                v = f"{{{time_stamp}}}" if decorate else time_stamp
            new_values['v'] = v

    new_result = log_format.curly_fmt.format(**new_values)
    return new_result

# Returns a cycle queue suitable for logging timestamps.
def get_cycle_object_for_timestamps():
    cobj = simics.SIM_current_clock()
    if cobj:
        return cobj
    # Pick a suitable clock in Global Context.
    if simics.VT_is_oec_thread() and conf.sim.current_cell:
        return conf.sim.current_cell.current_cycle_obj
    return None

class Logger:
    def __init__(self):
        self.global_logger = Logger_info()
        self.local_logger = {}
        self.hap_id = None
        self.update_callback()
        self.active_filters = []
        self.log_types = conf.sim.log_types[:]
        self.default_info = Logger_info()

    def get_logger_info(self, obj):
        return self.local_logger.get(obj, self.global_logger)

    def set_logger_info(self, obj):
        if obj is None:
            return self.global_logger
        if obj not in self.local_logger:
            l_obj = Logger_info(copy_from = self.global_logger)
            self.local_logger[obj] = l_obj
        return self.local_logger[obj]

    @contextlib.contextmanager
    def filter(self, fun):
        '''Return a context manager that calls fun() exactly once for
        each logged message. If fun() returns a true value, the
        message is suppressed. fun accepts three parameters: object,
        log_type and message. If multiple filters are active at the
        same time, e.g., in a nested with statement, then all filter
        functions are called, but in an undefined order.'''
        self.active_filters.append(fun)
        try:
            yield
        finally:
            self.active_filters.remove(fun)

    def log_internal(self, obj, log_type, msg, log_level, group_ids,
                     is_trace=True):
        log_string = get_log_string(self, obj, log_type, msg, log_level,
                                    group_ids, is_trace)

        # add \n before printing string to ensure atomic output with MT
        log_string += "\n"
        if self.get_logger_info(obj).console:
            simics.CORE_python_write(log_string)
        if self.get_logger_info(obj).file:
            self.get_logger_info(obj).file.write(log_string)
            self.get_logger_info(obj).file.flush()

    # generic output routine, also used for trace- commands.
    def log(self, obj, log_type, msg, is_trace=True):
        self.log_internal(obj, log_type, msg, None, 0, is_trace=is_trace)

    # will only be called when group/type/level matches
    def callback(self, arg, obj, log_type, str, level, group_ids):
        # Deliberately use eager evaluation, in case any fun() wants
        # to do a side-effect
        if not any([f(obj, log_type, str) for f in self.active_filters]):
            self.log_internal(obj, self.log_types[log_type], str, level,
                              group_ids, is_trace=False)

    def update_callback(self):
        needs_filter = (self.global_logger.console
                        or self.global_logger.file
                        or any(val.console or val.file
                               for val in self.local_logger.values()))

        if needs_filter:
            if self.hap_id:
                return
            self.hap_id = simics.SIM_hap_add_callback(
                "Core_Log_Message_Filtered", self.callback, None)
        else:
            if not self.hap_id:
                return
            simics.SIM_hap_delete_callback_id("Core_Log_Message_Filtered",
                                              self.hap_id)
            self.hap_id = None

    def set_format_fields_to_default(self, obj):
        '''Sets formatting fields to the default values.'''
        for (name, value) in [
                ('real_time', self.default_info.real_time),
                ('include_level', self.default_info.include_level),
                ('include_group', self.default_info.include_group),
                ('time_stamp', self.default_info.time_stamp),
                ('pico_seconds', self.default_info.pico_seconds),
                ('disassembly', self.default_info.disassembly),
                ('custom_format', self.default_info.custom_format)]:
            self.field_update(obj, name, value)

    def set_log_file(self, obj, file_name, may_overwrite = False):
        '''Enable log file with specified name or disable if file_name is None.
           If not "may_overwrite", it is an error if the log file already
           exists.'''

        if file_name:
            if not may_overwrite and os.path.exists(file_name):
                raise CliError(f"File {file_name} already exists.")
            try:
                new_log_file = codecs.open(file_name, "w", "utf-8")
            except OSError as ex:
                raise CliError(f"Failed opening log file {file_name} : {ex}")

            self.field_update(obj, "file", new_log_file)
            self.field_update(obj, "file_name", file_name)
        else:
            self.field_update(obj, "file", self.default_info.file)
            self.field_update(obj, "file_name", self.default_info.file_name)

        self.update_callback()

    def field_update(self, obj, name, val):
        setattr(self.set_logger_info(obj), name, val)
        if obj is None:
            for o in self.local_logger.values():
                setattr(o, name, val)

    def setup_cmd(self, obj, ts, no_ts, ps, no_ps, real, no_real, co, no_co,
                  grp, no_grp, lvl, no_lvl, no_lf, disas, no_disas,
                  ow, logfile, fmt):
        if ow and not logfile:
            raise CliError("-overwrite used without any file name")

        self.check_exclusive_args(ts, no_ts, ps, no_ps, real, no_real, co,
                                  no_co, grp, no_grp, lvl, no_lvl,
                                  no_lf, disas, no_disas, logfile, fmt)

        def return_message():
            l_obj = self.get_logger_info(obj)
            log_file = f'"{l_obj.file_name}"' if (
                l_obj.file is not None) else "disabled"
            fmt_str = f'"{l_obj.get_cli_format()}"'
            data = []
            if l_obj.custom_format is None:
                for (description, field) in [
                    ("Time stamp      ", "time_stamp"),
                    ("Picoseconds     ", "pico_seconds"),
                    ("Real time       ", "real_time"),
                    ("Disassembly     ", "disassembly"),
                    ("Log to console  ", "console"),
                    ("Include group   ", "include_group"),
                    ("Include level   ", "include_level")]:
                    enabled = getattr(l_obj, field)
                    data.append(f'{description}: {enabled_str(enabled)}')
            data.extend([f"Log file        : {log_file}",
                         f'Format          : {fmt_str}'])
            return '\n'.join(data)

        def return_value():
            l_obj = self.get_logger_info(obj)
            return [
                ["console", bool(l_obj.console)],
                ["include_level", bool(l_obj.include_level)],
                ["include_group", bool(l_obj.include_group)],
                ["time_stamp", bool(l_obj.time_stamp)],
                ["pico_seconds", bool(l_obj.pico_seconds)],
                ["real_time", bool(l_obj.real_time)],
                ["disassembly", bool(l_obj.disassembly)],
                ["file_name", l_obj.file_name],
                ["file", bool(l_obj.file)],
                ["format", l_obj.get_cli_format()]]

        def enabled_str(b): return "enabled" if b else "disabled"

        default_fmt_args = [
            disas or no_disas,
            grp or no_grp,
            lvl or no_lvl,
            ps or no_ps,
            real or no_real,
            ts or no_ts,
        ]
        custom_fmt_arg = [fmt is not None]
        output_args = [co or no_co,
                      no_lf,
                      logfile]
        mutating_args = default_fmt_args + custom_fmt_arg + output_args
        if not any(mutating_args):
            return command_return(message=return_message, value=return_value)

        l_obj = self.get_logger_info(obj)

        if fmt is None:
            if any(default_fmt_args):
                # if default arguments are set, clear custom format and set
                # default values for all formatting fields.
                if l_obj.custom_format:
                    self.set_format_fields_to_default(obj)

                for (cond, enable, field) in [
                        (ts or no_ts, ts, 'time_stamp'),
                        (ps or no_ps, ps, 'pico_seconds'),
                        (real or no_real, real, 'real_time'),
                        (lvl or no_lvl, lvl, 'include_level'),
                        (grp or no_grp, grp, 'include_group'),
                        (disas or no_disas, disas, 'disassembly')]:
                    if cond:
                        self.field_update(obj, field, enable)

        elif fmt == '':
            if l_obj.custom_format is not None:
                self.set_format_fields_to_default(obj)
        else:
            msg = Logger_info.is_valid_format(fmt)
            if msg is not None:
                raise CliError(f"{msg}. See 'help log-setup'")
            self.field_update(obj, "custom_format", fmt)

        if co or no_co:
            self.field_update(obj, "console", co)
            self.update_callback()

        if logfile:
            self.set_log_file(obj, logfile, may_overwrite = ow)
        elif no_lf:
            self.set_log_file(obj, self.default_info.file_name)
        return command_quiet_return(value=return_value)

    def check_exclusive_args(self, ts, no_ts, ps, no_ps, real, no_real, co,
                            no_co, grp, no_grp, lvl, no_lvl, no_lf,
                            disas, no_disas, logfile, fmt):
        def exclusive(a, b, a_name, b_name):
            if a and b:
                raise CliError(f"{a_name} and {b_name} are mutually exclusive.")

        for (args, names) in [((co, no_co), ("-console", "-no-console"))]:
            exclusive(*args, *names)

        for (args, names) in [
                ((ts, no_ts), ("-time-stamp", "-no-time-stamp")),
                ((ps, no_ps), ("-pico-seconds", "-no-pico-seconds")),
                ((real, no_real), ("-real-time", "-no-real-time")),
                ((lvl, no_lvl), ("-level", "-no-level")),
                ((grp, no_grp), ("-group", "-no-group")),
                ((disas, no_disas), ("-disassemble", "-no-disassemble"))]:
            exclusive(*args, *names)
            for (argument, name) in zip(args, names):
                exclusive(argument, fmt is not None, name, 'format')

logger = Logger()

def get_log_string(logger, obj, log_type, msg, log_level, group_ids, is_trace):
    l_obj = logger.get_logger_info(obj)
    if is_trace:
        if obj:
            fmt = l_obj.format_for_trace_with_obj
        else:
            fmt = l_obj.format_for_trace
    else:
        fmt = l_obj.format_for_log

    is_default_fmt = l_obj.custom_format is None
    log_string = format_log(is_default_fmt, fmt, obj, log_type, msg,
                            log_level, group_ids)
    return log_string

def get_log_string_exported(obj, log_type, msg, log_level, groups, trace):
    return get_log_string(logger, obj, conf.sim.log_types[log_type], msg,
                          log_level, groups, trace)

new_command("log-setup", logger.setup_cmd,
            args  = [arg(obj_t("object"), "object", "?", None),
                     arg(flag_t, "-time-stamp"),
                     arg(flag_t, "-no-time-stamp"),
                     arg(flag_t, "-pico-seconds"),
                     arg(flag_t, "-no-pico-seconds"),
                     arg(flag_t, "-real-time"),
                     arg(flag_t, "-no-real-time"),
                     arg(flag_t, "-console"),
                     arg(flag_t, "-no-console"),
                     arg(flag_t, "-group"),
                     arg(flag_t, "-no-group"),
                     arg(flag_t, "-level"),
                     arg(flag_t, "-no-level"),
                     arg(flag_t, "-no-log-file"),
                     arg(flag_t, "-disassemble"),
                     arg(flag_t, "-no-disassemble"),
                     arg(flag_t, "-overwrite"),
                     arg(filename_t(), "logfile", "?", None),
                     arg(str_t, "format", "?", None)],
            type  = ["Logging"],
            short = "configure log behavior",
            see_also = ["log", "<conf_object>.log-group", "log-size",
                        "log-type", "bp.log.wait-for"],
            doc = """
The <cmd>log-setup</cmd> command controls the output generated by
the logging system, such as trace set up using the breakpoint manager.

When called without any arguments, the current log settings are printed.

The <tt>-time-stamp</tt> flag will cause future log output to include virtual
time stamps: the name of the current processor, its current program counter
value, and its current cycle count. If the current "processor" does not execute
instructions (such as the <class>clock</class>), the program counter value is
omitted. Time stamps are disabled with <tt>-no-time-stamp</tt>.

The <tt>-pico-seconds</tt> flag will cause future log output to include virtual
time stamps in picoseconds. Picosecond time stamps are disabled with
<tt>-no-pico-seconds</tt>.

The <tt>-real-time</tt> flag will cause log output to include wall clock time
stamps. It is disabled with <tt>-no-real-time</tt>.

A file that receives all log output can be specified with the <arg>logfile</arg>
argument. <tt>-no-log-file</tt> disables an existing log file. To overwrite an
existing file, the <tt>-overwrite</tt> flag has to be given.

The <tt>-console</tt> and <tt>-no-console</tt> flags turn output from the
log system to the command line console on or off.

The <tt>-group</tt> and <tt>-no-group</tt> flags controls if the log group
should be part of the output. Default is not to include the log group.

The <tt>-level</tt> and <tt>-no-level</tt> flags controls if the log level
should be part of the output. Default is not to include the log level.

The <tt>-disassemble</tt> and <tt>-no-disassemble</tt> flags control
whether disassembly of the current instruction on the current "processor" is
included in the output. Default is to not show disassembly.

Any log messages printed at a level below or equal to the current log level (see
the <cmd>log-level</cmd> command) will always be stored in the in-memory log
buffer (see the <cmd>log</cmd> command).

The default format of log output is <tt>[object log-type] {processor address
cycle} [real-time] {pico-seconds ps} message</tt>. The second, third and fourth
groups, in curly, square and curly brackets, respectively, are optional.

The <arg>object</arg> argument can be used to apply the configuration to the
specified object only. The global command is used to reset object specific
settings, meaning that doing a change without the <arg>object</arg> argument
will override that setting for all objects, even for the objects that have had
that setting set specially.

It is also possible to set a custom format strings for the log by setting
<arg>format</arg>. When setting <arg>format</arg>, this will override other
flags which specify log properties. In the format string, log properties are
specified with the <tt>%x</tt> syntax, where <tt>x</tt> is one of the following:
<tt>'d'</tt> (disassembly),
<tt>'g'</tt> (log group),
<tt>'l'</tt> (log level),
<tt>'t'</tt> (log type),
<tt>'m'</tt> (message),
<tt>'o'</tt> (object),
<tt>'p'</tt> (pico-seconds),
<tt>'r'</tt> (real-time),
<tt>'v'</tt> (virtual time-stamp).

To remove a custom log format, either set <arg>format</arg> to the empty string,
<tt>""</tt> or specify at least on of the (<em>-</em> or <em>-no-</em>) for
<em>real-time</em>, <em>level</em>, <em>group</em>, <em>time-stamp</em>,
<em>pico-seconds</em>, <em>disassemble</em>. This will restore the default
format and default settings for all properties, for an object or for all objects
if no object is specified.""")

def logging_affected_objects(obj, recursive=False):
    """Returns a list of objects that an obj.log-* command should handle

       Args:
           obj (Simics object): object to operate on or None
           recursive (boolean): recurse to sub-objects

       If no object is given the current namespace will be used
       If a component is given the objects which it contains will be used
       If an object is given the subordinate objects which are tightly coupled
         with the object, i.e. descendants of 'bank', 'impl' and 'port' will be
         included."""
    # (SIMICS-11374, SIMICS-15500)
    def helper(obj, recursive):
        if obj is None:
            root = cli.current_component()  # current namespace
            yield from SIM_object_iterator(root)
        elif recursive:
            yield obj
            yield from SIM_object_iterator(obj)
        elif cli.is_component(obj):
            yield obj
            for o in obj.iface.component.get_slot_objects():
                if not cli.is_component(o):
                    yield o
                    yield from friends_iterator(o)
        else:
            yield obj
            yield from friends_iterator(obj)
    return list(helper(obj, recursive))

def friends_iterator(obj):
    """Iterates over the "friends" of an object, i.e. descendants of
    the namespaces 'bank', 'impl' and 'port'"""
    if not isinstance(obj, simics.conf_object_t):
        # SIMICS-15892
        raise CliError("Not instantiated objects detected")
    for relname in ["bank", "impl", "port"]:
        o = simics.SIM_object_descendant(obj, relname)
        if o:
            yield o
            yield from SIM_object_iterator(o)
#
# -------------------- log-level --------------------
#

def global_log_level_cmd(obj, level, classname, all_flag, recursive):

    if all_flag and recursive:
        raise CliError("-all and -r flags cannot be used together")
    if all_flag and obj:
        raise CliError("-all flag cannot be used together"
                       " with the 'object' argument")
    if recursive and not obj:
        raise CliError("-r flag cannot be used without the 'object' argument")
    if classname and (obj and not recursive):
        raise CliError("the 'class' argument cannot be used with the 'object'"
                       " argument unless -r flag is specified")
    if level and (level < 0 or level > 4):
        raise CliError("Illegal log level: %d. Allowed are 0 - 4." % level)

    if obj:
        return log_level_cmd(obj, level, recursive)

    # we are operating on a hierarchy
    root = None if all_flag else cli.current_component()
    log_objects = set(o for o in simics.SIM_object_iterator(root)
                      if classname in [None, o.classname])
    if root and (classname in [None, root.classname]):
        log_objects.add(root)
    if not log_objects:
        print('No objects found to operate on')
        return

    if classname:
        sub_objs = set()
        for o in log_objects:
            sub_objs.update(logging_affected_objects(o))
        log_objects.update(sub_objs)

    class_message = ' for the %s class' % classname if classname else ''
    if level is None:
        objects = [(o.log_level, o.name) for o in sorted(log_objects)]
        print("Current log levels%s%s:" % (
            class_message, ' in %s' % root.name if root else ''))
        print()
        print_columns('rl', [('Lvl', 'Object')] + objects)
        print()
        print("Default log level: %d" % conf.sim.default_log_level)
        return

    for o in log_objects:
        o.log_level = level

    if root is None:
        if classname is None:
            # also change the default log-level
            conf.sim.default_log_level = level
        msg = "New global log level%s: %d" % (class_message, level)
    else:
        msg = "New log level%s in the %s namespace: %d" % (
            class_message, root.name, level)

    return command_return(message = msg)

def exp_log_levels(prefix):
    return get_completions(prefix, [str(i) for i in range(5)])

# this command is tested by t310_components_v2/s-log-level.py
# as well as t413_hierarchical_objects/s-log-level.py
new_command("log-level", global_log_level_cmd,
            args  = [arg(obj_t("object"), "object", "?", None),
                     arg(int_t, "level", "?", None,
                         expander = exp_log_levels),
                     arg(str_t, "class", "?", None,
                         expander = conf_class_expander(True)),
                     arg(flag_t, "-all"),
                     arg(flag_t, "-r")],
            type  = ["Logging"],
            short = "set or get the log level",
            see_also = ["log", "<conf_object>.log-group", "log-size",
                        "log-type", "change-namespace"],
            doc = """
This command is used to get or set the log <arg>level</arg>
of all objects in the current namespace, of an <arg>object</arg>
in the current namespace, or globally if <tt>-all</tt> is set.
When <arg>object</arg> is specified the command will also recursively update
log groups for descendants of <arg>object</arg> whose name matches
<arg>object</arg>.bank[.*], <arg>object</arg>.port[.*] or
<arg>object</arg>.impl[.*] pattern.
If <arg>object</arg> is a component then the log level will be set for all
objects belonging to the component. The flag <tt>-r</tt> can be used to operate
on all the descendants of the object <arg>object</arg>.

If the <arg>class</arg> argument is specified, the operation with be done
only on objects of that class.

Objects in Simics can generate log messages on different <i>log levels</i>.
These messages will be shown in the Simics command line window if the log level
for the object has been set high enough.

The default level is 1, and this is the lowest level that objects can report
messages on. Setting it to 0 will inhibit output of all messages except
error messages.

Messages are also added to an access log that can be viewed by the
<cmd>log</cmd> command in Simics.

There are four log levels defined: <br/>
  1 - important messages printed by default <br/>
  2 - "high-level" informative messages <br/>
  3 - standard debug messages <br/>
  4 - detailed information, such as register accesses

The namespace version of this command,
<cmd class="conf_object">log-level</cmd>, sets the log level on all objects of
the specified component. The <tt>-r</tt> flag recursively updates all
sub-components and their objects.""")

#
# -------------------- <obj>.log-level --------------------
#

def log_level_cmd(obj, level, recursive):
    old = obj.log_level
    objs = logging_affected_objects(obj, recursive)

    if level is None:
        output = io.StringIO()
        objects = [(o.log_level, o.name) for o in objs]
        print("Current log levels:", file = output)
        print(file = output)
        print_columns('rl', [('Lvl', 'Object')] + objects, outfile = output)
        print(file = output)
        return command_return(
            output.getvalue(),
            old if all(o.log_level == old for o in objs) else None)

    if level < 0 or level > 4:
        raise CliError("Illegal log level: %d. Allowed are 0 - 4." % level)

    if all(level == o.log_level for o in objs):
        return command_return(
            "[%s] Log level unchanged, level: %d" % (obj.name, old), old)

    for o in objs:
        o.log_level = level
    return command_return("[%s] Changing log level%s: %d -> %d"
                          % (obj.name,
                             " recursively" if recursive
                             else " in component" if cli.is_component(obj)
                             else "",
                             old, level))

new_command("log-level", log_level_cmd,
            args  = [arg(int_t, "level", "?", expander = exp_log_levels),
                     arg(flag_t, "-r")],
            type  = ["Logging"],
            iface = "conf_object",
            short = "set or get the log level",
            doc_with = "log-level")

#
# -------------------- log-type --------------------
#

def log_names(names_list, mask):
    return " ".join('"{}"'.format(name) for i, name in enumerate(names_list)
                    if mask & (1 << i))

def cli_log_types():
    # Hide trace type
    types = list(conf.sim.log_types)
    types.remove('trace')
    return types

def log_type_expander(prefix):
    return get_completions(prefix, cli_log_types() + ['all'])

def log_type_cmd(obj, flags, log_type, recursive):
    def log_types_as_string(obj, recursive):
        objs = logging_affected_objects(obj, recursive)
        log_types = cli_log_types()

        objs_filtered = [o for o in objs if o.classname not in internal_classes()]
        objs = objs_filtered or objs  # make sure objs won't be empty

        return "\n".join(
            "{}:".format(o.name)
            + "\n enabled log types: {}".format(
                log_names(log_types, o.log_type_mask))
            + "\n disabled log types: {}".format(
                log_names(log_types, ~o.log_type_mask))
            for o in objs)

    (_, _, flag) = flags
    add_flag = flag in ["-enable"]
    sub_flag = flag in ["-disable"]
    log_types = cli_log_types()

    if log_type is None:
        if obj:
            print(log_types_as_string(obj, recursive))
            return
        print("Current log types:")
        for o in sorted(simics.SIM_object_iterator(None)):
            print("[%s] %s" % (o.name, log_names(log_types,
                                                      o.log_type_mask)))
        print()
        return

    objs = logging_affected_objects(obj, recursive)

    if log_type == "all":
        change_mask = 0xffffffff
        if sub_flag:
            raise CliError("Cannot remove all log types.")
    else:
        if log_type not in log_types:
            raise CliError("Unknown log type: %s " % log_type)
        change_mask = 1 << log_types.index(log_type)

    for o in objs:
        if add_flag:
            new_mask = o.log_type_mask | change_mask
        elif sub_flag:
            new_mask = o.log_type_mask & ~change_mask
        else:
            new_mask = change_mask
        o.log_type_mask = new_mask

    if obj:
        return command_return(log_types_as_string(obj, recursive))

    if add_flag:
        return command_return(
            "Enabling the following log type(s) in all objects: %s"
            % log_names(log_types, change_mask))
    elif sub_flag:
        return command_return(
            "Disabling following log type(s) in all objects: %s"
            % log_names(log_types, change_mask))
    else:
        return command_return(
            "The following log type(s) were set for all objects: %s"
            % log_names(log_types, change_mask))

new_command("log-type", log_type_cmd,
            args  = [arg(obj_t("object"), "object", "?", None),
                     arg((flag_t, flag_t),
                         ("-enable", "-disable"), "?",
                         (flag_t, 0, None)),
                     arg(str_t, "log-type", "?", None,
                         expander = log_type_expander),
                     arg(flag_t, "-r"),
            ],
            type  = ["Logging"],
            short = "set or get the current log types",
            see_also = ["log", "<conf_object>.log-group", "log-level",
                        "log-size"],
            doc = """
Log messages are categorised into one of the several log types. By default,
messages of all types are handled in the same way. This command can be used
to select one or several types. Only messages of the selected types will be
logged and displayed, as defined by the <cmd>log-level</cmd> command. The
flags <tt>-enable</tt> and <tt>-disable</tt> can be used to add and remove a
single log type.

The <arg>object</arg> argument can be used to apply the change just to
a particular object. Please note that when <arg>object</arg> is
specified the log type will be also recursively updated for all
descendants of <arg>object</arg>, whose name matches <arg>object</arg>.bank[.*],
<arg>object</arg>.port[.*] or <arg>object</arg>.impl[.*] pattern. The flag
<tt>-r</tt> can be used to operate on all the descendants of the object
<arg>object</arg>.

The log types are Info, Warning, Error, Critical, Spec_Violation and
Unimplemented.

The Info type is used for harmless info or debug messages. Warning is
used for problems that does not prevent the simulation from
continuing. Error is used when an error prevents the simulation from
running properly; this type does not have any log-level. Critical is
used to signal serious errors that a model may not be able to resume
from; the simulation is stopped. Spec_Violation is used when a target
program runs a command that violates the device specification.  And
Unimplemented is used when a model does not implement a specific
functionality, bit or register.

All types can be enabled by setting <arg>log-type</arg> to <tt>all</tt>. It is
not possible to disable breaking on Critical.
""")

#
# -------------------- log-group --------------------
#

def is_log_group_enabled(obj, group):
    bit = 1 << obj.log_groups.index(group)
    return obj.log_group_mask & bit != 0

def log_group_state_info(log_group, objs):
    outstr = ""
    enabled = []
    disabled = []
    for o in objs:
        if is_log_group_enabled(o, log_group):
            enabled.append(o.name)
        else:
            disabled.append(o.name)
    if enabled:
        outstr = "Log group '%s' is enabled in %d object(s):\n%s" % (
            log_group, len(enabled), "\n".join(sorted(enabled)))
    if disabled:
        outstr += "\n" if outstr else ""
        outstr += "Log group '%s' is disabled in %d object(s):\n%s" % (
            log_group, len(disabled), "\n".join(sorted(disabled)))
    return outstr

def global_log_group_cmd(obj, flags, log_group, recursive):
    (_, _, flag) = flags
    if log_group == "all" and not flag:
        raise CliError("'all' requires either -enable or -disable flag")
    if log_group is None and obj is None:
        raise CliError("Both object and log_group parameters cannot be omitted")

    if obj:
        return log_group_cmd(obj, flags[0:2] + (flag,), log_group, recursive)

    if log_group == 'all':
        objs = list(SIM_object_iterator(None))
    else:
        root = cli.current_component()
        objs = [o for o in SIM_object_iterator(root)
                if log_group in o.log_groups]
        if not objs:
            return command_return("Log group '%s' not found in any object."
                                  % log_group, value = [])
    if flag:
        for o in objs:
            log_group_cmd(o, flags, log_group, recursive=False)
        act = "enabled" if flag == "-enable" else "disabled"
        return command_return("Log group '%s' was %s in %d object(s)."
                              % (log_group, act, len(objs)),
                              value = objs)

    # No flags specified, just list current state for the log group
    outstr = log_group_state_info(log_group, objs)
    return command_return(outstr, value=objs)

def global_log_group_expander(prefix, _, prev_args):
    if prev_args[0]:
        return log_group_expander(prefix, prev_args[0])
    else:
        groups = {'all'}
        for obj in SIM_object_iterator(None):
            groups.update(obj.log_groups)
        return get_completions(prefix, list(groups))

new_command("log-group", global_log_group_cmd,
            args  = [arg(obj_t("object"), "object", "?", None),
                     arg((flag_t, flag_t),
                         ("-enable", "-disable"), "?",
                         (flag_t, 0, None)),
                     arg(str_t, "log-group", "?", None,
                         expander = global_log_group_expander),
                     arg(flag_t, "-r"),
            ],
            type  = ["Logging"],
            short = "enable/disable a log group",
            see_also = ["log", "log-level", "log-size", "log-type"],
            doc = """
Enable (<tt>-enable</tt>) or disable (<tt>-disable</tt>) a <arg>log-group</arg>,
or show whether it is enabled. If no <arg>object</arg> is specified, do so on
all objects in the configuration that define the log group. When
<arg>object</arg> is specified the command will also recursively update
log groups for all descendants of <arg>object</arg> whose name matches
<arg>object</arg>.bank[.*], <arg>object</arg>.port[.*] or
<arg>object</arg>.impl[.*] pattern. The flag <tt>-r</tt> can be used to operate
on all the descendants of the object <arg>object</arg>.

To enable or disable all log groups, specify <tt>all</tt> as
<arg>log-group</arg>.

An object in Simics can specify a number of groups, and each log message is
associated with one or more groups. Groups are typically used to separate log
messages belonging to different aspects of an object such as a device. Log
messages not associated with any model-specific group will all be collected in
the <tt>Default_Log_Group</tt>.

For example, a network device can have one group each for the receive and
transmit engines, one group for the host protocol and another for PCI accesses.

Having multiple groups simplifies debugging when only messages of the selected
groups are logged and displayed. By default, all groups are enabled.
""")

#
# -------------------- <obj>.log-group --------------------
#

def log_group_expander(prefix, obj):
    return get_completions(prefix, obj.log_groups + ['all'])

def log_group_cmd(obj, flags, log_group, recursive):
    def log_groups_as_string(obj, recursive):
        objs = logging_affected_objects(obj, recursive)
        objs_filtered = [o for o in objs
                         if o.classname not in internal_classes()]
        objs = objs_filtered or objs  # make sure objs won't be empty

        return "\n".join(
            "{}:".format(o.name)
            + "\n enabled log groups: {}".format(
                log_names(o.log_groups, o.log_group_mask))
            + "\n disabled log groups: {}".format(
                log_names(o.log_groups, ~o.log_group_mask))
            for o in objs)

    (_, _, flag) = flags
    add_flag = flag == "-enable"

    if log_group is None:
        return command_return(log_groups_as_string(obj, recursive))

    objs = logging_affected_objects(obj, recursive)
    if log_group == "all":
        # NB: 'log-group "all"' (i.e. without -enable flag) enables all groups
        new_mask = 0xffffffffffffffff if not flag or add_flag else 0
        for o in objs:
            o.log_group_mask = new_mask
        return command_return(log_groups_as_string(obj, recursive))

    objs = [o for o in objs if log_group in o.log_groups]
    if not objs:
        msg = f"Log group '{log_group}' is not present in '{obj.name}'"
        msg += " or any objects below." if recursive else "."
        raise CliError(msg)

    if not flag:
        outstr = log_group_state_info(log_group, objs)
        return command_return(message=outstr, value=all(
            is_log_group_enabled(o, log_group) for o in objs))

    for o in objs:
        if log_group not in o.log_groups:
            continue
        group_id = o.log_groups.index(log_group)
        if add_flag:
            new_mask = o.log_group_mask | (1 << group_id)
        else:
            new_mask = o.log_group_mask & ~(1 << group_id)
        o.log_group_mask = new_mask

    return command_return(log_groups_as_string(obj, recursive))

new_command("log-group", log_group_cmd,
            args  = [arg((flag_t, flag_t),
                         ("-enable", "-disable"), "?",
                         (flag_t, 0, None)),
                     arg(str_t, "log-group", "?", None,
                         expander = log_group_expander),
                     arg(flag_t, "-r")
            ],
            type  = ["Logging"],
            iface = "conf_object",
            short = "enable/disable a log group",
            see_also = ["log", "log-level", "log-size", "log-type"],
            doc_with = "log-group")


#
# -------------------- log-size --------------------
#

def log_size_ns(obj, newsize):
    oldsize = obj.log_buffer_size
    if newsize == None:
        print("Current log buffer size: %d entries" % oldsize)
        return

    try:
        obj.log_buffer_size = newsize
    except Exception as ex:
        raise CliError("Error changing log buffer size: %s" % ex)
    return command_return("[%s] Changing size of the log buffer: %d -> %d"
                          % (obj.name, oldsize, newsize))

def log_size_cmd(obj, newsize):
    if obj is not None:
        return log_size_ns(obj, newsize)

    if newsize == None:
        print("Current log buffer sizes: (number of entries)")
        for obj in SIM_object_iterator(None):
            print("[%s] %d" % (obj.name, obj.log_buffer_size))
        return

    for obj in SIM_object_iterator(None):
        try:
            obj.log_buffer_size = newsize
        except Exception as ex:
            raise CliError("Error changing log buffer size: %s" % ex)
    return command_return("Setting new size of all log buffers: %d" % newsize)

new_command("log-size", log_size_cmd,
            [arg(obj_t("object"), "object", "?", None),
             arg(uint_t, "size", "?", None)],
            alias = "",
            type  = ["Logging"],
            short = "set log buffer size",
            see_also = ["log", "<conf_object>.log-group", "log-level",
                        "log-type"],
            doc = """
The command changes the buffer <arg>size</arg> (number of entries)
for log messages and I/O trace entries for all objects or
for an <arg>object</arg>.""")

#
# -------------------- log --------------------
#

# Returns true for big endian and false for little, None if the endianness
# cannot be determined, or is not applicable
def get_log_endian(obj, opsize):
    if opsize > 8 or not obj:
        return None
    if hasattr(obj.iface, "processor_info"):
        return obj.iface.processor_info.get_endian() == simics.Sim_Endian_Big
    return conf.prefs.default_log_endianness == "big"

def display_log_entry(obj, trace):
    ((timestamp, cpu, pc), trace_info, messages) = trace
    if cpu:
        cpu_name = cpu.name
    else:
        cpu_name = "None"
    str = (" Timestamp: obj = %s cycle = %d cpu = %-5s pc = 0x%x"
           % (obj.name, timestamp, cpu_name, pc))
    if trace_info == []:
        print("   *   %s" % str)
    else:
        (ini_obj, addr, size, rw, value, count) = trace_info
        print("%6d %s" % (count, str))
        print(("        "
               + format_log_line(
                   ini_obj, addr, rw == simics.Sim_RW_Read, value, size,
                   get_log_endian(ini_obj, size))))

    group_names = obj.log_groups
    for (msg, groups, msgtype) in messages:
        grps = groups
        prefix = ""
        names = ""
        i = 0
        while grps > 0:
            if grps & 1:
                names += prefix
                if i < len(group_names):
                    names += group_names[i]
                else:
                    names += 'group %d' % i
                prefix = ', '
            grps >>= 1
            i += 1
        print("        [%s - %s] %s" % (conf.sim.log_types[msgtype], names,
                                        msg))
    print()

def log_cmd_ns(obj, num):
    entries = list(obj.log_buffer)
    if not entries:
        print('There are no log entries.')
        return

    # List the last 'num' entries in reverse order.
    for entry in list(reversed(entries))[:num]:
        display_log_entry(obj, entry)

    if num > len(entries):
        print(("Only %d entr%s listed (no more in buffer)"
               % (len(entries), y_or_ies(len(entries)))))

def trace_sort_key(data):
    (obj, entry) = data
    ((time, _, _), _, _) = entry
    # Sort by time (descending) and then name (ascending).
    return (-time, obj.name)

def log_cmd(obj, num):
    if obj is not None:
        log_cmd_ns(obj, num)
        return

    trace_list = [(obj, entry)
                  for obj in SIM_object_iterator(None)
                  for entry in list(reversed(list(obj.log_buffer)))[:num]]
    for (obj, trace) in sorted(trace_list, key=trace_sort_key)[:num]:
        display_log_entry(obj, trace)
    if not trace_list:
        print("There are no log entries.")
    elif len(trace_list) < num:
        print("Only %d entr%s listed (no more in log buffers)"
                   % (len(trace_list), y_or_ies(len(trace_list))))

new_command("log", log_cmd,
            args = [arg(obj_t("object"), "object", "?", None),
                    arg(int_t, "count", "?", 10)],
            alias = "",
            type  = ["Logging"],
            short = "print log entries for all objects",
            see_also = ["<conf_object>.log-group", "log-level", "log-size",
                        "log-type"],
            doc = """
Display entries in the log buffers. Use the <arg>object</arg> argument
to display the entries for a specific object, otherwise the command lists the
entries of all object's log buffers but sorted by time. The optional
<arg>count</arg> argument is the number of entries to list. Only the last 10
entries are listed by default.

All log buffers are zero-sized by default. The <cmd>log-size</cmd> command has
to be used to allocate space for log entries. This has to be done before
running the part of the simulation that generates the log messages.

Only log messages the match the currently configured level, group and type are
saved to the log buffers.
""")

#
# -------------------- log-filter --------------------
#

def log_filter_clear(obj, substring):
    new_log_filter = []
    if obj is not None and substring is not None:
        new_log_filter = [e for e in conf.sim.log_filter if
                          obj != e[0] or substring != e[1]]
    elif obj is not None:
        new_log_filter = [e for e in conf.sim.log_filter if
                          obj != e[0]]
    elif substring is not None:
        new_log_filter = [e for e in conf.sim.log_filter if
                          substring != e[1]]
    entries_removed = len(conf.sim.log_filter) - len(new_log_filter)
    if entries_removed:
        conf.sim.log_filter = new_log_filter
        print("Removed {} entr{}.".format(
            entries_removed, y_or_ies(entries_removed)))
    else:
        print("No entries were removed.")

def log_filter(obj, substring, is_temporary, clear):
    if clear:
        log_filter_clear(obj, substring)
        return

    if obj is None and substring is not None:
        raise CliError("Please provide the 'object' argument")

    if substring is None:
        # just print current entries for an object or for all objects
        obj_substrs = {}
        for o, substr, is_temp in conf.sim.log_filter:
            if obj is None or o == obj:
                obj_substrs.setdefault(o, []).append([substr, is_temp])

        if not obj_substrs:
            print("No entries{}.".format(" for " + obj.name if obj else ""))
            return

        for o in sorted(obj_substrs):
            print("Log filtering settings for the '{}' object:".format(o.name))
            for substr, is_temp in sorted(obj_substrs[o]):
                print(f' "{substr}"' + (' (temporary)' if is_temp else ''))

        return

    if not any(f for f in conf.sim.log_filter
               if f[0] == obj and f[1] == substring):
        conf.sim.log_filter.append([obj, substring, is_temporary])

new_command("log-filter", log_filter,
            args = [arg(obj_t('object'), "object", "?", None),
                    arg(str_t, "substr", "?", None),
                    arg(flag_t,"-temporary"),
                    arg(flag_t,"-clear")],
            type  = ["Logging"],
            short = "suppress log messages for the object",
            doc = """
Adds a filter that selectively suppresses log messages from an object.

While it is possible to disable logging for a particular object by setting its
log level to 0, doing so may also hide important information. As an alternative,
this command can suppress select log messages from a particular object. This
is useful when lots of messages are printed by a misbehaving model. Using
<cmd>log-filter</cmd> should be a temporary solution until the model is fixed
by moving offending log messages to one or more log groups or to a higher log
level.

When used without any arguments, or with just the <arg>object</arg> argument,
the command will print all current log suppression entries, or those for the
specified object.

To add a filter, both the <arg>object</arg> and <arg>substr</arg>
arguments are mandatory. A message will be suppressed when it is
logged by the specified <arg>object</arg> and it matches the
<arg>substr</arg>. Messages of "critical" type are never
suppressed. If the <tt>-temporary</tt> flag is specified, the filter
will be removed if a message not suppressed by any filter is encountered.

The <tt>-clear</tt> flag is used to disable log suppression. When the flag is
used and no other arguments, all suppression entries will be cleared.
Otherwise, the <arg>object</arg> and <arg>substr</arg> arguments are
required to disable suppression for the specified object and substring.
""")

class _test_logger_info(unittest.TestCase):
    ch_to_attr = Logger_info.ch_to_attr
    default_format = "[%o %t %g %l] %v %r %p%d %m"
    default_format_trace = "[%t] %v %r %p%d %m"
    default_format_trace_obj = "[%o %t] %v %r %p%d %m"

    def test_default_formats(self):
        info = Logger_info()
        for field in ('disassembly',
                      'include_group',
                      'include_level',
                      'pico_seconds',
                      'real_time',
                      'time_stamp'):
            setattr(info, field, True)
        for (field, exp) in [
                ('format_for_log', self.default_format),
                ('format_for_trace', self.default_format_trace),
                ('format_for_trace_with_obj', self.default_format_trace_obj)]:
            got = getattr(info, field).fmt
            self.assertEqual(got, exp)

    def test_custom_formats(self):
        def get_fmt(ch_list):
            return '%' + '%'.join(ch_list)

        info = Logger_info()
        all_ch = Logger_info.ch_to_attr.keys()
        fmt = '%' + '%'.join(all_ch)
        info.custom_format = get_fmt(all_ch)
        for (missing, field) in [
                ((), 'format_for_log'),
                (info.ch_not_in_trace, 'format_for_trace'),
                (info.ch_not_in_trace_obj, 'format_for_trace_with_obj')]:
            exp = get_fmt([ch for ch in fmt.replace('%', '') if (
                ch not in missing)])
            got = getattr(info, field)
            self.assertTrue(got, exp)
