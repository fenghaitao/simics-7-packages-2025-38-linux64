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


import wx
import simics
import sys
from .win_utils import simics_lock

# Under MSW, the raw key code is the value of @c wParam parameter of the
# corresponding message. (wParam depends on the Windows language setting)
# https://msdn.microsoft.com/en-us/library/windows/desktop/ms646280.aspx
# Under GTK, the raw key code is the @c keyval field of the corresponding
# GDK event, i.e. X11 keysym.
# Under OS X, the raw key code is the @c keyCode field of the
# corresponding NSEvent.

# Under MSW, the raw flags are just the value of @c lParam parameter of
# the corresponding message. Bits 16-23 contain the scan code. Bit 24 also
# indicate if it is a right Ctrl/Alt.
# Under GTK, the raw flags contain the @c hardware_keycode field of the
# corresponding GDK event, i.e. X11 keycode.
# Under OS X, the raw flags contain the modifiers state.

# From wxKeyEvent documentation:
# For the other alphanumeric keys (e.g. 7 or +), the untranslated key code
# corresponds to the character produced by the key when it is pressed without
# Shift. E.g. in standard US keyboard layout the untranslated key code
# for the key =/+ in the upper right corner of the keyboard is 61
# which is the ASCII value of =.


# Convert wxPython keycodes to text_console_key_t
SPECIAL_KEYS = {
    wx.WXK_BACK: simics.Text_Console_Key_Backspace,
    wx.WXK_TAB: simics.Text_Console_Key_Tab,
    wx.WXK_RETURN: simics.Text_Console_Key_Return,
    wx.WXK_ESCAPE: simics.Text_Console_Key_Escape,

    wx.WXK_LEFT: simics.Text_Console_Key_Left,
    wx.WXK_UP: simics.Text_Console_Key_Up,
    wx.WXK_RIGHT: simics.Text_Console_Key_Right,
    wx.WXK_DOWN: simics.Text_Console_Key_Down,

    wx.WXK_NUMPAD_LEFT: simics.Text_Console_Key_Left,
    wx.WXK_NUMPAD_RIGHT: simics.Text_Console_Key_Right,
    wx.WXK_NUMPAD_UP: simics.Text_Console_Key_Up,
    wx.WXK_NUMPAD_DOWN: simics.Text_Console_Key_Down,

    wx.WXK_INSERT: simics.Text_Console_Key_Ins,
    wx.WXK_DELETE: simics.Text_Console_Key_Del,
    wx.WXK_HOME: simics.Text_Console_Key_Home,
    wx.WXK_END: simics.Text_Console_Key_End,
    wx.WXK_PAGEUP: simics.Text_Console_Key_Pgup,
    wx.WXK_PAGEDOWN: simics.Text_Console_Key_Pgdn,

    wx.WXK_NUMPAD_INSERT: simics.Text_Console_Key_Ins,
    wx.WXK_NUMPAD_DELETE: simics.Text_Console_Key_Del,
    wx.WXK_NUMPAD_HOME: simics.Text_Console_Key_Home,
    wx.WXK_NUMPAD_END: simics.Text_Console_Key_End,
    wx.WXK_NUMPAD_PAGEUP: simics.Text_Console_Key_Pgup,
    wx.WXK_NUMPAD_PAGEDOWN: simics.Text_Console_Key_Pgdn,

    wx.WXK_NUMPAD_ENTER: simics.Text_Console_Key_KP_Enter,
    wx.WXK_NUMPAD_ADD: simics.Text_Console_Key_KP_Plus,
    wx.WXK_NUMPAD_SUBTRACT: simics.Text_Console_Key_KP_Minus,
    wx.WXK_NUMPAD_MULTIPLY: simics.Text_Console_Key_KP_Mul,
    wx.WXK_NUMPAD_DIVIDE: simics.Text_Console_Key_KP_Div,
    wx.WXK_NUMPAD_DECIMAL: simics.Text_Console_Key_KP_Dot,

    wx.WXK_NUMPAD0: simics.Text_Console_Key_KP_0,
    wx.WXK_NUMPAD1: simics.Text_Console_Key_KP_1,
    wx.WXK_NUMPAD2: simics.Text_Console_Key_KP_2,
    wx.WXK_NUMPAD3: simics.Text_Console_Key_KP_3,
    wx.WXK_NUMPAD4: simics.Text_Console_Key_KP_4,
    wx.WXK_NUMPAD5: simics.Text_Console_Key_KP_5,
    wx.WXK_NUMPAD6: simics.Text_Console_Key_KP_6,
    wx.WXK_NUMPAD7: simics.Text_Console_Key_KP_7,
    wx.WXK_NUMPAD8: simics.Text_Console_Key_KP_8,
    wx.WXK_NUMPAD9: simics.Text_Console_Key_KP_9,

    wx.WXK_F1: simics.Text_Console_Key_F1,
    wx.WXK_F2: simics.Text_Console_Key_F2,
    wx.WXK_F3: simics.Text_Console_Key_F3,
    wx.WXK_F4: simics.Text_Console_Key_F4,
    wx.WXK_F5: simics.Text_Console_Key_F5,
    wx.WXK_F6: simics.Text_Console_Key_F6,
    wx.WXK_F7: simics.Text_Console_Key_F7,
    wx.WXK_F8: simics.Text_Console_Key_F8,
    wx.WXK_F9: simics.Text_Console_Key_F9,
    wx.WXK_F10: simics.Text_Console_Key_F10,
    wx.WXK_F11: simics.Text_Console_Key_F11,
    wx.WXK_F12: simics.Text_Console_Key_F12,
}

# keycode should be wx.KeyEvent.GetKeyCode() from a KeyDown event.
# Determine if key should be passed to text console backend as a special key
# rather than as a character.
def special_key(keycode):
    if keycode in SPECIAL_KEYS:
        return SPECIAL_KEYS[keycode]
    else:
        return None


# Map wx keycodes for certain function keys to the corresponding
# physical keys, for use in the symbolic keyboard mode.
symbolic_function_keys = {
    wx.WXK_BACK:     simics.SK_BACKSPACE,
    wx.WXK_TAB:      simics.SK_TAB,
    wx.WXK_RETURN:   simics.SK_ENTER,
    wx.WXK_ESCAPE:   simics.SK_ESC,

    wx.WXK_LEFT:     simics.SK_GR_LEFT,
    wx.WXK_RIGHT:    simics.SK_GR_RIGHT,
    wx.WXK_UP:       simics.SK_GR_UP,
    wx.WXK_DOWN:     simics.SK_GR_DOWN,

    wx.WXK_INSERT:   simics.SK_GR_INSERT,
    wx.WXK_DELETE:   simics.SK_GR_DELETE,
    wx.WXK_HOME:     simics.SK_GR_HOME,
    wx.WXK_END:      simics.SK_GR_END,
    wx.WXK_PAGEUP:   simics.SK_GR_PG_UP,
    wx.WXK_PAGEDOWN: simics.SK_GR_PG_DOWN,

    # Num-lock dependent keys: these are mapped to non-numpad keys so
    # that they work regardless of num-lock state in the model.
    wx.WXK_NUMPAD_LEFT:     simics.SK_GR_LEFT,
    wx.WXK_NUMPAD_RIGHT:    simics.SK_GR_RIGHT,
    wx.WXK_NUMPAD_UP:       simics.SK_GR_UP,
    wx.WXK_NUMPAD_DOWN:     simics.SK_GR_DOWN,
    wx.WXK_NUMPAD_INSERT:   simics.SK_GR_INSERT,
    wx.WXK_NUMPAD_DELETE:   simics.SK_GR_DELETE,
    wx.WXK_NUMPAD_HOME:     simics.SK_GR_HOME,
    wx.WXK_NUMPAD_END:      simics.SK_GR_END,
    wx.WXK_NUMPAD_PAGEUP:   simics.SK_GR_PG_UP,
    wx.WXK_NUMPAD_PAGEDOWN: simics.SK_GR_PG_DOWN,
    wx.WXK_NUMPAD_DECIMAL:  simics.SK_PERIOD,
    wx.WXK_NUMPAD0:         simics.SK_0,
    wx.WXK_NUMPAD1:         simics.SK_1,
    wx.WXK_NUMPAD2:         simics.SK_2,
    wx.WXK_NUMPAD3:         simics.SK_3,
    wx.WXK_NUMPAD4:         simics.SK_4,
    wx.WXK_NUMPAD5:         simics.SK_5,
    wx.WXK_NUMPAD6:         simics.SK_6,
    wx.WXK_NUMPAD7:         simics.SK_7,
    wx.WXK_NUMPAD8:         simics.SK_8,
    wx.WXK_NUMPAD9:         simics.SK_9,

    wx.WXK_NUMPAD_ENTER:    simics.SK_GR_ENTER,
    wx.WXK_NUMPAD_ADD:      simics.SK_GR_PLUS,
    wx.WXK_NUMPAD_SUBTRACT: simics.SK_GR_MINUS,
    wx.WXK_NUMPAD_MULTIPLY: simics.SK_GR_MULTIPLY,
    wx.WXK_NUMPAD_DIVIDE:   simics.SK_GR_DIVIDE,

    wx.WXK_F1:  simics.SK_F1,
    wx.WXK_F2:  simics.SK_F2,
    wx.WXK_F3:  simics.SK_F3,
    wx.WXK_F4:  simics.SK_F4,
    wx.WXK_F5:  simics.SK_F5,
    wx.WXK_F6:  simics.SK_F6,
    wx.WXK_F7:  simics.SK_F7,
    wx.WXK_F8:  simics.SK_F8,
    wx.WXK_F9:  simics.SK_F9,
    wx.WXK_F10: simics.SK_F10,
    wx.WXK_F11: simics.SK_F11,
    wx.WXK_F12: simics.SK_F12,

    wx.WXK_PAUSE: simics.SK_PAUSE,
    wx.WXK_PRINT: simics.SK_PRNT_SCRN,

    wx.WXK_MENU: simics.SK_LIST_BIT,
    wx.WXK_WINDOWS_MENU: simics.SK_LIST_BIT,
    wx.WXK_WINDOWS_LEFT: simics.SK_LEFT_WIN,
    wx.WXK_WINDOWS_RIGHT: simics.SK_RIGHT_WIN,
}

# Return (sim_key, modifiers) for a wx keycode of a function key,
# or None if no symbolic mapping could be found.
def symbolic_function_key(keycode):
    if keycode in symbolic_function_keys:
        return (symbolic_function_keys[keycode], 0)
    if keycode == wx.WXK_CANCEL:   # Ctrl-Break
        return (simics.SK_PAUSE, wx.MOD_CONTROL)
    return None

# Map wx keycodes for various keys to the corresponding
# physical keys and modifiers, for use in the symbolic keyboard mode.
# This mapping assumes the US (ANSI) keyboard layout on the target.
symbolic_keys = {
    ord("'"): (simics.SK_APOSTROPHE, 0),
    ord('"'): (simics.SK_APOSTROPHE, wx.MOD_SHIFT),
    ord(','): (simics.SK_COMMA, 0),
    ord('<'): (simics.SK_COMMA, wx.MOD_SHIFT),
    ord('.'): (simics.SK_PERIOD, 0),
    ord('>'): (simics.SK_PERIOD, wx.MOD_SHIFT),
    ord(';'): (simics.SK_SEMICOLON, 0),
    ord(':'): (simics.SK_SEMICOLON, wx.MOD_SHIFT),
    ord('='): (simics.SK_EQUAL, 0),
    ord('+'): (simics.SK_EQUAL, wx.MOD_SHIFT),
    ord('/'): (simics.SK_SLASH, 0),
    ord('?'): (simics.SK_SLASH, wx.MOD_SHIFT),
    ord('\\'): (simics.SK_BACKSLASH, 0),
    ord('|'): (simics.SK_BACKSLASH, wx.MOD_SHIFT),
    ord(' '): (simics.SK_SPACE, 0),
    ord('['): (simics.SK_LEFT_BRACKET, 0),
    ord('{'): (simics.SK_LEFT_BRACKET, wx.MOD_SHIFT),
    ord(']'): (simics.SK_RIGHT_BRACKET, 0),
    ord('}'): (simics.SK_RIGHT_BRACKET, wx.MOD_SHIFT),
    ord('-'): (simics.SK_MINUS, 0),
    ord('_'): (simics.SK_MINUS, wx.MOD_SHIFT),
    ord('`'): (simics.SK_GRAVE, 0),
    ord('~'): (simics.SK_GRAVE, wx.MOD_SHIFT),

    ord('!'): (simics.SK_1, wx.MOD_SHIFT),
    ord('@'): (simics.SK_2, wx.MOD_SHIFT),
    ord('#'): (simics.SK_3, wx.MOD_SHIFT),
    ord('$'): (simics.SK_4, wx.MOD_SHIFT),
    ord('%'): (simics.SK_5, wx.MOD_SHIFT),
    ord('^'): (simics.SK_6, wx.MOD_SHIFT),
    ord('&'): (simics.SK_7, wx.MOD_SHIFT),
    ord('*'): (simics.SK_8, wx.MOD_SHIFT),
    ord('('): (simics.SK_9, wx.MOD_SHIFT),
    ord(')'): (simics.SK_0, wx.MOD_SHIFT),
}

# Return (sim_key, modifiers) for a wx keycode of a non-function key,
# or None if no symbolic mapping could be found.
def symbolic_char_key(keycode):
    if keycode in symbolic_keys:
        return symbolic_keys[keycode]
    if 0x30 <= keycode <= 0x39:         # 0-9
        return (simics.SK_0 + keycode - 0x30, 0)
    if 0x41 <= keycode <= 0x5a:         # A-Z
        return (simics.SK_A + keycode - 0x41, wx.MOD_SHIFT)
    if 0x61 <= keycode <= 0x7a:         # a-z
        return (simics.SK_A + keycode - 0x61, 0)
    if 0x01 <= keycode <= 0x5a:         # Ctrl-A - Ctrl-Z
        return (simics.SK_A + keycode - 0x01, wx.MOD_CONTROL)

    return None

# FIXME: debug code, remove
sk_keynames = {getattr(simics, name): name
               for name in dir(simics) if name.startswith("SK_")}

on_windows = (wx.Platform == "__WXMSW__")

# Map Windows scan codes (including the "extended key" flag in bit 8)
# to Simics key codes.
win_scan_codes_to_key = {
    1:   simics.SK_ESC,

    59:  simics.SK_F1,
    60:  simics.SK_F2,
    61:  simics.SK_F3,
    62:  simics.SK_F4,
    63:  simics.SK_F5,
    64:  simics.SK_F6,
    65:  simics.SK_F7,
    66:  simics.SK_F8,
    67:  simics.SK_F9,
    68:  simics.SK_F10,
    87:  simics.SK_F11,
    88:  simics.SK_F12,

    # Main alphanumeric cluster.
    41:  simics.SK_GRAVE,
    2:   simics.SK_1,
    3:   simics.SK_2,
    4:   simics.SK_3,
    5:   simics.SK_4,
    6:   simics.SK_5,
    7:   simics.SK_6,
    8:   simics.SK_7,
    9:   simics.SK_8,
    10:  simics.SK_9,
    11:  simics.SK_0,
    12:  simics.SK_MINUS,
    13:  simics.SK_EQUAL,
    14:  simics.SK_BACKSPACE,

    15:  simics.SK_TAB,
    16:  simics.SK_Q,
    17:  simics.SK_W,
    18:  simics.SK_E,
    19:  simics.SK_R,
    20:  simics.SK_T,
    21:  simics.SK_Y,
    22:  simics.SK_U,
    23:  simics.SK_I,
    24:  simics.SK_O,
    25:  simics.SK_P,
    26:  simics.SK_LEFT_BRACKET,
    27:  simics.SK_RIGHT_BRACKET,
    43:  simics.SK_BACKSLASH,

    58:  simics.SK_CAPS_LOCK,
    30:  simics.SK_A,
    31:  simics.SK_S,
    32:  simics.SK_D,
    33:  simics.SK_F,
    34:  simics.SK_G,
    35:  simics.SK_H,
    36:  simics.SK_J,
    37:  simics.SK_K,
    38:  simics.SK_L,
    39:  simics.SK_SEMICOLON,
    40:  simics.SK_APOSTROPHE,
    28:  simics.SK_ENTER,

    42:  simics.SK_SHIFT_L,
    86:  simics.SK_KEYB,
    44:  simics.SK_Z,
    45:  simics.SK_X,
    46:  simics.SK_C,
    47:  simics.SK_V,
    48:  simics.SK_B,
    49:  simics.SK_N,
    50:  simics.SK_M,
    51:  simics.SK_COMMA,
    52:  simics.SK_PERIOD,
    53:  simics.SK_SLASH,
    54:  simics.SK_SHIFT_R,

    29:  simics.SK_CTRL_L,
    91+256: simics.SK_LEFT_WIN,
    56:  simics.SK_ALT_L,
    57:  simics.SK_SPACE,
    56+256: simics.SK_ALT_R,
    92+256: simics.SK_RIGHT_WIN,
    93+256: simics.SK_LIST_BIT,         # "Menu"
    29+256: simics.SK_CTRL_R,

    # Top middle cluster.
    55+256: simics.SK_PRNT_SCRN,
    84:  simics.SK_SYSREQ,
    70:  simics.SK_SCROLL_LOCK,
    69:  simics.SK_PAUSE,
    70+256: simics.SK_BREAK,

    # Edit/navigation cluster.
    82+256: simics.SK_GR_INSERT,
    71+256: simics.SK_GR_HOME,
    73+256: simics.SK_GR_PG_UP,
    83+256: simics.SK_GR_DELETE,
    79+256: simics.SK_GR_END,
    81+256: simics.SK_GR_PG_DOWN,

    # Arrow cluster.
    72+256: simics.SK_GR_UP,
    75+256: simics.SK_GR_LEFT,
    80+256: simics.SK_GR_DOWN,
    77+256: simics.SK_GR_RIGHT,

    # Numerical keypad.
    69+256: simics.SK_NUM_LOCK,
    53+256: simics.SK_GR_DIVIDE,
    55:  simics.SK_GR_MULTIPLY,
    74:  simics.SK_GR_MINUS,
    71:  simics.SK_KP_HOME,
    72:  simics.SK_KP_UP,
    73:  simics.SK_KP_PG_UP,
    75:  simics.SK_KP_LEFT,
    76:  simics.SK_KP_CENTER,
    77:  simics.SK_KP_RIGHT,
    78:  simics.SK_GR_PLUS,
    79:  simics.SK_KP_END,
    80:  simics.SK_KP_DOWN,
    81:  simics.SK_KP_PG_DOWN,
    82:  simics.SK_KP_INSERT,
    83:  simics.SK_KP_DELETE,
    28+256:  simics.SK_GR_ENTER,
}

# Map GTK (X11 actually) keycodes to Simics key codes.
gtk_keycodes_to_key = {
    9:   simics.SK_ESC,

    67:  simics.SK_F1,
    68:  simics.SK_F2,
    69:  simics.SK_F3,
    70:  simics.SK_F4,
    71:  simics.SK_F5,
    72:  simics.SK_F6,
    73:  simics.SK_F7,
    74:  simics.SK_F8,
    75:  simics.SK_F9,
    76:  simics.SK_F10,
    95:  simics.SK_F11,
    96:  simics.SK_F12,

    # Main alphanumeric cluster.
    49:  simics.SK_GRAVE,
    10:  simics.SK_1,
    11:  simics.SK_2,
    12:  simics.SK_3,
    13:  simics.SK_4,
    14:  simics.SK_5,
    15:  simics.SK_6,
    16:  simics.SK_7,
    17:  simics.SK_8,
    18:  simics.SK_9,
    19:  simics.SK_0,
    20:  simics.SK_MINUS,
    21:  simics.SK_EQUAL,
    22:  simics.SK_BACKSPACE,

    23:  simics.SK_TAB,
    24:  simics.SK_Q,
    25:  simics.SK_W,
    26:  simics.SK_E,
    27:  simics.SK_R,
    28:  simics.SK_T,
    29:  simics.SK_Y,
    30:  simics.SK_U,
    31:  simics.SK_I,
    32:  simics.SK_O,
    33:  simics.SK_P,
    34:  simics.SK_LEFT_BRACKET,
    35:  simics.SK_RIGHT_BRACKET,
    51:  simics.SK_BACKSLASH,

    66:  simics.SK_CAPS_LOCK,
    38:  simics.SK_A,
    39:  simics.SK_S,
    40:  simics.SK_D,
    41:  simics.SK_F,
    42:  simics.SK_G,
    43:  simics.SK_H,
    44:  simics.SK_J,
    45:  simics.SK_K,
    46:  simics.SK_L,
    47:  simics.SK_SEMICOLON,
    48:  simics.SK_APOSTROPHE,
    36:  simics.SK_ENTER,

    50:  simics.SK_SHIFT_L,
    94:  simics.SK_KEYB,
    52:  simics.SK_Z,
    53:  simics.SK_X,
    54:  simics.SK_C,
    55:  simics.SK_V,
    56:  simics.SK_B,
    57:  simics.SK_N,
    58:  simics.SK_M,
    59:  simics.SK_COMMA,
    60:  simics.SK_PERIOD,
    61:  simics.SK_SLASH,
    62:  simics.SK_SHIFT_R,

    37:  simics.SK_CTRL_L,
    133: simics.SK_LEFT_WIN,
    64:  simics.SK_ALT_L,
    65:  simics.SK_SPACE,
    108: simics.SK_ALT_R,
    134: simics.SK_RIGHT_WIN,
    145: simics.SK_LIST_BIT,
    105: simics.SK_CTRL_R,

    # Top middle cluster.
    107: simics.SK_PRNT_SCRN,           # FIXME: special sysrq code?
    78:  simics.SK_SCROLL_LOCK,
    127: simics.SK_PAUSE,               # FIXME: special break code?

    # Edit/navigation cluster.
    118: simics.SK_GR_INSERT,
    110: simics.SK_GR_HOME,
    112: simics.SK_GR_PG_UP,
    119: simics.SK_GR_DELETE,
    115: simics.SK_GR_END,
    117: simics.SK_GR_PG_DOWN,

    # Arrow cluster.
    111: simics.SK_GR_UP,
    113: simics.SK_GR_LEFT,
    116: simics.SK_GR_DOWN,
    114: simics.SK_GR_RIGHT,

    # Numerical keypad.
    77:  simics.SK_NUM_LOCK,
    106: simics.SK_GR_DIVIDE,
    63:  simics.SK_GR_MULTIPLY,
    82:  simics.SK_GR_MINUS,
    79:  simics.SK_KP_HOME,
    80:  simics.SK_KP_UP,
    81:  simics.SK_KP_PG_UP,
    83:  simics.SK_KP_LEFT,
    84:  simics.SK_KP_CENTER,
    85:  simics.SK_KP_RIGHT,
    86:  simics.SK_GR_PLUS,
    87:  simics.SK_KP_END,
    88:  simics.SK_KP_DOWN,
    89:  simics.SK_KP_PG_DOWN,
    90:  simics.SK_KP_INSERT,
    91:  simics.SK_KP_DELETE,
    104: simics.SK_GR_ENTER,
}

# Default mapping used in physical keyboard setup dialog
def default_phys_key_mapping():
    if on_windows:
        return win_scan_codes_to_key.copy()
    else:
        return gtk_keycodes_to_key.copy()

# Convert wx "raw code" to the key used in the dicts returned by
# default_phys_key_mapping
def physical_key_code(rawcode):
    if on_windows:
        # Index our look-up table by the scan code augmented with the
        # extended key flag in bit 8.
        return (rawcode >> 16) & 0x1ff
    else:
        return rawcode

# Convert wx modifiers to Simics keycodes.
def convert_modifiers(modifiers):
    codes = []
    if modifiers & (wx.MOD_ALT | wx.MOD_META):
        codes.append(simics.SK_ALT_L)
    if modifiers & wx.MOD_CONTROL:
        codes.append(simics.SK_CTRL_L)
    if modifiers & wx.MOD_SHIFT:
        codes.append(simics.SK_SHIFT_L)
    return codes

modifiers = {
    simics.SK_CTRL_L: wx.WXK_CONTROL,
    simics.SK_ALT_L: wx.WXK_ALT,
    simics.SK_SHIFT_L: wx.WXK_SHIFT,
}

# Convert Simics grab modifier to wx keycode
def convert_grab_modifier(modifier):
    assert modifier in modifiers
    return modifiers[modifier]

mouse_buttons = {
    simics.Gfx_Console_Mouse_Button_Left: wx.MOUSE_BTN_LEFT,
    simics.Gfx_Console_Mouse_Button_Middle: wx.MOUSE_BTN_MIDDLE,
    simics.Gfx_Console_Mouse_Button_Right: wx.MOUSE_BTN_RIGHT,
}

# Convert to Simics grab button to wx code
def convert_grab_button(button):
    assert button in mouse_buttons
    return mouse_buttons[button]

# Helper class used by physical keyboard mapping dialog.
class Key:
    def __init__(self, label, desc, x, y, width, height, sim_key):
        # Key label displayed on the on-screen keyboard.
        self.label = label
        # Longer key description displayed in a status bar or similar.
        self.desc = desc
        # Position of key on the on-screen keyboard, in half-units.
        self.x = x
        self.y = y
        # Size of key on the on-screen keyboard, in half-units.
        self.width = width
        self.height = height
        # Corresponding Simics key code.
        self.sim_key = sim_key

# On-screen keyboard data structure
phys_keys = [
    Key("Esc", "Escape", 0, 0, 2, 2, simics.SK_ESC),

    Key("F1",  "F1",     4, 0, 2, 2, simics.SK_F1),
    Key("F2",  "F2",     6, 0, 2, 2, simics.SK_F2),
    Key("F3",  "F3",     8, 0, 2, 2, simics.SK_F3),
    Key("F4",  "F4",    10, 0, 2, 2, simics.SK_F4),

    Key("F5",  "F5",    13, 0, 2, 2, simics.SK_F5),
    Key("F6",  "F6",    15, 0, 2, 2, simics.SK_F6),
    Key("F7",  "F7",    17, 0, 2, 2, simics.SK_F7),
    Key("F8",  "F8",    19, 0, 2, 2, simics.SK_F8),

    Key("F9",  "F9",    22, 0, 2, 2, simics.SK_F9),
    Key("F10", "F10",   24, 0, 2, 2, simics.SK_F10),
    Key("F11", "F11",   26, 0, 2, 2, simics.SK_F11),
    Key("F12", "F12",   28, 0, 2, 2, simics.SK_F12),

    # Main alphanumeric cluster.
    Key("`",   "` ~",    0, 3, 2, 2, simics.SK_GRAVE),
    Key("1",   "1 !",    2, 3, 2, 2, simics.SK_1),
    Key("2",   "2 @",    4, 3, 2, 2, simics.SK_2),
    Key("3",   "3 #",    6, 3, 2, 2, simics.SK_3),
    Key("4",   "4 $",    8, 3, 2, 2, simics.SK_4),
    Key("5",   "5 %",   10, 3, 2, 2, simics.SK_5),
    Key("6",   "6 ^",   12, 3, 2, 2, simics.SK_6),
    Key("7",   "7 &&",   14, 3, 2, 2, simics.SK_7),
    Key("8",   "8 *",   16, 3, 2, 2, simics.SK_8),
    Key("9",   "9 (",   18, 3, 2, 2, simics.SK_9),
    Key("0",   "0 )",   20, 3, 2, 2, simics.SK_0),
    Key("-",   "- _",   22, 3, 2, 2, simics.SK_MINUS),
    Key("=",   "= +",   24, 3, 2, 2, simics.SK_EQUAL),
    Key("Backsp", "Backspace", 26, 3, 4, 2, simics.SK_BACKSPACE),

    Key("Tab", "Tab",    0, 5, 3, 2, simics.SK_TAB),
    Key("Q",   "Q",      3, 5, 2, 2, simics.SK_Q),
    Key("W",   "W",      5, 5, 2, 2, simics.SK_W),
    Key("E",   "E",      7, 5, 2, 2, simics.SK_E),
    Key("R",   "R",      9, 5, 2, 2, simics.SK_R),
    Key("T",   "T",     11, 5, 2, 2, simics.SK_T),
    Key("Y",   "Y",     13, 5, 2, 2, simics.SK_Y),
    Key("U",   "U",     15, 5, 2, 2, simics.SK_U),
    Key("I",   "I",     17, 5, 2, 2, simics.SK_I),
    Key("O",   "O",     19, 5, 2, 2, simics.SK_O),
    Key("P",   "P",     21, 5, 2, 2, simics.SK_P),
    Key("[",   "[{",    23, 5, 2, 2, simics.SK_LEFT_BRACKET),
    Key("]",   "]}",    25, 5, 2, 2, simics.SK_RIGHT_BRACKET),
    Key("\\",  "\\ |",  27, 5, 3, 2, simics.SK_BACKSLASH),

    Key("Caps", "Caps Lock", 0, 7, 4, 2, simics.SK_CAPS_LOCK),
    Key("A",   "A",      4, 7, 2, 2, simics.SK_A),
    Key("S",   "S",      6, 7, 2, 2, simics.SK_S),
    Key("D",   "D",      8, 7, 2, 2, simics.SK_D),
    Key("F",   "F",     10, 7, 2, 2, simics.SK_F),
    Key("G",   "G",     12, 7, 2, 2, simics.SK_G),
    Key("H",   "H",     14, 7, 2, 2, simics.SK_H),
    Key("J",   "J",     16, 7, 2, 2, simics.SK_J),
    Key("K",   "K",     18, 7, 2, 2, simics.SK_K),
    Key("L",   "L",     20, 7, 2, 2, simics.SK_L),
    Key(";",   "; :",   22, 7, 2, 2, simics.SK_SEMICOLON),
    Key("'",   "' \"",  24, 7, 2, 2, simics.SK_APOSTROPHE),
    Key("Ret", "Return", 26, 7, 4, 2, simics.SK_ENTER),

    Key("Shift", "Left Shift", 0, 9, 3, 2, simics.SK_SHIFT_L),
    Key("<>", "Key 102", 3, 9, 2, 2, simics.SK_KEYB),
    Key("Z",   "Z",      5, 9, 2, 2, simics.SK_Z),
    Key("X",   "X",      7, 9, 2, 2, simics.SK_X),
    Key("C",   "C",      9, 9, 2, 2, simics.SK_C),
    Key("V",   "V",     11, 9, 2, 2, simics.SK_V),
    Key("B",   "B",     13, 9, 2, 2, simics.SK_B),
    Key("N",   "N",     15, 9, 2, 2, simics.SK_N),
    Key("M",   "M",     17, 9, 2, 2, simics.SK_M),
    Key(",",   ", <",   19, 9, 2, 2, simics.SK_COMMA),
    Key(".",   ". >",   21, 9, 2, 2, simics.SK_PERIOD),
    Key("/",   "/ ?",   23, 9, 2, 2, simics.SK_SLASH),
    Key("Shift", "Right Shift", 25, 9, 5, 2, simics.SK_SHIFT_R),

    Key("Ctrl", "Left Control", 0, 11, 3, 2, simics.SK_CTRL_L),
    Key("Win",  "Left Windows", 3, 11, 3, 2, simics.SK_LEFT_WIN),
    Key("Alt",  "Left Alt",     6, 11, 3, 2, simics.SK_ALT_L),
    Key("Space", "Space",       9, 11, 9, 2, simics.SK_SPACE),
    Key("Alt",  "Right Alt",   18, 11, 3, 2, simics.SK_ALT_R),
    Key("Win",  "Right Windows", 21, 11, 3, 2, simics.SK_RIGHT_WIN),
    Key("Menu", "Menu",        24, 11, 3, 2, simics.SK_LIST_BIT),
    Key("Ctrl", "Right Control",27, 11, 3, 2, simics.SK_CTRL_R),

    # Top middle cluster.
    Key("PrSc", "Print Screen / SysReq", 31, 0, 2, 2, simics.SK_PRNT_SCRN),
    Key("Scr",  "Scroll Lock", 33, 0, 2, 2, simics.SK_SCROLL_LOCK),
    Key("Pau",  "Pause / Break", 35, 0, 2, 2, simics.SK_PAUSE),

    # Edit/navigation cluster.
    Key("Ins",  "Insert",      31, 3, 2, 2, simics.SK_GR_INSERT),
    Key("Hom",  "Home",        33, 3, 2, 2, simics.SK_GR_HOME),
    Key("PgU", "Page Up",     35, 3, 2, 2, simics.SK_GR_PG_UP),
    Key("Del",  "Delete",      31, 5, 2, 2, simics.SK_GR_DELETE),
    Key("End",  "End",         33, 5, 2, 2, simics.SK_GR_END),
    Key("PgD", "Page Down",   35, 5, 2, 2, simics.SK_GR_PG_DOWN),

    # Arrow cluster.
    Key("↑",    "Up",          33, 9, 2, 2, simics.SK_GR_UP),
    Key("←",    "Left",        31, 11, 2, 2, simics.SK_GR_LEFT),
    Key("↓",    "Down",        33, 11, 2, 2, simics.SK_GR_DOWN),
    Key("→",    "Right",       35, 11, 2, 2, simics.SK_GR_RIGHT),

    # Numerical keypad.
    Key("Num",  "Num Lock",    38, 3, 2, 2, simics.SK_NUM_LOCK),
    Key("/",    "/",           40, 3, 2, 2, simics.SK_GR_DIVIDE),
    Key("*",    "*",           42, 3, 2, 2, simics.SK_GR_MULTIPLY),
    Key("–",    "–",           44, 3, 2, 2, simics.SK_GR_MINUS),
    Key("7",    "7 / Home",    38, 5, 2, 2, simics.SK_KP_HOME),
    Key("8",    "8 / Up",      40, 5, 2, 2, simics.SK_KP_UP),
    Key("9",    "9 / PgUp",    42, 5, 2, 2, simics.SK_KP_PG_UP),
    Key("4",    "4 / Left",    38, 7, 2, 2, simics.SK_KP_LEFT),
    Key("5",    "5",           40, 7, 2, 2, simics.SK_KP_CENTER),
    Key("6",    "6 / Right",   42, 7, 2, 2, simics.SK_KP_RIGHT),
    Key("+",    "+",           44, 5, 2, 4, simics.SK_GR_PLUS),
    Key("1",    "1 / End",     38, 9, 2, 2, simics.SK_KP_END),
    Key("2",    "2 / Down",    40, 9, 2, 2, simics.SK_KP_DOWN),
    Key("3",    "3 / PgDn",    42, 9, 2, 2, simics.SK_KP_PG_DOWN),
    Key("0",    "0 / Insert",  38, 11, 4, 2, simics.SK_KP_INSERT),
    Key(",",    ", / Delete",  42, 11, 2, 2, simics.SK_KP_DELETE),
    Key("Ent",  "Enter",       44, 9, 2, 4, simics.SK_GR_ENTER),
]

# On-screen keyboard panel, taking care of the drawing of all keys.
# Since keys have varying lengths and positions, e.g. Q starting half-way
# under 1, we use a grid system with a unit box of 8x8 pixels.
# All keys have sizes and positions in half-units.
class Screen_keyboard(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY)
        # Outer dialog window
        self.parent = parent
        # Each key has corresponding instances of Key and wx.Panel
        self.key_by_id = {}
        # Lookup from a Simics keycode to corresponding wx.Panel
        self.sim_key_to_box = {}

        # Pixel size for one half-unit
        half_unit_height = 16
        half_unit_width = 16
        for k in phys_keys:
            box_id = wx.Window.NewControlId()

            # Create panel for key
            box = wx.Panel(self, box_id, style = wx.SIMPLE_BORDER,
                           pos = wx.Point(half_unit_width * k.x,
                                          half_unit_height * k.y),
                           size = wx.Size(half_unit_width * k.width,
                                          half_unit_height * k.height))
            box.SetBackgroundColour(wx.WHITE)
            box.Bind(wx.EVT_LEFT_DOWN, self.key_click)
            box.Bind(wx.EVT_LEFT_DCLICK, self.key_dclick)
            box.Bind(wx.EVT_ENTER_WINDOW, self.key_enter)
            box.Bind(wx.EVT_LEAVE_WINDOW, self.key_leave)

            # Create text label inside panel
            txt = wx.StaticText(box, id = box_id, label = k.label)
            # For some reason, key-click events won't propagate from the
            # label to its surrounding box, so we have to bind both.
            txt.Bind(wx.EVT_LEFT_DOWN, self.key_click)
            txt.Bind(wx.EVT_LEFT_DCLICK, self.key_dclick)
            self.key_by_id[box_id] = k
            self.sim_key_to_box[k.sim_key] = box

        # Set keyboard panel size
        max_width = (max(k.x + k.width
                         for k in phys_keys) + 2) * half_unit_width
        max_height = (max(k.y + k.height
                          for k in phys_keys) + 2) * half_unit_height
        self.SetSize(wx.Size(max_width, max_height))

    # Reset display of box corresponding to sim_key to unmapped state.
    def reset_key(self, sim_key):
        box = self.sim_key_to_box[sim_key]
        box.SetBackgroundColour(wx.WHITE)
        box.Refresh()

    # Reset all boxes to unmapped state.
    def reset_all(self):
        for sim_key in self.sim_key_to_box:
            self.reset_key(sim_key)

    # Change display of box corresponding to sim_key to mapped state.
    def map_key(self, sim_key):
        box = self.sim_key_to_box[sim_key]
        box.SetBackgroundColour(wx.GREEN)
        box.Refresh()

    # Change display of box corresponding to sim_key to waiting for map state.
    def waiting_key(self, sim_key):
        box = self.sim_key_to_box[sim_key]
        box.SetBackgroundColour(wx.YELLOW)
        box.Refresh()

    # Does sim_key correspond to a key on the keyboard?
    def is_valid_key(self, sim_key):
        return sim_key in self.sim_key_to_box

    # Pass on click events to parent window

    def key_dclick(self, event):
        self.parent.key_dclick(self.key_by_id[event.Id])
        event.Skip()

    def key_click(self, event):
        self.parent.key_click(self.key_by_id[event.Id])
        event.Skip()

    def key_enter(self, event):
        self.parent.key_enter(self.key_by_id[event.Id])
        event.Skip()

    def key_leave(self, event):
        self.parent.key_leave(self.key_by_id[event.Id])
        event.Skip()

# Physical keyboard mapping setup dialog
class Phys_mapping_dialog(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, title = "Physical key mapping")

        # Place text, keyboard, info and buttons top-down
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Informative text
        txt = ("Click on a key on the simulated keyboard below to bind"
               " it to a key on your keyboard."
               " Double click on a key to remove the binding.")
        top_txt = wx.StaticText(self, label = txt)
        sizer.Add(top_txt, 0, wx.ALL, border = 8)

        # Keyboard panel
        self.kbd = Screen_keyboard(self)
        sizer.Add(self.kbd, 0, wx.ALL, border = 8)

        # Label for displaying long key description
        self.info_lbl = wx.StaticText(self, label = "")
        sizer.Add(self.info_lbl, 0, wx.ALL, border = 8)

        # Place buttons left-right
        but_sizer = wx.BoxSizer(wx.HORIZONTAL)

        but_sizer.AddStretchSpacer()
        self.clear_but = wx.Button(self, wx.ID_ANY, "Clear All")
        but_sizer.Add(self.clear_but, 0, wx.RIGHT, border = 16)

        but_sizer.AddStretchSpacer()
        self.default_but = wx.Button(self, wx.ID_ANY, "Reset to Default")
        but_sizer.Add(self.default_but, 0, wx.RIGHT, border = 16)

        but_sizer.AddStretchSpacer()
        self.saved_but = wx.Button(self, wx.ID_ANY, "Revert to Saved")
        but_sizer.Add(self.saved_but, 0, 0)

        but_sizer.AddStretchSpacer()
        self.save_but = wx.Button(self, wx.ID_ANY, "Save to Preferences")
        but_sizer.Add(self.save_but, 0, 0)

        but_sizer.AddStretchSpacer()
        sizer.Add(but_sizer)
        self.SetSizerAndFit(sizer)

        # Button click callbacks
        self.clear_but.Bind(wx.EVT_BUTTON, self.clear_click)
        self.default_but.Bind(wx.EVT_BUTTON, self.reset_click)
        self.saved_but.Bind(wx.EVT_BUTTON, self.revert_click)
        self.save_but.Bind(wx.EVT_BUTTON, self.save_click)

        # User defined mapping used by the console.
        self.keycodes_to_key = {}
        # Inverse mapping.
        self.key_to_keycode = {}

        # Active Key after user selected them
        self.active_key = None
        self.reset_to_default()
        # Use EVT_CHAR_HOOK to let main window catch all key presses.
        self.Bind(wx.EVT_CHAR_HOOK, self.map_key_input)

    # Return the Simics key corresponding to a raw wx key code (raw flags),
    # or None if no translation could be found.
    def lookup_key(self, rawcode):
        return self.keycodes_to_key.get(physical_key_code(rawcode), None)

    # Remove all mappings
    def clear_mapping(self):
        self.keycodes_to_key.clear()
        self.key_to_keycode.clear()
        self.display_current_mapping()

    # Set current mapping to the given mapping: a dict with format as
    # returned by default_phys_key_mapping
    def set_mapping(self, mapping):
        # Store mapping
        self.keycodes_to_key = mapping

        # Update inverse mapping.
        invalid = []
        for (phys_key, sim_key) in self.keycodes_to_key.items():
            # Make sure no non-existing keys are used, e.g. in preferences
            if self.kbd.is_valid_key(sim_key):
                self.key_to_keycode[sim_key] = phys_key
            else:
                invalid.append(phys_key)

        # Remove any invalid mappings
        for phys_key in invalid:
            del self.keycodes_to_key[phys_key]

    # Reset all wx.Panel colours to be consistent with current mapping.
    def display_current_mapping(self):
        # First reset everything to "unmapped"
        self.kbd.reset_all()
        # Now display all mapped keys
        for sim_key in self.keycodes_to_key.values():
            self.kbd.map_key(sim_key)

    # Reset current mapping to system default.
    def reset_to_default(self):
        self.clear_mapping()
        self.set_mapping(default_phys_key_mapping())
        self.display_current_mapping()

    # Reset current mapping to user preferences
    def revert_to_saved(self):
        with simics_lock():
            prefs = simics.SIM_get_object("prefs")
            try:
                mapping = prefs.iface.preference.get_preference_for_module_key(
                    "gfx-console", "key-mapping")
            except simics.SimExc_Attribute:
                return False

        self.clear_mapping()
        self.set_mapping(mapping)
        self.display_current_mapping()
        return True

    # Does simulated key sim_key has a mapping from some physical key?
    def has_mapping(self, sim_key):
        return sim_key in self.key_to_keycode

    # Set a new key mapping keycode -> sim_key
    def set_key_mapping(self, keycode, sim_key):
        # Set key mapping and inverse map
        self.keycodes_to_key[keycode] = self.active_key.sim_key
        self.key_to_keycode[self.active_key.sim_key] = keycode

    # Remove mapping to simulated key sim_key.
    def unmap_key(self, sim_key):
        assert sim_key in self.key_to_keycode
        # Physical key mapped to sim_key
        phys_key = self.key_to_keycode[sim_key]
        # Remove mapping
        del self.keycodes_to_key[phys_key]
        del self.key_to_keycode[sim_key]
        # Update display
        self.kbd.reset_key(sim_key)

    # Add a new mapping from the given keycode to the selected key
    def map_key(self, keycode):
        assert self.active_key is not None

        # Remove any existing mapping for this physical key press.
        if keycode in self.keycodes_to_key:
            self.unmap_key(self.keycodes_to_key[keycode])

        # Remove any existing mapping for this simulated key.
        if self.has_mapping(self.active_key.sim_key):
            self.unmap_key(self.active_key.sim_key)

        # Set up mapping of selected key.
        self.set_key_mapping(keycode, self.active_key.sim_key)
        # Display new mapping
        self.kbd.map_key(self.active_key.sim_key)
        self.active_key = None

    # Button click events

    def clear_click(self, event):
        self.clear_mapping()

    def reset_click(self, event):
        self.reset_to_default()

    def revert_click(self, event):
        if not self.revert_to_saved():
            print(("Could not load physical keyboard"
                                 " mapping from preferences."), file=sys.stderr)

    def save_click(self, event):
        with simics_lock():
            prefs = simics.SIM_get_object("prefs")
            try:
                prefs.iface.preference.set_preference_for_module_key(
                    self.keycodes_to_key, "gfx-console", "key-mapping")
            except simics.SimExc_Attribute:
                print(("Could not save physical keyboard"
                                     " mapping to preferences."), file=sys.stderr)

    # Clicking on a key will put it in a waiting state, and next keyboard
    # input on the host will define the mapping.
    def key_click(self, key):
        if self.active_key is not None:
            # Reset keyboard display, in case another key was selected already
            self.display_current_mapping()

        if self.active_key != key:
            # Mark clicked key as selected
            self.active_key = key
            self.kbd.waiting_key(key.sim_key)
        else:
            # Clicking on the same key again will exit the waiting state
            self.active_key = None

    # Double click on a key will remove the corresponding mapping.
    def key_dclick(self, key):
        if self.has_mapping(key.sim_key):
            self.unmap_key(key.sim_key)
            self.active_key = None

    # Display long key description when hovering
    def key_enter(self, key):
        self.info_lbl.SetLabel(key.desc)

    def key_leave(self, key):
        self.info_lbl.SetLabel("")

    def map_key_input(self, event):
        # Ignore key input unless a key has been selected.
        if self.active_key is not None:
            self.map_key(physical_key_code(event.GetRawKeyFlags()))
