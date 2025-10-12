# © 2016 Intel Corporation
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
    arg,
    filename_t,
    flag_t,
    int_t,
    new_command,
    new_info_command,
    new_status_command,
    str_t,
    )
import text_console_commands
import simics

console_class = "textcon"
frontend_class = "text-frontend-winsome"

def setup_cli_commands(cls):
    new_command("enable-cmd-line-output",
                text_console_commands.enable_cmdline_output_cmd,
                [],
                type = ["Consoles"],
                short = "enable output to Simics command line",
                cls = cls,
                see_also = ['<%s>.disable-cmd-line-output' % cls],
                doc = """
If enabled, console output will be sent to the Simics command
line, and also logged at level 3. This is automatically enabled if
Simics is started with the console invisible.
""")

    new_command("disable-cmd-line-output",
                text_console_commands.disable_cmdline_output_cmd,
                [],
                type = ["Consoles"],
                short = "disable output to Simics command line",
                cls = cls,
                see_also = ['<%s>.enable-cmd-line-output' % cls],
                doc_with = '<%s>.enable-cmd-line-output' % cls)

    new_command("show", text_console_commands.show_window_cmd,
                [],
                type = ["Consoles"],
                short = "display the console window",
                cls = cls,
                see_also = ['<%s>.hide' % cls],
                doc = "Display the console window")

    new_command("hide", text_console_commands.hide_window_cmd,
                [],
                type = ["Consoles"],
                short = "hide the console window",
                cls = cls,
                see_also = ['<%s>.show' % cls],
                doc = """
Hide the console window. When the console window is hidden, any output
is redirected to the Simics command line. This can be suppressed using
the <attr>cmd_line_output</attr> attribute.
""")

    new_command(
        "input", text_console_commands.input_cmd,
        args = [arg(str_t, "string"),
                arg(flag_t, "-e")],
        type = ["Consoles"],
        short = "send input to a console",
        cls = cls,
        see_also = ['bp.console_string.wait-then-write'],
        doc = """Send <arg>string</arg> to the text console.

The command supports common escape sequences such as &quot;\\n&quot; for new
line and &quot;\\t&quot; for tab.

Octal or hexadecimal escape sequences can be used to send control characters to
the console, for example &quot;\\003&quot; or &quot;\\x03&quot; for Ctrl-C.

If <tt>-e</tt> is specified, then the string is interpreted as an
Emacs-style keystroke sequence. The following characters and modifiers
are accepted: 'C' (Ctrl), 'A' (Alt), 'S (Shift)', 'Enter',
'Backspace', 'Del', 'Up', 'Down', 'Left', 'Right', 'Esc', 'Tab',
'Home', 'End', 'Ins', 'Spc', 'PgDn', 'PgUp', 'F1' to 'F12', keypad
keys 'Kp_0' to 'Kp_9', 'Kp_Plus', 'Kp_Minus', 'Kp_Mul', 'Kp_Div',
'Kp_Dot', 'Kp_Enter' as well as regular alpha-numeric characters,
i.e. [a-zA-Z0-9_?]. Key strokes are delimited by whitespace, and
characters/modifiers are combined using the '-' character. For
example, "C-a" will input Ctrl and 'a' pressed together, "C-a a" will
do that followed by a single 'a' but "C-aa" is invalid. "C-A-Del" will
produce the famous Ctrl-Alt-Del sequence. Modifiers cannot be sent
individually, so e.g. "C" will send the character 'C', not Ctrl.
""")

    new_command("input-file", text_console_commands.insert_file_cmd,
                args = [arg(filename_t(exist = 1, simpath = 0), "file"),
                         arg(flag_t, "-binary")],
                type = ["Consoles"],
                short = "input a file into a console",
                cls = cls,
                doc = """
Inputs the contents of <arg>file</arg> into the text console. If
<tt>-binary</tt> is specified, the file is treated as a binary
file. If not, line endings are converted to CR.
""")

    new_command("capture-start", text_console_commands.cap_start_cmd,
                args = [arg(filename_t(), "filename"),
                        arg(flag_t, "-overwrite")],
                type = ["Consoles"],
                short = "capture output to file",
                cls = cls,
                see_also = ['<%s>.capture-stop' % cls],
                doc = """
Capture all output from the console to <arg>filename</arg>. If
<tt>-overwrite</tt> is specified, the file is
overwritten, otherwise it is appended.
""")

    new_command("capture-stop", text_console_commands.cap_stop_cmd,
                args = [],
                type = ["Consoles"],
                short = "stop output capture to file",
                cls = cls,
                see_also = ['<%s>.capture-start' % cls],
                doc = """
Stop capturing all output from the console.
""")

    new_command("save-to-file", text_console_commands.save_to_file_cmd,
                args = [arg(filename_t(), "filename"),
                        arg(flag_t, "-overwrite")],
                type = ["Consoles"],
                short = "save console screen to file",
                cls = cls,
                see_also = ['<%s>.capture-start' % cls],
                doc = """
Save all console screen and scrollback data to <arg>filename</arg>. If
<tt>-overwrite</tt> is specified, the file is
overwritten, otherwise it is appended.
""")

    new_command("telnet-setup", text_console_commands.telnet_setup_cmd,
                args = [arg((int_t, filename_t()),
                            ("port", "unix_socket"), "?", [int_t, 0, "port"]),
                        arg(flag_t, "-shutdown"),
                        arg(flag_t, "-raw"),],
                type = ["Consoles"],
                short = "setup telnet connection",
                cls = cls,
                see_also = ['<%s>.telnet-status' % cls],
                doc = """
Start telnet server on <arg>port</arg> or on UNIX socket
<arg>unix_socket</arg>. If neither <arg>port</arg> or <arg>unix_socket</arg>
is specified, or if <arg>port</arg> is set to 0, then an arbitrary port
is used. If the port is busy, the command fails, unless the
new_telnet_port_if_busy attribute has been set. The listening port is
returned, or NIL on failure.

The given port must not be a privileged port, i.e. allowed
range is [1024, 65535]. The command will fail if the <arg>unix_socket</arg>
argument specifies an already existing file. UNIX sockets are not supported
on Windows.

If <tt>-raw</tt> is specified, the telnet connections will use raw
mode, where telnet control codes will not be interpreted.

If <tt>-shutdown</tt> is specified, any open telnet connections will
be shutdown before starting a new server.
""")

    new_command("telnet-status", text_console_commands.telnet_status_cmd,
                args = [],
                type = ["Consoles"],
                short = "return telnet connection data",
                cls = cls,
                see_also = ['<%s>.telnet-setup' % cls],
                doc = """
Prints information about the telnet server connection status.

When used in an expression, the command returns a list with 5 entries:

1. The local port, or NIL if no telnet server is started.

2. TRUE if telnet raw mode is used, else FALSE.

3. TRUE if IPv4 is used, else FALSE.

4. The remote IP, or NIL if no telnet connection is active.

5. The remote port, or NIL if no telnet connection is active.
""")

    new_command("host-serial-setup",
                text_console_commands.host_serial_setup_cmd,
                args = [arg(str_t, "pty", "?", None)],
                type = ["Consoles"],
                short = "setup host serial connection",
                cls = cls,
                see_also = ['<%s>.telnet-setup' % cls],
                doc = """
Start host serial server on <arg>pty</arg> (or newly opened pty/COM if not
set or if None). If the pty/COM is busy, the command fails.
The name of the pty/COM is returned, or NIL on failure.
""")

    new_command("record-start",
                text_console_commands.start_output_recording_cmd,
                args = [],
                type = ["Consoles", "Recording"],
                short = "start recording of output on the console",
                cls = cls,
                see_also = ['<%s>.record-stop' % cls],
                doc = """
Starts recording of output on the console. All previously recorded output will
be discarded. The recorded string can be read with the
<cmd class="%s">record-stop</cmd> command.""" % cls)

    new_command("record-stop", text_console_commands.stop_output_recording_cmd,
                args = [],
                type = ["Consoles", "Recording"],
                short = "stop recording of output on the console",
                cls = cls,
                see_also = ['<%s>.record-start' % cls],
                doc = """
Stops recording of output on the console, and return the recorded string.""")

    new_info_command(cls, text_console_commands.get_info)
    new_status_command(cls, text_console_commands.get_status)

setup_cli_commands(console_class)

new_info_command(frontend_class, text_console_commands.frontend_info)
new_status_command(frontend_class, text_console_commands.frontend_status)
