# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from blueprints import Builder, ConfObject, Config, Namespace
from .state import GFXInputConnectionState, GFXConsoleConnectionState, UARTConnectionState
from .colors import color_name_to_rgb
from blueprints.data import blueprint
from blueprints.params import params_from_config

class TextConsoleParams(Config):
    unconnected_title = "Serial console, not connected"
    console_title = "serial console"
    title = ""
    fg_color = "black"
    bg_color = "white"
    width = 80
    height = 24
    scrollback = 10000
    pty: str = None
    visible = True

def textcon_finalize(console, pty):
    if pty is not None:
        if pty:
            console.iface.host_serial.setup(pty)
        else:
            console.iface.host_serial.setup(None)

@blueprint(params_from_config(TextConsoleParams))
def text_console(bp: Builder, name: Namespace, params: TextConsoleParams,
                 dev: UARTConnectionState=None):
    uart = dev or bp.read_state(name, UARTConnectionState, allow_local=True)
    # Connector
    uart.remote_connector = bp.obj(name.connector, "uart-remote-connector",
          device=name,
          aname="device",
          remote=uart.uart_connector
    )

    title = params.title
    if not title and uart.uart:
        title = params.console_title
    else:
        title = params.unconnected_title

    fg_color = color_name_to_rgb(params.fg_color)
    bg_color = color_name_to_rgb(params.bg_color)

    uart.remote = bp.obj(name, "textcon",
        recorder = name.recorder,
        device = uart.uart,
        max_scrollback_size = params.scrollback,
        screen_size = [params.width, params.height],
        visible = params.visible,
        window_title = title,
        default_colours = [fg_color, bg_color],
    )
    bp.obj(name.recorder, "recorder")
    bp.at_post_instantiate(name, textcon_finalize,
        console=name,
        pty=params.pty)

class GfxConsoleParams(Config):
    unconnected_title = "Graphics console, not connected"
    console_title = "graphics console"
    title = None
    width = 640
    height = 480
    vnc_port = None
    visible = True
    title = None

def gfx_console(bp: Builder, name: Namespace, gfx_in: GFXInputConnectionState,
                gfx_con: GFXConsoleConnectionState,
                params: GfxConsoleParams):
    title = params.title
    if not title and gfx_con.gfx_device:
        title = params.console_title
    else:
        title = params.unconnected_title

    gfx_con.console = bp.obj(name, "graphcon",
        mouse = gfx_in.mouse,
        keyboard = gfx_in.keyboard,
        device = gfx_con.gfx_device,
        abs_mouse = gfx_in.abs_pointer,
        abs_pointer_enabled = bool(gfx_in.abs_pointer),
        recorder = name.recorder,
        visible = params.visible,
        screen_size = [params.width, params.height],
        window_title = title,
    )
    gfx_in.console = gfx_con.console
    bp.obj(name.recorder, "recorder")
    # configure <graphcon>.tcp port-object
    bp.set(name.tcp, port=params.vnc_port)

def script_engine(bp: Builder, name: Namespace,
                  script: list[str],
                  con: ConfObject|None=None,
                  output: ConfObject|None=None,
                  input: ConfObject|None=None):
    """
    The script_engine blueprint takes the following parameters:

    script       list with scripting directives
    output       wait object (typically a console)
    input        object for scripted input (typically a console)
    con          console object (used for both input and output).
    """

    wait_obj = output if output else con
    input_obj = input if input else con
    bp.obj(name, "script-engine",
        wait_obj = wait_obj, input_obj = input_obj, script = script)
