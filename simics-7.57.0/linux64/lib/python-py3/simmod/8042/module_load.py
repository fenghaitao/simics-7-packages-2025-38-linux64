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
    get_completions,
    int_t,
    new_command,
    new_info_command,
    new_status_command,
    str_t,
    )
from simics import *

def key_expander(prefix, obj):
    return get_completions(prefix, [x for x in obj.keys if x != "ILLEGAL"])

def key_press_cmd(obj, keys):
    key_codes = []
    for key in keys:
        try:
            key_codes.append(obj.keys.index(key))
        except ValueError:
            raise CliError("No key '%s' on the keyboard" % key)
    try:
        for key_code in key_codes:
            obj.key_event[key_code] = False
        for key_code in reversed(key_codes):
            obj.key_event[key_code] = True
    except SimExc_Attribute as ex:
        raise CliError("Failed pressing button: %s" % ex)

new_command("key-press", key_press_cmd,
            [arg(str_t, "key", "+", expander = key_expander)],
            short = "send key press",
            cls = "i8042",
            doc = """
Press a <arg>key</arg> on the keyboard. Several keys can be pressed at the
same time. This translates to a series of key down events followed by the
matching key up events. The names correspond to the keys on a U.S. keyboard
with no keys remapped by software.""")

def key_down_cmd(obj, key_code):
    try:
        obj.key_event[key_code] = False
    except SimExc_Attribute as ex:
        raise CliError("Failed pressing button: %s" % ex)

def key_up_cmd(obj, key_code):
    try:
        obj.key_event[key_code] = True
    except SimExc_Attribute as ex:
        raise CliError("Failed releasing button: %s" % ex)

new_command("key-down", key_down_cmd,
            [arg(int_t, "key-code")],
            short = "send key down event",
            cls = "i8042",
            see_also = ['<i8042>.key-press'],
            doc = """
Send a key press to the keyboard controller. The argument is the internal
Simics <arg>key-code</arg>. The <cmd class="i8042">key-press</cmd> command is
recommend instead.
""")

new_command("key-up", key_up_cmd,
            [arg(int_t, "key-code")],
            cls = "i8042",
            short = "send key up event",
            doc_with = "<i8042>.key-down")

def right_button_cmd(obj, dir):
    if dir == "up":
        obj.button_event[1] = True
    elif dir == "down":
        obj.button_event[1] = False
    else:
        raise CliError("Illegal button direction: %s" % dir)


def left_button_cmd(obj, dir):
    if dir == "up":
        obj.button_event[0] = True
    elif dir == "down":
        obj.button_event[0] = False
    else:
        raise CliError("Illegal button direction: %s" % dir)

def middle_button_cmd(obj, dir):
    if dir == "up":
        obj.button_event[2] = True
    elif dir == "down":
        obj.button_event[2] = False
    else:
        raise CliError("Illegal button direction: %s" % dir)

def i8042_up_down_expander(string):
    return get_completions(string, ("up", "down"))

new_command("right-button", right_button_cmd,
            [arg(str_t, "direction", expander = i8042_up_down_expander)],
            short = "set button state",
            cls = "i8042",
            doc = """
Set the state of the left, right or middle mouse button.
Valid values for the <arg>direction</arg> are "up" and "down".""")

new_command("left-button", left_button_cmd,
            [arg(str_t, "direction", expander = i8042_up_down_expander)],
            short = "set button state",
            cls = "i8042",
            doc_with = "<i8042>.right-button")

new_command("middle-button", middle_button_cmd,
            [arg(str_t, "direction", expander = i8042_up_down_expander)],
            short = "set button state",
            cls = "i8042",
            doc_with = "<i8042>.right-button")

def mouse_cmd(obj, delta, direction):
    if abs(delta) > 1000:
        raise CliError("Mouse movement too large")
    obj.mouse_event[direction] = delta

new_command("mouse-up", lambda x, y: mouse_cmd(x, y, 0),
            [arg(int_t, "millimeters")],
            short = "move mouse",
            cls = "i8042",
            doc = """
Move the mouse up/down/left/right a specified number of
<arg>millimeters</arg>.""")

new_command("mouse-down", lambda x, y: mouse_cmd(x, y, 1),
            [arg(int_t, "millimeters")],
            short = "move mouse",
            cls = "i8042",
            doc_with = "<i8042>.mouse-up")

new_command("mouse-left", lambda x, y: mouse_cmd(x, y, 2),
            [arg(int_t, "millimeters")],
            short = "move mouse",
            cls = "i8042",
            doc_with = "<i8042>.mouse-up")

new_command("mouse-right", lambda x, y: mouse_cmd(x, y, 3),
            [arg(int_t, "millimeters")],
            short = "move mouse",
            cls = "i8042",
            doc_with = "<i8042>.mouse-up")

# TODO: Extend to a generic key-pressing function.
# Not tested yet!
def ctrl_alt_del_cmd(obj):
    print("Sending Ctrl-Alt-Del to %s" % obj.name)
    # False is for pressing a key down, True is for releasing a key
    obj.key_event[SK_CTRL_L] = False
    obj.key_event[SK_ALT_L] = False
    obj.key_event[SK_GR_DELETE] = False
    obj.key_event[SK_CTRL_L] = True
    obj.key_event[SK_ALT_L] = True
    obj.key_event[SK_GR_DELETE] = True
    print("Done.")

new_command("ctrl-alt-del", ctrl_alt_del_cmd,
            [],
            short = "send ctrl-alt-del to console",
            cls = "i8042",
            doc = """
Sends a Ctrl-Alt-Del command to the console. This is useful primarily on
a Windows-hosted Simics to avoid having Ctrl-Alt-Del caught by the host OS.
""")

#
# ------------------------ info -----------------------
#

def mouse_encoding(x):
    if x == 0:
        return "3-button mouse"
    elif x == 1:
        return "3-button wheel mouse"
    elif x == 2:
        return "5-button wheel mouse"
    else:
        return "mouse type %d" % x

def get_info(obj):
    return [ (None,
              [ ("Connected Console", obj.console) ]),
             ("Interrupts",
              [ ("Interrupt Device", obj.attr.irq_dev),
                ("Keyboard Interrupt", obj.kbd_irq_level),
                ("Mouse Interrupt", obj.mouse_irq_level) ]),
             ("Mouse",
              [ ("Type", mouse_encoding(obj.mouse_type)),
                ("Scaling", 2 if obj.mou_two_to_one else 1),
                ("Resolution", (1 << obj.mou_resolution)),
                ("Sample Rate", obj.mou_sample_rate) ]) ]

new_info_command('i8042', get_info)

def get_status(obj):
    if obj.key_buf_num == 0:
        kbuffer = "Empty"
    else:
        key_buffer = obj.key_buffer
        kbuffer = ""
        for i in range(obj.key_buf_num):
            kbuffer += "0x%0x " % key_buffer[(obj.key_first + i)
                                             % len(key_buffer)]

    if obj.mou_buf_num == 0:
        mbuffer = "Empty"
    else:
        mou_buffer = obj.mou_buffer
        mbuffer = ""
        for i in range(obj.mou_buf_num):
            mbuffer += "0x%0x " % mou_buffer[(obj.mou_first + i)
                                             % len(mou_buffer)]
    left = obj.mouse_current_button_state & 0x01
    right = obj.mouse_current_button_state & 0x02
    middle = obj.mouse_current_button_state & 0x04
    btn4 = obj.mouse_current_button_state & 0x08
    btn5 = obj.mouse_current_button_state & 0x10
    return [ ("Controller",
              [ ("Output Buffer",
                 ("0x%x" % obj.obuffer) if obj.ofull else "Empty"),
                ("Mouse Buffer", "Full" if obj.mfull else "Empty"),
                ("Last Access", "Command" if obj.command_last else "Data"),
                ("System Flag", obj.selftest_ok),
                ("Scan Convert", "On" if obj.scan_convert else "Off"),
                ("Keyboard", "Dis" if obj.kbd_disabled else "En"),
                ("Keyboard Irq", "En" if obj.kbd_irq_en else "Dis"),
                ("Mouse", "Dis" if obj.mouse_disabled else "En"),
                ("Mouse Irq", "En" if obj.mouse_irq_en else "Dis") ]),
             ("Keyboard",
              [ ("State", "Enabled" if obj.key_enabled else "Disabled"),
                ("Caps Lock", "On" if obj.key_caps_lock else "Off"),
                ("Num Lock", "On" if obj.key_num_lock else "Off"),
                ("Scroll Lock", "On" if obj.key_scroll_lock else "Off"),
                ("Buffer", kbuffer) ]),
             ("Mouse",
              [ ("Mode", mouse_encoding(obj.mouse_mode)),
                ("State", "Enabled" if obj.mou_enabled else "Disabled"),
                ("Left Button", "Down" if left else "Up"),
                ("Middle Button", "Down" if middle else "Up"),
                ("Right Button", "Down" if right else "Up"),
                ("Button 4", "Down" if btn4 else "Up"),
                ("Button 5", "Down" if btn5 else "Up"),
                ("Buffer", mbuffer) ]) ]

new_status_command('i8042', get_status)
