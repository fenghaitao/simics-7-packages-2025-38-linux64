# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import conf
import unittest
import string
from .errors import CliTypeError, CliSyntaxError
from .documentation import doc

radixes = [2, 8, 10, 16]

whitespace = " \t\r\v\f"
alphanums = string.ascii_letters + string.digits
alnum_tab = alphanums + "\a" + "."

#
# Reads a number in base base from string text
# returns number and parsed chars in a tuple
# valid is valid characters for base
# Throws cliSyntaxError exception
#
def get_base_integer(text, base, valid, type):
    num = 0
    len = 0
    for c in text:
        if c == '_':
            len += 1
            continue
        pos = valid.find(c)
        if pos == -1:
            if c not in whitespace and c in alnum_tab:
                raise CliSyntaxError("illegal character '"
                                     + c +"' in " + type + " number")
            break
        len = len + 1
        num = num * base + pos
    if len == 0:
        raise CliTypeError("empty " + type + " integer")
    return (num, len)

#
# Reads an integer from text in some supported base.
# Supported bases are 2, 8, 10 and 16 and each base has
# a special prefix. "0b" for binary, "0o" for octal and
# "0x" for hexadecimal. Decimal numbers has no prefix.
# Throws CliTypeError exception.
#
def get_integer(text):
    len = 2
    if text.startswith("0x"):
        base = 16
        valid = "0123456789abcdef"
        type = "hexadecimal"
    elif text.startswith("0b"):
        base = 2
        valid = "01"
        type = "binary"
    elif text.startswith("0o"):
        base = 8
        valid = "01234567"
        type = "octal"
    elif text and text[0] in "0123456789":
        base = 10
        valid = "0123456789"
        type = "decimal"
        len = 0
    else:
        raise CliTypeError("Unknown integer type")

    (num, pos) = get_base_integer(text[len:].lower(), base, valid, type)
    return (num, len + pos)

def set_output_radix(radix):
    if radix not in radixes:
        raise ValueError("The radix must be either 2, 8, 10, or 16.")
    conf.prefs.output_radix = radix

def get_output_radix():
    return conf.prefs.output_radix

def set_output_grouping(rad, digits):
    if rad not in radixes:
        raise ValueError("The radix must be either 2, 8, 10, or 16.")
    if digits < 0 or digits > 8:
        raise ValueError("The digit grouping must be between 0 and 8 inclusive")
    conf.prefs.output_grouping[radixes.index(rad)] = digits

def get_output_grouping(radix):
    return conf.prefs.output_grouping[radixes.index(radix)]

def number_group(prefix, str, group):
    if group == 0:
        return str
    n = len(str)
    while True:
        n -= group
        if n <= 0:
            break
        str = str[:n] + '_' + str[n:]

    if prefix:
        while n < 0:
            n += 1
            str = '0' + str
    return str

@doc('return a ready-to-print representation of a number',
     module = 'cli',
     return_value = 'A string representing the number.',
     see_also = 'cli.str_number')
def number_str(val, radix=None, group=None, use_prefix=True, precision=1):
    """Return a ready-to-print representation of the number
    <param>val</param> in a given base (<param>radix</param>) or the
    current base by default, using the current settings for number
    representation as set by the <cmd>output-radix</cmd> and
    <cmd>digit-grouping</cmd> commands.

    The default digit grouping can be overridden with the
    <param>group</param> parameter, where 0 means no grouping.
    The radix prefix can be removed
    by specifying <param>use_prefix</param> as <tt>False</tt>.

    The minimum number of digits to be printed is specified by
    <param>precision</param>. If <param>precision</param> is negative,
    the precision is taken to be zero. Regardless of the radix, a
    value of zero with zero precision will always return the empty
    string.

    Negative numbers that fit in a signed 64-bit integer are treated
    as such. Other negative numbers are prefixed with a minus
    ("-")."""
    if radix is None:
        radix = get_output_radix()
    prefix = ''

    if precision < 0:
        precision = 0

    sign = ""
    if val < 0:
        if val > -0x8000000000000000 and radix != 10:
            val += 0x10000000000000000
        else:
            sign = "-"
            val = -val

    if precision > 0 or val != 0:
        if radix == 2:
            res = bin(val)[2:] if val else ''
            res = '0' * max(0, precision - len(res)) + res
            prefix = '0b'
        elif radix == 8:
            res = "%.*o" % (precision, val)
            prefix = "0o"
        elif radix == 10:
            res = "%.*d" % (precision, val)
        elif radix == 16:
            res = "%.*x" % (precision, val)
            prefix = "0x"
        else:
            raise Exception("bad radix")
    else:
        res = ""

    if not use_prefix or not res:
        prefix = ""

    if group is None:
        group = get_output_grouping(radix)

    return sign + prefix + number_group(prefix, res, group)

@doc('convert a string to a number',
     module = 'cli',
     see_also = 'cli.number_str',
     return_value = 'A number representing the string.')
def str_number(text):
    """Converts a string returned from <fun>number_str</fun> back to
    an integer.

    Raises ValueError for invalid arguments."""
    if text.startswith('-'):
        negative = True
        text = text[1:]
    else:
        negative = False

    try:
        (num, length) = get_integer(text)
    except CliTypeError:
        raise ValueError('invalid integer')

    if negative:
        return -num
    else:
        return num

class _test_number_str(unittest.TestCase):
    def setUp(self):
        self.old_output_radix = conf.prefs.output_radix
        self.old_output_grouping = conf.prefs.output_grouping
        conf.prefs.output_radix = 10
        conf.prefs.output_grouping = [0] * len(radixes)

    def tearDown(self):
        conf.prefs.output_radix = self.old_output_radix
        self.old_output_grouping = conf.prefs.output_grouping

    def test_number_str(self):
        def test(args, target, precision=1):
            self.assertEqual(number_str(precision=precision, *args), target)
            num = args[0]
            if (num < 0 and num > -0x8000000000000000
                and conf.prefs.output_radix != 10):
                result = 0x10000000000000000 + num
            else:
                result = num
            self.assertEqual(str_number(number_str(num)), result)

        test((471529,), "471529")
        test((471529, 10), "471529")
        test((471529, 16), "0x731e9")
        test((471529, 8), "0o1630751")
        test((471529, 2), "0b1110011000111101001")
        test((0, 10), "0")
        test((0, 16), "0x0")

        conf.prefs.output_grouping = [8, 3, 3, 4]
        conf.prefs.output_radix = 16
        test((471529,), "0x0007_31e9")
        test((471529, 10), "471_529")
        test((471529, 16), "0x0007_31e9")
        test((471529, 8), "0o001_630_751")
        test((471529, 2), "0b00000111_00110001_11101001")
        test((0, 10), "0")
        test((0, 16), "0x0000")
        test((-471533, 10), "-471_533")
        test((-471533, 16), "0xffff_ffff_fff8_ce13")
        test((-1, 10), "-1")
        test((-1, 8), "0o001_777_777_777_777_777_777_777")
        large = (0x123 << 64) + 0xabcd
        test((large, 16), "0x0123_0000_0000_0000_abcd")
        test((-large, 16), "-0x0123_0000_0000_0000_abcd")

        test((471529, 16), "0x0007_31e9", precision=0)
        test((471529, 16), "0x0000_0007_31e9", precision=10)

        conf.prefs.output_grouping = [0, 0, 0, 0]
        conf.prefs.output_radix = 10
        for precision in (-1, 0):
            for radix in radixes:
                test((0, radix), "", precision=precision)
        test((471529, 10), "471529", precision=0)
        test((471529, 10), "471529", precision=1)
        test((471529, 10), "0000471529", precision=10)
        test((471529, 16), "0x731e9", precision=0)
        test((471529, 16), "0x00000731e9", precision=10)
        test((10, 2), "0b1010", precision=0)
        test((10, 2), "0b1010", precision=1)
        test((10, 2), "0b0000001010", precision=10)
