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
    arg,
    filename_t,
    flag_t,
    float_t,
    get_completions,
    int_t,
    list_t,
    new_command,
    new_info_command,
    new_status_command,
    poly_t,
    str_t,
    boolean_t,
    )
import gfx_console_commands
import itertools
import simics

console_class = "graphcon"
frontend_class = "gfx-frontend-winsome"

def btn_expander(string, console):
    return get_completions(string, ["left", "right", "middle"])

def mod_expander(string, console):
    return get_completions(string, ["control", "alt", "shift"])

def save_expander(string, console):
    return get_completions(string, ["png", "bmp"])

def setup_cli_commands(cls):
    new_command("show", gfx_console_commands.show_window_cmd,
                [],
                type = ["Graphics"],
                short = "display the console window",
                cls = cls,
                see_also = ['<%s>.hide' % cls],
                doc = "Display the console window")

    new_command("hide", gfx_console_commands.hide_window_cmd,
                [],
                type = ["Graphics"],
                short = "hide the console window",
                cls = cls,
                see_also = ['<%s>.show' % cls],
                doc = "Hide the console window")

    new_command("grab-setup", gfx_console_commands.grab_setup_cmd,
                args = [arg(str_t, "button", "?", "inquiry",
                            expander = btn_expander),
                        arg(str_t, "modifier", "?", "none",
                            expander = mod_expander)],
                type = ["Graphics"],
                short = "set grab button and modifier",
                cls = cls,
                doc = """
The grab button <arg>button</arg> specifies which mouse button
that is used to grab and ungrab input for the console. A keyboard
modifier <arg>modifier</arg> should also be specified that must be
pressed for grabbing to occur. Valid buttons are left, middle and
right, while valid modifiers are alt, control and shift. Only the left
side modifier are currently used.  When called with no arguments, the
currently selected button and modifier will be printed.
""")

    new_command("screenshot", gfx_console_commands.screenshot_cmd,
                args = [arg(filename_t(), "filename"),
                        arg(str_t, "format", "?", "",
                            expander = save_expander)],
                type = ["Graphics"],
                short = "save screen as PNG or BMP",
                cls = cls,
                doc = """
This command saves the current console window contents to <arg>filename</arg>
in PNG or BMP format, depending on <arg>format</arg>, which defaults to PNG.
                """)

    new_command("save-break-xy", gfx_console_commands.save_break_xy_cmd,
                args = [arg(filename_t(exist = 0), "filename"),
                        arg(int_t, "left"),
                        arg(int_t, "top"),
                        arg(int_t, "right"),
                        arg(int_t, "bottom")],
                type = ["Graphics", "Breakpoints"],
                short = "specify and save a graphical breakpoint",
                see_also = ['<gfx_break>.bp-break-gfx',
                            'bp.delete',
                            '<%s>.gfx-break-match' % cls,
                            '<%s>.gfx-break-info' % cls,
                            '<%s>.gfx-break-png' % cls,
                            'bp.list'],
                cls = cls,
                doc = """
Stores a rectangular area of the screen to the file specified by
<arg>filename</arg>, for use with the <cmd>bp.gfx.break</cmd> command.
The rectangle is specified by the top left corner (<arg>left</arg>,
<arg>top</arg>) and the bottom right corner (<arg>right</arg>,
<arg>bottom</arg>), which must define a non-empty rectangle contained
in the console screen.""")

    new_command("gfx-break-match", gfx_console_commands.break_match_cmd,
                args = [arg(filename_t(exist = 1), "filename")],
                type = ["Graphics", "Breakpoints"],
                short = "determine if graphical breakpoint currently matches",
                cls = cls,
                see_also = ['<%s>.save-break-xy' % cls,
                            '<gfx_break>.bp-break-gfx',
                            '<%s>.gfx-break-info' % cls,
                            '<%s>.gfx-break-png' % cls],
                doc = """
Determine if the graphical breakpoint stored in
<arg>filename</arg> matches the current console screen.
""")

    new_command("gfx-break-info", gfx_console_commands.break_info_cmd,
                args = [arg(filename_t(exist = 1), "filename")],
                type = ["Graphics", "Breakpoints"],
                short = "return information about a graphical breakpoint",
                cls = cls,
                see_also = ['<%s>.save-break-xy' % cls,
                            '<gfx_break>.bp-break-gfx',
                            '<%s>.gfx-break-match' % cls,
                            '<%s>.gfx-break-png' % cls],
                doc = """
Return the screen area that the graphical breakpoint stored in
<arg>filename</arg> should match, as a list with four elements (left,
top, width, height).
""")

    new_command("gfx-break-png", gfx_console_commands.break_png_cmd,
                args = [arg(filename_t(exist = 1), "filename"),
                        arg(filename_t(exist = 0), "output")],
                type = ["Graphics"],
                short = "export graphical breakpoint data to a PNG file",
                cls = cls,
                see_also = ['<%s>.save-break-xy' % cls,
                            '<gfx_break>.bp-break-gfx',
                            '<%s>.gfx-break-match' % cls,
                            '<%s>.gfx-break-info' % cls],
                doc = """
Exports the graphical breakpoint data stored in
<arg>filename</arg> as a file <arg>output</arg> in PNG format.
""")

    new_command("input", gfx_console_commands.insert_cmd,
            args = [arg(str_t, "string"),
                    arg(flag_t, "-e")],
            type = ["Graphics", "Consoles"],
            short = "send string to a console",
            cls = cls,
            see_also = ['bp.console_string.wait-then-write'],
            doc = """
Send <arg>string</arg> to the console. This will not work if the
string contains non-printable or non-ASCII characters.

If <tt>-e</tt> is specified, then the string is interpreted as an
Emacs-style keystroke sequence. The following characters and modifiers
are accepted: 'C' (Ctrl), 'A' (Alt), 'Del', 'Up', 'Down', 'Left',
'Right', 'Esc', 'F1' to 'F12', 'Win', 'Enter' as well as the same characters
that are accepted without the <tt>-e</tt> flag. Key strokes are
combined using the '-' character. For example, "C-a" will input Ctrl
and 'a' pressed together. "C-A-Del" will produce the famous
Ctrl-Alt-Del sequence.  """)

    new_command("input-file", gfx_console_commands.insert_file_cmd,
                args = [arg(filename_t(exist = 1, simpath = 0), "file"),
                        arg(flag_t, "-binary")],
                type = ["Graphics"],
                short = "input a file into a console",
                cls = cls,
                doc = """
Inputs the contents of <arg>file</arg> into the console. If the
<tt>-binary</tt> flag is specified, the file is treated as a binary
file. If not, line endings are converted to CR. This command will not
work if the file contains non-printable or non-ASCII characters.
""")

    new_command("capture-start", gfx_console_commands.cap_start_cmd,
                args = [arg(filename_t(), "filename"),
                        arg(flag_t, "-overwrite")],
                type = ["Graphics"],
                short = "capture output to file",
                cls = cls,
                see_also = ['<%s>.capture-stop' % cls],
                doc = """
Capture all output from the console to <arg>filename</arg>. If
<tt>-overwrite</tt> is specified, the file is
overwritten, otherwise it is appended. This only works with legacy
devices and video modes that are text compatible, like old VGA.
""")

    new_command("capture-stop", gfx_console_commands.cap_stop_cmd,
                args = [],
                type = ["Graphics"],
                short = "stop output capture to file",
                cls = cls,
                see_also = ['<%s>.capture-start' % cls],
                doc = """
Stop capturing text output from the console.
""")

    new_command("vnc-setup", gfx_console_commands.vnc_setup_cmd,
                args = [arg((int_t, filename_t()),
                            ("port", "unix_socket"), "?", (int_t, 0, "port")),
                        arg(str_t, "password", "?"),
                        ],
                type = ["Graphics"],
                short = "setup VNC connection",
                cls = cls,
                see_also = ['<%s>.vnc-status' % cls],
                doc = """
Start VNC server on <arg>port</arg> or on UNIX socket <arg>unix_socket</arg>.
If neither <arg>port</arg> nor <arg>unix_socket</arg> is specified, or
if <arg>port</arg> is set to 0, then an arbitrary port is used. If the port
is busy, the command fails, unless the new_vnc_port_if_busy attribute
has been set. The listening port is returned, or NIL on failure.

The given port must not be a privileged port, i.e. allowed
range is [1024, 65535]. The command will fail if the <arg>unix_socket</arg>
argument specifies an already existing file. UNIX sockets are not support
on Windows.

If <arg>password</arg> is provided, the VNC server will use
authentication and require this password for new connections.
""")

    new_command("vnc-status", gfx_console_commands.vnc_status_cmd,
                args = [],
                type = ["Graphics"],
                short = "return VNC connection data",
                cls = cls,
                see_also = ['<%s>.vnc-setup' % cls],
                doc = """
Prints information about the VNC server connection status.

When used in an expression, the command returns a list with 3 entries:

1. The local port, or NIL if no VNC server is started.

2. TRUE if IPv4 is used, else FALSE.

3. The number of connected VNC clients.
""")

    new_command("set-pixel", gfx_console_commands.set_pixel_cmd,
                args = [arg(int_t, "x"),
                        arg(int_t, "y"),
                        arg(poly_t("rgb", list_t, str_t), "rgb")],
                type = ["Graphics"],
                short = "write pixel value",
                cls = cls,
                see_also = ['<gfx_break>.bp-break-gfx',
                            '<%s>.get-pixel' % cls],
                doc = """
Set pixel value at (<arg>x</arg>, <arg>y</arg>) from given
pixel data <arg>rgb</arg>, either as a 3-element list with format [R, G, B],
or as a hex string "#RRGGBB".
""")

    new_command("get-pixel", gfx_console_commands.get_pixel_cmd,
                args = [arg(int_t, "x"),
                        arg(int_t, "y")],
                type = ["Graphics"],
                short = "read pixel value",
                cls = cls,
                see_also = ['<gfx_break>.bp-break-gfx',
                            '<%s>.set-pixel' % cls],
                doc = """
Return pixel value at (<arg>x</arg>, <arg>y</arg>) as a 3-element
list with format [R, G, B].
""")

    new_command("wait-for-pixel-value", gfx_console_commands.wait_for_pixel_cmd,
                args = [arg(int_t, "x"),
                        arg(int_t, "y"),
                        arg(poly_t("rgb", list_t, str_t), "rgb"),
                        arg(float_t, "interval")],
                type = ["Graphics"],
                short = "real pixel value",
                cls = cls,
                see_also = ['<gfx_break>.bp-wait-for-gfx',
                            '<%s>.get-pixel' % cls],
                doc = """
Wait until the pixel at (<arg>x</arg>, <arg>y</arg>) has the given
value, specified by <arg>rgb</arg>, either a 3-element list with
format [R, G, B] or as a hex string "#RRGGBB". The pixel is checked every
<arg>interval</arg> seconds of virtual time on the clock associated to
the console.
""")

    new_command("dimming", gfx_console_commands.set_dimming,
                args = [arg(boolean_t, "value", "?", None)],
                type = ["Graphics"],
                short = "get/set dimming status",
                cls = cls,
                see_also = ["save-preferences"],
                doc = """
Returns whether the graphics console dims the screen when the
simulation is not running. Optionally, a new value can be supplied via
the <arg>value</arg> parameter, in which case the old value is
returned.

The setting can be saved between Simics runs using the
<cmd>save-preferences</cmd> command.
""")

    new_info_command(cls, gfx_console_commands.get_info)
    new_status_command(cls, gfx_console_commands.get_status)

setup_cli_commands(console_class)
gfx_console_commands.setup_interfaces(console_class)
new_info_command(frontend_class, gfx_console_commands.frontend_info)
new_status_command(frontend_class, gfx_console_commands.frontend_status)
