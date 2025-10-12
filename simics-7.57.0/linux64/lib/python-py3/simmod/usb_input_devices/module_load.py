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
    CliError,
    arg,
    bool_t,
    get_completions,
    int_t,
    new_command,
    new_info_command,
    new_status_command,
    str_t,
    )
from simics import *

# Info & Status
def get_info(obj):
    return [("Connections",
             [("Host",   obj.usb_host)])]

def get_status(obj):
    return []

for ns in ["usb_hs_keyboard","usb_keyboard","usb_mouse"]:
    new_info_command(ns, get_info)
    new_status_command(ns, get_status)

#
# -------------------- key-press --------------------
#

keys_table = [        "ILLEGAL", "ESC",                                                                 \
        "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",                      \
        "PRNT_SCRN", "SCROLL_LOCK", "NUM_LOCK", "CAPS_LOCK",                                            \
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",                                               \
        "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N",                           \
        "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",                                     \
        "APOSTROPHE", "COMMA", "PERIOD", "SEMICOLON", "EQUAL", "SLASH", "BACKSLASH", "SPACE",           \
        "LEFT_BRACKET", "RIGHT_BRACKET", "MINUS", "GRAVE", "TAB", "ENTER", "BACKSPACE",                 \
        "CTRL_L", "CTRL_R", "SHIFT_L", "SHIFT_R", "ALT_L", "ALT_R",                                     \
        "GR_DIVIDE", "GR_MULTIPLY", "GR_MINUS", "GR_PLUS", "GR_ENTER", "GR_INSERT", "GR_HOME",          \
        "GR_PG_UP", "GR_DELETE", "GR_END", "GR_PG_DOWN", "GR_UP", "GR_DOWN", "GR_LEFT", "GR_RIGHT",     \
        "KP_HOME", "KP_UP", "KP_PG_UP", "KP_LEFT", "KP_CENTER", "KP_RIGHT", "KP_END", "KP_DOWN",        \
        "KP_PG_DOWN", "KP_INSERT", "KP_DELETE",                                                         \
        "PAUSE",                                                                                        \
        "LEFT_WIN", "RIGHT_WIN", "LIST_BIT",                                                            \
        "KEY102", "BREAK", "SYSREQ",                                                                    \
        "SUN_STOP", "SUN_AGAIN", "SUN_PROPS", "SUN_UNDO", "SUN_FRONT", "SUN_COPY", "SUN_OPEN",          \
        "SUN_PASTE", "SUN_FIND", "SUN_CUT", "SUN_HELP", "SUN_COMPOSE", "SUN_META_L",                    \
        "SUN_META_R", "SUN_POWER", "SUN_AUDIO_D", "SUN_AUDIO_U", "SUN_AUDIO_M", "SUN_EMPTY",
]

def key_expander(prefix):
    return get_completions(prefix, [x for x in keys_table if x != "ILLEGAL"])

def key_press_cmd(obj, keys, simultaneously):
    key_codes = []
    for key in keys:
        try:
            key_codes.append(keys_table.index(key))
        except ValueError:
            raise CliError("No key '%s' on the keyboard" % key)
    print(key_codes)
    if simultaneously:
        for key_code in key_codes:
            obj.iface.keyboard.keyboard_event(0, key_code)
        for key_code in reversed(key_codes):
            obj.iface.keyboard.keyboard_event(1, key_code)
    else:
        for key_code in key_codes:
            obj.iface.keyboard.keyboard_event(0, key_code)
            obj.iface.keyboard.keyboard_event(1, key_code)

for ns in ["usb_hs_keyboard","usb_keyboard"]:
    new_command("key-press", key_press_cmd,
            [arg(str_t, "key", "+", expander = key_expander),
             arg(bool_t(), "simultaneously", "?", 0)],
            type = ["USB"],
            cls = ns,
            short = "send key event",
            doc = """
Press one or more keys on the keyboard. This translates to a series of key down
events followed by the matching key up events. The <arg>key</arg> names
correspond to the keys on a U.S. keyboard with no keys remapped by software. If
<arg>simultaneously</arg> is true, that means you press keys simultaneously,
otherwise, you press keys sequentially. Default of simultaneously is false.""")

#
# -------------------- key-down, key-up --------------------
#

def key_down_cmd(obj, key_code):
    obj.iface.keyboard.keyboard_event(0, key_code)

def key_up_cmd(obj, key_code):
    obj.iface.keyboard.keyboard_event(1, key_code)

for ns in ["usb_hs_keyboard","usb_keyboard"]:
    new_command("key-down", key_down_cmd,
            [arg(int_t, "key-code")],
            type = ["USB"],
            cls = ns,
            see_also = ['<usb_hs_keyboard>.key-press'],
            short = "send key down event",
            doc = """
Send a key press to the keyboard controller. The <arg>key-code</arg> argument
is the internal Simics keycode. The <cmd class="%s">key-press</cmd>
command is recommend instead.""" % ns)

for ns in ["usb_hs_keyboard","usb_keyboard"]:
    new_command("key-up", key_up_cmd,
            [arg(int_t, "key-code")],
            type = ["USB"],
            cls = ns,
            short = "send key up event",
            doc_with = "<usb_hs_keyboard>.key-down")


STEP_LIMIT = 8      # MAX pixeles number per moving step in the moveto command

def truncate(x, limit):
    if abs(x) > limit:
        if x > 0:
            return limit
        else:
            return -limit
    else:
        return x

# move mouse to coordinator x, y
def moveto_cmd(obj, x, y):
    while ((abs(x - obj.curr_x) > STEP_LIMIT) or (abs(y - obj.curr_y) > STEP_LIMIT)):
        diff_x = truncate(x - obj.curr_x, STEP_LIMIT)
        diff_y = truncate(y - obj.curr_y, STEP_LIMIT)
        obj.iface.mouse.mouse_event(diff_x/obj.ratio, -diff_y/obj.ratio, 0, 0)
        obj.curr_x += diff_x
        obj.curr_y += diff_y
    obj.iface.mouse.mouse_event((x-obj.curr_x)/obj.ratio, -(y-obj.curr_y)/obj.ratio, 0, 0)
    obj.curr_x = x
    obj.curr_y = y

def reset_cmd(obj):
    for i in range(2560/STEP_LIMIT):
        obj.iface.mouse.mouse_event(-STEP_LIMIT/obj.ratio, STEP_LIMIT/obj.ratio, 0, 0)
    obj.curr_x = 0
    obj.curr_y = 0

def left_button_cmd(obj, dir):
    if dir == "down":
        button = 0x1
    elif dir == "up":
        button = 0
    else:
        raise CliError("Illegal button direction: %s" % dir)

    obj.iface.mouse.mouse_event(0, 0, 0, button)

def right_button_cmd(obj, dir):
    if dir == "down":
        button = 0x2
    elif dir == "up":
        button = 0
    else:
        raise CliError("Illegal button direction: %s" % dir)

    obj.iface.mouse.mouse_event(0, 0, 0, button)

def middle_button_cmd(obj, dir):
    if dir == "down":
        button = 0x4
    elif dir == "up":
        button = 0
    else:
        raise CliError("Illegal button direction: %s" % dir)

    obj.iface.mouse.mouse_event(0, 0, 0, button)

for ns in ["usb_mouse"]:
    new_command("moveto", moveto_cmd,
        [arg(int_t, "coordinator_x"), arg(int_t, "coordinator_y")],
        type = ["USB"],
        cls = ns,
        see_also = ['<usb_mouse>.reset'],
        short = "move mouse cursor",
        doc = """
Move the mouse cursor to a specific position of the screen identified by
<arg>coordinator_x</arg> and <arg>coordinator_y</arg>. To correctly run this
command, target OS should disable its mouse acceleration feature.
The feature has been available in Windows through "Enhance Pointer Precision" setting
from Mouse properties in control panel. If the target OS is Linux, the feature can also
be disabled through xinput command as "xinput set-prop 10 259 -1".
It is better to run "Reset" command right after the target OS setting to clear
previous side-effects caused by this target OS feature.
""")

    new_command("reset", reset_cmd,
        [],
        type = ["USB"],
        cls = ns,
        see_also = ['<usb_mouse>.moveto'],
        short = "reset mouse cursor",
        doc = """
Reset the mouse cursor to the left-top of the screen.
It is recommended to run this command before a serial of "moveto" commands.
The mouse acceleration feature of the target OS should be disabled before this command.
""")

    new_command("left-button", left_button_cmd,
        [arg(str_t, "direction")],
        type = ["USB"],
        cls = ns,
        short = "send button down/up event",
        doc = """
Presses or releases a mouse button. The <arg>direction</arg> is <tt>up</tt> or
<tt>down</tt>.""")

    new_command("right-button", right_button_cmd,
        [arg(str_t, "direction")],
        type = ["USB"],
        cls = ns,
        short = "send button down/up event",
        doc_with = "<usb_mouse>.left-button")

    new_command("middle-button", middle_button_cmd,
        [arg(str_t, "direction")],
        type = ["USB"],
        cls = ns,
        short = "send button down/up event",
        doc_with = "<usb_mouse>.left-button")
