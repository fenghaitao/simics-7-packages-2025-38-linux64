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


from comp import StandardConnectorComponent
from comp import SimpleConfigAttribute, SimpleAttribute
from connectors import StandardConnector
from simics import Sim_Attr_Required, Sim_Attr_Optional, Sim_Attr_Pseudo
from simics import Sim_Set_Ok, Sim_Set_Illegal_Value
from simics import Sim_Connector_Direction_Up
from simics import SIM_is_restoring_state
import itertools
import re

# These all come from the usual rgb.txt.
named_colors = {
    'alice blue':             0xf0f8ff,
    'aliceblue':              0xf0f8ff,
    'antique white':          0xfaebd7,
    'antiquewhite':           0xfaebd7,
    'antiquewhite1':          0xffefdb,
    'antiquewhite2':          0xeedfcc,
    'antiquewhite3':          0xcdc0b0,
    'antiquewhite4':          0x8b8378,
    'aquamarine':             0x7fffd4,
    'aquamarine1':            0x7fffd4,
    'aquamarine2':            0x76eec6,
    'aquamarine3':            0x66cdaa,
    'aquamarine4':            0x458b74,
    'azure':                  0xf0ffff,
    'azure1':                 0xf0ffff,
    'azure2':                 0xe0eeee,
    'azure3':                 0xc1cdcd,
    'azure4':                 0x838b8b,
    'beige':                  0xf5f5dc,
    'bisque':                 0xffe4c4,
    'bisque1':                0xffe4c4,
    'bisque2':                0xeed5b7,
    'bisque3':                0xcdb79e,
    'bisque4':                0x8b7d6b,
    'black':                  0x000000,
    'blanched almond':        0xffebcd,
    'blanchedalmond':         0xffebcd,
    'blue':                   0x0000ff,
    'blue violet':            0x8a2be2,
    'blue1':                  0x0000ff,
    'blue2':                  0x0000ee,
    'blue3':                  0x0000cd,
    'blue4':                  0x00008b,
    'blueviolet':             0x8a2be2,
    'brown':                  0xa52a2a,
    'brown1':                 0xff4040,
    'brown2':                 0xee3b3b,
    'brown3':                 0xcd3333,
    'brown4':                 0x8b2323,
    'burlywood':              0xdeb887,
    'burlywood1':             0xffd39b,
    'burlywood2':             0xeec591,
    'burlywood3':             0xcdaa7d,
    'burlywood4':             0x8b7355,
    'cadet blue':             0x5f9ea0,
    'cadetblue':              0x5f9ea0,
    'cadetblue1':             0x98f5ff,
    'cadetblue2':             0x8ee5ee,
    'cadetblue3':             0x7ac5cd,
    'cadetblue4':             0x53868b,
    'chartreuse':             0x7fff00,
    'chartreuse1':            0x7fff00,
    'chartreuse2':            0x76ee00,
    'chartreuse3':            0x66cd00,
    'chartreuse4':            0x458b00,
    'chocolate':              0xd2691e,
    'chocolate1':             0xff7f24,
    'chocolate2':             0xee7621,
    'chocolate3':             0xcd661d,
    'chocolate4':             0x8b4513,
    'coral':                  0xff7f50,
    'coral1':                 0xff7256,
    'coral2':                 0xee6a50,
    'coral3':                 0xcd5b45,
    'coral4':                 0x8b3e2f,
    'cornflower blue':        0x6495ed,
    'cornflowerblue':         0x6495ed,
    'cornsilk':               0xfff8dc,
    'cornsilk1':              0xfff8dc,
    'cornsilk2':              0xeee8cd,
    'cornsilk3':              0xcdc8b1,
    'cornsilk4':              0x8b8878,
    'cyan':                   0x00ffff,
    'cyan1':                  0x00ffff,
    'cyan2':                  0x00eeee,
    'cyan3':                  0x00cdcd,
    'cyan4':                  0x008b8b,
    'dark blue':              0x00008b,
    'dark cyan':              0x008b8b,
    'dark goldenrod':         0xb8860b,
    'dark gray':              0xa9a9a9,
    'dark green':             0x006400,
    'dark grey':              0xa9a9a9,
    'dark khaki':             0xbdb76b,
    'dark magenta':           0x8b008b,
    'dark olive green':       0x556b2f,
    'dark orange':            0xff8c00,
    'dark orchid':            0x9932cc,
    'dark red':               0x8b0000,
    'dark salmon':            0xe9967a,
    'dark sea green':         0x8fbc8f,
    'dark slate blue':        0x483d8b,
    'dark slate gray':        0x2f4f4f,
    'dark slate grey':        0x2f4f4f,
    'dark turquoise':         0x00ced1,
    'dark violet':            0x9400d3,
    'darkblue':               0x00008b,
    'darkcyan':               0x008b8b,
    'darkgoldenrod':          0xb8860b,
    'darkgoldenrod1':         0xffb90f,
    'darkgoldenrod2':         0xeead0e,
    'darkgoldenrod3':         0xcd950c,
    'darkgoldenrod4':         0x8b6508,
    'darkgray':               0xa9a9a9,
    'darkgreen':              0x006400,
    'darkgrey':               0xa9a9a9,
    'darkkhaki':              0xbdb76b,
    'darkmagenta':            0x8b008b,
    'darkolivegreen':         0x556b2f,
    'darkolivegreen1':        0xcaff70,
    'darkolivegreen2':        0xbcee68,
    'darkolivegreen3':        0xa2cd5a,
    'darkolivegreen4':        0x6e8b3d,
    'darkorange':             0xff8c00,
    'darkorange1':            0xff7f00,
    'darkorange2':            0xee7600,
    'darkorange3':            0xcd6600,
    'darkorange4':            0x8b4500,
    'darkorchid':             0x9932cc,
    'darkorchid1':            0xbf3eff,
    'darkorchid2':            0xb23aee,
    'darkorchid3':            0x9a32cd,
    'darkorchid4':            0x68228b,
    'darkred':                0x8b0000,
    'darksalmon':             0xe9967a,
    'darkseagreen':           0x8fbc8f,
    'darkseagreen1':          0xc1ffc1,
    'darkseagreen2':          0xb4eeb4,
    'darkseagreen3':          0x9bcd9b,
    'darkseagreen4':          0x698b69,
    'darkslateblue':          0x483d8b,
    'darkslategray':          0x2f4f4f,
    'darkslategray1':         0x97ffff,
    'darkslategray2':         0x8deeee,
    'darkslategray3':         0x79cdcd,
    'darkslategray4':         0x528b8b,
    'darkslategrey':          0x2f4f4f,
    'darkturquoise':          0x00ced1,
    'darkviolet':             0x9400d3,
    'deep pink':              0xff1493,
    'deep sky blue':          0x00bfff,
    'deeppink':               0xff1493,
    'deeppink1':              0xff1493,
    'deeppink2':              0xee1289,
    'deeppink3':              0xcd1076,
    'deeppink4':              0x8b0a50,
    'deepskyblue':            0x00bfff,
    'deepskyblue1':           0x00bfff,
    'deepskyblue2':           0x00b2ee,
    'deepskyblue3':           0x009acd,
    'deepskyblue4':           0x00688b,
    'dim gray':               0x696969,
    'dim grey':               0x696969,
    'dimgray':                0x696969,
    'dimgrey':                0x696969,
    'dodger blue':            0x1e90ff,
    'dodgerblue':             0x1e90ff,
    'dodgerblue1':            0x1e90ff,
    'dodgerblue2':            0x1c86ee,
    'dodgerblue3':            0x1874cd,
    'dodgerblue4':            0x104e8b,
    'firebrick':              0xb22222,
    'firebrick1':             0xff3030,
    'firebrick2':             0xee2c2c,
    'firebrick3':             0xcd2626,
    'firebrick4':             0x8b1a1a,
    'floral white':           0xfffaf0,
    'floralwhite':            0xfffaf0,
    'forest green':           0x228b22,
    'forestgreen':            0x228b22,
    'gainsboro':              0xdcdcdc,
    'ghost white':            0xf8f8ff,
    'ghostwhite':             0xf8f8ff,
    'gold':                   0xffd700,
    'gold1':                  0xffd700,
    'gold2':                  0xeec900,
    'gold3':                  0xcdad00,
    'gold4':                  0x8b7500,
    'goldenrod':              0xdaa520,
    'goldenrod1':             0xffc125,
    'goldenrod2':             0xeeb422,
    'goldenrod3':             0xcd9b1d,
    'goldenrod4':             0x8b6914,
    'gray':                   0xbebebe,
    'gray0':                  0x000000,
    'gray1':                  0x030303,
    'gray10':                 0x1a1a1a,
    'gray100':                0xffffff,
    'gray11':                 0x1c1c1c,
    'gray12':                 0x1f1f1f,
    'gray13':                 0x212121,
    'gray14':                 0x242424,
    'gray15':                 0x262626,
    'gray16':                 0x292929,
    'gray17':                 0x2b2b2b,
    'gray18':                 0x2e2e2e,
    'gray19':                 0x303030,
    'gray2':                  0x050505,
    'gray20':                 0x333333,
    'gray21':                 0x363636,
    'gray22':                 0x383838,
    'gray23':                 0x3b3b3b,
    'gray24':                 0x3d3d3d,
    'gray25':                 0x404040,
    'gray26':                 0x424242,
    'gray27':                 0x454545,
    'gray28':                 0x474747,
    'gray29':                 0x4a4a4a,
    'gray3':                  0x080808,
    'gray30':                 0x4d4d4d,
    'gray31':                 0x4f4f4f,
    'gray32':                 0x525252,
    'gray33':                 0x545454,
    'gray34':                 0x575757,
    'gray35':                 0x595959,
    'gray36':                 0x5c5c5c,
    'gray37':                 0x5e5e5e,
    'gray38':                 0x616161,
    'gray39':                 0x636363,
    'gray4':                  0x0a0a0a,
    'gray40':                 0x666666,
    'gray41':                 0x696969,
    'gray42':                 0x6b6b6b,
    'gray43':                 0x6e6e6e,
    'gray44':                 0x707070,
    'gray45':                 0x737373,
    'gray46':                 0x757575,
    'gray47':                 0x787878,
    'gray48':                 0x7a7a7a,
    'gray49':                 0x7d7d7d,
    'gray5':                  0x0d0d0d,
    'gray50':                 0x7f7f7f,
    'gray51':                 0x828282,
    'gray52':                 0x858585,
    'gray53':                 0x878787,
    'gray54':                 0x8a8a8a,
    'gray55':                 0x8c8c8c,
    'gray56':                 0x8f8f8f,
    'gray57':                 0x919191,
    'gray58':                 0x949494,
    'gray59':                 0x969696,
    'gray6':                  0x0f0f0f,
    'gray60':                 0x999999,
    'gray61':                 0x9c9c9c,
    'gray62':                 0x9e9e9e,
    'gray63':                 0xa1a1a1,
    'gray64':                 0xa3a3a3,
    'gray65':                 0xa6a6a6,
    'gray66':                 0xa8a8a8,
    'gray67':                 0xababab,
    'gray68':                 0xadadad,
    'gray69':                 0xb0b0b0,
    'gray7':                  0x121212,
    'gray70':                 0xb3b3b3,
    'gray71':                 0xb5b5b5,
    'gray72':                 0xb8b8b8,
    'gray73':                 0xbababa,
    'gray74':                 0xbdbdbd,
    'gray75':                 0xbfbfbf,
    'gray76':                 0xc2c2c2,
    'gray77':                 0xc4c4c4,
    'gray78':                 0xc7c7c7,
    'gray79':                 0xc9c9c9,
    'gray8':                  0x141414,
    'gray80':                 0xcccccc,
    'gray81':                 0xcfcfcf,
    'gray82':                 0xd1d1d1,
    'gray83':                 0xd4d4d4,
    'gray84':                 0xd6d6d6,
    'gray85':                 0xd9d9d9,
    'gray86':                 0xdbdbdb,
    'gray87':                 0xdedede,
    'gray88':                 0xe0e0e0,
    'gray89':                 0xe3e3e3,
    'gray9':                  0x171717,
    'gray90':                 0xe5e5e5,
    'gray91':                 0xe8e8e8,
    'gray92':                 0xebebeb,
    'gray93':                 0xededed,
    'gray94':                 0xf0f0f0,
    'gray95':                 0xf2f2f2,
    'gray96':                 0xf5f5f5,
    'gray97':                 0xf7f7f7,
    'gray98':                 0xfafafa,
    'gray99':                 0xfcfcfc,
    'green':                  0x00ff00,
    'green yellow':           0xadff2f,
    'green1':                 0x00ff00,
    'green2':                 0x00ee00,
    'green3':                 0x00cd00,
    'green4':                 0x008b00,
    'greenyellow':            0xadff2f,
    'grey':                   0xbebebe,
    'grey0':                  0x000000,
    'grey1':                  0x030303,
    'grey10':                 0x1a1a1a,
    'grey100':                0xffffff,
    'grey11':                 0x1c1c1c,
    'grey12':                 0x1f1f1f,
    'grey13':                 0x212121,
    'grey14':                 0x242424,
    'grey15':                 0x262626,
    'grey16':                 0x292929,
    'grey17':                 0x2b2b2b,
    'grey18':                 0x2e2e2e,
    'grey19':                 0x303030,
    'grey2':                  0x050505,
    'grey20':                 0x333333,
    'grey21':                 0x363636,
    'grey22':                 0x383838,
    'grey23':                 0x3b3b3b,
    'grey24':                 0x3d3d3d,
    'grey25':                 0x404040,
    'grey26':                 0x424242,
    'grey27':                 0x454545,
    'grey28':                 0x474747,
    'grey29':                 0x4a4a4a,
    'grey3':                  0x080808,
    'grey30':                 0x4d4d4d,
    'grey31':                 0x4f4f4f,
    'grey32':                 0x525252,
    'grey33':                 0x545454,
    'grey34':                 0x575757,
    'grey35':                 0x595959,
    'grey36':                 0x5c5c5c,
    'grey37':                 0x5e5e5e,
    'grey38':                 0x616161,
    'grey39':                 0x636363,
    'grey4':                  0x0a0a0a,
    'grey40':                 0x666666,
    'grey41':                 0x696969,
    'grey42':                 0x6b6b6b,
    'grey43':                 0x6e6e6e,
    'grey44':                 0x707070,
    'grey45':                 0x737373,
    'grey46':                 0x757575,
    'grey47':                 0x787878,
    'grey48':                 0x7a7a7a,
    'grey49':                 0x7d7d7d,
    'grey5':                  0x0d0d0d,
    'grey50':                 0x7f7f7f,
    'grey51':                 0x828282,
    'grey52':                 0x858585,
    'grey53':                 0x878787,
    'grey54':                 0x8a8a8a,
    'grey55':                 0x8c8c8c,
    'grey56':                 0x8f8f8f,
    'grey57':                 0x919191,
    'grey58':                 0x949494,
    'grey59':                 0x969696,
    'grey6':                  0x0f0f0f,
    'grey60':                 0x999999,
    'grey61':                 0x9c9c9c,
    'grey62':                 0x9e9e9e,
    'grey63':                 0xa1a1a1,
    'grey64':                 0xa3a3a3,
    'grey65':                 0xa6a6a6,
    'grey66':                 0xa8a8a8,
    'grey67':                 0xababab,
    'grey68':                 0xadadad,
    'grey69':                 0xb0b0b0,
    'grey7':                  0x121212,
    'grey70':                 0xb3b3b3,
    'grey71':                 0xb5b5b5,
    'grey72':                 0xb8b8b8,
    'grey73':                 0xbababa,
    'grey74':                 0xbdbdbd,
    'grey75':                 0xbfbfbf,
    'grey76':                 0xc2c2c2,
    'grey77':                 0xc4c4c4,
    'grey78':                 0xc7c7c7,
    'grey79':                 0xc9c9c9,
    'grey8':                  0x141414,
    'grey80':                 0xcccccc,
    'grey81':                 0xcfcfcf,
    'grey82':                 0xd1d1d1,
    'grey83':                 0xd4d4d4,
    'grey84':                 0xd6d6d6,
    'grey85':                 0xd9d9d9,
    'grey86':                 0xdbdbdb,
    'grey87':                 0xdedede,
    'grey88':                 0xe0e0e0,
    'grey89':                 0xe3e3e3,
    'grey9':                  0x171717,
    'grey90':                 0xe5e5e5,
    'grey91':                 0xe8e8e8,
    'grey92':                 0xebebeb,
    'grey93':                 0xededed,
    'grey94':                 0xf0f0f0,
    'grey95':                 0xf2f2f2,
    'grey96':                 0xf5f5f5,
    'grey97':                 0xf7f7f7,
    'grey98':                 0xfafafa,
    'grey99':                 0xfcfcfc,
    'honeydew':               0xf0fff0,
    'honeydew1':              0xf0fff0,
    'honeydew2':              0xe0eee0,
    'honeydew3':              0xc1cdc1,
    'honeydew4':              0x838b83,
    'hot pink':               0xff69b4,
    'hotpink':                0xff69b4,
    'hotpink1':               0xff6eb4,
    'hotpink2':               0xee6aa7,
    'hotpink3':               0xcd6090,
    'hotpink4':               0x8b3a62,
    'indian red':             0xcd5c5c,
    'indianred':              0xcd5c5c,
    'indianred1':             0xff6a6a,
    'indianred2':             0xee6363,
    'indianred3':             0xcd5555,
    'indianred4':             0x8b3a3a,
    'ivory':                  0xfffff0,
    'ivory1':                 0xfffff0,
    'ivory2':                 0xeeeee0,
    'ivory3':                 0xcdcdc1,
    'ivory4':                 0x8b8b83,
    'khaki':                  0xf0e68c,
    'khaki1':                 0xfff68f,
    'khaki2':                 0xeee685,
    'khaki3':                 0xcdc673,
    'khaki4':                 0x8b864e,
    'lavender':               0xe6e6fa,
    'lavender blush':         0xfff0f5,
    'lavenderblush':          0xfff0f5,
    'lavenderblush1':         0xfff0f5,
    'lavenderblush2':         0xeee0e5,
    'lavenderblush3':         0xcdc1c5,
    'lavenderblush4':         0x8b8386,
    'lawn green':             0x7cfc00,
    'lawngreen':              0x7cfc00,
    'lemon chiffon':          0xfffacd,
    'lemonchiffon':           0xfffacd,
    'lemonchiffon1':          0xfffacd,
    'lemonchiffon2':          0xeee9bf,
    'lemonchiffon3':          0xcdc9a5,
    'lemonchiffon4':          0x8b8970,
    'light blue':             0xadd8e6,
    'light coral':            0xf08080,
    'light cyan':             0xe0ffff,
    'light goldenrod':        0xeedd82,
    'light goldenrod yellow': 0xfafad2,
    'light gray':             0xd3d3d3,
    'light green':            0x90ee90,
    'light grey':             0xd3d3d3,
    'light pink':             0xffb6c1,
    'light salmon':           0xffa07a,
    'light sea green':        0x20b2aa,
    'light sky blue':         0x87cefa,
    'light slate blue':       0x8470ff,
    'light slate gray':       0x778899,
    'light slate grey':       0x778899,
    'light steel blue':       0xb0c4de,
    'light yellow':           0xffffe0,
    'lightblue':              0xadd8e6,
    'lightblue1':             0xbfefff,
    'lightblue2':             0xb2dfee,
    'lightblue3':             0x9ac0cd,
    'lightblue4':             0x68838b,
    'lightcoral':             0xf08080,
    'lightcyan':              0xe0ffff,
    'lightcyan1':             0xe0ffff,
    'lightcyan2':             0xd1eeee,
    'lightcyan3':             0xb4cdcd,
    'lightcyan4':             0x7a8b8b,
    'lightgoldenrod':         0xeedd82,
    'lightgoldenrod1':        0xffec8b,
    'lightgoldenrod2':        0xeedc82,
    'lightgoldenrod3':        0xcdbe70,
    'lightgoldenrod4':        0x8b814c,
    'lightgoldenrodyellow':   0xfafad2,
    'lightgray':              0xd3d3d3,
    'lightgreen':             0x90ee90,
    'lightgrey':              0xd3d3d3,
    'lightpink':              0xffb6c1,
    'lightpink1':             0xffaeb9,
    'lightpink2':             0xeea2ad,
    'lightpink3':             0xcd8c95,
    'lightpink4':             0x8b5f65,
    'lightsalmon':            0xffa07a,
    'lightsalmon1':           0xffa07a,
    'lightsalmon2':           0xee9572,
    'lightsalmon3':           0xcd8162,
    'lightsalmon4':           0x8b5742,
    'lightseagreen':          0x20b2aa,
    'lightskyblue':           0x87cefa,
    'lightskyblue1':          0xb0e2ff,
    'lightskyblue2':          0xa4d3ee,
    'lightskyblue3':          0x8db6cd,
    'lightskyblue4':          0x607b8b,
    'lightslateblue':         0x8470ff,
    'lightslategray':         0x778899,
    'lightslategrey':         0x778899,
    'lightsteelblue':         0xb0c4de,
    'lightsteelblue1':        0xcae1ff,
    'lightsteelblue2':        0xbcd2ee,
    'lightsteelblue3':        0xa2b5cd,
    'lightsteelblue4':        0x6e7b8b,
    'lightyellow':            0xffffe0,
    'lightyellow1':           0xffffe0,
    'lightyellow2':           0xeeeed1,
    'lightyellow3':           0xcdcdb4,
    'lightyellow4':           0x8b8b7a,
    'lime green':             0x32cd32,
    'limegreen':              0x32cd32,
    'linen':                  0xfaf0e6,
    'magenta':                0xff00ff,
    'magenta1':               0xff00ff,
    'magenta2':               0xee00ee,
    'magenta3':               0xcd00cd,
    'magenta4':               0x8b008b,
    'maroon':                 0xb03060,
    'maroon1':                0xff34b3,
    'maroon2':                0xee30a7,
    'maroon3':                0xcd2990,
    'maroon4':                0x8b1c62,
    'medium aquamarine':      0x66cdaa,
    'medium blue':            0x0000cd,
    'medium orchid':          0xba55d3,
    'medium purple':          0x9370db,
    'medium sea green':       0x3cb371,
    'medium slate blue':      0x7b68ee,
    'medium spring green':    0x00fa9a,
    'medium turquoise':       0x48d1cc,
    'medium violet red':      0xc71585,
    'mediumaquamarine':       0x66cdaa,
    'mediumblue':             0x0000cd,
    'mediumorchid':           0xba55d3,
    'mediumorchid1':          0xe066ff,
    'mediumorchid2':          0xd15fee,
    'mediumorchid3':          0xb452cd,
    'mediumorchid4':          0x7a378b,
    'mediumpurple':           0x9370db,
    'mediumpurple1':          0xab82ff,
    'mediumpurple2':          0x9f79ee,
    'mediumpurple3':          0x8968cd,
    'mediumpurple4':          0x5d478b,
    'mediumseagreen':         0x3cb371,
    'mediumslateblue':        0x7b68ee,
    'mediumspringgreen':      0x00fa9a,
    'mediumturquoise':        0x48d1cc,
    'mediumvioletred':        0xc71585,
    'midnight blue':          0x191970,
    'midnightblue':           0x191970,
    'mint cream':             0xf5fffa,
    'mintcream':              0xf5fffa,
    'misty rose':             0xffe4e1,
    'mistyrose':              0xffe4e1,
    'mistyrose1':             0xffe4e1,
    'mistyrose2':             0xeed5d2,
    'mistyrose3':             0xcdb7b5,
    'mistyrose4':             0x8b7d7b,
    'moccasin':               0xffe4b5,
    'navajo white':           0xffdead,
    'navajowhite':            0xffdead,
    'navajowhite1':           0xffdead,
    'navajowhite2':           0xeecfa1,
    'navajowhite3':           0xcdb38b,
    'navajowhite4':           0x8b795e,
    'navy':                   0x000080,
    'navy blue':              0x000080,
    'navyblue':               0x000080,
    'old lace':               0xfdf5e6,
    'oldlace':                0xfdf5e6,
    'olive drab':             0x6b8e23,
    'olivedrab':              0x6b8e23,
    'olivedrab1':             0xc0ff3e,
    'olivedrab2':             0xb3ee3a,
    'olivedrab3':             0x9acd32,
    'olivedrab4':             0x698b22,
    'orange':                 0xffa500,
    'orange red':             0xff4500,
    'orange1':                0xffa500,
    'orange2':                0xee9a00,
    'orange3':                0xcd8500,
    'orange4':                0x8b5a00,
    'orangered':              0xff4500,
    'orangered1':             0xff4500,
    'orangered2':             0xee4000,
    'orangered3':             0xcd3700,
    'orangered4':             0x8b2500,
    'orchid':                 0xda70d6,
    'orchid1':                0xff83fa,
    'orchid2':                0xee7ae9,
    'orchid3':                0xcd69c9,
    'orchid4':                0x8b4789,
    'pale goldenrod':         0xeee8aa,
    'pale green':             0x98fb98,
    'pale turquoise':         0xafeeee,
    'pale violet red':        0xdb7093,
    'palegoldenrod':          0xeee8aa,
    'palegreen':              0x98fb98,
    'palegreen1':             0x9aff9a,
    'palegreen2':             0x90ee90,
    'palegreen3':             0x7ccd7c,
    'palegreen4':             0x548b54,
    'paleturquoise':          0xafeeee,
    'paleturquoise1':         0xbbffff,
    'paleturquoise2':         0xaeeeee,
    'paleturquoise3':         0x96cdcd,
    'paleturquoise4':         0x668b8b,
    'palevioletred':          0xdb7093,
    'palevioletred1':         0xff82ab,
    'palevioletred2':         0xee799f,
    'palevioletred3':         0xcd6889,
    'palevioletred4':         0x8b475d,
    'papaya whip':            0xffefd5,
    'papayawhip':             0xffefd5,
    'peach puff':             0xffdab9,
    'peachpuff':              0xffdab9,
    'peachpuff1':             0xffdab9,
    'peachpuff2':             0xeecbad,
    'peachpuff3':             0xcdaf95,
    'peachpuff4':             0x8b7765,
    'peru':                   0xcd853f,
    'pink':                   0xffc0cb,
    'pink1':                  0xffb5c5,
    'pink2':                  0xeea9b8,
    'pink3':                  0xcd919e,
    'pink4':                  0x8b636c,
    'plum':                   0xdda0dd,
    'plum1':                  0xffbbff,
    'plum2':                  0xeeaeee,
    'plum3':                  0xcd96cd,
    'plum4':                  0x8b668b,
    'powder blue':            0xb0e0e6,
    'powderblue':             0xb0e0e6,
    'purple':                 0xa020f0,
    'purple1':                0x9b30ff,
    'purple2':                0x912cee,
    'purple3':                0x7d26cd,
    'purple4':                0x551a8b,
    'red':                    0xff0000,
    'red1':                   0xff0000,
    'red2':                   0xee0000,
    'red3':                   0xcd0000,
    'red4':                   0x8b0000,
    'rosy brown':             0xbc8f8f,
    'rosybrown':              0xbc8f8f,
    'rosybrown1':             0xffc1c1,
    'rosybrown2':             0xeeb4b4,
    'rosybrown3':             0xcd9b9b,
    'rosybrown4':             0x8b6969,
    'royal blue':             0x4169e1,
    'royalblue':              0x4169e1,
    'royalblue1':             0x4876ff,
    'royalblue2':             0x436eee,
    'royalblue3':             0x3a5fcd,
    'royalblue4':             0x27408b,
    'saddle brown':           0x8b4513,
    'saddlebrown':            0x8b4513,
    'salmon':                 0xfa8072,
    'salmon1':                0xff8c69,
    'salmon2':                0xee8262,
    'salmon3':                0xcd7054,
    'salmon4':                0x8b4c39,
    'sandy brown':            0xf4a460,
    'sandybrown':             0xf4a460,
    'sea green':              0x2e8b57,
    'seagreen':               0x2e8b57,
    'seagreen1':              0x54ff9f,
    'seagreen2':              0x4eee94,
    'seagreen3':              0x43cd80,
    'seagreen4':              0x2e8b57,
    'seashell':               0xfff5ee,
    'seashell1':              0xfff5ee,
    'seashell2':              0xeee5de,
    'seashell3':              0xcdc5bf,
    'seashell4':              0x8b8682,
    'sienna':                 0xa0522d,
    'sienna1':                0xff8247,
    'sienna2':                0xee7942,
    'sienna3':                0xcd6839,
    'sienna4':                0x8b4726,
    'sky blue':               0x87ceeb,
    'skyblue':                0x87ceeb,
    'skyblue1':               0x87ceff,
    'skyblue2':               0x7ec0ee,
    'skyblue3':               0x6ca6cd,
    'skyblue4':               0x4a708b,
    'slate blue':             0x6a5acd,
    'slate gray':             0x708090,
    'slate grey':             0x708090,
    'slateblue':              0x6a5acd,
    'slateblue1':             0x836fff,
    'slateblue2':             0x7a67ee,
    'slateblue3':             0x6959cd,
    'slateblue4':             0x473c8b,
    'slategray':              0x708090,
    'slategray1':             0xc6e2ff,
    'slategray2':             0xb9d3ee,
    'slategray3':             0x9fb6cd,
    'slategray4':             0x6c7b8b,
    'slategrey':              0x708090,
    'snow':                   0xfffafa,
    'snow1':                  0xfffafa,
    'snow2':                  0xeee9e9,
    'snow3':                  0xcdc9c9,
    'snow4':                  0x8b8989,
    'spring green':           0x00ff7f,
    'springgreen':            0x00ff7f,
    'springgreen1':           0x00ff7f,
    'springgreen2':           0x00ee76,
    'springgreen3':           0x00cd66,
    'springgreen4':           0x008b45,
    'steel blue':             0x4682b4,
    'steelblue':              0x4682b4,
    'steelblue1':             0x63b8ff,
    'steelblue2':             0x5cacee,
    'steelblue3':             0x4f94cd,
    'steelblue4':             0x36648b,
    'tan':                    0xd2b48c,
    'tan1':                   0xffa54f,
    'tan2':                   0xee9a49,
    'tan3':                   0xcd853f,
    'tan4':                   0x8b5a2b,
    'thistle':                0xd8bfd8,
    'thistle1':               0xffe1ff,
    'thistle2':               0xeed2ee,
    'thistle3':               0xcdb5cd,
    'thistle4':               0x8b7b8b,
    'tomato':                 0xff6347,
    'tomato1':                0xff6347,
    'tomato2':                0xee5c42,
    'tomato3':                0xcd4f39,
    'tomato4':                0x8b3626,
    'turquoise':              0x40e0d0,
    'turquoise1':             0x00f5ff,
    'turquoise2':             0x00e5ee,
    'turquoise3':             0x00c5cd,
    'turquoise4':             0x00868b,
    'violet':                 0xee82ee,
    'violet red':             0xd02090,
    'violetred':              0xd02090,
    'violetred1':             0xff3e96,
    'violetred2':             0xee3a8c,
    'violetred3':             0xcd3278,
    'violetred4':             0x8b2252,
    'wheat':                  0xf5deb3,
    'wheat1':                 0xffe7ba,
    'wheat2':                 0xeed8ae,
    'wheat3':                 0xcdba96,
    'wheat4':                 0x8b7e66,
    'white':                  0xffffff,
    'white smoke':            0xf5f5f5,
    'whitesmoke':             0xf5f5f5,
    'yellow':                 0xffff00,
    'yellow green':           0x9acd32,
    'yellow1':                0xffff00,
    'yellow2':                0xeeee00,
    'yellow3':                0xcdcd00,
    'yellow4':                0x8b8b00,
    'yellowgreen':            0x9acd32,
}

# The RGB value (0xRRGGBB) of a string on #RRGGBB form, or None.
def parse_rgb_color(s):
    m = re.match(r"#[0-9a-fA-F]{6}$", s)
    if m:
        return int(s[1:], 16)
    else:
        return None

def valid_color(s):
    return s.lower() in named_colors or parse_rgb_color(s) is not None

def color_name_to_rgb(s):
    if s.lower() in named_colors:
        return named_colors[s.lower()]
    else:
        return parse_rgb_color(s)

def ConsoleAttribute(init, data_type, attr, valid = lambda _: True):
    class CA(SimpleConfigAttribute(init, data_type, attr)):
        def setter(self, value):
            if self._up.is_configured() or not valid(value):
                return Sim_Set_Illegal_Value
            else:
                self.val = value
                return Sim_Set_Ok
    return CA

class SerialUpConnector(StandardConnector):
    '''The SerialUpConnector class handles serial up connections.
The first argument to the init method is the name of the console.
The console is expected to have a device attribute.'''

    type = 'serial'
    direction = Sim_Connector_Direction_Up
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, con):
        self.con = con

    def get_connect_data(self, comp, cnt):
        # construct attr in other side's connect method
        return [None, comp.get_slot(self.con)]

    def check(self, comp, cnt, attr):
        return True

    # attr = (link or None, device obj, device obj name)
    def connect(self, comp, cnt, attr):
        link = attr[0]
        device = attr[1:]
        con = comp.get_slot(self.con)

        if link:
            con.device = link
        else:
            (obj, name) = device
            con.device = obj
            if name:
                comp._update_title(name)
            else:
                comp._update_title(obj.name)

    def disconnect(self, comp, cnt):
        con = comp.get_slot(self.con)
        con.device = None
        comp._update_console_title('Console - not connected')

class console_component(StandardConnectorComponent):
    _console_slot = 'con'
    _do_not_init = object()

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()

    def is_configured(self):
        return self.obj.configured

    def _update_console_title(self, title):
        if self.has_user_defined_title.val:
            self.get_slot(self._console_slot).window_title = self.title.val
        else:
            self.get_slot(self._console_slot).window_title = title
            self.title.val = title

    class has_user_defined_title(SimpleAttribute(False, 'b')):
        '''return True if current title is set by users.'''
        pass

    class title(SimpleConfigAttribute('Console - not connected', 's',
                                      Sim_Attr_Optional)):
        '''The Window title.'''
        def setter(self, val):
            if self._up.obj.configured:
                self._up.get_slot(
                    self._up._console_slot).window_title = val
            self.val = val
            if not SIM_is_restoring_state(self._up.obj):
                self._up.has_user_defined_title.val = True

    # Meta-data for Eclipse and Winsome

    class top_level(StandardConnectorComponent.top_level):
        def _initialize(self):
            self.val = False

def is_valid_port(value):
    return value is None or value == 0 or 1024 <= value < 65536

class txt_console_comp(console_component):
    """Simics text console."""
    _class_desc = "text console"
    _help_categories = ()

    class basename(console_component.basename):
        val = 'text_console'

    def add_objects(self):
        con = self.add_pre_obj(console_component._console_slot, 'textcon')
        con.screen_size = [self.width.val, self.height.val]
        con.default_colours = [color_name_to_rgb(self.fg_color.val),
                               color_name_to_rgb(self.bg_color.val)]
        con.max_scrollback_size = self.scrollback.val
        # Default startup visibility behaviour if not set by user.
        if self.visible.val is not None:
            con.visible = self.visible.val

        self.add_connector(
            'serial', SerialUpConnector(console_component._console_slot))

    def _update_title(self, name):
        if name:
            title = f'{name} - serial console'
        else:
            title = 'Serial console, not connected'
        self._update_console_title(title)

    def _set_default_title(self):
        con_title = self.get_slot(self._console_slot).window_title
        if con_title != self.title.val:
            device = self.get_slot(console_component._console_slot).device
            if device:
                self._update_title(device.name)
            else:
                self._update_title(None)

    class component(StandardConnectorComponent.component):
        def post_instantiate(self):
            self._up._set_default_title()
            con = self._up.get_slot(console_component._console_slot)
            if self._up.telnet_port.val is not None:
                con.tcp.port = self._up.telnet_port.val
            if self._up.pty.val is not None:
                if self._up.pty.val != "":
                    con.iface.host_serial.setup(self._up.pty.val)
                else:
                    con.iface.host_serial.setup(None)

    class component_icon(StandardConnectorComponent.component_icon):
        val = "textcon.png"

    class width(ConsoleAttribute(
            80, 'i', Sim_Attr_Optional, lambda x: x > 0)):
        '''The width of the console window.'''
        pass

    class height(ConsoleAttribute(
            24, 'i', Sim_Attr_Optional, lambda x: x > 0)):
        '''The height of the console window.'''
        pass

    class scrollback(ConsoleAttribute(
            10000, 'i', Sim_Attr_Optional, lambda x: x > 0)):
        '''The maximum number of scrollback lines.'''
        pass

    class telnet_port(ConsoleAttribute(
            None, 'i|n', Sim_Attr_Optional, is_valid_port)):
        '''Port to open a telnet server on. This is independent of the <arg>visible</arg> parameter. The port must not be a privileged port,
i.e. the allowed range is [1024, 65535], or 0 for an arbitrary port.
If the port cannot be opened, an arbitrary port is chosen instead.'''
        pass

    class pty(ConsoleAttribute(
            None, 's|n', Sim_Attr_Pseudo)):
        '''Existing pty to open a host-serial server on. This is independent of the <arg>visible</arg> parameter. If the port cannot be opened, an error is thrown. If this parameter is the empty string, a new port is created and opened.'''
        def getter(self):
            return self._up.get_slot(self._up._console_slot).pty

    class bg_color(ConsoleAttribute(
            "white", 's', Sim_Attr_Optional,
            valid_color)):
        '''The default background color, either by name ("red")
           or on the form #RRGGBB.'''
        pass

    class fg_color(ConsoleAttribute(
            "black", 's', Sim_Attr_Optional,
            valid_color)):
        '''The default foreground color, either by name ("blue")
           or on the form #RRGGBB.'''
        pass

    class visible(ConsoleAttribute(
            None, 'b|n', Sim_Attr_Optional,
            lambda x: x in [True, False, None])):
        '''Should console be visible upon startup?.'''
        pass

class MouseUpConnector(StandardConnector):
    '''The MouseUpConnector class handles mouse up
 connections. The first argument to the init method is the
 console which sends coordinates to a mouse device.'''

    type = 'mouse'
    direction = Sim_Connector_Direction_Up
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, con):
        self.con = con

    def get_connect_data(self, comp, cnt):
        return [comp.get_slot(self.con)]

    def connect(self, comp, cnt, attr):
        obj = attr[0]
        con = comp.get_slot(self.con)
        con.mouse = obj

    def disconnect(self, comp, cnt):
        con = comp.get_slot(self.con)
        con.mouse = None

class AbsMouseUpConnector(StandardConnector):
    '''The AbsMouseUpConnector class handles abs-mouse up connections.
The first argument to the init method is the name of the console.'''
    type = 'abs-mouse'
    direction = Sim_Connector_Direction_Up
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, con):
        self.con = con

    def get_connect_data(self, comp, cnt):
        return [comp.get_slot(self.con)]

    def connect(self, comp, cnt, attr):
        obj = attr[0]
        con = comp.get_slot(self.con)
        con.abs_mouse = obj

    def disconnect(self, comp, cnt):
        con = comp.get_slot(self.con)
        con.abs_mouse = None

class KeyboardUpConnector(StandardConnector):
    '''The KeyboardUpConnector class handles keyboard up
 connections. The first argument to the init method is the
 console which sends keys to a keyboard device.'''

    type = 'keyboard'
    direction = Sim_Connector_Direction_Up
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, con):
        self.con = con

    def get_connect_data(self, comp, cnt):
        return [comp.get_slot(self.con)]

    def connect(self, comp, cnt, attr):
        obj = attr[0]
        con = comp.get_slot(self.con)
        con.keyboard = obj

    def disconnect(self, comp, cnt):
        con = comp.get_slot(self.con)
        con.keyboard = None

class GfxUpConnector(StandardConnector):
    '''The GfxUpConnector class handles Graphics up connections.
The first argument to the init method is the name of the console'''

    type = 'graphics-console'
    direction = Sim_Connector_Direction_Up
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, con):
        self.con = con

    def get_connect_data(self, comp, cnt):
        return [comp.get_slot(self.con)]

    # attr = (link or None, device obj, device obj name)
    def connect(self, comp, cnt, attr):
        link = attr[0]
        device = attr[1:]
        con = comp.get_slot(self.con)

        if device:
            (obj, name) = device
            con.device = obj
            if name:
                comp._update_title(name)
            else:
                comp._update_title(obj.name)
        else:
            con.device = link

    def disconnect(self, comp, cnt):
        con = comp.get_slot(self.con)
        con.device = None
        comp._update_console_title('Console - not connected')

class gfx_console_comp(console_component):
    """Simics graphics console."""
    _class_desc = "graphics console"
    _help_categories = ()

    class basename(console_component.basename):
        val = 'gfx_console'

    def add_objects(self):
        con = self.add_pre_obj(console_component._console_slot,
                               'graphcon')
        con.screen_size = [self.width.val, self.height.val]
        # Default startup visibility behaviour if not set by user.
        if self.visible.val is not None:
            con.visible = self.visible.val
        if self.vnc_port.val is not None:
            con.tcp.port = self.vnc_port.val

        self.add_connector(
            'keyboard', KeyboardUpConnector(console_component._console_slot))
        self.add_connector(
            'mouse', MouseUpConnector(console_component._console_slot))
        self.add_connector(
            'device', GfxUpConnector(console_component._console_slot))
        self.add_connector(
            'abs_mouse', AbsMouseUpConnector(console_component._console_slot))

    def _update_title(self, name):
        if name:
            title = f'{name} - graphics console'
        else:
            title = 'Graphics console, not connected'
        self._update_console_title(title)

    def _disable_device_refresh(self):
        device = self.get_slot(console_component._console_slot).device
        if device and hasattr(device, "refresh_rate"):
            device.refresh_rate = 0

    def _set_default_title(self):
        con_title = self.get_slot(self._console_slot).window_title
        if con_title != self.title.val:
            device = self.get_slot(console_component._console_slot).device
            if device:
                self._update_title(device.name)
            else:
                self._update_title(None)

    class component(StandardConnectorComponent.component):
        def post_instantiate(self):
            self._up._set_default_title()
            self._up._disable_device_refresh()

            con = self._up.get_slot(console_component._console_slot)
            if con.abs_mouse is not None:
                con.abs_pointer_enabled = True

    class component_icon(StandardConnectorComponent.component_icon):
        val = "graphcon.png"

    class width(ConsoleAttribute(
            640, 'i', Sim_Attr_Optional, lambda x: x > 0)):
        '''The initial screen width in pixels.'''

    class height(ConsoleAttribute(
            480, 'i', Sim_Attr_Optional, lambda x: x > 0)):
        '''The initial screen height in pixels.'''
        pass

    class vnc_port(ConsoleAttribute(
            None, 'i|n', Sim_Attr_Optional, is_valid_port)):
        '''Port to open a VNC server on. This is independent of the
<arg>visible</arg> parameter. The port must not be a privileged
port, i.e. the allowed range is [1024, 65535], or 0 for an arbitrary port.'''
        pass

    class visible(ConsoleAttribute(
            None, 'b|n', Sim_Attr_Optional,
            lambda x: x in [True, False, None])):
        '''Should console be visible upon startup?.'''
        pass
