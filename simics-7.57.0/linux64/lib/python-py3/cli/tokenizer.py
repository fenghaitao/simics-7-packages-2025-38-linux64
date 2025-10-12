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


import unittest
import re
from io import StringIO, BytesIO

from simicsutils.internal import ensure_text, ensure_binary
import simics

from .errors import CliError, CliSyntaxError
from . import impl
from . import number_utils

#
# tokenizes the input command line string.
#
#

def define_float_re():
    dec0 = r'(\d*\.\d+|\d+\.)([eE][+-]?\d+)?'
    dec1 = r'(\d+)([eE][+-]?\d+)'
    return re.compile(r'-?(' + dec0 + '|' + dec1 + ')')

float_regexp = define_float_re()

def to_string(text):
    try:
        return ensure_text(text)
    except UnicodeDecodeError:
        raise CliError("Cannot convert non UTF-8 string to CLI value")

_str_escapes = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'a': '\a',
                'v': '\v', 'f': '\f', 'e': '\033', '\\': '\\', '"': '"'}
_rev_str_escapes = dict((a, b) for b, a in _str_escapes.items()
                        if b != "e")

def isxdigit(s: str) -> bool:
    """Returns True if 's' is a hexadecimal digit."""
    return '0' <= s <= '9' or 'a' <= s <= 'f' or 'A' <= s <= 'F'

def repr_cli_string(s: [str, bytes], show_unicode=False) -> str:
    """Returns a CLI representation of the string 's', which will
    evaluate back to 's'. Cf. parse_cli_string().

    If 'show_unicode', return a string with Unicode characters;
    otherwise a UTF-8 encoded string (default)."""
    assert isinstance(s, (bytes, str))

    if show_unicode:
        import unicodedata
        result = StringIO()
        r = s if isinstance(s, str) else s.decode('utf-8')
        result.write('"')
        for c in r:
            if c in _rev_str_escapes:
                result.write('\\')
                result.write(_rev_str_escapes[c])
            elif (' ' <= c < '\x7f' or unicodedata.category(c)[0] in 'LMNPS'):
                #  Letter Mark Number Punctuation Symbol
                result.write(c)
            else:
                cn = ord(c)
                if cn <= 0x7f:
                    result.write(f'\\x{cn:02x}')
                elif cn <= 0xffff:
                    result.write(f'\\u{cn:04x}')
                else:
                    assert cn <= 0xffffffff
                    result.write(f'\\U{cn:08x}')
        result.write('"')
        return result.getvalue()
    else:
        result = BytesIO()
        result.write(b'"')
        r = s if isinstance(s, bytes) else s.encode('utf-8')
        for c in r:
            cc = bytes((c,))
            b = chr(c)
            if b in _rev_str_escapes:
                result.write(b'\\')
                result.write(_rev_str_escapes[b].encode('utf-8'))
            elif b' ' <= cc < b'\x7f':
                result.write(cc)
            else:
                assert(c <= 0xff)
                result.write(f'\\x{c:02x}'.encode('utf-8'))
        result.write(b'"')
        return result.getvalue().decode('utf-8')

def parse_octal(s: str) -> tuple:
    value = 0
    num_chars = 0
    for c in s:
        if c >= '0' and c <= '7':
            nvalue = value * 8 + ord(c) - ord(b'0')
            if nvalue > 0xff:
                # octals can only be in 0..255
                break
            else:
                num_chars += 1
                value = nvalue
        else:
            break
    return (bytes((value,)), num_chars - 1)

def parse_cli_string(s: str) -> bytes:
    """Returns the string 's' with escapes expanded.
    parse_cli_string(repr_cli_string(s)[1:-1]) == s."""
    assert isinstance(s, str)
    result = BytesIO()
    i = 0
    slen = len(s)
    while i < slen:
        if s[i] != '\\':
            result.write(s[i].encode('utf-8'))
            i += 1
            continue

        i += 1
        if i >= slen:
            raise CliSyntaxError(f'Invalid escape sequence in string "{s}"')

        c = s[i]
        i += 1
        if c in _str_escapes:
            # Escape character case
            result.write(_str_escapes[c].encode('utf-8'))
        elif c >= '0' and c <= '7':
            # Octal numeral
            octend = min(slen, i + 2)
            (val, num_chars) = parse_octal(c + s[i:octend])
            i += num_chars
            result.write(val)
        elif c == 'x' and (i + 2 <= slen
                           and all(isxdigit(s[i + j]) for j in range(2))):
            # Hexadecimal numeral
            result.write(bytes((int(s[i:i + 2], 16),)))
            i += 2
        elif c == 'u' and (i + 4 <= slen
                           and all(isxdigit(s[i + j]) for j in range(4))):
            # Unicode numeral
            result.write(chr(int(s[i:i + 4], 16)).encode('utf-8'))
            i += 4
        elif c == 'U' and (i + 8 <= slen
                           and all(isxdigit(s[i + j]) for j in range(8))):
            # Long unicode numeral
            result.write(chr(int(s[i:i + 8], 16)).encode('utf-8'))
            i += 8
        else:
            raise CliSyntaxError(f'Invalid escape sequence in string "{s}"')
    return result.getvalue()

class _test_str_token(unittest.TestCase):
    achars = 'A\n\033\177"\\'
    lchars = achars + '\200\377B'
    uchars = lchars + '\u0100\uffff\u1234'
    def test_parse(self):
        def ec(u):
            # skip b'
            return repr(u.encode('utf-8'))[2:-1]
        self.assertEqual(parse_cli_string(repr(self.achars)[1:-1]),
                         ensure_binary(self.achars))
        self.assertEqual(parse_cli_string(ec(self.lchars)),
                         self.lchars.encode('utf-8'))
        self.assertEqual(parse_cli_string(ec(self.uchars)),
                         self.uchars.encode('utf-8'))
    def test_repr(self):
        def t(s):
            from ast import literal_eval
            a = repr_cli_string(s)
            self.assertEqual(type(a), str)
            assert all(c >= ' ' and c <= '\x7f' for c in a)
            a = literal_eval(a)
            b = ensure_binary(str(s))
            self.assertEqual([ord(x) for x in a], list(b))

            a = repr_cli_string(s, show_unicode = True)
            self.assertTrue(isinstance(a, impl.string_types))
            a = literal_eval('u' + a)
            self.assertEqual(a, s)
        t(self.achars)
        t(self.lchars)
        t(self.uchars)
    def test_self(self):
        for u in (False, True):
            self.assertEqual(
                parse_cli_string(repr_cli_string(self.achars, u)[1:-1]),
                ensure_binary(self.achars))
            self.assertEqual(
                parse_cli_string(repr_cli_string(self.lchars, u)[1:-1]),
                self.lchars.encode('utf-8'))
            self.assertEqual(
                parse_cli_string(repr_cli_string(self.uchars, u)[1:-1]),
                self.uchars.encode('utf-8'))
    def test_error(self):
        for s in [ '\\x01', '\\u0123' ]:
            for l in range(1, len(s)):
                for a in [ s[:l], s[:l] + 'Q' ]:
                    self.assertRaises(CliSyntaxError, parse_cli_string, a)

class cli_token:
    __slots__ = ('value', 'line', 'cliret')
    def __init__(self, line):
        self.value = None
        self.line = line
        self.cliret = None
    def __hash__(self):
        return id(self)
    def __eq__(self, other):
        return self.__class__ == other.__class__
    def __ne__(self, other):
        return not self.__eq__(other)
    def quiet(self):
        """Returns True if no message or value should be printed when this
        token is used interactively."""
        if self.cliret:
            return self.cliret.is_quiet()
        return False
    def verbose(self):
        """Returns True if a message or value should be printed when this
        token is used non-interactively."""
        if self.cliret:
            return self.cliret.is_verbose()
        return False
    def message(self):
        """Returns a message to be used interactively for 'token', or False if
        no special message exists."""
        if self.cliret:
            return self.cliret.get_message()
        return False
    def print_token(self):
        if not self.quiet():
            msg = self.message()
            if msg:
                print(msg)
            else:
                print(self.string())
    def get_py_value(self, use_return_message = True):
        'Returns token as a Python value'
        if use_return_message and not self.quiet():
            msg = self.message()
            if msg:
                print(msg)
        return self.value

    # efficient deep copy support
    def copy(self):
        r = object.__new__(type(self))
        (r.value, r.line, r.cliret) = (self.value, self.line, self.cliret)
        if hasattr(self, "tokens"):
            r.tokens = list(t.copy() for t in self.tokens)
        return r

class newline_token(cli_token):
    __slots__ = ()
    def __init__(self, line = -1):
        cli_token.__init__(self, line)
    def __repr__(self):
        return "NL"

class separator_token(cli_token):
    __slots__ = ()
    def __init__(self, line = -1):
        cli_token.__init__(self, line)
    def __repr__(self):
        return ";"

class block_token(cli_token):
    __slots__ = ("tokens")
    def __init__(self, tokens, line = -1):
        cli_token.__init__(self, line)
        for i in range(len(tokens)):
            if isinstance(tokens[i], newline_token):
                tokens[i] = separator_token(line)
        self.tokens = tokens
    def __repr__(self):
        return "{" + ", ".join([repr(x) for x in self.tokens]) + "}"
    def __hash__(self):
        return id(self)
    def __eq__(self, other):
        return (cli_token.__eq__(self, other)
                and self.tokens == other.tokens)

class exp_token(cli_token):
    __slots__ = ("tokens")
    def __init__(self, tokens, line = -1):
        cli_token.__init__(self, line)
        self.tokens = [x for x in tokens if not isinstance(x, newline_token)]
    def __repr__(self):
        return "(" + ", ".join([repr(x) for x in self.tokens]) + ")"
    def __hash__(self):
        return id(self)
    def __eq__(self, other):
        return (cli_token.__eq__(self, other)
                and self.tokens == other.tokens)

class flag_token(cli_token):
    __slots__ = ()
    def __init__(self, flag, line = -1):
        cli_token.__init__(self, line)
        self.value = flag
    def __repr__(self):
        return "%s" % (self.value)
    def __hash__(self):
        return id(self)
    def __eq__(self, other):
        return (cli_token.__eq__(self, other)
                and self.value == other.value)
    def string(self):
        return self.value

class value_token(cli_token):
    __slots__ = ()
    def __init__(self, value, line = -1):
        cli_token.__init__(self, line)
        self.value = value
    def __repr__(self):
        return "%s:%s" % (self.desc, repr(self.value))
    def __hash__(self):
        return id(self)
    def __eq__(self, other):
        return (cli_token.__eq__(self, other)
                and self.value == other.value)

class void_token(value_token):
    __slots__ = ()
    desc = 'V'
    def __init__(self, line = -1):
        cli_token.__init__(self, line)
    def quiet(self):
        # voids are always quiet
        return True
    def string(self):
        return "<void>"

class list_token(value_token):
    __slots__ = ("tokens")
    desc = 'L'
    def __init__(self, tokens, line = -1):
        cli_token.__init__(self, line)
        self.tokens = [x for x in tokens if not isinstance(x, newline_token)]
    def __repr__(self):
        return "[" + ", ".join([repr(x) for x in self.tokens]) + "]"
    def __hash__(self):
        return id(self)
    def __eq__(self, other):
        return (value_token.__eq__(self, other)
                and self.tokens == other.tokens)
    def __getattribute__(self, name):
        if name == 'value':
            ret = []
            for t in self.tokens:
                ret.append(t.value)
            return ret
        else:
            return value_token.__getattribute__(self, name)
    def string(self):
        if not self.tokens and self.verbose() and not self.quiet():
            # interactive mode and empty list SIMICS-15909
            return ""
        ret = ''
        sep = ''
        for tok in self.tokens:
            ret += sep + tok.string()
            sep = ', '
        return '[' + ret + ']'

class float_token(value_token):
    __slots__ = ()
    desc = 'F'
    def string(self):
        return str(self.value)

class int_token(value_token):
    __slots__ = ()
    desc = 'I'
    def string(self):
        return number_utils.number_str(self.value)

class address_token(value_token):
    __slots__ = ()
    desc = 'A'
    def __init__(self, prefix, line = -1):
        cli_token.__init__(self, line)
        self.value = prefix
    def string(self):
        return self.value + ':'

class bool_token(value_token):
    __slots__ = ()
    desc = 'B'
    def string(self):
        return 'TRUE' if self.value else 'FALSE'

class nil_token(value_token):
    __slots__ = ()
    desc = 'N'
    def string(self):
        return 'NIL'

class string_token(value_token):
    __slots__ = ()
    def __init__(self, value, line = -1):
        cli_token.__init__(self, line)
        self.value = to_string(value)
    def __repr__(self):
        return repr_cli_string(self.value, True)
    def string(self):
        return repr_cli_string(self.value, True)

class quoted_token(string_token):
    __slots__ = ()
    desc = 'Q'

class unquoted_token(string_token):
    __slots__ = ()
    desc = 'U'

class unicode_token(unquoted_token):
    __slots__ = ()
    desc = 'Un'

def create_unquoted(text, line):
    if text == 'TRUE':
        return bool_token(True, line)
    elif text == 'FALSE':
        return bool_token(False, line)
    elif text == 'NIL':
        return nil_token(None, line)
    elif text.isascii():
        return unquoted_token(text, line)
    else:
        return unicode_token(text, line)

def split_tokens(tokens, key):
    start = -1
    for i in reversed(range(len(tokens))):
        if tokens[i] == key:
            start = i
            break
    if start == -1:
        raise CliSyntaxError("Expected parenthesis missing")
    exp = tokens[start + 1:]
    if any(t in ['(', '[', '{', '}', ']', ')'] for t in exp):
        raise CliSyntaxError("Unbalanced parentheses")
    return (tokens[:start], exp)

def check_unbalanced(tokens):
    for t in tokens:
        if isinstance(t, (block_token, exp_token)):
            check_unbalanced(t.tokens)
        if isinstance(t, impl.string_types):
            raise CliSyntaxError("Unbalanced parentheses")

def cleanup_tokens(tokens):
    check_unbalanced(tokens)
    return [t for t in tokens if not isinstance(t, newline_token)]

def find_previous_parenthesis(tokens):
    for (i, t) in enumerate(reversed(tokens)):
        if t == '(':
            return len(tokens) - i - 1
        elif not isinstance(t, newline_token):
            break
    return -1

# flag-token checks, always compare both functions below if editing
def is_flag_token(text):
    return re.match(r"^(-[a-zA-Z][a-zA-Z0-9-]*)$", text) is not None

def check_flag_token(text):
    return re.match(r"\s+(-[a-zA-Z][a-zA-Z0-9-]*)(?=(\s|\)|;))", text)
# END flag-token checks

def add_sentinel(text):
    """Add a sentinel to the text to ensure it ends with a whitespace."""
    return " " + text + " "

def tokenize(text, tab_complete = False):
    # put a sentinel last so that we always end with a white space
    text = add_sentinel(text)

    first_on_line = True
    cur_brac_is_list = []
    tokens = []
    line = 0

    no_letter_cmds = impl.all_commands.no_letter_cmds()
    no_letter_cmds_flat = set("".join(no_letter_cmds))

    while text != "":
        # look for flag token, i.e. \s+-wordchars\s
        mo = check_flag_token(text)
        if mo:
            tokens.append(flag_token(mo.group(1), line))
            text = text[mo.end():]
            first_on_line = False
            continue

        # Eat whites, but not NL
        prev_whitespace = text[0] == ' '
        text = text.lstrip(number_utils.whitespace)

        if text == "":
            break

        is_help_mode = tokens and (unquoted_token("help") == tokens[0]
                                   or unquoted_token("h") == tokens[0])
        if is_help_mode and text[0] in ("!", "#", "%", "$", "@"):
            if len(text) > 1 and text[1] in ("=", "<", ">"):
                tokens.append(unquoted_token(text[0] + text[1], line))
                text = text[2:]
            else:
                tokens.append(unquoted_token(text[0], line))
                text = text[1:]
            continue

        # look for eol commands
        if (text[0] in ('@', '#')
            or (text[0] == '!' and len(text) > 1 and text[1] != '=')):
            if text[0] in ('@', '!') and not first_on_line:
                simics.pr_err('%s command not issued first on a line' % text[0])
            line_end = 0
            while line_end > -1:
                line_end = text.find('\n', line_end + 1)
                if line_end < 0:
                    last_line = True
                    line_end = len(text)
                else:
                    last_line = False
                cmd = text[1:line_end].strip(' ')
                if text[0] == '@':
                    if (impl.complete_command_prefix('@' + cmd + '\n') or last_line):
                        cmd += '\n'
                        break
                else:
                    break
            if text[0] != '#':
                tokens.append(unquoted_token(text[0], line))
                tokens.append(create_unquoted(cmd, line))
            text = text[line_end:]
            if last_line:
                return cleanup_tokens(tokens)
            continue

        first_on_line = False

        # command separator
        if text[0] == ";":
            tokens.append(separator_token(line))
            text = text[1:]
            continue

        if text[0] == "\n":
            line += 1
            tokens.append(newline_token())
            text = text[1:]
            first_on_line = True
            continue

        # look for variables, i.e. $wordchars
        if text.startswith('$'):
            mo = re.match(r"\$([a-zA-Z_][a-zA-Z0-9_]*\a?)", text)
            if mo:
                text = text[mo.end():]
                tail = text.lstrip(number_utils.whitespace)
                # keep $ first
                if len(tail) and ((tail[0] in ('=', '[')
                                   and not tail.startswith('=='))
                                  or tail[:2] in ('+=', '-=')):
                    if (tokens
                        and isinstance(tokens[-1], string_token)
                        and tokens[-1].value == 'local'):
                        tokens[-1] = unquoted_token('$' + mo.group(0), line)
                    else:
                        tokens.append(create_unquoted(mo.group(0), line))
                else:
                    tokens.append(unquoted_token("$", line))
                    tokens.append(create_unquoted(mo.group(1), line))
                continue
            else:
                if not re.match(r"\$ *\a", text):
                    raise CliSyntaxError("$ must be followed by a "
                                         "variable name")

        # look for % (register access)
        if text.startswith('%'):
            mo = re.match("\\%([a-zA-Z][a-zA-Z0-9_]*\a?)", text)
            if mo:
                realtail = text[mo.end():]
                tail = realtail.lstrip(number_utils.whitespace)
                if len(tail) and ((tail[0] == '='
                                   and not tail.startswith('=='))
                                  or tail[:2] in ('+=', '-=')):
                    # keep % first
                    tokens.append(create_unquoted(mo.group(0), line))
                    text = tail
                    continue
                if len(realtail):
                    # separate variable from the following text.
                    # Special case for - since %a-4 shouldn't be
                    # expanded to %a -4, but %a - 4
                    if realtail[0] == '-':
                        text = (mo.group(0) + ' ' + realtail[0]
                                + ' ' + realtail[1:])
                    else:
                        text = mo.group(0) + ' ' + realtail
            else:
                text = text[1:]
                if text.startswith("%"):
                    raise CliSyntaxError("Duplicate %")
                elif text.strip():
                    tokens.append(create_unquoted('%%', line))
                else:
                    tokens.append(create_unquoted('%', line))
                continue

        # look for address prefix
        mo = re.match(r"(%s):" % ('|'.join(impl.address_space_prefixes),), text)
        if mo:
            tokens.append(address_token(mo.group(1), line))
            text = text[mo.end():]
            continue

        # string?
        if text[0] == '"':
            mo = re.match(r'"((\\.|[^"])*)"', text)

            if mo:
                tokens.append(quoted_token(parse_cli_string(mo.group(1)), line))
                text = text[mo.end():]
                continue
            else:
                pos = text.find('\a ')
                if pos < 0:
                    raise CliSyntaxError("Unterminated string")
                # terminate string on tab-completion
                text = text.replace('\a ', '\a"', 1)
                continue

        # eval Python expr -> pass it to eval Python command
        mo = re.match(r"`(.*?)`", text, re.DOTALL)
        if mo:
            # This is translated to "Python exp", which is a specially
            # treated prefix operator with high priority
            tokens.append(exp_token([unquoted_token("python", line),
                                     unquoted_token(mo.group(1), line)]))
            text = text[mo.end():]
            continue

        mo = re.match(r'\d+\.\d+\.', text)
        if mo:
            possible_number = 0
        else:
            possible_number = 1

        mo = float_regexp.match(text)
        if (mo and possible_number and text[mo.end():][:1] != '\a'
            and text[mo.end():][:1] not in impl.letters):
            # convert floats to Python floats
            tokens.append(float_token(float(mo.group(0)), line))
            text = text[mo.end():]
            continue

        try:
            if text[0] in "0123456789":
                number_utils.get_integer(text)
            elif text[0] == "-" or text[0] == "~":
                number_utils.get_integer(text[1:])
            else:
                raise Exception
            is_integer = possible_number
        except:
            is_integer = 0

        if text[0] == '{':
            tokens.append('{')
            text = text[1:]
        elif text[0] == '}':
            (tokens, blk) = split_tokens(tokens, '{')
            tokens.append(block_token(blk, line))
            text = text[1:]
        elif text[0] == '(':
            tokens.append('(')
            text = text[1:]
        elif text[0] == ')':
            (tokens, exp) = split_tokens(tokens, '(')
            tokens.append(exp_token(exp, line))
            text = text[1:]
        elif text[0] in "0123456789" and is_integer:
            (num, pos) = number_utils.get_integer(text)
            text = text[pos:]
            tokens.append(int_token(num, line))
        elif (text[0] == "-" and text[1] not in ('?', '>', '=')
              and tokens and isinstance(tokens[-1], (int_token, exp_token))):
            text = text[1:]
            tokens.append(unquoted_token('-', line))
        elif (text[0] == "/"
              and tokens and isinstance(tokens[-1], (int_token, exp_token))):
            tokens.append(unquoted_token('/', line))
            text = text[1:]
        elif text[0] == "-" and is_integer:
            text = text[1:]
            (num, pos) = number_utils.get_integer(text)
            text = text[pos:]
            tokens.append(int_token(-num, line))
        elif text[0] == "~" and is_integer:
            text = text[1:]
            (num, pos) = number_utils.get_integer(text)
            text = text[pos:]
            tokens.append(int_token(~num, line))
        elif text[0] == '[':
            text = text[1:]
            if (not prev_whitespace
                and tokens
                and ((isinstance(tokens[-1], string_token)
                      and tokens[-1].value
                      and tokens[-1].value[-1] in number_utils.alphanums)
                     or isinstance(tokens[-1], (list_token, exp_token)))):
                tokens.append(unquoted_token('[', line))
                cur_brac_is_list.append(False)
            else:
                cur_brac_is_list.append(True)
                if (tokens and isinstance(tokens[-1], string_token) and
                    tokens[-1].value.startswith('$')):
                    tokens[-1:-1] = [unquoted_token("$", tokens[-1].line)]
                    tokens[-1].value = tokens[-1].value[1:]
            tokens.append('[')
            tokens.append('(')
        elif text[0] == ']':
            text = text[1:]
            if not cur_brac_is_list:
                raise CliSyntaxError('unbalanced parentheses')
            pos = find_previous_parenthesis(tokens)
            if tokens and pos >= 0:
                # remove empty parenthesis (happens for , at end of list)
                tokens.pop(pos)
            else:
                (tokens, exp) = split_tokens(tokens, '(')
                tokens.append(exp_token(exp, line))
            (tokens, lst) = split_tokens(tokens, '[')
            if cur_brac_is_list.pop():
                tokens.append(list_token(lst, line))
            else:
                tokens.extend(lst)
        elif text[0] == ',':
            try:
                (tokens, exp) = split_tokens(tokens, '(')
            except CliSyntaxError:
                raise CliSyntaxError("Illegal list syntax")
            tokens.append(exp_token(exp, line))
            text = text[1:]
            tokens.append('(')
        else:
            for (i, ch) in enumerate(text):
                # look for no-letter-commands in string, they separate tokens
                cmd = ''
                if ch in no_letter_cmds_flat:
                    for c in no_letter_cmds:
                        if text.startswith(c, i):
                            cmd = c
                            break
                # we do not want e.g. 'command :RESET' to be concatenated
                if cmd and not (text[i] == ':' and prev_whitespace):
                    if i > 0:
                        tokens.append(create_unquoted(text[:i], line))
                        # the following no_letter_cmds have special treatment
                        # in the loop above and cannot just be added to the
                        # token list
                        if cmd in ['$', '%', '@', '#']:
                            text = text[i:]
                            break
                    tokens.append(create_unquoted(text[i:i+len(cmd)], line))
                    text = text[i+len(cmd):]
                    break
                # let '[]' be part of str-token if tab-completing, but end token
                # if dot appears after ']'
                # used for array slots
                elif ch in (number_utils.whitespace + "(){};," +
                            ("" if tab_complete else "[]")):
                    tokens.append(create_unquoted(text[:i], line))
                    text = text[i:]
                    break
                elif ch == '"':
                    raise CliSyntaxError("beginning of quoted string in"
                                         " middle of unquoted string")
                elif ch == '\n':
                    tokens.append(create_unquoted(text[:i], line))
                    tokens.append(newline_token())
                    line += 1
                    text = text[i:].replace('\n', '', 1)
                    first_on_line = True
                    break
    return cleanup_tokens(tokens)

class _test_tokenize(unittest.TestCase):
    def test_tokenize(self):
        def gives(s, t): self.assertEqual(tokenize(s), t)
        gives('', [])
        gives('abc 123 "xyz" 7.25 -f v:0x100',
              [unquoted_token('abc'), int_token(123), quoted_token('xyz'),
               float_token(7.25), flag_token('-f'), address_token('v'),
               int_token(0x100)])
        gives('a/b 3/b a-b 3-b a+b',
              [unquoted_token('a/b'), int_token(3), unquoted_token('/'),
               unquoted_token('b'), unquoted_token('a-b'), int_token(3),
               unquoted_token('-'), unquoted_token('b'), unquoted_token('a'),
               unquoted_token('+'), unquoted_token('b')])
        gives('a(b)c',
              [unquoted_token('a'), exp_token([unquoted_token('b')]),
               unquoted_token('c')])
        gives('@ x + y ', [unquoted_token('@'), unquoted_token('x + y\n')])
        gives('! x + y ', [unquoted_token('!'), unquoted_token('x + y')])
        gives('a;b\nc',
              [unquoted_token('a'), separator_token(), unquoted_token('b'),
               unquoted_token('c')])
        gives('$var == 1',
              [unquoted_token('$'), unquoted_token('var'),
               unquoted_token('=='), int_token(1)])
        gives('$var = 1', [unquoted_token('$var'), unquoted_token('='),
                           int_token(1)])
        gives('local $var = 1', [unquoted_token('$$var'),
                                 unquoted_token('='), int_token(1)])
        gives('%reg == 1',
              [unquoted_token('%'), unquoted_token('reg'),
               unquoted_token('=='), int_token(1)])
        gives('%reg = 1', [unquoted_token('%reg'), unquoted_token('='),
                           int_token(1)])
        gives('%reg-4',
              [unquoted_token('%'), unquoted_token('reg'),
               unquoted_token('-'), int_token(4)])
        gives('v: ds: :', [address_token('v'), address_token('ds'),
                           unquoted_token(':')])
        gives('"x / y\\nz"', [quoted_token('x / y\nz')])
        gives('`x / y`', [exp_token([unquoted_token('python'),
                                     unquoted_token('x / y')])])
        gives('a_b.c-d', [unquoted_token('a_b.c-d')])
        gives('1.25', [float_token(1.25)])
        gives('1.', [float_token(1.0)])
        gives('1.a', [unquoted_token('1.a')])
        gives('1.5e3', [float_token(1.5e3)])
        gives('1.e3', [float_token(1.e3)])
        gives('1.2.3', [unquoted_token('1.2.3')])
        gives('1.2.3.4', [unquoted_token('1.2.3.4')])
        gives('a.b.c.d', [unquoted_token('a.b.c.d')])
        gives('$foo[1]', [unquoted_token('$foo'), unquoted_token('['),
                          exp_token([int_token(1)])])
        gives('$foo [1]', [unquoted_token('$'), unquoted_token('foo'),
                           list_token([exp_token([int_token(1)])])])
        gives('$a.$b.$c.$d', [unquoted_token('$'), unquoted_token('a'),
                              unquoted_token('.'),
                              unquoted_token('$'), unquoted_token('b'),
                              unquoted_token('.'),
                              unquoted_token('$'), unquoted_token('c'),
                              unquoted_token('.'),
                              unquoted_token('$'), unquoted_token('d')])
        gives('$a.$b.c', [unquoted_token('$'), unquoted_token('a'),
                          unquoted_token('.'),
                          unquoted_token('$'), unquoted_token('b'),
                          unquoted_token('.c')])
        gives('[\n]', [list_token([])])
        # bug 13707
        gives('x $y -z', [unquoted_token('x'), unquoted_token('$'),
                          unquoted_token('y'), flag_token('-z')])
        # bug 13707 related
        gives('x %y -z', [unquoted_token('x'), unquoted_token('%'),
                          unquoted_token('y'), flag_token('-z')])
        gives('x==y=z+=y+z',
              [unquoted_token('x'), unquoted_token('=='), unquoted_token('y'),
               unquoted_token('='),
               unquoted_token('z'), unquoted_token('+='), unquoted_token('y'),
               unquoted_token('+'), unquoted_token('z')])
        # some tests checking special "help"/"h" handling done by tokenizer:
        gives('h #', [unquoted_token('h'), unquoted_token('#')])
        gives('help #', [unquoted_token('help'), unquoted_token('#')])
        gives('help !', [unquoted_token('help'), unquoted_token('!')])
        gives('help !=', [unquoted_token('help'), unquoted_token('!=')])
        gives('$h #', [unquoted_token('$'), unquoted_token('h')])
        gives('$help #=', [unquoted_token('$'), unquoted_token('help')])
