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


import os
import cli
import simics
import conf
import re
import console_break_strings
from simicsutils.host import is_windows
from deprecation import DEPRECATED

key_modifiers = {
    "A": simics.Text_Console_Modifier_Alt,
    "C": simics.Text_Console_Modifier_Ctrl,
    "S": simics.Text_Console_Modifier_Shift,
}

special_keys = {
    "Tab": simics.Text_Console_Key_Tab,
    "Enter": simics.Text_Console_Key_Return,
    "Esc": simics.Text_Console_Key_Escape,
    "Left": simics.Text_Console_Key_Left,
    "Up": simics.Text_Console_Key_Up,
    "Right": simics.Text_Console_Key_Right,
    "Down": simics.Text_Console_Key_Down,
    "F1": simics.Text_Console_Key_F1,
    "F2": simics.Text_Console_Key_F2,
    "F3": simics.Text_Console_Key_F3,
    "F4": simics.Text_Console_Key_F4,
    "F5": simics.Text_Console_Key_F5,
    "F6": simics.Text_Console_Key_F6,
    "F7": simics.Text_Console_Key_F7,
    "F8": simics.Text_Console_Key_F8,
    "F9": simics.Text_Console_Key_F9,
    "F10": simics.Text_Console_Key_F10,
    "F11": simics.Text_Console_Key_F11,
    "F12": simics.Text_Console_Key_F12,

    "Backspace": simics.Text_Console_Key_Backspace,
    "Home": simics.Text_Console_Key_Home,
    "End": simics.Text_Console_Key_End,
    "Ins": simics.Text_Console_Key_Ins,
    "Del": simics.Text_Console_Key_Del,
    "PgDn": simics.Text_Console_Key_Pgup,
    "PgUp": simics.Text_Console_Key_Pgdn,
    "Spc": ord(' '),

    "Kp_0": simics.Text_Console_Key_KP_0,
    "Kp_1": simics.Text_Console_Key_KP_1,
    "Kp_2": simics.Text_Console_Key_KP_2,
    "Kp_3": simics.Text_Console_Key_KP_3,
    "Kp_4": simics.Text_Console_Key_KP_4,
    "Kp_5": simics.Text_Console_Key_KP_5,
    "Kp_6": simics.Text_Console_Key_KP_6,
    "Kp_7": simics.Text_Console_Key_KP_7,
    "Kp_8": simics.Text_Console_Key_KP_8,
    "Kp_9": simics.Text_Console_Key_KP_9,
    "Kp_Plus": simics.Text_Console_Key_KP_Plus,
    "Kp_Minus": simics.Text_Console_Key_KP_Minus,
    "Kp_Mul": simics.Text_Console_Key_KP_Mul,
    "Kp_Div": simics.Text_Console_Key_KP_Div,
    "Kp_Dot": simics.Text_Console_Key_KP_Dot,
    "Kp_Enter": simics.Text_Console_Key_KP_Enter,
}

def enable_cmdline_output_cmd(obj):
    obj.cmd_line_output = True

def disable_cmdline_output_cmd(obj):
    obj.cmd_line_output = False

def show_window_cmd(obj):
    if conf.sim.hide_console_windows:
        print(
"""Console windows are globally hidden.
Set the sim->hide_console_windows attribute to FALSE to change this
(e.g. by running the 'sim->hide_console_windows = FALSE' command
on Simics command-line interface).""")
        return
    elif obj.visible:
        msg = "Window already displayed."
    else:
        obj.visible = True
        msg = "Display console window."
    return cli.command_return(msg)

def hide_window_cmd(obj):
    if not obj.visible:
        msg = "Window already hidden."
    else:
        obj.visible = False
        msg = "Hiding console window."
    return cli.command_return(msg)

def input_cmd(console, string, emacs):
    if not emacs:
        console.iface.con_input.input_str(string)
    else:
        # Only accept [a-zA-Z0-9_?] as non-special keys
        key_re = re.compile(r"^(\w|[?])$", re.ASCII)
        strokes = []

        # Keystrokes are whitespace delimited
        for key in string.split(' '):
            stroke = key.split('-')
            if len(stroke) > len(key_modifiers) + 1:
                raise cli.CliError(f"Invalid Emacs keystrokes: {string}."
                                   " Too many key modifiers.")
            mods = stroke[:-1]
            k = stroke[-1]
            modifier = 0
            for m in mods:
                if m in key_modifiers:
                    if modifier & key_modifiers[m]:
                        raise cli.CliError(
                            f"Invalid Emacs keystrokes: {string}."
                            f" Modifier {m} already applied.")
                    modifier |= key_modifiers[m]
                else:
                    raise cli.CliError(
                        f"Invalid Emacs keystrokes: {string}."
                        f" Unknown modifier {m}.")
            if k in special_keys:
                strokes.append((special_keys[k], modifier))
            elif key_re.fullmatch(k):
                strokes.append((ord(k), modifier))
            else:
                raise cli.CliError(
                    f"Invalid Emacs keystrokes: {string}."
                    " Characters must be white space delimited")
        for s in strokes:
            console.iface.text_console_backend.input(s[0], s[1])

def insert_file_cmd(console, filename, binary):
    try:
        size = os.stat(filename).st_size
    except OSError as ex:
        raise cli.CliError("[%s] Error reading file size of \'%s\': %s"
                           % (console.name, filename, ex))
    try:
        input_file = open(filename, "rb")
    except IOError as ex:
        raise cli.CliError("[%s] Error opening file \'%s\': %s"
                           % (console.name, filename, ex))
    try:
        data = input_file.read(size)
    except IOError as ex:
        raise cli.CliError("[%s] Error reading file \'%s\': %s"
                           % (console.name, filename, ex))

    # Replace Windows line endings with Unix line endings to avoid getting
    # the effect of pressing enter twice after each line.
    if not binary:
        data = data.replace(b"\r\n", b"\n")
        console.iface.con_input.input_str(data.decode('utf-8'))
    else:
        console.iface.con_input.input_data(data)
    try:
        input_file.close()
    except IOError as ex:
        raise cli.CliError("[%s] Error closing file \'%s\': %s"
                           % (console.name, filename, ex))

def cap_start_cmd(console, filename, overwrite):
    if overwrite and os.path.exists(filename):
        try:
            os.unlink(filename)
        except OSError as ex:
            raise cli.CliError("Failed removing existing file '%s': %s"
                               % (filename, ex))
    try:
        console.output_file = filename
    except simics.SimExc_IllegalValue:
        raise cli.CliError(f"Could not open output file '{filename}'")

def cap_stop_cmd(console):
    filename = console.output_file
    console.output_file = ""
    return cli.command_return("Capture to file '%s' stopped." % filename)

def get_screen_lines(data, width, line_data):
    lines = []
    for row in range(len(line_data)):
        line_len = line_data[row][0]
        line_wrap = line_data[row][1]
        line = b''.join([bytes((data[row * width + col],))
                         for col in range(line_len)])
        if not line_wrap:
            line += os.linesep.encode('utf-8')
        lines.append(line)

    # remove trailing empty lines SIMICS-15450
    for i in range(len(lines) - 1, 0, -1):
        if not len(lines[i].rstrip()):
            lines.pop(i)
        else:
            break
    return lines

# Return the screen contents from the console in the standard format.
def get_screen_contents(con):
    screen_size = con.screen_size
    width = screen_size[0]
    sb_data = con.scrollback_data
    data = [c for c in sb_data[0]]
    line_data = list(sb_data[3])
    screen_data = con.screen_data
    data += screen_data[0]
    line_data += screen_data[2]
    return get_screen_lines(data, width, line_data)

def save_to_file_cmd(console, filename, overwrite):
    if overwrite and os.path.exists(filename):
        try:
            os.unlink(filename)
        except OSError as ex:
            raise cli.CliError("Failed removing existing file '%s': %s"
                               % (filename, ex))
    lines = get_screen_contents(console)
    with open(filename, "ab") as f:
        for l in lines:
            f.write(l)
    return cli.command_return("Console screen saved to %s" % filename)

def telnet_setup_cmd(console, port_or_socket_arg, shutdown, raw):
    (_, port_or_socket, _) = port_or_socket_arg
    console.telnet_raw = raw
    if shutdown:
        console.iface.telnet_connection_v2.disconnect()

    if isinstance(port_or_socket, str):
        try:
            if not is_windows():
                console.unix_socket.socket_name = port_or_socket
        except simics.SimExc_IllegalValue:
            pass
        else:
            if not is_windows():
                socket = console.unix_socket.socket_name
            else:
                socket = None
            if socket:
                return cli.command_return(f"Telnet server started on {socket}",
                                          value=socket)
        return cli.command_return(f"Failed to start telnet server on"
                                  f" socket '{port_or_socket}'")

    else:
        # Privileged ports not allowed
        port = port_or_socket
        if not (port == 0 or 1024 <= port <= 65535):
            raise cli.CliError(f"Privileged port {port} not allowed")

        try:
            console.tcp.port = port
        except simics.SimExc_IllegalValue:
            pass
        else:
            real_port = console.tcp.port
            if real_port:
                return cli.command_return(
                    message=f"Telnet server started on port {real_port}",
                    value=real_port)

        return cli.command_return("Failed to start telnet server")

def telnet_status_cmd(console):
    if (console.iface.telnet_connection_v2.connected()
        or console.iface.telnet_connection_v2.listening()):
        server_port = console.tcp.port
        if not is_windows():
            unix_socket = console.unix_socket.socket_name
        else:
            unix_socket = None
        ipv4 = simics.VT_use_ipv4()
        msg = [f"Host port: {server_port}",
               f"UNIX socket: {unix_socket}",
               f"Raw: {console.telnet_raw}",
               f"IPv4 connections only: {ipv4}",
               f"Send data on connect: {console.telnet_send_data_on_connect}"]
        val = [server_port, unix_socket, console.telnet_raw, ipv4]
        return cli.command_return("\n".join(msg), val)
    else:
        return cli.command_return("Telnet server not started",
                                  [None, None, None, None, None])

def host_serial_setup_cmd(console, pty):
    if console.iface.host_serial.setup(pty):
        return console.iface.host_serial.name()
    else:
        return None

def start_output_recording_cmd(obj):
    obj.recorded_output = ""
    obj.output_recording = True

def stop_output_recording_cmd(obj):
    record = obj.recorded_output
    obj.output_recording = False
    obj.recorded_output = ""
    return record

def get_info(console):
    if console and hasattr(console, 'iface'):
        return [(None,
                 [("Device", console.device),
                  ("Serial frontends", len(console.serial_frontends)),
                  ("Recorder", console.recorder)])]
    else:
        return [(None, [])]

def get_status(console):
    if console and hasattr(console, 'iface'):
        server_port = console.tcp.port
        if not is_windows():
            unix_socket = console.unix_socket.socket_name
        else:
            unix_socket = None
        return [("Screen",
                 [("Size width x height",
                   "%dx%d" % (console.screen_size[0], console.screen_size[1])),
                  ("Break strings", len(console.break_strings)),
                  ("Max scrollback lines", console.max_scrollback_size),
                  ("Used scrollback lines", len(console.scrollback_data[3])),
                  ("Pty", console.pty)]),
                ("Telnet",
                 [("Port", server_port),
                  ("UNIX socket", unix_socket),
                  ("Listening", console.iface.telnet_connection_v2.listening()),
                  ("Connected", console.iface.telnet_connection_v2.connected())]),
                ("ANSI escape sequence filtering",
                 [("Breakpoint matching", console.filter_esc[0]),
                  ("CLI output", console.filter_esc[1]),
                  ("Log output", console.filter_esc[2]),
                  ("Elsewhere", console.filter_esc[3])]),
                ("Misc",
                 [("Capture filename", console.output_file)]),
        ]
    else:
        return [(None, [])]

def frontend_info(console):
    return [(None, [])]

def frontend_status(console):
    return [(None, [])]

def obsolete_cmd(console):
    raise cli.CliError("[%s] Obsolete command not available" % console.name)

def wait_then_write_cmd(console, slow_flag, regexp, emacs, wait_str, write_str):
    console_break_strings.wait_then_write_cmd(
        console, slow_flag, regexp, emacs, wait_str, write_str,
        lambda con, s, e: input_cmd(con, s, e))
