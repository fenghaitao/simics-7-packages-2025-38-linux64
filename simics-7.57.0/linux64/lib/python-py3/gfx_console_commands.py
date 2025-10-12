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


import os
import cli
import simics
import gfx_console_common
import conf
import script_branch
import struct
import string
import console_break_strings
from simicsutils.host import is_windows
from deprecation import DEPRECATED

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
        msg = "Displaying console window."
    return cli.command_return(msg)

def hide_window_cmd(obj):
    if not obj.visible:
        msg = "Window already hidden."
    else:
        obj.visible = False
        msg = "Hiding console window."
    return cli.command_return(msg)

def save_break_xy_cmd(console, filename, left, top, right, bottom):
    if console.iface.gfx_break.store(
            filename, left, top, right, bottom):
        print("Stored graphical breakpoint")
    else:
        raise cli.CliError("Could not store graphical breakpoint to %s"
                           % filename)

def break_match_cmd(console, filename):
    match = console.iface.gfx_break.match(filename)
    if match >= 0:
        return match > 0
    else:
        raise cli.CliError("Could not load graphical breakpoint")

def break_info_cmd(console, filename):
    header = console.iface.gfx_break.info(filename)
    if header[2] > 0:
        width = header[5] - header[3] + 1
        height = header[6] - header[4] + 1
        return  [header[3], header[4], width, height]
    else:
        raise cli.CliError("Could not load graphical breakpoint")

def break_png_cmd(console, filename, png_filename):
    ok = console.iface.gfx_break.export_png(filename, png_filename)
    if ok:
        return ok
    else:
        raise cli.CliError("Could not export graphical breakpoint")

def input_string(console, string):
    # Try to construct keystrokes generating string.
    data = gfx_console_common.string_to_keystrokes(string)
    if data:
        for (ch, stroke) in data:
            (up, code) = stroke
            console.iface.con_input_code.input(code, up == 0)
    else:
        raise cli.CliError("[%s] Failed writing string" % console.name)

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
        input_string(console, data)
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

def insert_cmd(console, s, e):
    if e:
        # Input emacs-style key combination.
        release = []
        for key in s.split('-'):
            data = gfx_console_common.emacs_to_keystrokes(key)
            if data:
                for (up, code) in data:
                    if up == 1:
                        release.append(code)
                    else:
                        console.iface.con_input_code.input(code, True)
            else:
                raise cli.CliError("[%s] Failed writing Emacs string"
                                   % console.name)
        for code in release:
            console.iface.con_input_code.input(code, False)
    else:
        input_string(console, s)

def setup_interfaces(cls):
    # We implement con_input interface in terms of con_input_code
    # to allow similar usage on text and graphics consoles.
    input_if = simics.con_input_interface_t(
        input_str = input_string,
        input_data = input_string)
    simics.SIM_register_interface(cls, "con_input", input_if)

def get_info(console):
    if console and hasattr(console, 'iface'):
        return [(None,
                 [("VGA device", console.device),
                  ("Keyboard", console.keyboard),
                  ("Mouse", console.mouse),
                  ("Recorder", console.recorder)])]

def get_status(console):
    if console and hasattr(console, 'iface'):
        server_port = console.tcp.port
        if not is_windows():
            unix_socket = console.unix_socket.socket_name
        else:
            unix_socket = None
        return [("Mouse",
                 [("Absolute positioning", console.abs_pointer_enabled),
                  ("Absolute pointer device", console.abs_mouse)]),
                ("Grab", [("Mouse button", console.grab_button),
                          ("Modifier", console.grab_modifier)]),
                ("VNC", [("Port", server_port),
                         ("UNIX socket", unix_socket),
                         ("Listening", console.iface.vnc_server_v2.listening()),
                         ("Connections",
                          console.iface.vnc_server_v2.num_clients())]),
                ("Screen", [("Size width x height",
                             "%dx%d" % (console.screen_size[0],
                                        console.screen_size[1])),
                            ("Refresh rate (Hz, {time} time)".format(
                                time=("virtual" if
                                      console.refresh_in_virtual_time else
                                      "real")), console.refresh_rate)])]

def vnc_setup_cmd(console, port_or_socket_arg, password):
    (_, port_or_socket, _) = port_or_socket_arg
    if password:
        try:
            console.vnc_password = password
        except simics.SimExc_IllegalValue as ex:
            raise cli.CliError(str(ex))
    else:
        console.vnc_password = None

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
                return cli.command_return(f"VNC server started on {socket}",
                                          value=socket)
        return cli.command_return("Failed to start VNC server on"
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
                    message=f"VNC server started on port {real_port}",
                    value=real_port)
        return cli.command_return("Failed to start VNC server")

def vnc_status_cmd(console):
    if (console.iface.vnc_server_v2.listening()
        or (not is_windows() and console.unix_socket.socket_name)):
        server_port = console.tcp.port
        num_clients = console.iface.vnc_server_v2.num_clients()
        if not is_windows():
            unix_socket = console.unix_socket.socket_name
        else:
            unix_socket = None
        ipv4 = simics.VT_use_ipv4()
        password = console.vnc_password or ""
        msg = [f"Host port: {server_port}",
               f"UNIX socket: {unix_socket}",
               f"VNC password: {password}",
               f"IPv4 connections only: {ipv4}",
               f"Clients: {num_clients}"]
        val = [server_port, unix_socket, password, ipv4, num_clients]
        return cli.command_return("\n".join(msg), val)
    else:
        return cli.command_return("VNC server not started",
                                  [None, None, None, None, None])

def frontend_info(console):
    return [(None, [])]

def frontend_status(console):
    return [(None, [])]

def screenshot_cmd(console, fname, fmt):
    if fmt == '':
        if fname.lower().endswith('png'):
            fmt = 'png'
        elif fname.lower().endswith('bmp'):
            fmt = 'bmp'

    if fmt == 'png':
        if console.iface.screenshot.save_png(fname):
            return cli.command_return(
                "[%s]: PNG file saved as '%s'" % (console.name, fname))
        else:
            raise cli.CliError("Error saving PNG file")
    elif fmt == 'bmp':
        if console.iface.screenshot.save_bmp(fname):
            return cli.command_return(
                "[%s]: BMP file saved as '%s'" % (console.name, fname))
        else:
            raise cli.CliError("Error saving BMP file")
    else:
        raise cli.CliError("Unknown screenshot format '%s'" % fmt)

def grab_setup_cmd(console, button, modifier):
    if button == "inquiry" and modifier == "none":
        mod = console.grab_modifier
        mod_str = 'left "%s" key + ' % mod
        print('Input is currently grabbed with: %s%s mouse button.' % (
            mod_str, console.grab_button))
    else:
        if button != "inquiry":
            try:
                console.grab_button = button
            except simics.SimExc_IllegalValue as msg:
                raise cli.CliError("Failed setting selected grab button (%s)"
                                   % msg)
        if modifier != "none":
            try:
                console.grab_modifier = modifier
            except simics.SimExc_IllegalValue as msg:
                raise cli.CliError("Failed setting selected grab modifier (%s)"
                                   % msg)
        if simics.SIM_get_quiet() == 0:
            print(("Setting grab/ungrab to: %s mouse button, modifier: %s"
                   % (console.grab_button, console.grab_modifier)))

def verify_coord(console, x, y):
    size = console.screen_size
    if not (x >= 0 and x < size[0] and y >= 0 and y < size[1]):
        raise cli.CliError("Invalid pixel coordinate (x, y) = (%u, %u)"
                           " on screen of size (w, h) = (%u, %u)"
                           % (x, y, size[0], size[1]))

def decode_pixel(rgb):
    if isinstance(rgb, list):
        if len(rgb) != 3 or not all(k >= 0 and k < 256 for k in rgb):
            raise cli.CliError("Pixel must be a 3-element list of 8-bit values")
        return rgb
    else:
        assert isinstance(rgb, str)
        if not (len(rgb) == 7 and rgb[0] == '#' and
                all(c in string.hexdigits for c in rgb[1:])):
            raise cli.CliError("Pixel string must have form #RRGGBB")
        return [int(rgb[1:3], 16), int(rgb[3:5], 16), int(rgb[5:], 16)]

def set_pixel_cmd(console, x, y, rgb):
    verify_coord(console, x, y)
    pixel = decode_pixel(rgb)
    console.iface.gfx_con.put_pixel_rgb(
        x, y, pixel[0] << 16 | pixel[1] << 8 | pixel[2])
    console.iface.gfx_con.redraw()

def get_pixel_cmd(console, x, y):
    verify_coord(console, x, y)
    start = 4 * (console.screen_size[0] * y + x)
    # Screen memory is stored as BGRx
    return list(reversed(console.screen_data[start : start + 3]))

# This must match the gbp_header_t structure
def create_gfx_break(x, y, rgb):
    return (struct.pack("=LLQLLLL", 0xe0e0e0e0, 32, 4, x, y, x, y)
            + struct.pack("=BBBB", rgb[2], rgb[1], rgb[0], 0))

def wait_for_pixel_cmd(console, x, y, rgb, interval):
    verify_coord(console, x, y)
    pixel = decode_pixel(rgb)

    cli.check_script_branch_command("wait-for-pixel-value")
    break_id = console.iface.gfx_break.add_bytes(
        create_gfx_break(x, y, pixel), "", False, interval, None, None)
    try:
        script_branch.sb_wait_for_hap_internal(
                            '%s.wait-for-pixel-value' % console.name,
                            "Gfx_Break", console, break_id)
    finally:
        if isinstance(console, simics.conf_object_t):
            # unregister, unless SB interrupted because object was deleted.
            console.iface.gfx_break.remove(break_id)

def wait_then_write_cmd(console, slow_flag, regexp, emacs, wait_str, write_str):
    console_break_strings.wait_then_write_cmd(
        console, slow_flag, regexp, emacs, wait_str, write_str,
        lambda con, s, e: insert_cmd(con, s, e))

def prefs_should_dim():
    try:
        return conf.prefs.iface.preference.get_preference_for_module_key(
            "graphcon", "dim-on-stop")
    except simics.SimExc_Attribute:
        return True

def set_dimming(console, value):
    old_value = prefs_should_dim()
    if value is not None:
        conf.prefs.iface.preference.set_preference_for_module_key(
            value, "graphcon", "dim-on-stop")
        msg=f"Dimming setting changed: {old_value} -> {value}"
        # Make sure preferences changed notifier is triggered
        prefs = dict(conf.prefs.module_preferences)
        conf.prefs.module_preferences = prefs
    else:
        msg=f"Dimming setting: {old_value}"
    return cli.command_return(message=msg, value=old_value)
