# © 2020 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import conf
import simics
import cli
import console_break_strings

break_doc = """
Set Simics to break simulation when <arg>string</arg> is seen on
the console.
""" + (console_break_strings.break_arg_doc("break")
       + console_break_strings.regexp_arg_doc("bp-break-string"))

wait_for_doc = """
Wait for the output of the text <arg>string</arg> on the
console. This command can only be run from a script branch
where it suspends the branch until the string has been
found in the output.
""" + (console_break_strings.break_arg_doc("wait-for")
       + console_break_strings.regexp_arg_doc("bp-wait-for-console-string"))

run_until_doc = """
Run the simulation until the text <arg>string</arg> appear on the
console.
""" + (console_break_strings.break_arg_doc("run-until")
       + console_break_strings.regexp_arg_doc("bp-run-until-string"))

trace_doc = """
Enable tracing of appearances of the text <arg>string</arg> on the
console.
""" + (console_break_strings.break_arg_doc("trace")
       + console_break_strings.regexp_arg_doc("bp-trace-string"))

class Breakpoint:
    __slots__ = ('con', 'con_id', 'string', 'regexp', 'once')
    def __init__(self, con, con_id, string, regexp, once):
        self.con = con
        self.con_id = con_id
        self.string = string
        self.regexp = regexp
        self.once = once
    def format_break_string(self):
        if self.regexp:
            return f'"{self.string}" (regexp)'
        else:
            # escape non-printable characters
            return '"' + repr(self.string)[1:-1] + '"'

class ConStrBreakpoints:
    TYPE_DESC = "target console string output breakpoints"
    cls = simics.confclass("bp-manager.con-string", short_doc=TYPE_DESC,
                           doc=TYPE_DESC, pseudo=True)

    def __init__(self):
        self.bp_data = {}
        self.next_id = 1

    @cls.objects_finalized
    def objects_finalized(self):
        conf.bp.iface.breakpoint_type.register_type(
            "console-string", self.obj,
            [["str_t", "string", "1", None, None, "", None],
             ["flag_t", "-regexp", "1", None, None, "", None]],
            None, 'break_strings_v2',
            ["set string breakpoint", break_doc,
             "run until string appears", run_until_doc,
             "wait for specified string", wait_for_doc,
             "enable tracing of string appearances", trace_doc], True, False,
            False)

    def _delete_bp(self, _, bm_id):
        self.remove_bp(conf.bp.iface.breakpoint_type.get_break_id(bm_id))

    def _describe_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"Console '{bp.con.name}' break on {bp.format_break_string()}"

    def _get_props(self, _, bm_id):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        bp = self.bp_data[bp_id]
        return {"temporary": bp.once,
                "planted": True,
                "object": bp.con.name,
                "description": self._describe_bp(bp_id)}

    def _create_bp(self, con, string, regexp, once, cb):
        bp_id = self.next_id
        self.next_id += 1

        if regexp:
            con_id = con.iface.break_strings_v2.add_regexp(string, cb, bp_id)
        else:
            con_id = con.iface.break_strings_v2.add(string, cb, bp_id)
        self.bp_data[bp_id] = Breakpoint(con, con_id, string, regexp, once)
        return bp_id

    def _bp_cb(self, con, string, con_id, bp_id):
        conf.bp.iface.breakpoint_type.trigger(self.obj, bp_id, con,
                                              self.trace_msg(bp_id))
        return 1

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bpm_iface = conf.bp.iface.breakpoint_registration
        return bpm_iface.register_breakpoint(
            self._delete_bp, None, self._get_props, None, None, None,
            None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, _, args):
        (con, string, regexp, once) = args
        return self._create_bp(con, string, regexp, once, self._bp_cb)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        if isinstance(bp.con, simics.conf_object_t):
            bp.con.iface.break_strings_v2.remove(bp.con_id)
        del self.bp_data[bp_id]

    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"matched {bp.format_break_string()}"

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"{bp.con.name} will break on {bp.format_break_string()}"

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"{bp.con.name} waiting on {bp.format_break_string()}"

    @staticmethod
    def wait_then_write_cmd(obj, con, regexp, emacs, wait_str, write_str):
        if (hasattr(con.iface, 'break_strings_v2')
            and con.iface.break_strings_v2):
            con.cli_cmds.bp_wait_for_console_string(string=wait_str,
                                                    _regexp=regexp)
            con.cli_cmds.input(string=write_str, _e=emacs)
        else:
            raise cli.CliError("The given object must implement"
                               " the 'break_strings_v2' interface.")

def register_console_breakpoints(bpm_class):
    simics.SIM_register_port(bpm_class, "console_string",
                             ConStrBreakpoints.cls.classname,
                             ConStrBreakpoints.TYPE_DESC)

    cli.new_command("wait-then-write", ConStrBreakpoints.wait_then_write_cmd,
                    args = [cli.arg(cli.obj_t("con", iface='break_strings_v2'),
                                    "console"),
                            cli.arg(cli.flag_t, "-regexp"),
                            cli.arg(cli.flag_t, "-e"),
                            cli.arg(cli.str_t, "output-string"),
                            cli.arg(cli.str_t, "input-string")],
                    type=["Breakpoints", "Debugging"],
                    short="wait for a string, then write an input string",
                    cls=ConStrBreakpoints.cls.classname,
                    see_also = ['<break_strings_v2>.bp-break-console-string',
                                '<break_strings_v2>.bp-wait-for-console-string',
                                'script-branch'],
                    doc = """
Wait for the output of the text <arg>output-string</arg> on
<arg>console</arg>. When the text is found, write
<arg>input-string</arg> to the console.  This command can only be run
from a script branch where it suspends the branch until the string has
been found in the output.

The <tt>-e</tt> flag allows specifying the input string using an
Emacs-style keystroke, similar to <cmd class="textcon">input</cmd>.
""" + console_break_strings.regexp_arg_doc("wait-then-write"))
