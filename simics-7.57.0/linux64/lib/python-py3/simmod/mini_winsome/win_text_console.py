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
import simmod.mini_winsome.win_main
import itertools
import simmod.mini_winsome.keycodes
import threading
from simmod.mini_winsome.win_utils import *
import simmod.mini_winsome.console_util
import simmod.mini_winsome.console_window
import simmod.mini_winsome.console_panel
import text_console_commands
import simics
from simicsutils.internal import ensure_text

# Simics to WX font flags.
FONT_FLAGS = {
    0: 0,
    simics.Text_Console_Attrib_Bold: wx.FONTFLAG_BOLD,
    simics.Text_Console_Attrib_Underline: wx.FONTFLAG_UNDERLINED,
}

# Initial screen size.
# Backend changes these immediately.
DEFAULT_SCREEN_SIZE = wx.Size(80, 24)
DEFAULT_MAX_SB_LINES = 10000
DEFAULT_BG_COL = 0xffffff
DEFAULT_FG_COL = 0

# Size in bytes of text_console_attrib_t.
ATTRIB_SIZE = 5

# RGB values of VT100 console colour definitions.
COLOURS = {
    simics.Text_Console_Colour_Black: wx.Colour(0, 0, 0),
    simics.Text_Console_Colour_Red: wx.Colour(205, 0, 0),
    simics.Text_Console_Colour_Green: wx.Colour(0, 205, 0),
    simics.Text_Console_Colour_Yellow: wx.Colour(205, 205, 0),
    simics.Text_Console_Colour_Blue: wx.Colour(0, 0, 238),
    simics.Text_Console_Colour_Magenta: wx.Colour(205, 0, 205),
    simics.Text_Console_Colour_Cyan: wx.Colour(0, 205, 205),
    simics.Text_Console_Colour_White: wx.Colour(229, 229, 229),
    simics.Text_Console_Colour_Black_Bright: wx.Colour(127, 127, 127),
    simics.Text_Console_Colour_Red_Bright: wx.Colour(255, 0, 0),
    simics.Text_Console_Colour_Green_Bright: wx.Colour(0, 255, 0),
    simics.Text_Console_Colour_Yellow_Bright: wx.Colour(255, 255, 0),
    simics.Text_Console_Colour_Blue_Bright: wx.Colour(92, 92, 255),
    simics.Text_Console_Colour_Magenta_Bright: wx.Colour(255, 0, 255),
    simics.Text_Console_Colour_Cyan_Bright: wx.Colour(0, 255, 255),
    simics.Text_Console_Colour_White_Bright: wx.Colour(255, 255, 255),
    simics.Text_Console_Colour_Cube_16: wx.Colour(0, 0, 0),
    simics.Text_Console_Colour_Cube_17: wx.Colour(0, 0, 95),
    simics.Text_Console_Colour_Cube_18: wx.Colour(0, 0, 135),
    simics.Text_Console_Colour_Cube_19: wx.Colour(0, 0, 175),
    simics.Text_Console_Colour_Cube_20: wx.Colour(0, 0, 215),
    simics.Text_Console_Colour_Cube_21: wx.Colour(0, 0, 255),
    simics.Text_Console_Colour_Cube_22: wx.Colour(0, 95, 0),
    simics.Text_Console_Colour_Cube_23: wx.Colour(0, 95, 95),
    simics.Text_Console_Colour_Cube_24: wx.Colour(0, 95, 135),
    simics.Text_Console_Colour_Cube_25: wx.Colour(0, 95, 175),
    simics.Text_Console_Colour_Cube_26: wx.Colour(0, 95, 215),
    simics.Text_Console_Colour_Cube_27: wx.Colour(0, 95, 255),
    simics.Text_Console_Colour_Cube_28: wx.Colour(0, 135, 0),
    simics.Text_Console_Colour_Cube_29: wx.Colour(0, 135, 95),
    simics.Text_Console_Colour_Cube_30: wx.Colour(0, 135, 135),
    simics.Text_Console_Colour_Cube_31: wx.Colour(0, 135, 175),
    simics.Text_Console_Colour_Cube_32: wx.Colour(0, 135, 215),
    simics.Text_Console_Colour_Cube_33: wx.Colour(0, 135, 255),
    simics.Text_Console_Colour_Cube_34: wx.Colour(0, 175, 0),
    simics.Text_Console_Colour_Cube_35: wx.Colour(0, 175, 95),
    simics.Text_Console_Colour_Cube_36: wx.Colour(0, 175, 135),
    simics.Text_Console_Colour_Cube_37: wx.Colour(0, 175, 175),
    simics.Text_Console_Colour_Cube_38: wx.Colour(0, 175, 215),
    simics.Text_Console_Colour_Cube_39: wx.Colour(0, 175, 255),
    simics.Text_Console_Colour_Cube_40: wx.Colour(0, 215, 0),
    simics.Text_Console_Colour_Cube_41: wx.Colour(0, 215, 95),
    simics.Text_Console_Colour_Cube_42: wx.Colour(0, 215, 135),
    simics.Text_Console_Colour_Cube_43: wx.Colour(0, 215, 175),
    simics.Text_Console_Colour_Cube_44: wx.Colour(0, 215, 215),
    simics.Text_Console_Colour_Cube_45: wx.Colour(0, 215, 255),
    simics.Text_Console_Colour_Cube_46: wx.Colour(0, 255, 0),
    simics.Text_Console_Colour_Cube_47: wx.Colour(0, 255, 95),
    simics.Text_Console_Colour_Cube_48: wx.Colour(0, 255, 135),
    simics.Text_Console_Colour_Cube_49: wx.Colour(0, 255, 175),
    simics.Text_Console_Colour_Cube_50: wx.Colour(0, 255, 215),
    simics.Text_Console_Colour_Cube_51: wx.Colour(0, 255, 255),
    simics.Text_Console_Colour_Cube_52: wx.Colour(95, 0, 0),
    simics.Text_Console_Colour_Cube_53: wx.Colour(95, 0, 95),
    simics.Text_Console_Colour_Cube_54: wx.Colour(95, 0, 135),
    simics.Text_Console_Colour_Cube_55: wx.Colour(95, 0, 175),
    simics.Text_Console_Colour_Cube_56: wx.Colour(95, 0, 215),
    simics.Text_Console_Colour_Cube_57: wx.Colour(95, 0, 255),
    simics.Text_Console_Colour_Cube_58: wx.Colour(95, 95, 0),
    simics.Text_Console_Colour_Cube_59: wx.Colour(95, 95, 95),
    simics.Text_Console_Colour_Cube_60: wx.Colour(95, 95, 135),
    simics.Text_Console_Colour_Cube_61: wx.Colour(95, 95, 175),
    simics.Text_Console_Colour_Cube_62: wx.Colour(95, 95, 215),
    simics.Text_Console_Colour_Cube_63: wx.Colour(95, 95, 255),
    simics.Text_Console_Colour_Cube_64: wx.Colour(95, 135, 0),
    simics.Text_Console_Colour_Cube_65: wx.Colour(95, 135, 95),
    simics.Text_Console_Colour_Cube_66: wx.Colour(95, 135, 135),
    simics.Text_Console_Colour_Cube_67: wx.Colour(95, 135, 175),
    simics.Text_Console_Colour_Cube_68: wx.Colour(95, 135, 215),
    simics.Text_Console_Colour_Cube_69: wx.Colour(95, 135, 255),
    simics.Text_Console_Colour_Cube_70: wx.Colour(95, 175, 0),
    simics.Text_Console_Colour_Cube_71: wx.Colour(95, 175, 95),
    simics.Text_Console_Colour_Cube_72: wx.Colour(95, 175, 135),
    simics.Text_Console_Colour_Cube_73: wx.Colour(95, 175, 175),
    simics.Text_Console_Colour_Cube_74: wx.Colour(95, 175, 215),
    simics.Text_Console_Colour_Cube_75: wx.Colour(95, 175, 255),
    simics.Text_Console_Colour_Cube_76: wx.Colour(95, 215, 0),
    simics.Text_Console_Colour_Cube_77: wx.Colour(95, 215, 95),
    simics.Text_Console_Colour_Cube_78: wx.Colour(95, 215, 135),
    simics.Text_Console_Colour_Cube_79: wx.Colour(95, 215, 175),
    simics.Text_Console_Colour_Cube_80: wx.Colour(95, 215, 215),
    simics.Text_Console_Colour_Cube_81: wx.Colour(95, 215, 255),
    simics.Text_Console_Colour_Cube_82: wx.Colour(95, 255, 0),
    simics.Text_Console_Colour_Cube_83: wx.Colour(95, 255, 95),
    simics.Text_Console_Colour_Cube_84: wx.Colour(95, 255, 135),
    simics.Text_Console_Colour_Cube_85: wx.Colour(95, 255, 175),
    simics.Text_Console_Colour_Cube_86: wx.Colour(95, 255, 215),
    simics.Text_Console_Colour_Cube_87: wx.Colour(95, 255, 255),
    simics.Text_Console_Colour_Cube_88: wx.Colour(135, 0, 0),
    simics.Text_Console_Colour_Cube_89: wx.Colour(135, 0, 95),
    simics.Text_Console_Colour_Cube_90: wx.Colour(135, 0, 135),
    simics.Text_Console_Colour_Cube_91: wx.Colour(135, 0, 175),
    simics.Text_Console_Colour_Cube_92: wx.Colour(135, 0, 215),
    simics.Text_Console_Colour_Cube_93: wx.Colour(135, 0, 255),
    simics.Text_Console_Colour_Cube_94: wx.Colour(135, 95, 0),
    simics.Text_Console_Colour_Cube_95: wx.Colour(135, 95, 95),
    simics.Text_Console_Colour_Cube_96: wx.Colour(135, 95, 135),
    simics.Text_Console_Colour_Cube_97: wx.Colour(135, 95, 175),
    simics.Text_Console_Colour_Cube_98: wx.Colour(135, 95, 215),
    simics.Text_Console_Colour_Cube_99: wx.Colour(135, 95, 255),
    simics.Text_Console_Colour_Cube_100: wx.Colour(135, 135, 0),
    simics.Text_Console_Colour_Cube_101: wx.Colour(135, 135, 95),
    simics.Text_Console_Colour_Cube_102: wx.Colour(135, 135, 135),
    simics.Text_Console_Colour_Cube_103: wx.Colour(135, 135, 175),
    simics.Text_Console_Colour_Cube_104: wx.Colour(135, 135, 215),
    simics.Text_Console_Colour_Cube_105: wx.Colour(135, 135, 255),
    simics.Text_Console_Colour_Cube_106: wx.Colour(135, 175, 0),
    simics.Text_Console_Colour_Cube_107: wx.Colour(135, 175, 95),
    simics.Text_Console_Colour_Cube_108: wx.Colour(135, 175, 135),
    simics.Text_Console_Colour_Cube_109: wx.Colour(135, 175, 175),
    simics.Text_Console_Colour_Cube_110: wx.Colour(135, 175, 215),
    simics.Text_Console_Colour_Cube_111: wx.Colour(135, 175, 255),
    simics.Text_Console_Colour_Cube_112: wx.Colour(135, 215, 0),
    simics.Text_Console_Colour_Cube_113: wx.Colour(135, 215, 95),
    simics.Text_Console_Colour_Cube_114: wx.Colour(135, 215, 135),
    simics.Text_Console_Colour_Cube_115: wx.Colour(135, 215, 175),
    simics.Text_Console_Colour_Cube_116: wx.Colour(135, 215, 215),
    simics.Text_Console_Colour_Cube_117: wx.Colour(135, 215, 255),
    simics.Text_Console_Colour_Cube_118: wx.Colour(135, 255, 0),
    simics.Text_Console_Colour_Cube_119: wx.Colour(135, 255, 95),
    simics.Text_Console_Colour_Cube_120: wx.Colour(135, 255, 135),
    simics.Text_Console_Colour_Cube_121: wx.Colour(135, 255, 175),
    simics.Text_Console_Colour_Cube_122: wx.Colour(135, 255, 215),
    simics.Text_Console_Colour_Cube_123: wx.Colour(135, 255, 255),
    simics.Text_Console_Colour_Cube_124: wx.Colour(175, 0, 0),
    simics.Text_Console_Colour_Cube_125: wx.Colour(175, 0, 95),
    simics.Text_Console_Colour_Cube_126: wx.Colour(175, 0, 135),
    simics.Text_Console_Colour_Cube_127: wx.Colour(175, 0, 175),
    simics.Text_Console_Colour_Cube_128: wx.Colour(175, 0, 215),
    simics.Text_Console_Colour_Cube_129: wx.Colour(175, 0, 255),
    simics.Text_Console_Colour_Cube_130: wx.Colour(175, 95, 0),
    simics.Text_Console_Colour_Cube_131: wx.Colour(175, 95, 95),
    simics.Text_Console_Colour_Cube_132: wx.Colour(175, 95, 135),
    simics.Text_Console_Colour_Cube_133: wx.Colour(175, 95, 175),
    simics.Text_Console_Colour_Cube_134: wx.Colour(175, 95, 215),
    simics.Text_Console_Colour_Cube_135: wx.Colour(175, 95, 255),
    simics.Text_Console_Colour_Cube_136: wx.Colour(175, 135, 0),
    simics.Text_Console_Colour_Cube_137: wx.Colour(175, 135, 95),
    simics.Text_Console_Colour_Cube_138: wx.Colour(175, 135, 135),
    simics.Text_Console_Colour_Cube_139: wx.Colour(175, 135, 175),
    simics.Text_Console_Colour_Cube_140: wx.Colour(175, 135, 215),
    simics.Text_Console_Colour_Cube_141: wx.Colour(175, 135, 255),
    simics.Text_Console_Colour_Cube_142: wx.Colour(175, 175, 0),
    simics.Text_Console_Colour_Cube_143: wx.Colour(175, 175, 95),
    simics.Text_Console_Colour_Cube_144: wx.Colour(175, 175, 135),
    simics.Text_Console_Colour_Cube_145: wx.Colour(175, 175, 175),
    simics.Text_Console_Colour_Cube_146: wx.Colour(175, 175, 215),
    simics.Text_Console_Colour_Cube_147: wx.Colour(175, 175, 255),
    simics.Text_Console_Colour_Cube_148: wx.Colour(175, 215, 0),
    simics.Text_Console_Colour_Cube_149: wx.Colour(175, 215, 95),
    simics.Text_Console_Colour_Cube_150: wx.Colour(175, 215, 135),
    simics.Text_Console_Colour_Cube_151: wx.Colour(175, 215, 175),
    simics.Text_Console_Colour_Cube_152: wx.Colour(175, 215, 215),
    simics.Text_Console_Colour_Cube_153: wx.Colour(175, 215, 255),
    simics.Text_Console_Colour_Cube_154: wx.Colour(175, 255, 0),
    simics.Text_Console_Colour_Cube_155: wx.Colour(175, 255, 95),
    simics.Text_Console_Colour_Cube_156: wx.Colour(175, 255, 135),
    simics.Text_Console_Colour_Cube_157: wx.Colour(175, 255, 175),
    simics.Text_Console_Colour_Cube_158: wx.Colour(175, 255, 215),
    simics.Text_Console_Colour_Cube_159: wx.Colour(175, 255, 255),
    simics.Text_Console_Colour_Cube_160: wx.Colour(215, 0, 0),
    simics.Text_Console_Colour_Cube_161: wx.Colour(215, 0, 95),
    simics.Text_Console_Colour_Cube_162: wx.Colour(215, 0, 135),
    simics.Text_Console_Colour_Cube_163: wx.Colour(215, 0, 175),
    simics.Text_Console_Colour_Cube_164: wx.Colour(215, 0, 215),
    simics.Text_Console_Colour_Cube_165: wx.Colour(215, 0, 255),
    simics.Text_Console_Colour_Cube_166: wx.Colour(215, 95, 0),
    simics.Text_Console_Colour_Cube_167: wx.Colour(215, 95, 95),
    simics.Text_Console_Colour_Cube_168: wx.Colour(215, 95, 135),
    simics.Text_Console_Colour_Cube_169: wx.Colour(215, 95, 175),
    simics.Text_Console_Colour_Cube_170: wx.Colour(215, 95, 215),
    simics.Text_Console_Colour_Cube_171: wx.Colour(215, 95, 255),
    simics.Text_Console_Colour_Cube_172: wx.Colour(215, 135, 0),
    simics.Text_Console_Colour_Cube_173: wx.Colour(215, 135, 95),
    simics.Text_Console_Colour_Cube_174: wx.Colour(215, 135, 135),
    simics.Text_Console_Colour_Cube_175: wx.Colour(215, 135, 175),
    simics.Text_Console_Colour_Cube_176: wx.Colour(215, 135, 215),
    simics.Text_Console_Colour_Cube_177: wx.Colour(215, 135, 255),
    simics.Text_Console_Colour_Cube_178: wx.Colour(215, 175, 0),
    simics.Text_Console_Colour_Cube_179: wx.Colour(215, 175, 95),
    simics.Text_Console_Colour_Cube_180: wx.Colour(215, 175, 135),
    simics.Text_Console_Colour_Cube_181: wx.Colour(215, 175, 175),
    simics.Text_Console_Colour_Cube_182: wx.Colour(215, 175, 215),
    simics.Text_Console_Colour_Cube_183: wx.Colour(215, 175, 255),
    simics.Text_Console_Colour_Cube_184: wx.Colour(215, 215, 0),
    simics.Text_Console_Colour_Cube_185: wx.Colour(215, 215, 95),
    simics.Text_Console_Colour_Cube_186: wx.Colour(215, 215, 135),
    simics.Text_Console_Colour_Cube_187: wx.Colour(215, 215, 175),
    simics.Text_Console_Colour_Cube_188: wx.Colour(215, 215, 215),
    simics.Text_Console_Colour_Cube_189: wx.Colour(215, 215, 255),
    simics.Text_Console_Colour_Cube_190: wx.Colour(215, 255, 0),
    simics.Text_Console_Colour_Cube_191: wx.Colour(215, 255, 95),
    simics.Text_Console_Colour_Cube_192: wx.Colour(215, 255, 135),
    simics.Text_Console_Colour_Cube_193: wx.Colour(215, 255, 175),
    simics.Text_Console_Colour_Cube_194: wx.Colour(215, 255, 215),
    simics.Text_Console_Colour_Cube_195: wx.Colour(215, 255, 255),
    simics.Text_Console_Colour_Cube_196: wx.Colour(255, 0, 0),
    simics.Text_Console_Colour_Cube_197: wx.Colour(255, 0, 95),
    simics.Text_Console_Colour_Cube_198: wx.Colour(255, 0, 135),
    simics.Text_Console_Colour_Cube_199: wx.Colour(255, 0, 175),
    simics.Text_Console_Colour_Cube_200: wx.Colour(255, 0, 215),
    simics.Text_Console_Colour_Cube_201: wx.Colour(255, 0, 255),
    simics.Text_Console_Colour_Cube_202: wx.Colour(255, 95, 0),
    simics.Text_Console_Colour_Cube_203: wx.Colour(255, 95, 95),
    simics.Text_Console_Colour_Cube_204: wx.Colour(255, 95, 135),
    simics.Text_Console_Colour_Cube_205: wx.Colour(255, 95, 175),
    simics.Text_Console_Colour_Cube_206: wx.Colour(255, 95, 215),
    simics.Text_Console_Colour_Cube_207: wx.Colour(255, 95, 255),
    simics.Text_Console_Colour_Cube_208: wx.Colour(255, 135, 0),
    simics.Text_Console_Colour_Cube_209: wx.Colour(255, 135, 95),
    simics.Text_Console_Colour_Cube_210: wx.Colour(255, 135, 135),
    simics.Text_Console_Colour_Cube_211: wx.Colour(255, 135, 175),
    simics.Text_Console_Colour_Cube_212: wx.Colour(255, 135, 215),
    simics.Text_Console_Colour_Cube_213: wx.Colour(255, 135, 255),
    simics.Text_Console_Colour_Cube_214: wx.Colour(255, 175, 0),
    simics.Text_Console_Colour_Cube_215: wx.Colour(255, 175, 95),
    simics.Text_Console_Colour_Cube_216: wx.Colour(255, 175, 135),
    simics.Text_Console_Colour_Cube_217: wx.Colour(255, 175, 175),
    simics.Text_Console_Colour_Cube_218: wx.Colour(255, 175, 215),
    simics.Text_Console_Colour_Cube_219: wx.Colour(255, 175, 255),
    simics.Text_Console_Colour_Cube_220: wx.Colour(255, 215, 0),
    simics.Text_Console_Colour_Cube_221: wx.Colour(255, 215, 95),
    simics.Text_Console_Colour_Cube_222: wx.Colour(255, 215, 135),
    simics.Text_Console_Colour_Cube_223: wx.Colour(255, 215, 175),
    simics.Text_Console_Colour_Cube_224: wx.Colour(255, 215, 215),
    simics.Text_Console_Colour_Cube_225: wx.Colour(255, 215, 255),
    simics.Text_Console_Colour_Cube_226: wx.Colour(255, 255, 0),
    simics.Text_Console_Colour_Cube_227: wx.Colour(255, 255, 95),
    simics.Text_Console_Colour_Cube_228: wx.Colour(255, 255, 135),
    simics.Text_Console_Colour_Cube_229: wx.Colour(255, 255, 175),
    simics.Text_Console_Colour_Cube_230: wx.Colour(255, 255, 215),
    simics.Text_Console_Colour_Cube_231: wx.Colour(255, 255, 255),
    simics.Text_Console_Colour_Grey_232: wx.Colour(8, 8, 8),
    simics.Text_Console_Colour_Grey_233: wx.Colour(18, 18, 18),
    simics.Text_Console_Colour_Grey_234: wx.Colour(28, 28, 28),
    simics.Text_Console_Colour_Grey_235: wx.Colour(38, 38, 38),
    simics.Text_Console_Colour_Grey_236: wx.Colour(48, 48, 48),
    simics.Text_Console_Colour_Grey_237: wx.Colour(58, 58, 58),
    simics.Text_Console_Colour_Grey_238: wx.Colour(68, 68, 68),
    simics.Text_Console_Colour_Grey_239: wx.Colour(78, 78, 78),
    simics.Text_Console_Colour_Grey_240: wx.Colour(88, 88, 88),
    simics.Text_Console_Colour_Grey_241: wx.Colour(98, 98, 98),
    simics.Text_Console_Colour_Grey_242: wx.Colour(108, 108, 108),
    simics.Text_Console_Colour_Grey_243: wx.Colour(118, 118, 118),
    simics.Text_Console_Colour_Grey_244: wx.Colour(128, 128, 128),
    simics.Text_Console_Colour_Grey_245: wx.Colour(138, 138, 138),
    simics.Text_Console_Colour_Grey_246: wx.Colour(148, 148, 148),
    simics.Text_Console_Colour_Grey_247: wx.Colour(158, 158, 158),
    simics.Text_Console_Colour_Grey_248: wx.Colour(168, 168, 168),
    simics.Text_Console_Colour_Grey_249: wx.Colour(178, 178, 178),
    simics.Text_Console_Colour_Grey_250: wx.Colour(188, 188, 188),
    simics.Text_Console_Colour_Grey_251: wx.Colour(198, 198, 198),
    simics.Text_Console_Colour_Grey_252: wx.Colour(208, 208, 208),
    simics.Text_Console_Colour_Grey_253: wx.Colour(218, 218, 218),
    simics.Text_Console_Colour_Grey_254: wx.Colour(228, 228, 228),
    simics.Text_Console_Colour_Grey_255: wx.Colour(238, 238, 238),
}

# Convert text_console_attrib_t bitmask to WX font flag bitmask.
def convert_fontflags(attrib):
    flag = 0
    for x in FONT_FLAGS:
        flag = flag | FONT_FLAGS[attrib & x]
    return flag

def convert_colour(col):
    return wx.Colour(col & 0xff, (col >> 8) & 0xff, (col >> 16) & 0xff)

# Dialog where text console size can be specified.
class Size_dialog(wx.Dialog):
    def __init__(self, parent, cur_size):
        wx.Dialog.__init__(self, parent, title = "Console screen size")

        # Border between grid bag cells.
        border = 2
        # Text style used by StaticText header widgets.
        header_style = wx.ALIGN_LEFT
        # Text style used by editable TextCtrl widgets.
        data_style = (wx.TE_RIGHT | wx.TE_NOHIDESEL | wx.BORDER_NONE)

        sizer = wx.GridBagSizer(border, border)
        # Sizer flags.
        flags = wx.EXPAND | wx.LEFT | wx.RIGHT

        # Previous screen size, needed as default value from event handlers.
        self.old_size = cur_size

        # Data for generating widgets.
        data = [{
            # Identifying name.
            'name': 'cols',
            # Header text.
            'text': 'Columns',
            # Grid bag cell for header StaticText. Other widgets to the right.
            'pos': [1, 1],
            # Initial data for TextCtrl widget.
            'data': cur_size.width
        }, {
            'name': 'rows',
            'text': 'Rows',
            'pos': [2, 1],
            'data': cur_size.height
        }]
        self.size_data = {}
        spin_buttons = {}

        for elt in data:
            # Header text in bold.
            cols_text = wx.StaticText(self, wx.ID_ANY, elt['text'],
                                      style = header_style)
            font = cols_text.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            cols_text.SetFont(font)
            pos = elt['pos']
            sizer.Add(cols_text, pos, wx.GBSpan(1, 1),
                      flag = flags | wx.ALIGN_LEFT, border = border)

            # Text field containing chosen size.
            self.size_data[elt['name']] = wx.TextCtrl(
                self, wx.ID_ANY, str(elt['data']), style = data_style)
            self.size_data[elt['name']].SetBackgroundColour(
                self.GetBackgroundColour())
            pos[1] += 1
            sizer.Add(self.size_data[elt['name']], pos, wx.GBSpan(1, 1),
                      flag = flags | wx.ALIGN_RIGHT, border = border)

            # Spin button to the right of the text field.
            pos[1] += 1
            spin_buttons[elt['name']] = wx.SpinButton(
                self, style = wx.SP_VERTICAL | wx.SP_WRAP)
            # We do not use the range.
            spin_buttons[elt['name']].SetRange(1, 1000)
            spin_buttons[elt['name']].SetValue(elt['data'])
            sizer.Add(spin_buttons[elt['name']], pos, wx.GBSpan(1, 1),
                      flag = wx.LEFT | wx.RIGHT, border = border)

        # Buttons at the bottom of the dialog.
        buttons = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(buttons, (4, 1), wx.GBSpan(2, 3),
                  flag = (wx.ALIGN_CENTER_VERTICAL
                          | wx.ALIGN_CENTER_HORIZONTAL
                          | wx.ALL),
                  border = border)

        spin_buttons['cols'].Bind(wx.EVT_SPIN_UP, self.on_cols_up)
        spin_buttons['cols'].Bind(wx.EVT_SPIN_DOWN, self.on_cols_down)
        spin_buttons['rows'].Bind(wx.EVT_SPIN_UP, self.on_rows_up)
        spin_buttons['rows'].Bind(wx.EVT_SPIN_DOWN, self.on_rows_down)
        self.SetSizerAndFit(sizer)
        self.SetMaxSize(self.GetSize())

    def text_ctrl_value(self, ctrl, default):
        try:
            return int(ctrl.GetValue())
        except ValueError:
            return default

    def update_text_ctrl(self, ctrl, diff, default):
        value = max(0, self.text_ctrl_value(ctrl, default) + diff)
        ctrl.SetValue(str(value))

    # Spin button events, all ignoring spin range and changing the text fields.

    def on_cols_up(self, event):
        self.update_text_ctrl(self.size_data['cols'], 1, self.old_size.width)

    def on_cols_down(self, event):
        self.update_text_ctrl(self.size_data['cols'], -1, self.old_size.width)

    def on_rows_up(self, event):
        self.update_text_ctrl(self.size_data['rows'], 1, self.old_size.height)

    def on_rows_down(self, event):
        self.update_text_ctrl(self.size_data['rows'], -1, self.old_size.height)

    # Used by caller to retrieve user chosen size.
    def get_selected_size(self):
        return (self.text_ctrl_value(self.size_data['cols'],
                                     self.old_size.width),
                self.text_ctrl_value(self.size_data['rows'],
                                     self.old_size.height))

# Class encapsulating the screen text and attributes used by the console.
class Text_buffer:
    def __init__(self, backend, default_font):
        # Console Simics object.
        self.backend = backend
        # Screen size as wx.Size.
        self.size = DEFAULT_SCREEN_SIZE
        # Number of scrollback lines.
        self.sb_lines = 0
        # Maximum number of scrollback lines.
        self.max_sb_lines = DEFAULT_MAX_SB_LINES
        # Default colours (fg, bg) as wx.Colour objects.
        self.default_col = None
        # Default text font as a wx.Font object. This font is the basis of
        # the VT100 font attributes such as bold and underline.
        self.default_font = None
        # Screen text as an array of strings, one per line. Each line has length
        # self.size.width, length of array is self.size.height + self.sb_lines
        self.data = None
        # Screen attributes, also as array of lines, dimensions as self.data
        # Each line is an array of 2-tuples (font, colour), each having the
        # same representation as self.default_font and self.default_col.
        self.attrib = None

        # Create initial valid state.
        self.set_default_colours((convert_colour(DEFAULT_FG_COL),
                                  convert_colour(DEFAULT_BG_COL)))
        self.set_default_font(default_font)
        self.reset_screen_data()

    # Character for empty screen.
    def empty_char(self):
        return b' '

    # Attribute for empty screen: default colour and font.
    def empty_attrib(self):
        return [(self.default_font, self.default_col)]

    # Each text line must have the same size: we pad with spaces.
    def empty_text_line(self, width):
        return self.empty_char() * width

    # "Empty" means default colour and font.
    def empty_attrib_line(self, width):
        return self.empty_attrib() * width

    def empty_text_lines(self, width, num_lines):
        return [self.empty_text_line(width)] * num_lines

    def empty_attrib_lines(self, width, num_lines):
        return [self.empty_attrib_line(width)] * num_lines

    def reset_screen_data(self):
        self.data = self.empty_text_lines(
            self.line_len(), self.screen_lines() + self.sb_size())
        self.attrib = self.empty_attrib_lines(self.line_len(), self.length())
        assert len(self.data) == self.screen_lines() + self.sb_size()
        assert len(self.attrib) == len(self.data)
        for i in range(len(self.data)):
            assert len(self.data[i]) == self.line_len()
            assert len(self.attrib[i]) == self.line_len()

    # Create wx.Font objects for variations of given font, corresponding to
    # different attributes that we need.
    def create_fonts(self, font_name, point_size):
        return {x: wx.FFont(
                       point_size, wx.FONTFAMILY_TELETYPE,
                       faceName = font_name, flags = convert_fontflags(x),
                       encoding = wx.FONTENCODING_ISO8859_1)
                for x in range(256)}

    def set_default_font(self, font):
        self.default_font = font
        # Pre-compute fonts for different VT100 attributes.
        self.font_list = self.create_fonts(
            self.default_font.GetFaceName(), self.default_font.GetPointSize())

    def set_default_colours(self, cols):
        self.default_col = (cols[0], cols[1])

    def get_default_colours(self):
        return self.default_col

    # Decode a text_console_colour_t into a wx.Colour
    def decode_colour(self, colour):
        assert colour <= 257
        if colour == simics.Text_Console_Colour_Default_Background:
            return self.default_col[1]
        elif colour == simics.Text_Console_Colour_Default_Foreground:
            return self.default_col[0]
        else:
            return COLOURS[colour]

    # Convert a text_console_colour_t.colour into a corresponding
    # wx.Colour object
    def unpack_colour(self, colour):
        assert len(colour) == 2
        col = colour[0] + 256 * colour[1]
        return self.decode_colour(col)

    # Convert a text_console_attrib_t into the form required by self.attrib
    def convert_attrib(self, attrib):
        return (self.font_list[attrib[0]],
                (self.unpack_colour(attrib[1:3]),
                 self.unpack_colour(attrib[3:5])))

    # Set text in specified rectangle of screen. The rectangle coordinates is
    # relative to the visible screen origin. The data must be a consecutive
    # buffer of characters which supports slicing such as a Python string,
    # i.e. something implementing the Python buffer protocol.
    def set_text(self, rect, data):
        assert not rect.IsEmpty()
        num_written = 0
        for y in range(rect.y + self.sb_size(),
                        rect.y + self.sb_size() + rect.height):
            line = data[num_written : num_written + rect.width]
            assert len(line) == rect.width
            self.data[y] = (self.data[y][:rect.x] + line
                            + self.data[y][rect.x + rect.width:])
            assert len(self.data[y]) == self.line_len()
            num_written += rect.width

    # Set attributes in specified rectangle of screen. The rectangle
    # coordinates is relative to the visible screen origin. The data must be a
    # consecutive buffer of text_console_attrib_t which supports slicing, such
    # as a Python string, i.e. something implementing the Python
    # buffer protocol.
    def set_attrib(self, rect, data):
        assert not rect.IsEmpty()
        num_written = 0
        for y in range(rect.y + self.sb_size(),
                        rect.y + self.sb_size() + rect.height):
            line = data[num_written * ATTRIB_SIZE :
                        (num_written + rect.width) * ATTRIB_SIZE]
            assert len(line) == rect.width * ATTRIB_SIZE
            attrib = [self.convert_attrib(line[i : i + ATTRIB_SIZE])
                      for i in range(0, rect.width * ATTRIB_SIZE, ATTRIB_SIZE)]
            self.attrib[y] = (self.attrib[y][:rect.x] + attrib
                             + self.attrib[y][rect.x + rect.width : ])
            num_written += rect.width
        assert len(self.attrib) == len(self.data)

    # Resize visible screen to given size, as wx.Size object.
    def resize(self, size):
        # Change width, hence also change all scrollback lines.
        if size.width < self.line_len():
            for y in range(len(self.data)):
                self.data[y] = self.data[y][:size.width]
                self.attrib[y] = self.attrib[y][:size.width]
        elif size.width > self.line_len():
            for y in range(len(self.data)):
                # Fill new space with "empty" space.
                self.data[y] += self.empty_text_line(
                    size.width - self.line_len())
                self.attrib[y] += self.empty_attrib_line(
                    size.width - self.line_len())

        # If height changes, we must only modify visible screen, not scrollback.
        if size.height < self.screen_lines():
            # Remove lines at the bottom.
            removed = self.length() - size.height - self.sb_size()
            self.data = self.data[removed:]
            self.attrib = self.attrib[removed:]
        elif size.height > self.screen_lines():
            # Add lines at the bottom.
            added = size.height - self.screen_lines()
            self.data += self.empty_text_lines(size.width, added)
            self.attrib += self.empty_attrib_lines(size.width, added)
        self.size = size
        assert(self.length() == self.screen_lines() + self.sb_size())

    # Number of lines in text buffer, both scrollback and screen.
    def length(self):
        return len(self.data)

    # Number of scrollback lines in text buffer.
    def sb_size(self):
        return self.sb_lines

    # Line lengths in characters.
    def line_len(self):
        return self.size.width

    # Number of lines of console screen.
    def screen_lines(self):
        return self.size.height

    # Return character at specified position (wx.Point or wx.Size)
    # Coordinate system includes scrollback and screen.
    def get_char(self, pos):
        return ensure_text(bytes((self.data[pos.y][pos.x],)))

    # Return actual length of specified line, which must be within
    # the screen range.
    def line_length(self, line):
        if line >= 0 and line < self.length():
            with simics_lock():
                if self.backend and hasattr(self.backend, 'iface'):
                    return self.backend.iface.text_console_backend.line_length(
                        line - self.sb_lines)
        else:
            return 0

    # Return whether or not the specified line wraps onto the next line.
    # The line number must be a line within the screen range.
    def line_wrap(self, line):
        if line >= 0 and line < self.length():
            with simics_lock():
                if self.backend and hasattr(self.backend, 'iface'):
                    return self.backend.iface.text_console_backend.line_wrap(
                        line - self.sb_lines)
        else:
            return False

    # Given two wx.Point or wx.Size defining start and stop of usual terminal
    # style text mark region, return the corresponding substring of the text.
    # start and stop can point to any position within scrollback or screen.
    # Screen data is trimmed to actual line lengths are explicit new line
    # characters are inserted at the end of each non-wrapping line.
    def get_substr(self, start, stop):
        if start.y < stop.y:
            line_len = self.line_length(start.y)
            substr = self.data[start.y][start.x : line_len]
            if not self.line_wrap(start.y):
                substr += b"\n"
            for y in range(start.y + 1, stop.y):
                line_len = self.line_length(y)
                substr += self.data[y][:line_len]
                if not self.line_wrap(y):
                    substr += b"\n"
            line_len = self.line_length(stop.y)
            substr += self.data[stop.y][: min(stop.x + 1, line_len)]
            if stop.x + 1 > line_len:
                substr += b"\n"
        else:
            line_len = self.line_length(stop.y)
            substr = self.data[start.y][start.x : min(stop.x + 1, line_len)]
            if stop.x + 1 > line_len:
                substr += b"\n"
        return substr

    # Given two wx.Point or wx.Size defining top left and bottom right of a
    # rectangle, return the corresponding substring of the text.
    # start and stop can point to any position within scrollback or screen.
    # New line characters are inserted at the end of each rectangle line.
    def get_rect_substr(self, start, stop):
        return b"\n".join(self.data[y][start.x : stop.x + 1]
                          for y in range(start.y, stop.y + 1))

    # Retrieve screen data from specified line, positions start..start+width.
    # Data is returned as a 3-tuple of iterators (text, fonts, colours) where
    # text is string data, fonts are wx.Font objects and colours are 2-tuples
    # (fg, bg) of wx.Colour objects.
    def get_data(self, line, start, width):
        attribs = self.attrib[line][start : start + width]
        return (itertools.islice(self.data[line], start, start + width),
                (attrib[0] for attrib in attribs),
                (attrib[1] for attrib in attribs))

    # Make sure the scrollback is not longer than the specified number of lines.
    def ensure_max_scrollback_size(self, num_lines):
        if num_lines > 0 and self.sb_lines > num_lines:
            removed = self.sb_lines - num_lines
            self.data = self.data[removed:]
            self.attrib = self.attrib[removed:]
            self.sb_lines = num_lines
        assert(len(self.attrib) == self.screen_lines() + self.sb_lines)
        assert(len(self.data) == self.screen_lines() + self.sb_lines)

    def set_max_scrollback_size(self, num_lines):
        self.max_sb_lines = num_lines
        self.ensure_max_scrollback_size(self.max_sb_lines)

    # Make sure scrollback has the specified number of lines.
    def ensure_used_scrollback_size(self, num_lines):
        if self.sb_lines < num_lines:
            text = self.empty_text_lines(self.line_len(),
                                         num_lines - self.sb_lines)
            attrib = self.empty_attrib_lines(self.line_len(),
                                             num_lines - self.sb_lines)
            self.data = text + self.data
            self.attrib = attrib + self.attrib
        elif self.sb_lines > num_lines:
            start = self.sb_lines - num_lines
            self.data = self.data[start:]
            self.attrib = self.attrib[start:]

        self.sb_lines = num_lines

    # Append specified number of empty lines at the end of the screen,
    # implicitly moving lines into the scrollback.
    def append_lines(self, num_lines):
        self.data += self.empty_text_lines(self.line_len(), num_lines)
        self.attrib += self.empty_attrib_lines(self.line_len(), num_lines)
        self.sb_lines += num_lines
        self.ensure_max_scrollback_size(self.max_sb_lines)

    # Replace all text and attribute data: text and attrib must follow the
    # conventions of set_data and set_attrib and must include enough data for
    # the complete scrollback and screen.
    def refresh(self, text, attrib):
        rect = wx.Rect(0, -self.sb_lines, self.line_len(), self.length())
        self.set_text(rect, text)
        self.set_attrib(rect, attrib)

# Class encapsulating the main Simics console GUI behaviour: a panel with a
# scrollbar, handling the communication between frontend and backend, but
# it is not a top window with menus etc.
class Text_console(wx.Panel, simmod.mini_winsome.console_panel.Console_panel):
    def __init__(self, parent, backend):
        with simics_lock():
            wx.Panel.__init__(self, parent)
            # Top-level window.
            self.parent = parent
            # Winsome part of backend, a conf_object_t.
            self.winsome_backend = backend
            if backend and isinstance(backend, simics.conf_object_t):
                # Actual console backend conf_object_t.
                self.backend = simics.SIM_object_parent(self.winsome_backend)
                assert self.backend is not None
                assert self.backend.iface.text_console_backend is not None
            else:
                self.backend = None

            # This panel contains another panel where the drawing is done,
            # and a separate scrollbar object.
            # WANTS_CHARS necessary to obtain all key events.
            self.panel = wx.Panel(self, style = wx.WANTS_CHARS)
            self.scroll = wx.ScrollBar(self, style = wx.SB_VERTICAL)

            # Most events go to the inner panel.
            self.panel.Bind(wx.EVT_CHAR, self.char_input)
            self.panel.Bind(wx.EVT_KEY_DOWN, self.key_down)
            self.panel.Bind(wx.EVT_LEFT_DOWN, self.left_down)
            self.panel.Bind(wx.EVT_LEFT_UP, self.left_up)
            self.panel.Bind(wx.EVT_MOTION, self.mouse_motion)
            self.panel.Bind(wx.EVT_MIDDLE_DOWN, self.middle)
            self.panel.Bind(wx.EVT_LEFT_DCLICK, self.left_dbl_click)
            self.panel.Bind(wx.EVT_PAINT, self.repaint)
            self.panel.Bind(wx.EVT_SIZE, self.on_resize)
            # Events affecting scrollbar must go to other panel.
            self.Bind(wx.EVT_MOUSEWHEEL, self.mouse_wheel)
            self.Bind(wx.EVT_COMMAND_SCROLL, self.on_scroll, self.scroll)

            # Avoid erase background events.
            self.panel.SetBackgroundStyle(wx.BG_STYLE_PAINT)

            # Cursor position in characters.
            self.cursor_pos = wx.Point(0, 0)
            # Current mouse wheel rotation.
            self.mouse_rotation = 0
            # Condition variable which is flagged when there are no threaded
            # console events that are being processed. These events are
            # the ones posted by win_text_console.update_thread
            self.event_cond = threading.Condition()
            # Associated predicate to the condition variable.
            self.processing_events = False

            # Chosen text font, a wx.Font object.
            self.font = None
            # Font size in pixels, a wx.Size object.
            self.font_size = None
            # Pen and brush used for rendering.
            self.pen = None
            self.brush = None
            # wx.Rect defining screen size, in characters.
            self.screen = None
            # wx.Size defining maximum (lower right) character coordinates.
            self.max_coord = None

            self.panel.SetCursor(wx.Cursor(wx.CURSOR_IBEAM))

            # Read default font from prefs
            default_font = self.get_default_font()
            # Initialise text buffer container.
            self.text = Text_buffer(self.backend, default_font)
            # Initialise colours, pen and brush.
            self.set_default_colours(DEFAULT_FG_COL, DEFAULT_BG_COL)
            # Initialise font.
            self.font_setup(default_font)
            # Set scrollbar and initialise screen and max_coord.
            self.on_text_buffer_resize()

            # Initialise super class.
            simmod.mini_winsome.console_panel.Console_panel.__init__(self)
            # Layout panel and scrollbar.
            self.update_window_size()

    ## Window size related functions

    # Update state after text buffer size change.
    def on_text_buffer_resize(self):
        self.set_scrollbar(self.panel.GetSize())
        self.screen = wx.Rect(0, 0, self.text.line_len(), self.text.length())
        self.max_coord = wx.Size(self.text.line_len() - 1,
                                 self.text.length() - 1)

    # Update window max sizes, after text buffer size change.
    def update_max_sizes(self):
        self.set_panel_max_size()
        self.set_max_size()
        self.parent.set_max_size()

    # Set panel max size (e.g. after text buffer size change)
    def set_panel_max_size(self):
        max_height = self.text.length() * self.font_size.height
        self.panel.SetMaxSize(wx.Size(
            self.panel.GetSize().GetWidth(), max_height))

    def set_panel_size(self, size):
        self.panel.SetSize(size)
        self.panel.SetClientSize(size)

    def set_max_size(self):
        size_diff = self.GetSize() - self.panel.GetSize()
        self.parent.SetSizeHints(minW = -1, minH = -1,
                                 maxH = -1, maxW = -1)
        self.SetMaxSize(wx.Size(
            self.GetSize().GetWidth(),
            self.panel.GetMaxSize().GetHeight() + size_diff.GetHeight()))

    # Callback for user window size change.
    # Only vertical size change allowed, restricted by SetMaxSize.
    def on_resize(self, event):
        # Floor to text size.
        text_size = self.pixel_to_text(event.GetSize())
        size = self.text_to_pixel(text_size)
        # Override size from event.
        self.set_panel_size(size)
        # Scroll thumb must be set correctly.
        self.set_scrollbar(size)
        self.refresh_all()
        event.Skip()

    # Set console panel and scroll bar size, and max/min sizes, to facilitate
    # use in a Sizer used by parent window.
    # This must be called after window size change from backend or if the
    # font size changes.
    def update_window_size(self):
        text_size = wx.Size(self.text.line_len(), self.text.screen_lines())
        # Uses current font size.
        size = self.text_to_pixel(text_size)

        # Set sizes of inner panel.
        self.set_panel_size(size)
        self.panel.SetMinSize(size)
        self.set_panel_max_size()
        dc = wx.ClientDC(self.panel)
        dc.Clear()

        # Add inner controls to sizer.
        self.SetSizer(None)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.panel, flag = wx.ALL | wx.EXPAND, border = 2)
        sizer.Add(self.scroll, flag = wx.EXPAND)

        # Must reset max size before layout.
        self.SetMaxSize(wx.Size(-1, -1))
        self.SetSizer(sizer)
        self.Layout()
        self.Fit()

        # Set new max size.
        self.set_max_size()
        self.refresh_all()

    # Resize text buffer, upon window resize from backend.
    def resize_text_buffer(self, width, height):
        self.text.resize(wx.Size(width, height))
        self.on_text_buffer_resize()

    ## Functions required by console_panel super class

    def get_char(self, idx):
        return self.text.get_char(idx)

    def get_text_size(self):
        return self.text.size

    def line_length(self, line):
        return self.text.line_length(line)

    def line_wrap(self, line):
        return self.text.line_wrap(line)

    def get_rect_mark_str(self, start, stop):
        return self.text.get_rect_substr(start, stop)

    def get_line_mark_str(self, start, stop):
        return self.text.get_substr(start, stop)

    def text_to_pixel(self, size):
        return simmod.mini_winsome.console_util.text_to_pixel(
            size, self.font_size.width, self.font_size.height)

    def pixel_to_text(self, size):
        return simmod.mini_winsome.console_util.pixel_to_text(
            size, self.font_size.width, self.font_size.height)

    def refresh_text_rect(self, rect):
        rect.Offset(0, -self.text.sb_size())
        self.refresh(rect)

    ## Scrollbar functions

    # Reset scrollbar to given pixel size, after panel height has been changed
    # or after text buffer length has changed.
    def set_scrollbar(self, size):
        text_size = self.pixel_to_text(size)
        assert self.scroll.IsVertical()
        maxpos = self.text.length()
        thumbsize = max(text_size.height, 1)
        pagesize = text_size.height
        self.scroll.SetScrollbar(maxpos, thumbsize, maxpos, pagesize)

    # Top line in text buffer that is visible on screen, given scroll bar pos.
    def top_visible_screen_line(self):
        return self.scroll.GetThumbPosition()

    # Prepare given DC so that it will start rendering from chosen scroll bar
    # position.
    def prepare_dc(self, dc):
        dc.SetDeviceOrigin(0, -self.top_visible_screen_line()
                           * self.font_size.height)

    # Force scroll bar position to specified line.
    def set_scroll(self, pos):
        self.scroll.SetThumbPosition(pos)
        self.refresh_all()

    # Move scroll bar up or down given lines (-/+)
    def scroll_lines(self, line_diff):
        pos = min(max(self.top_visible_screen_line() + line_diff, 0),
                  self.scroll.GetRange() - 1)
        self.set_scroll(pos)

    def scroll_lineup(self):
        self.scroll_lines(-1)

    def scroll_linedown(self):
        self.scroll_lines(1)

    # Scroll to end, e.g. when user types text.
    def scroll_end(self):
        text_size = self.pixel_to_text(self.panel.GetSize())
        self.set_scroll(max(0, self.text.length() - text_size.height))

    # Event callback for user scrollback change.
    def on_scroll(self, event):
        self.set_scroll(event.GetPosition())
        event.Skip()

    ## Mouse event callbacks

    # EVT_MOUSE_WHEEL callback
    def mouse_wheel(self, event):
        if event.GetWheelAxis() == wx.MOUSE_WHEEL_VERTICAL:
            self.mouse_rotation += event.GetWheelRotation()
            # Make window scroll using mouse wheel.
            if abs(self.mouse_rotation) >= event.GetWheelDelta():
                self.scroll_lines(-self.mouse_rotation // event.GetWheelDelta())
                self.mouse_rotation = 0

    # EVT_MOUSE_MOTION callback
    def mouse_motion(self, event):
        dc = wx.ClientDC(self.panel)
        self.prepare_dc(dc)
        # Handle text marking.
        self.on_mouse_motion(event, dc)

        # Make window scroll while marking text and moving outside screen.
        if event.Dragging() and event.LeftIsDown() and self.drag_started():
            if event.GetPosition().y < 0:
                self.scroll_lineup()
            elif event.GetPosition().y > self.panel.GetSize().GetHeight():
                self.scroll_linedown()

    # EVT_LEFT_DCLICK callback
    def left_dbl_click(self, event):
        dc = wx.ClientDC(self.panel)
        self.prepare_dc(dc)
        # Handle text marking.
        self.on_left_dbl_click(event, dc)

    # EVT_LEFT_DOWN callback
    def left_down(self, event):
        dc = wx.ClientDC(self.panel)
        self.prepare_dc(dc)
        # Handle text marking.
        self.on_left_down(event, dc)
        # Make sure we receive key events
        event.Skip()

    # EVT_LEFT_UP callback
    def left_up(self, event):
        dc = wx.ClientDC(self.panel)
        self.prepare_dc(dc)
        # Handle text marking.
        self.on_left_up(event, dc)
        event.Skip()

    # EVT_MIDDLE_DOWN callback
    def middle(self, event):
        self.parent.paste_from_primary()

    ## Functions required by console_window super class

    # Send string to Simics. Must be run in the Simics thread.
    def string_to_simics(self, text):
        for c in text:
            self.key_to_simics((ord(c), 0))

    # Callback for clipboard paste functions.
    def paste_text(self, text):
        self.scroll_end()
        simics.SIM_thread_safe_callback(self.string_to_simics, text)

    # Callback for menu item.
    def copy_screen(self):
        y = self.top_visible_screen_line()
        box = self.pixel_to_text(self.panel.GetSize())
        box.height = min(self.text.length() - 1, y + box.height - 1)
        box.width = min(self.text.line_len() - 1, box.width - 1)
        simmod.mini_winsome.console_util.set_clipboard_string(
            self.text.get_substr(wx.Size(0, y), box), False)

    # Used by info dialog
    def get_info(self):
        return text_console_commands.get_info(self.backend)

    # Used by status dialog
    def get_status(self):
        return text_console_commands.get_status(self.backend)

    # Callback for user show/hide of console GUI window.
    # Notifies console backend of visibility state.
    def set_visible(self, visible):
        with simics_lock():
            # The console backend may be deleted
            if self.backend and hasattr(self.backend, 'iface'):
                self.backend.iface.text_console_backend.set_visible(visible)

    ## Keyboard input functions

    # Send key to Simics. Must be run in the Simics thread.
    def key_to_simics(self, args):
        if (self.backend and hasattr(self.backend, 'iface')
            and simics.SIM_simics_is_running()):
            self.backend.iface.text_console_backend.input(*args)

    # Send key and modifier to console backend.
    def process_key_stroke(self, key, modifiers):
        # Move to visible and remove mark, following XTerm.
        self.scroll_end()
        self.remove_mark()
        simics.SIM_thread_safe_callback(self.key_to_simics, (key, modifiers))

    # Convert wxPython key modifiers to text_console_modifier_t.
    def simics_modifiers(self, event):
        return ((0, simics.Text_Console_Modifier_Alt)[event.AltDown()
                                                      or event.MetaDown()]
                | (0, simics.Text_Console_Modifier_Ctrl)[event.ControlDown()]
                | [0, simics.Text_Console_Modifier_Shift][event.ShiftDown()])

    # EVT_KEY_DOWN callback
    def key_down(self, event):
        # Handle Shift + PgUp/PgDn as scrollback accelerator keys,
        # following XTerm.
        kc = event.GetKeyCode()
        if event.ShiftDown():
            if kc == wx.WXK_PAGEUP:
                self.scroll_lines(-self.text.screen_lines())
                return
            elif kc == wx.WXK_PAGEDOWN:
                self.scroll_lines(self.text.screen_lines())
                return

        # GetKeyCode in EVT_KEY_DOWN seems to be the only way to distinguish
        # cursor and numpad arrow keys consistently on Windows and Linux.
        code = simmod.mini_winsome.keycodes.special_key(kc)
        if code is not None:
            self.process_key_stroke(code, self.simics_modifiers(event))
        else:
            event.Skip()

    # EVT_CHAR callback
    def char_input(self, event):
        # Ignore non-Latin1 characters.
        if event.GetKeyCode() > 0:
            # Special keys handled by EVT_KEY_DOWN.
            self.process_key_stroke(event.GetKeyCode(),
                                    self.simics_modifiers(event))

    ## Refresh window functions.

    # Refresh rect given in text coords, from top of scrollback.
    def refresh(self, rect):
        start = self.text_to_pixel(wx.Size(rect.x, rect.y))
        size = self.text_to_pixel(wx.Size(rect.width, rect.height))
        screen = wx.Point(start.x, start.y)
        draw_rect = wx.Rect(screen.x, screen.y, size.width, size.height)
        # TODO Avoid refreshing all, to obtain O(1) update.
        self.refresh_all()
        self.panel.RefreshRect(draw_rect, False)

    # Refresh screen rect given in text coords.
    def refresh_screen_coords(self, rect):
        self.refresh(rect)

    # Complete refresh inner text panel (text and scrollback).
    def refresh_all(self):
        self.panel.Refresh(False)

    def refresh_screen_cb(self, arg):
        if self.backend and hasattr(self.backend, 'iface'):
            self.backend.iface.text_console_backend.request_refresh()

    # Query console backend for complete screen and scrollback update.
    # A call to text_console_frontend.refresh_screen should soon follow.
    def refresh_screen(self):
        simics.SIM_thread_safe_callback(self.refresh_screen_cb, None)

    ## Callbacks corresponding to text_console_frontend functions

    # text_console_frontend.set_size
    def resize(self, width, height):
        with simics_lock():
            # Make sure we can move cursor to expected position after resize.
            cursor_diff = self.text.screen_lines() - self.cursor_pos.y
            self.resize_text_buffer(width, height)
            self.cursor_pos = wx.Point(min(self.cursor_pos.x, width - 1),
                                       max(height - cursor_diff, 0))
            self.update_window_size()
            self.parent.update_window_size()

    # text_console_frontend.set_default_colours
    def set_default_colours(self, fg_col, bg_col):
        cols = [convert_colour(col) for col in (fg_col, bg_col)]
        self.text.set_default_colours(cols)
        self.SetBackgroundColour(cols[1])
        self.parent.SetBackgroundColour(cols[1])
        self.pen = wx.Pen(cols[1])
        self.brush = wx.Brush(cols[1])
        # Make sure everything is repainted using new colours.
        self.refresh_screen()

    # text_console_frontend.set_max_scrollback_size
    def set_max_scrollback_size(self, num_lines):
        self.text.set_max_scrollback_size(num_lines)
        self.on_text_buffer_resize()
        self.update_max_sizes()
        self.refresh_all()

    # Replace text console contents.
    # Corresponding to text_console_frontend.refresh_screen
    def refresh_contents(self, screen_text, screen_attrib,
                         sb_text, sb_attrib, sb_lines):
        text = sb_text + screen_text
        attrib = sb_attrib + screen_attrib
        self.text.ensure_used_scrollback_size(sb_lines)
        self.text.refresh(text, attrib)
        self.on_text_buffer_resize()
        self.update_max_sizes()
        self.refresh_all()
        # Immediate paint event.
        self.panel.Update()

    # Replace specified screen rectangle with data and attributes.
    # Corresponding to text_console_frontend.set_contents
    def set_contents(self, left, top, right, bottom, data, attrib):
        rect = wx.Rect(left, top, right - left + 1, bottom - top + 1)
        self.text.set_text(rect, data)
        self.text.set_attrib(rect, attrib)
        self.refresh_screen_coords(rect)
        # Immediate paint event.
        self.panel.Update()

    # Move cursor to specified screen position.
    # Corresponding to text_console_frontend.set_cursor_pos
    def move_cursor(self, x, y):
        new_pos = wx.Point(x, y)
        if new_pos != self.cursor_pos:
            assert new_pos.x < self.text.line_len()
            assert new_pos.y < self.text.screen_lines()
            self.refresh_screen_coords(wx.Rect(
                self.cursor_pos.x, self.cursor_pos.y, 1, 1))
            self.cursor_pos = new_pos
            self.refresh_screen_coords(wx.Rect(
                self.cursor_pos.x, self.cursor_pos.y, 1, 1))

    # Append specified lines with attributes to the bottom of the screen,
    # implicitly scrolling lines up and into the scrollback.
    # Corresponding to text_console_frontend.append_text
    def append_text(self, num_lines, text, attrib):
        # Append empty lines to the text buffer.
        self.text.append_lines(num_lines)
        # Handle text buffer size change.
        self.on_text_buffer_resize()
        self.update_max_sizes()
        self.refresh_all()

        # Replace text at the newly added lines.
        if text is not None and len(text) > 0:
            self.set_contents(
                0, self.text.screen_lines() - num_lines,
                self.text.line_len() - 1, self.text.screen_lines() - 1,
                text, attrib)

    ## Rendering functions

    # Render given text using fonts and colours, at specified character
    # position. Invert flag means flipping foreground and background colours,
    # for use with marked text.
    def draw_text(self, dc, text, font, fg, bg, text_coord, invert):
        dc.SetFont(font)
        if invert:
            dc.SetTextForeground(bg)
            dc.SetTextBackground(fg)
        else:
            dc.SetTextForeground(fg)
            dc.SetTextBackground(bg)

        # Uses current font size, which must match given font.
        start = self.text_to_pixel(text_coord)

        # We only support drawing Latin-1 characters at the moment.
        try:
            output = text.decode("iso-8859-1")
        except ValueError:
            print("Text console GUI: Ignoring non-ISO-8859-1 text", file=sys.stderr)
            output = ''
        dc.DrawText(output, start.x, start.y)

    # Render text console in the specified rectangle, possibly with
    # inverted colours, in character coordinates from the scrollback top.
    def update_text(self, dc, rect, invert):
        dc.SetBackgroundMode(wx.SOLID)
        assert rect.height > 0
        assert self.screen.Union(rect) == self.screen
        last_font = None
        last_fg = None
        last_bg = None

        for y in range(rect.y, rect.y + rect.height):
            # Fetch text and attribute data of current line.
            (data, fonts, colours) = self.text.get_data(y, rect.x, rect.width)
            coord = wx.Size(rect.x, y)
            last_coord = wx.Size(coord.x, coord.y)

            # Accumulate characters until attribute changes, then render.
            text = b''
            for char, font, colour in zip(data, fonts, colours):
                if (last_font != font
                    or last_fg != colour[0] or last_bg != colour[1]):
                    if len(text) > 0:
                        self.draw_text(dc, text, last_font,
                                       last_fg, last_bg, last_coord, invert)
                        text = b''
                        last_coord = wx.Size(coord.x, coord.y)
                    last_fg = colour[0]
                    last_bg = colour[1]
                    last_font = font
                text += bytes((char,))
                coord.IncBy(1, 0)
            if len(text) > 0:
                self.draw_text(dc, text, last_font,
                               last_fg, last_bg, last_coord, invert)

    # Render rectangle marked text.
    def draw_rect_mark(self, dc, mark_start, mark_stop):
        rect = simmod.mini_winsome.console_util.get_rect_mark_coords(mark_start, mark_stop)
        if not rect.IsEmpty():
            self.update_text(dc, rect, True)

    # Render text console marked text.
    def draw_mark(self, dc, mark_start, mark_stop):
        (start, stop) = simmod.mini_winsome.console_util.get_mark_coords(
            mark_start, mark_stop, self.max_coord)
        if start.y < stop.y:
            rect = wx.Rect(start.x, start.y, self.text.line_len() - start.x, 1)
            self.update_text(dc, rect, True)
            if start.y < stop.y - 1:
                rect = wx.Rect(0, start.y + 1, self.text.line_len(),
                               stop.y - start.y - 1)
                self.update_text(dc, rect, True)
            rect = wx.Rect(0, stop.y, stop.x + 1, 1)
            self.update_text(dc, rect, True)
        else:
            rect = wx.Rect(start.x, start.y, stop.x - start.x + 1, 1)
            self.update_text(dc, rect, True)

    # Render given screen rectangle.
    def update_screen(self, dc, rect):
        dc.SetPen(self.pen)
        dc.SetBrush(self.brush)
        self.update_text(dc, rect, False)
        if self.has_mark():
            if self.rectangle_mark:
                self.draw_rect_mark(dc, self.mark_start, self.mark_stop)
            else:
                self.draw_mark(dc, self.mark_start, self.mark_stop)
        self.update_cursor(dc)

    # Determine if given character position is marked.
    def in_selection(self, x, y):
        if self.has_mark():
            if self.rectangle_mark:
                rect = simmod.mini_winsome.console_util.get_rect_mark_coords(
                    self.mark_start, self.mark_stop)
                return rect.Contains(x, y)
            else:
                (start, stop) = simmod.mini_winsome.console_util.get_mark_coords(
                    self.mark_start, self.mark_stop, self.max_coord)
                if start.y < stop.y:
                    return ((y == start.y and x >= start.x)
                            or (y == stop.y and x <= stop.x)
                            or (y > start.y and y < stop.y))
                else:
                    return (y == start.y and x >= start.x and x <= stop.x)
        else:
            return False

    # Render cursor.
    def update_cursor(self, dc):
        pos = wx.Size(self.cursor_pos.x, self.cursor_pos.y)
        # Convert from visible screen coordinates.
        pos.IncBy(0, self.text.sb_size())
        selected_cursor = self.in_selection(pos.x, pos.y)
        # Double inversion if cursor is selected.
        self.update_text(dc, wx.Rect(pos.x, pos.y, 1, 1), not selected_cursor)

    # EVT_PAINT callback
    def repaint(self, event):
        # On Windows we must use double buffering.
        dc = wx.AutoBufferedPaintDC(self.panel)
        # Render visible part, defined by scrollbar.
        self.prepare_dc(dc)

        # Do not render hidden part of window.
        region = self.panel.GetUpdateRegion()
        rects = wx.RegionIterator(region)
        while (rects.HaveRects()):
            # Dirty rectangle, convert to text coordinates.
            rect = rects.GetRect()
            start = wx.Point(rect.x, rect.y)
            size = wx.Size(rect.width, rect.height)
            size.DecTo(self.panel.GetSize())
            box = self.pixel_to_text(size)
            top = self.pixel_to_text(start)
            # Convert from screen coordinate to text buffer coordinates.
            top.y += self.top_visible_screen_line()
            left = min(self.text.line_len() - 1, top.x)
            top = min(self.text.length() - 1, top.y)
            right = min(self.text.line_len() - 1, left + box.width + 1)
            bottom = min(self.text.length() - 1, top + box.height + 1)
            # Rect now given in text coords, screen + used scrollback
            text_box = wx.Rect(left, top, right - left + 1, bottom - top + 1)
            if text_box.height > 0:
                self.update_screen(dc, text_box)
            rects.Next()

    ## Text font/colour functions

    # Set specified text font.
    def font_setup(self, font):
        self.font = font
        self.text.set_default_font(self.font)
        dc = wx.ScreenDC()
        dc.SetFont(font)
        (font_width, font_height) = dc.GetTextExtent('M')
        self.font_size = wx.Size(font_width, font_height)

    # If given font is fixed size, update text console and update window sizes.
    # Otherwise return False.
    def set_font(self, font):
        dc = wx.ScreenDC()
        dc.SetFont(font)
        if (font.IsFixedWidth()
            and dc.GetTextExtent('M') == dc.GetTextExtent('i')):
            self.font_setup(font)
            self.set_default_font(font)
            self.update_window_size()
            self.parent.update_window_size()
            # Make sure everything is repainted using new font.
            self.refresh_screen()
            return True
        else:
            return False

    # Save font as default font in preferences.
    def set_default_font(self, font):
        with simics_lock():
            prefs = simics.SIM_get_object("prefs")
            prefs.iface.preference.set_preference_for_module_key(
                [font.GetFaceName(), font.GetPointSize()],
                "text-console", "default_font")

    # Return default font from preferences.
    def get_default_font(self):
        prefs = simics.SIM_get_object("prefs")
        try:
            font_data = prefs.iface.preference.get_preference_for_module_key(
                "text-console", "default_font")
        except simics.SimExc_Attribute:
            from simmod.mini_winsome.win_target_consoles import get_prefs_tt_font
            return font_from_name(get_prefs_tt_font(self))
        return wx.FFont(font_data[1], wx.FONTFAMILY_TELETYPE,
                        faceName = font_data[0])

    def get_default_fg(self):
        return self.text.get_default_colours()[0]

    def get_default_bg(self):
        return self.text.get_default_colours()[1]

    def post_message_event(self, update, args):
        with self.event_cond:
            self.processing_events = True
            simmod.mini_winsome.win_main.post_text_console_event(
                update, (self,) + args)
            while self.processing_events:
                self.event_cond.wait()

# Class encapsulating the top-level console GUI window, with menus etc.
class Text_console_window(wx.Frame, simmod.mini_winsome.console_window.Console_window):
    def __init__(self, parent, backend, handle, title):
        # Text console size change is strictly controlled, hence no maximise.
        if backend and isinstance(backend, simics.conf_object_t):
            console = simics.SIM_object_parent(backend)
            name = console.name
        else:
            name = ""

        wx.Frame.__init__(
            self, parent, wx.ID_ANY, title = title, name = name,
            style = (wx.DEFAULT_FRAME_STYLE & ~wx.MAXIMIZE_BOX))

        # Actual text console, a wx.Panel.
        self.console = Text_console(self, backend)
        # Super class that takes care of some menus.
        simmod.mini_winsome.console_window.Console_window.__init__(
            self, parent, handle, self.console)

        # Set up Settings menu
        self.settings_menu = wx.Menu()
        font_id = wx.Window.NewControlId()
        size_id = wx.Window.NewControlId()
        fg_colour_id = wx.Window.NewControlId()
        bg_colour_id = wx.Window.NewControlId()
        self.settings_menu.Append(font_id, "Select font...")
        self.settings_menu.Append(size_id, "Change screen size...")
        self.settings_menu.Append(fg_colour_id, "Change foreground colour...")
        self.settings_menu.Append(bg_colour_id, "Change background colour...")
        self.menubar.Append(self.settings_menu, "Settings")
        self.Bind(wx.EVT_MENU, self.on_select_font, None, font_id)
        self.Bind(wx.EVT_MENU, self.on_change_size, None, size_id)
        self.Bind(wx.EVT_MENU, self.on_change_fg, None, fg_colour_id)
        self.Bind(wx.EVT_MENU, self.on_change_bg, None, bg_colour_id)

        self.Bind(wx.EVT_SET_FOCUS, self.set_console_focus)

        # Will console be opened automatically if it is the only one?
        self.enable_auto_show = True

        self.set_icon('open-idle')

    def set_console_focus(self, event):
        self.console.SetFocus()

    ## Text colour functions

    # Notify backend about text colour change.
    def change_text_colour(self, fg, bg):
        console = self.console
        # A call to text_console_frontend.set_default_colours will follow.
        with simics_lock():
            if console.backend and hasattr(console.backend, 'iface'):
                console.backend.iface.text_console_backend.set_default_colours(
                    fg.GetRGB(), bg.GetRGB())

    # Use standard colour dialog to let user choose colour.
    def change_colour_dialog(self, col, title):
        data = wx.ColourData()
        data.SetColour(col)
        dialog = wx.ColourDialog(self, data)
        dialog.SetTitle(title)
        res = dialog.ShowModal()
        if res == wx.ID_OK:
            return dialog.GetColourData().GetColour()
        else:
            return None

    # Menu item callback.
    def on_change_fg(self, event):
        fg = self.change_colour_dialog(self.console.get_default_fg(),
                                       "Choose foreground colour")
        if fg is not None:
            self.change_text_colour(fg, self.console.get_default_bg())

    # Menu item callback.
    def on_change_bg(self, event):
        bg = self.change_colour_dialog(self.console.get_default_bg(),
                                       "Choose background colour")
        if bg is not None:
            self.change_text_colour(self.console.get_default_fg(), bg)

    # Menu item callback.
    def on_select_font(self, event):
        # We only want fixed width fonts.
        fontdata = wx.FontData()
        fontdata.SetInitialFont(self.console.font)
        fontdata.SetAllowSymbols(False)
        fontdata.EnableEffects(False)

        # Loop until an allowed font was chosen or Cancel was pressed.
        while True:
            dlg = wx.FontDialog(self, fontdata)
            res = dlg.ShowModal()

            if res == wx.ID_OK:
                ok = self.console.set_font(dlg.GetFontData().GetChosenFont())
                if not ok:
                    dialog = wx.MessageDialog(
                        self, "The selected font does not have fixed width.",
                        style = wx.OK | wx.ICON_ERROR | wx.CENTRE)
                    dialog.SetOKLabel("Try again")
                    dialog.ShowModal()
                    dialog.Destroy()
                else:
                    break
            else:
                break
        dlg.Destroy()

    # Function required by Console_window super class.
    def icon_filenames(self):
        return {'closed-idle': "txt-closed-idle.png",
                'closed-output': "txt-closed-output.png",
                'open-idle': "txt-open-idle.png",
                'open-output': "txt-open-output.png"}

    ## Window size functions

    # Menu item callback.
    def on_change_size(self, event):
        # Display dialog with current size.
        console = self.console
        dialog = Size_dialog(self, console.get_text_size())
        res = dialog.ShowModal()
        if res == wx.ID_OK:
            # Inform backend about new size.
            # A call to text_console_frontend.set_size will follow.
            size = dialog.get_selected_size()
            with simics_lock():
                if console.backend and hasattr(console.backend, 'iface'):
                    console.backend.iface.text_console_backend.set_size(
                        size[0], size[1])
        dialog.Destroy()

    def update_window_size(self):
        self.SetSizer(None)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.console, flag = wx.EXPAND, proportion = 1)
        self.SetMaxSize(wx.Size(-1, -1))
        self.SetSizerAndFit(sizer)
        self.set_max_size()

    def set_max_size(self):
        size_diff = self.GetSize() - self.console.GetSize()
        self.SetMinSize(self.GetSize())
        self.Fit()
        self.SetMaxSize(wx.Size(
            self.GetSize().GetWidth(),
            self.console.GetMaxSize().GetHeight() + size_diff.GetHeight()))
