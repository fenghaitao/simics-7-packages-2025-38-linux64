# © 2018 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

from simics import (
    SK_0,
    SK_1,
    SK_2,
    SK_3,
    SK_4,
    SK_5,
    SK_6,
    SK_7,
    SK_8,
    SK_9,
    SK_A,
    SK_ALT_L,
    SK_APOSTROPHE,
    SK_BACKSLASH,
    SK_BACKSPACE,
    SK_COMMA,
    SK_CTRL_L,
    SK_ENTER,
    SK_EQUAL,
    SK_ESC,
    SK_F1,
    SK_F10,
    SK_F11,
    SK_F12,
    SK_F2,
    SK_F3,
    SK_F4,
    SK_F5,
    SK_F6,
    SK_F7,
    SK_F8,
    SK_F9,
    SK_GRAVE,
    SK_GR_DELETE,
    SK_GR_DOWN,
    SK_GR_LEFT,
    SK_GR_RIGHT,
    SK_GR_UP,
    SK_LEFT_BRACKET,
    SK_LEFT_WIN,
    SK_MINUS,
    SK_PERIOD,
    SK_RIGHT_BRACKET,
    SK_SEMICOLON,
    SK_SHIFT_L,
    SK_SLASH,
    SK_SPACE,
    SK_TAB,
    )

def char_to_keystrokes(ch):
    ret = []
    char_table = {'!': [[0, SK_SHIFT_L], [0, SK_1], [1, SK_1], [1, SK_SHIFT_L]],
                  '@': [[0, SK_SHIFT_L], [0, SK_2], [1, SK_2], [1, SK_SHIFT_L]],
                  '#': [[0, SK_SHIFT_L], [0, SK_3], [1, SK_3], [1, SK_SHIFT_L]],
                  '$': [[0, SK_SHIFT_L], [0, SK_4], [1, SK_4], [1, SK_SHIFT_L]],
                  '%': [[0, SK_SHIFT_L], [0, SK_5], [1, SK_5], [1, SK_SHIFT_L]],
                  '^': [[0, SK_SHIFT_L], [0, SK_6], [1, SK_6], [1, SK_SHIFT_L]],
                  '&': [[0, SK_SHIFT_L], [0, SK_7], [1, SK_7], [1, SK_SHIFT_L]],
                  '*': [[0, SK_SHIFT_L], [0, SK_8], [1, SK_8], [1, SK_SHIFT_L]],
                  '(': [[0, SK_SHIFT_L], [0, SK_9], [1, SK_9], [1, SK_SHIFT_L]],
                  ')': [[0, SK_SHIFT_L], [0, SK_0], [1, SK_0], [1, SK_SHIFT_L]],
                  '\'': [[0, SK_APOSTROPHE], [1, SK_APOSTROPHE]],
                  '"': [[0, SK_SHIFT_L], [0, SK_APOSTROPHE],
                        [1, SK_APOSTROPHE], [1, SK_SHIFT_L]],
                  ',': [[0, SK_COMMA], [1, SK_COMMA]],
                  '<': [[0, SK_SHIFT_L], [0, SK_COMMA],
                        [1, SK_COMMA], [1, SK_SHIFT_L]],
                  '.': [[0, SK_PERIOD], [1, SK_PERIOD]],
                  '>': [[0, SK_SHIFT_L], [0, SK_PERIOD],
                        [1, SK_PERIOD], [1, SK_SHIFT_L]],
                  ';': [[0, SK_SEMICOLON], [1, SK_SEMICOLON]],
                  ':': [[0, SK_SHIFT_L], [0, SK_SEMICOLON],
                        [1, SK_SEMICOLON], [1, SK_SHIFT_L]],
                  '=': [[0, SK_EQUAL], [1, SK_EQUAL]],
                  '+': [[0, SK_SHIFT_L], [0, SK_EQUAL],
                        [1, SK_EQUAL], [1, SK_SHIFT_L]],
                  '/': [[0, SK_SLASH], [1, SK_SLASH]],
                  '?': [[0, SK_SHIFT_L], [0, SK_SLASH],
                        [1, SK_SLASH], [1, SK_SHIFT_L]],
                  '\\': [[0, SK_BACKSLASH], [1, SK_BACKSLASH]],
                  '|': [[0, SK_SHIFT_L], [0, SK_BACKSLASH],
                        [1, SK_BACKSLASH], [1, SK_SHIFT_L]],
                  ' ': [[0, SK_SPACE], [1, SK_SPACE]],
                  '[': [[0, SK_LEFT_BRACKET], [1, SK_LEFT_BRACKET]],
                  '{': [[0, SK_SHIFT_L], [0, SK_LEFT_BRACKET],
                        [1, SK_LEFT_BRACKET], [1, SK_SHIFT_L]],
                  ']': [[0, SK_RIGHT_BRACKET], [1, SK_RIGHT_BRACKET]],
                  '}': [[0, SK_SHIFT_L], [0, SK_RIGHT_BRACKET],
                        [1, SK_RIGHT_BRACKET], [1, SK_SHIFT_L]],
                  '-': [[0, SK_MINUS], [1, SK_MINUS]],
                  '_': [[0, SK_SHIFT_L], [0, SK_MINUS],
                        [1, SK_MINUS], [1, SK_SHIFT_L]],
                  '`': [[0, SK_GRAVE], [1, SK_GRAVE]],
                  '~': [[0, SK_SHIFT_L], [0, SK_GRAVE],
                        [1, SK_GRAVE], [1, SK_SHIFT_L]],
                  '\033': [[0, SK_ESC], [1, SK_ESC]],
                  '\t': [[0, SK_TAB], [1, SK_TAB]],
                  '\n': [[0, SK_ENTER], [1, SK_ENTER]],
                  '\r': [[0, SK_ENTER], [1, SK_ENTER]],
                  '\b': [[0, SK_BACKSPACE], [1, SK_BACKSPACE]]}
    if ord(ch) >= ord('A') and ord(ch) <= ord('Z'):
        ret.append([0, SK_SHIFT_L])
        ret.append([0, ord(ch) - ord('A') + SK_A])
        ret.append([1, ord(ch) - ord('A') + SK_A])
        ret.append([1, SK_SHIFT_L])
    elif ord(ch) >= ord('a') and ord(ch) <= ord('z'):
        ret.append([0, ord(ch) - ord('a') + SK_A])
        ret.append([1, ord(ch) - ord('a') + SK_A])
    elif ord(ch) >= ord('0') and ord(ch) <= ord('9'):
        ret.append([0, ord(ch) - ord('0') + SK_0])
        ret.append([1, ord(ch) - ord('0') + SK_0])
    else:
        return char_table.get(ch, None)
    return ret

def string_to_keystrokes(string):
    ret = []
    for ch in string:
        c = ch
        for stroke in char_to_keystrokes(ch):
            if not stroke:
                return None
            ret.append((c, stroke))
            c = None
    return ret

def emacs_to_keystrokes(string):
    ret = []
    emacs_table = {'C': [[0, SK_CTRL_L], [1, SK_CTRL_L]],
                   'A': [[0, SK_ALT_L], [1, SK_ALT_L]],
                   'Del': [[0, SK_GR_DELETE], [1, SK_GR_DELETE]],
                   'Up': [[0, SK_GR_UP], [1, SK_GR_UP]],
                   'Down': [[0, SK_GR_DOWN], [1, SK_GR_DOWN]],
                   'Left': [[0, SK_GR_LEFT], [1, SK_GR_LEFT]],
                   'Right': [[0, SK_GR_RIGHT], [1, SK_GR_RIGHT]],
                   'Esc': [[0, SK_ESC], [1, SK_ESC]],
                   'F1': [[0, SK_F1], [1, SK_F1]],
                   'F2': [[0, SK_F2], [1, SK_F2]],
                   'F3': [[0, SK_F3], [1, SK_F3]],
                   'F4': [[0, SK_F4], [1, SK_F4]],
                   'F5': [[0, SK_F5], [1, SK_F5]],
                   'F6': [[0, SK_F6], [1, SK_F6]],
                   'F7': [[0, SK_F7], [1, SK_F7]],
                   'F8': [[0, SK_F8], [1, SK_F8]],
                   'F9': [[0, SK_F9], [1, SK_F9]],
                   'F10': [[0, SK_F10], [1, SK_F10]],
                   'F11': [[0, SK_F11], [1, SK_F11]],
                   'F12': [[0, SK_F12], [1, SK_F12]],
                   'Win': [[0, SK_LEFT_WIN], [1, SK_LEFT_WIN]],
                   'Tab': [[0, SK_TAB], [1, SK_TAB]],
                   'Enter': [[0, SK_ENTER], [1, SK_ENTER]]}
    if string in emacs_table:
        ret.extend(emacs_table[string])
    else:
        data = string_to_keystrokes(string)
        if data:
            for (a, b) in data:
                ret.append(b)
    return ret
