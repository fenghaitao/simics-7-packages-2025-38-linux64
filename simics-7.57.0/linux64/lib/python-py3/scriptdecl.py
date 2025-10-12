#!/usr/bin/env python3

# © 2013 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Parsing and validation of Simics script declaration sections

import sys
import re
import os
import shutil
import textwrap
from functools import total_ordering
from simicsutils.internal import ensure_text

class ParseError(Exception):
    """Represents a parse error. Arguments are (message, location)
    where location is (filename, line, column). line is 1-based,
    column 0-based."""
    def __str__(self):
        (msg, (filename, line, col)) = self.args
        return "%s:%d:%d: %s" % (filename, line, col + 1, msg)


class Token:
    def __init__(self, val, loc):
        self.val = val
        self.loc = loc                  # loc is (filename, line, column)
    def __repr__(self):
        m = re.search(r"\.([^']+)", str(self.__class__))
        return "%s(val=%r, loc=%r)" % (m.group(1), self.val, self.loc)

class NameToken(Token): pass
class SymbolToken(Token): pass       # brackets, punctuation, etc
class EndToken(Token): pass
class NumToken(Token): pass          # int or float
class StringToken(Token): pass       # val is string value (no quotes)
class DocToken(Token): pass          # val is string (no "!" or newline)
class UnknownToken(Token): pass      # cannot determine, use as string only if
                                     # the corresponding parameter is a string

# Binary SI prefix letters and their powers.
binary_powers = {
    "K": 10,
    "M": 20,
    "G": 30,
    "T": 40,
    "P": 50,
}

# Decimal SI prefix letters and their powers.
decimal_powers = {
    "K": 3,
    "M": 6,
    "G": 9,
    "T": 12,
    "P": 15,
}

def parse_suffixed_int(value):
    m = re.match(r"([^KMGTP]*)(([KMGTP])i?)?$", value.replace("_", ""))
    if m:
        if m.group(2) and len(m.group(2)) == 2:
            return int(m.group(1), 0) << binary_powers.get(m.group(3), 0)
        else:
            return (int(m.group(1), 0)
                    * (10 ** decimal_powers.get(m.group(3), 0)))
    else:
        return None

# Int and float tokens: val is the raw string value (unparsed)
class IntToken(NumToken):
    def value(self):
        return IntValue(parse_suffixed_int(self.val), self.val)

class FloatToken(NumToken):
    def value(self):
        return FloatValue(float(self.val), self.val)

escapes = {
    '"': '"',
    "'": "'",
    '\\': '\\',
    'n': '\n',
    'r': '\r',
    't': '\t',
    }

# Parse string escapes in s and return the resulting string.
def unescape(s, filename, line, col):
    p = 0
    r = []
    while True:
        bs = s.find('\\', p)
        if bs < 0:
            return "".join(r) + s[p:]
        r.append(s[p : bs])
        c = s[bs + 1]
        if c in escapes:
            r.append(escapes[c])
            p = bs + 2
        elif c == 'x' and re.match(r'[0-7][0-9a-fA-F]', s[bs + 2:]):
            r.append(chr(int(s[bs + 2 : bs + 4], 16)))
            p = bs + 4
        else:
            raise ParseError("Invalid escape sequence",
                             (filename, line, col + bs))

# Generate tokens from the file (line stream) f, using filename for
# the token locations..
def tokenise(f, filename, all_input = False):
    # We must take care to match things in the right order, even
    # within a single regexp. For instance, if given the regexp "A|B"
    # and both A and B would match, A is used even if B would be longer.

    # When parsing a command line value, match the full string. This way
    # strings with spaces do not require "double quotes", i.e. both for the
    # shell and for the parser here.
    suffix = "$" if all_input else ""

    whitespace_re = re.compile(r"\s*#.*|\s+")
    float_re = re.compile(r"(-?[0-9]+\.[0-9]+(?:e-?[0-9]+)?)(,|\]|\}|\s|$)"
                          + suffix)
    int_re = re.compile(
        r"""
         (-?
         (?:
            0x[0-9a-fA-F][0-9a-fA-F_]*
           |
            0b[01][01_]*
           |
            [0-9][0-9_]*
            ([KMGTP]i)?
         ))(,|\]|\}|\s|$)
        """ + suffix, re.X)

    string_re = re.compile(r'"((?:[^"\n\\]|\\.)*)"' + suffix)
    name_re = re.compile(r"[A-Za-z][A-Za-z0-9_]*" + suffix)
    sym_re = re.compile(r"[(){},:=]")
    doc_re = re.compile(r"!\s*(.*)")

    lnum = 0
    for line in f:
        lnum += 1
        col = 0
        try:
            line = ensure_text(line).rstrip()
            l = len(line)
            while col < l:
                if not all_input:
                    m = whitespace_re.match(line, col)
                    if m:
                        col = m.end()
                        continue

                m = float_re.match(line, col)
                if m:
                    yield FloatToken(m.group(1), (filename, lnum, col))
                    col += len(m.group(1))
                    continue

                m = int_re.match(line, col)
                if m:
                    yield IntToken(m.group(1), (filename, lnum, col))
                    col += len(m.group(1))
                    continue

                # Use a permissive regexp to match strings for better
                # diagnostics on escape errors.
                m = string_re.match(line, col)
                if m:
                    val = unescape(m.group(1), filename, lnum, col + 1)
                    yield StringToken(val, (filename, lnum, col))
                    col = m.end()
                    continue

                m = name_re.match(line, col)
                if m:
                    yield NameToken(m.group(), (filename, lnum, col))
                    col = m.end()
                    continue

                m = sym_re.match(line, col)
                if m:
                    yield SymbolToken(m.group(), (filename, lnum, col))
                    col = m.end()
                    continue

                m = doc_re.match(line, col)
                if m:
                    yield DocToken(m.group(1), (filename, lnum, m.start(1)))
                    col = m.end()
                    continue

                yield UnknownToken(line, (filename, lnum, col))
                col += len(line)
        except Exception as e:
            raise DeclError([("Exception when tokenising script: %s"
                              % e, (filename, lnum, col))])

    yield EndToken(None, (filename, lnum, 0))

class ExpansionError(Exception): pass

class Type:
    def __eq__(self, _): assert False
    def __ne__(self, other): return not (self == other)
    __hash__ = None

    # Check that value conforms to self.
    # file_existence_pred is the predicate to use for file existence checker.
    def typecheck(self, value): return False

    # Expand a value from the list of package installation directories.
    # Raise ExpansionError on failure.
    def expand(self, value, package_dirs):
        return value.val

class IntType(Type):
    def __eq__(self, other): return self.__class__ == other.__class__
    def __repr__(self): return "IntType"
    def pretty(self): return "integer"
    def typecheck(self, value):
        return isinstance(value, IntValue)

class FloatType(Type):
    def __eq__(self, other): return self.__class__ == other.__class__
    def __repr__(self): return "FloatType"
    def pretty(self): return "number"
    def typecheck(self, value):
        return isinstance(value, (FloatValue, IntValue))

class StringType(Type):
    def __eq__(self, other): return self.__class__ == other.__class__
    def __repr__(self): return "StringType"
    def pretty(self): return "string"
    def typecheck(self, value):
        return isinstance(value, StringValue)

class BoolType(Type):
    def __eq__(self, other): return self.__class__ == other.__class__
    def __repr__(self): return "BoolType"
    def pretty(self): return "boolean"
    def typecheck(self, value):
        return isinstance(value, BoolValue)

class FileType(Type):
    def __init__(self, pattern):
        self.pattern = pattern
    def __eq__(self, other):
        return (self.__class__ == other.__class__
                and self.pattern == other.pattern)
    def __repr__(self):
        return "FileType(%r)" % (self.pattern,)
    def pretty(self):
        s = "existing file"
        if self.pattern != "*":
            s += " (%s)" % self.pattern
        return s
    def typecheck(self, value):
        return isinstance(value, StringValue)

    def expand(self, value, package_dirs):
        assert isinstance(value, StringValue)
        filename = value.val
        if filename.startswith("%simics%/"):
            # FIXME: We don't expand %simics% but just check the file
            # existence. Should these paths be expanded?
            rel_f = filename[len("%simics%/"):]
            if any(os.path.isfile(os.path.join(pdir, rel_f))
                   for pdir in package_dirs):
                return filename
            raise ExpansionError("File not found in any installed package: %s"
                                 % filename)
        elif filename.startswith("%script%/"):
            rel_f = filename[len("%script%/"):]
            if value.loc is None:
                raise ExpansionError("No %%script%% expansion possible for %s"
                                     % (filename,))
            (scriptfile, _, _) = value.loc
            script_dir = os.path.dirname(os.path.abspath(scriptfile))
            eff_f = os.path.join(script_dir, rel_f)
            if os.path.isfile(eff_f):
                return eff_f
            raise ExpansionError("No file %s in directory %s"
                                 % (filename, script_dir))
        else:
            if os.path.isfile(filename):
                return filename
            raise ExpansionError("File not found: %s" % filename)


simple_types = {
    'int': IntType,
    'float': FloatType,
    'string': StringType,
    'bool': BoolType,
    }

class EnumType(Type):
    def __init__(self, values):
        self.values = values
    def __eq__(self, other):
        return (self.__class__ == other.__class__
                and self.values == other.values)
    def __repr__(self):
        return "EnumType{%s}" % (", ".join(map(repr, self.values)),)
    def pretty(self):
        return "one of {" + ", ".join(v.pretty() for v in self.values) + "}"
    def typecheck(self, value):
        return any(v == value for v in self.values)

class OrNilType(Type):
    def __init__(self, type):
        self.type = type
    def __eq__(self, other):
        return (self.__class__ == other.__class__
                and self.type == other.type)
    def __repr__(self):
        return "OrNilType(%s)" % (repr(self.type),)
    def pretty(self):
        return "%s or NIL" % self.type.pretty()
    def typecheck(self, value):
        return self.type.typecheck(value) or isinstance(value, NilValue)
    def expand(self, value, package_dirs):
        if isinstance(value, NilValue):
            return None
        else:
            return self.type.expand(value, package_dirs)

class Value:
    def __init__(self, val):
        self.val = val
    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.val == other.val
    def __ne__(self, other): return not (self == other)
    def __hash__(self): return 0

escaped_chars = {
    '"': r'\"',
    "\\": r"\\",
    "\n": r"\n",
    "\r": r"\r",
    "\t": r"\t"
    }

class StringValue(Value):
    def __init__(self, val, loc):
        self.val = val
        self.loc = loc
    def __repr__(self):
        return 'String(%r)' % (self.val,)
    def pretty(self):
        # FIXME: Should values not requiring quotes be printed as barewords?
        chars = []
        for c in self.val:
            if c in escaped_chars:
                chars.append(escaped_chars[c])
            else:
                v = ord(c)
                if v < 32 or v == 127:
                    chars.append(r"\x%02x" % v)
                else:
                    chars.append(c)
        return '"' + "".join(chars) + '"'

class UnknownValue(StringValue):
    pass

class NilValue(Value):
    def __repr__(self): return self.pretty()
    def pretty(self): return "NIL"

class BoolValue(Value):
    def __repr__(self): return self.pretty()
    def pretty(self): return "TRUE" if self.val else "FALSE"

class IntValue(Value):
    def __init__(self, val, original_repr):
        self.val = val
        self.original_repr = original_repr
    def __repr__(self):
        return "Int(%r = %s)" % (self.val, self.original_repr)
    def pretty(self): return self.original_repr

class FloatValue(Value):
    def __init__(self, val, original_repr):
        self.val = val
        self.original_repr = original_repr
    def __repr__(self):
        return "Float(%r = %s)" % (self.val, self.original_repr)
    def pretty(self): return self.original_repr


class JDocuTextToken(Token): pass
class JDocuStartTagToken(Token): pass
class JDocuEndTagToken(Token): pass

def add_to_loc(data, ofs):
    (filename, lnum, col) = data
    return (filename, lnum, col + ofs)

# Standard entities. JDocu defines a few more (ndash, mdash, trade, reg),
# but it's unclear whether they should be permitted here.
entities = {"amp", "lt", "gt", "quot", "apos"}

entity_ref_re = re.compile(r"&([^;]+);")

# Verify that all occurrences of "&" in txt are in valid entity references.
# Raise ParseError if not.
def check_entities(txt, loc):
    pos = -1
    while True:
        pos = txt.find("&", pos + 1)
        if pos < 0:
            break
        m = entity_ref_re.match(txt, pos)
        if not m:
            raise ParseError("JDocu mark-up error (use '&amp;' for '&')",
                             add_to_loc(loc, pos))
        if m.group(1) not in entities:
            raise ParseError("Undefined JDocu entity", add_to_loc(loc, pos))
        pos = m.end()

jdocu_tag_re = re.compile(r"(/?)([a-zA-Z_][a-zA-Z_0-9-]*)(/?)>")

# Given a doc comment as a sequence of `DocToken`s, generate a sequence
# of JDocu tokens. Raise ParseError on error.
def jdocu_tokenise(doc_toks):
    for tok in doc_toks:
        s = tok.val
        tloc = tok.loc
        l = len(s)
        ofs = 0
        while ofs < l:
            angle = s.find("<", ofs)
            if angle != 0:
                # Plain inter-element text.
                end = angle if angle > 0 else l
                txt = s[ofs : end]
                loc = add_to_loc(tloc, ofs)
                check_entities(txt, loc)
                yield JDocuTextToken(txt, loc)
                ofs = end

            if angle >= 0:
                loc = add_to_loc(tloc, angle)
                # The JDocu subset currently in effect does not use any
                # element attributes, so there is no need to parse them here.
                m = jdocu_tag_re.match(s, angle + 1)
                if m:
                    tagname = m.group(2)
                    if m.group(1):
                        if not m.group(3):
                            # End tag.
                            yield JDocuEndTagToken(tagname, loc)
                            ofs = m.end()
                            continue
                    else:
                        # Start/empty tag.
                        yield JDocuStartTagToken(tagname, loc)
                        if m.group(3):
                            # Empty tag; generate an end tag right away.
                            yield JDocuEndTagToken(tagname, loc)
                        ofs = m.end()
                        continue
                raise ParseError("JDocu syntax error", loc)

jdocu_elements = {"param", "em", "tt"}

# Validate a doc comment (a sequence of `DocToken`s) with respect to
# its mark-up. Raise ParseError on failure.
def validate_doc(doc_toks):
    elem_stack = []                     # stack of JDocuStartTagToken
    for t in jdocu_tokenise(doc_toks):
        if isinstance(t, JDocuStartTagToken):
            # Is the element allowed in this context?
            if t.val in jdocu_elements:
                if elem_stack:
                    raise ParseError("<%s> not permitted inside <%s>"
                                     % (t.val, elem_stack[-1].val),
                                     t.loc)
            else:
                raise ParseError(
                    "no element <%s> allowed in script doc strings" % t.val,
                    t.loc)
            elem_stack.append(t)
        elif isinstance(t, JDocuEndTagToken):
            if not elem_stack:
                raise ParseError("Unbalanced end tag", t.loc)
            start_tok = elem_stack.pop()
            if start_tok.val != t.val:
                raise ParseError("End tag </%s> does not match start <%s>"
                                 % (t.val, start_tok.val),
                                 t.loc)
        else:
            # Plain text.
            pass

    if elem_stack:
        raise ParseError("Tag <%s> lacks closing tag" % elem_stack[-1].val,
                         elem_stack[-1].loc)


def tok_error(t, msg):
    raise ParseError(msg, t.loc)

def is_symbol(t, sym):
    return isinstance(t, SymbolToken) and t.val == sym

def parse_doc(toks, t):
    doc_toks = []
    while True:
        doc_toks.append(t)
        t = next(toks)
        if not isinstance(t, DocToken):
            validate_doc(doc_toks)
            doc_str = "\n".join(dt.val for dt in doc_toks)
            return (t, doc_str)

def parse_value(toks):
    t = next(toks)
    if isinstance(t, StringToken):
        return StringValue(t.val, t.loc)
    if isinstance(t, UnknownToken):
        return UnknownValue(t.val, t.loc)
    if isinstance(t, NameToken):
        name = t.val
        if name == "NIL":
            return NilValue(None)
        if name == "TRUE":
            return BoolValue(True)
        if name == "FALSE":
            return BoolValue(False)
        return StringValue(name, t.loc)
    if isinstance(t, NumToken):
        return t.value()
    tok_error(t, "Not a valid value")

def parse_file_type(toks):
    t = next(toks)
    if not is_symbol(t, "("):
        tok_error(t, "Expected '('")

    t = next(toks)
    if not isinstance(t, StringToken):
        tok_error(t, "Expected string")
    pattern = t.val

    # Only accept patterns on the form * or *.suffix, since that is what
    # GUI file selectors generally accept as filters.
    m = re.match(r"\*(?:\.[a-zA-Z0-9.*]*)?$", pattern)
    if not m:
        tok_error(t, "Illegal file pattern")

    t = next(toks)
    if not is_symbol(t, ")"):
        tok_error(t, "Expected ')'")

    return FileType(pattern)

def parse_enum_type(toks):
    val = parse_value(toks)
    vals = [val]

    while True:
        t = next(toks)
        if is_symbol(t, "}"):
            return EnumType(vals)
        elif is_symbol(t, ","):
            val = parse_value(toks)
            vals.append(val)
        else:
            tok_error(t, "Expected ',' or '}'")

# Parse a type. Return (next_token, type).
def parse_type(toks, t):
    if isinstance(t, NameToken):
        if t.val in simple_types:
            typ = simple_types[t.val]()
        elif t.val == 'file':
            typ = parse_file_type(toks)
        else:
            tok_error(t, "Bad type")
    elif is_symbol(t, "{"):
        typ = parse_enum_type(toks)
    else:
        tok_error(t, "Syntax error (type expected)")

    t = next(toks)
    if isinstance(t, NameToken) and t.val == "or":
        t = next(toks)
        if not (isinstance(t, NameToken) and t.val == "nil"):
            tok_error(t, "Syntax error ('nil' expected)")
        typ = OrNilType(typ)
        t = next(toks)

    return (t, typ)

@total_ordering
class Param:
    def __init__(self, loc, name, type, defval, doc, group):
        self.loc = loc                  # (filename, line, col)
        self.name = name
        self.type = type
        self.defval = defval            # value or None
        self.doc = doc                  # string or None
        self.group = group              # string or None

    def __eq__(self, p):
        return self.loc == p.loc

    def __ne__(self, p):
        return not self == p

    def __lt__(self, p):
        return self.loc < p.loc

    def __hash__(self):
        return hash(self.loc)

class Result:
    def __init__(self, loc, name, type, doc):
        self.loc = loc                  # (filename, line, col)
        self.name = name
        self.type = type
        self.doc = doc                  # string or None

class Omission:
    def __init__(self, loc, name):
        self.loc = loc                  # (filename, line, col)
        self.name = name

class Default:
    def __init__(self, loc, name, defval):
        self.loc = loc
        self.name = name
        self.defval = defval

class Include:
    def __init__(self, loc, filename, omissions, defaults):
        self.loc = loc                  # (filename, line, col)
        self.filename = filename
        self.omissions = omissions      # {name -> Omission}
        self.defaults = defaults        # {name -> Default}

class Substitute:
    def __init__(self, loc, filename):
        self.loc = loc                  # (filename, line, col)
        self.filename = filename

class FileDecl:
    def __init__(self, doc, params, results, includes, substitute):
        self.doc = doc                  # string or None
        self.params = params            # {name -> Param}
        self.results = results          # {name -> Result}
        self.includes = includes        # [Include...]
        self.substitute = substitute    # Substitute or None


def parse_param(toks, group):
    t = next(toks)
    if not isinstance(t, NameToken):
        tok_error(t, "Expected identifier")
    name_tok = t

    t = next(toks)
    if not is_symbol(t, ":"):
        tok_error(t, "Expected ':'")

    t = next(toks)
    (t, typ) = parse_type(toks, t)

    if is_symbol(t, "="):
        defval = parse_value(toks)
        t = next(toks)
    else:
        defval = None

    if isinstance(t, DocToken):
        (t, d) = parse_doc(toks, t)
        doc = d
    else:
        doc = None

    return (t, Param(name_tok.loc, name_tok.val, typ, defval, doc, group))

def parse_result(toks):
    t = next(toks)
    if not isinstance(t, NameToken):
        tok_error(t, "Expected identifier")
    name_tok = t

    t = next(toks)
    if not is_symbol(t, ":"):
        tok_error(t, "Expected ':'")

    t = next(toks)
    (t, typ) = parse_type(toks, t)

    if isinstance(t, DocToken):
        (t, d) = parse_doc(toks, t)
        doc = d
    else:
        doc = None

    return (t, Result(name_tok.loc, name_tok.val, typ, doc))

def parse_include(toks):
    t = next(toks)
    if not (isinstance(t, NameToken) and t.val == "from"):
        tok_error(t, "Expected 'from'")

    t = next(toks)
    if not isinstance(t, StringToken):
        tok_error(t, "Expected string containing file name")
    filename_tok = t

    omissions = {}                      # name -> Omission
    t = next(toks)
    if isinstance(t, NameToken) and t.val == "except":
        while True:
            t = next(toks)
            if not isinstance(t, NameToken):
                tok_error(t, "Expected variable name")
            var = t.val
            if var in omissions:
                raise ParseError("Duplicated omitted variable", t.loc)
            omissions[var] = Omission(t.loc, var)

            t = next(toks)
            if not is_symbol(t, ","):
                break

    defaults = {}                       # name -> Default
    while isinstance(t, NameToken) and t.val == "default":
        t = next(toks)
        if not isinstance(t, NameToken):
            tok_error(t, "Expected variable name")
        name_tok = t
        if name_tok.val in defaults:
            tok_error(t, "Duplicated default for %s" % name_tok.val)
        t = next(toks)
        if not is_symbol(t, "="):
            tok_error(t, "Expected '='")
        defval = parse_value(toks)
        defaults[name_tok.val] = Default(name_tok.loc, name_tok.val, defval)
        t = next(toks)

    return (t, Include(filename_tok.loc, filename_tok.val,
                       omissions, defaults))

def parse_substitute(toks):
    t = next(toks)
    if not isinstance(t, StringToken):
        tok_error(t, "Expected string containing file name")
    filename_tok = t
    t = next(toks)
    return (t, Substitute(filename_tok.loc, filename_tok.val))

def parse_group(toks):
    t = next(toks)
    if not isinstance(t, StringToken):
        tok_error(t, "Expected string (group name)")
    group = t.val
    t = next(toks)
    return (t, group)

# Parse the file f (a stream of lines).
# script_filename is the file to use in the location information.
# If the file has a declaration, return (d, n) where d is a FileDecl and n
# the number of lines consumed from f. Otherwise, return None (with an
# unspecified number of lines consumed).
def parse_file(f, script_filename):
    toks = tokenise(f, script_filename)

    doc = None

    try:
        t = next(toks)
    except (StopIteration, ParseError):
        return None
    if not (isinstance(t, NameToken) and t.val == "decl"):
        return None

    t = next(toks)
    if not is_symbol(t, "{"):
        tok_error(t, "Expected '{'")

    t = next(toks)
    if isinstance(t, DocToken):
        (t, d) = parse_doc(toks, t)
        doc = d

    params = {}                         # name -> Param
    results = {}                        # name -> Result
    includes = []                       # [Include...]
    substitute = None                   # Substitute or None
    group = None
    while not is_symbol(t, "}"):
        if isinstance(t, NameToken):
            if t.val == "param":
                (t, par) = parse_param(toks, group)
                if par.name in params:
                    raise ParseError("Duplicated parameter '%s'" % par.name,
                                     par.loc)
                params[par.name] = par
                continue
            if t.val == "result":
                (t, res) = parse_result(toks)
                if res.name in results:
                    raise ParseError("Duplicated result '%s'" % res.name,
                                     res.loc)
                results[res.name] = res
                continue
            if t.val == "params":
                (t, inc) = parse_include(toks)
                if any(pi.filename == inc.filename for pi in includes):
                    raise ParseError("Duplicated 'params from'", inc.loc)
                includes.append(inc)
                continue
            if t.val == "substitute":
                if substitute:
                    raise ParseError("Duplicated 'substitute'", t.loc)
                (t, substitute) = parse_substitute(toks)
                continue
            if t.val == "group":
                (t, group) = parse_group(toks)
                continue
        tok_error(t, "Syntax error")

    # We use the location of the last token (the closing curly
    # bracket) to find out how many lines that we have used up.
    (_, nlines, _) = t.loc
    return (FileDecl(doc, params, results, includes, substitute), nlines)


# Convert a Python value to a Value object, for use in type-checking.
def value_from_py_value(val):
    # False positives from pychecker in this function
    # ("Function return types are inconsistent").
    if val is None:
        return NilValue(None)
    if isinstance(val, bool):
        return BoolValue(val)
    if isinstance(val, int):
        return IntValue(val, repr(val))
    if isinstance(val, float):
        return FloatValue(val, repr(val))
    if isinstance(val, str):
        return StringValue(val, None)

    raise Exception("ERROR: can't convert %r to a Value" % (val,))


class DeclError(Exception):
    """Raised for syntactic or semantic errors. The arguments is a list of
    (message, location) where location is None or (filename, line, column);
    line is 1-based, column 0-based."""

    # Format the error in GNU format, with 1-based lines and columns.
    def __str__(self):
        return "\n".join("%s:%d:%d: %s" % (filename, line, col + 1, msg)
                         for (msg, (filename, line, col)) in self.args[0])

def strip_jdocu_markup(s):
    return (re.sub(r"<[^>]*>", "", s)
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&apos;", "'")
            .replace("&amp;", "&"))

def print_str(f, string, indent):
    # scriptdecl is currently decoupled from Simics so we call
    # shutil.get_terminal_size directly to get command line width.
    # Even though the actual command line width may differ (e.g., when Simics'
    # telnet console is used), we try to get a reasonable value here. This
    # protects well against long lines in target scripts.
    width = min(shutil.get_terminal_size().columns, 80) - indent - 1

    string = strip_jdocu_markup(string)
    paragraphs = re.split('\n{2,}', string)
    for prg in paragraphs:
        prg = textwrap.fill(prg, width)
        prg = textwrap.indent(prg, prefix = " " * indent)
        print(prg, file = f)

class DeclSpec:
    def __init__(self, filename, decl):
        self.filename = filename
        self.decl = decl           # Decl

    def select_args(self, passed_args, cli_vars, package_dirs):
        """Select the actual arguments to be used from passed_args and
        cli_vars, both dicts from name to value, and from the default
        parameter values.

        The resulting arguments are type-checked against the
        declarations and returned as a dict.

        package_dirs is a list of directories to search for required
        files having the %simics%/ prefix."""

        formal_args = set(self.decl.params)
        superfluous_args = set(passed_args) - formal_args
        if superfluous_args:
            raise DeclError([("No parameter %s declared by this script"
                              % (a,),
                              (self.filename, 0, 0))
                             for a in sorted(superfluous_args)])

        errs = []
        actual_args = {}
        for p in formal_args:
            if p in passed_args:
                actual_args[p] = value_from_py_value(passed_args[p])
            elif p in cli_vars:
                actual_args[p] = value_from_py_value(cli_vars[p])
            else:
                par = self.decl.params[p]
                if par.defval is None:
                    errs.append(("Required argument %s missing" % (p,),
                                 par.loc))
                else:
                    actual_args[p] = par.defval

        if errs:
            raise DeclError(errs)

        # Now we should have everything.
        assert set(actual_args) == formal_args

        # Type-check and expand values.
        args = {}
        for p in formal_args:
            par = self.decl.params[p]
            if par.type.typecheck(actual_args[p]):
                try:
                    # FIXME: Use the file name from the value instead
                    # of our own?
                    args[p] = par.type.expand(actual_args[p], package_dirs)
                except ExpansionError as e:
                    errs.append(("Script argument %s: %s" % (p, e),
                                 par.loc))
            else:
                value_str = actual_args[p].pretty()
                errs.append(
                    ("Value of script argument %s: %s" % (p, value_str),
                     par.loc))
                errs.append(
                    ("does not match its type: %s" % (par.type.pretty(),),
                     par.loc))
        if errs:
            raise DeclError(errs)

        return args

    def select_results(self, cli_vars, package_dirs):
        """Select the results from cli_vars, perform a type-check,
        and return them as a dict.

        package_dirs is a list of directories to search for required
        files having the %simics%/ prefix."""

        errs = []
        results = {}
        for r in self.decl.results:
            res = self.decl.results[r]
            if r not in cli_vars:
                errs.append(("Result %s not set" % (r,), res.loc))
                continue
            val = cli_vars[r]
            v = value_from_py_value(val)
            if not res.type.typecheck(v):
                value_str = v.pretty()
                errs.append(
                    ("Value of script result %s: %s" % (r, value_str),
                     res.loc))
                errs.append(
                    ("does not match its type: %s" % (res.type.pretty(),),
                     res.loc))
                continue
            try:
                results[r] = res.type.expand(v, package_dirs)
            except ExpansionError as e:
                errs.append(("Script result %s: %s" % (r, e),
                             res.loc))
        if errs:
            raise DeclError(errs)

        return results

    def print_help(self, f):
        """Print help about the script and its parameters to the file f."""

        if self.decl.doc is not None:
            print_str(f, self.decl.doc, 0)
            print(file=f)

        def param_help(name, par, print_default):
            print_str(f, f"{name}  -  {par.type.pretty()}", 2)
            if par.doc is not None:
                print_str(f, par.doc, 4)
            if print_default:
                print_str(f, f"Default value: {par.defval.pretty()}", 4)
            print(file=f)

        # Show the parameters by group, the unnamed group last.
        groups = {param.group for param in list(self.decl.params.values())}
        other_name = "Parameters" if groups == {None} else "Other"
        for group in sorted(groups, key = lambda g: (g is None, g)):
            print("%s:" % (group or other_name), file=f)
            for param in sorted(p for p in self.decl.params
                                if self.decl.params[p].group == group):
                param_help(param, self.decl.params[param],
                           self.decl.params[param].defval is not None)

        if self.decl.results:
            print("Results:", file=f)
            for p in sorted(self.decl.results):
                param_help(p, self.decl.results[p], False)


# Quote a string for use in JDocu text (not in attributes).
def jdocu_quote(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def generate_jdocu(scriptname, package_dirs, section, heading):
    """
    Generate documentation for a script and its parameters in JDocu format,
    and return it as a string.

    scriptname    The script file name.
    package_dirs  A list of package directories, for resolving %simics%
                  references.
    section       The JDocu section ID to generate.
    heading       Its name in the documentation.
    """

    with open(scriptname) as scriptfile:
        (sd, _) = get_declspec(scriptfile, scriptname, package_dirs)

    dcl = sd.decl

    out = []
    out.append('<add id="%s">' % section)
    out.append('  <name>%s</name>' % jdocu_quote(heading))
    if dcl.doc is not None:
        out.append(dcl.doc)

    def gen_group(groupname, params, emit_default):
        o = []
        o.append("  <dt>%s</dt>" % jdocu_quote(groupname))
        o.append("  <dd>")
        o.append("    <dl>")
        for param in params:
            # We use the nl attribute to put the type on the same line
            # as the parameter name. Unfortunately, the JDocu backend
            # for HTML ignores that attribute (bug 22350), so the type
            # comes on a separate line in that format.
            o.append("      <dt nl='false'>%s</dt>" % jdocu_quote(param.name))
            o.append("      <dd>")
            o.append("        &ndash; %s<br/>"
                     % jdocu_quote(param.type.pretty()))
            if param.doc is not None:
                o.append(param.doc)
            if emit_default:
                if param.doc is not None:
                    o.append("        <br/>")
                if param.defval is not None:
                    o.append("        Default value: <tt>%s</tt>"
                             % jdocu_quote(param.defval.pretty()))
                else:
                    o.append("         <b>Mandatory parameter.</b>")
            o.append("      </dd>")

        o.append("    </dl>")
        o.append("  </dd>")
        return o

    out.append("  <dl>")

    groups = {param.group for param in list(dcl.params.values())}
    other_name = "Parameters" if groups == {None} else "Other"
    for group in sorted(groups, key = lambda g: (g is None, g)):
        groupname = group or other_name
        params = sorted(param for param in list(dcl.params.values())
                        if param.group == group)
        out += gen_group(groupname, params, True)

    if dcl.results:
        out += gen_group("Results", list(dcl.results.values()), False)

    out.append("  </dl>")
    out.append("</add>")
    out.append("")          # For the final newline.
    return "\n".join(out)


# Check consistency of a FileDecl, without resolving includes.
# Raise DeclError for errors found.
def check_file_decl_consistency(fdecl):
    errs = []
    for name in fdecl.params:
        par = fdecl.params[name]
        if par.defval is not None:
            # FIXME: We can't check for existence of relative paths
            # here since they depend on the CWD, but we should be able
            # to check absolute paths and perhaps %simics%-relative or
            # %script%-relative ones.
            if not par.type.typecheck(par.defval):
                errs.append(
                    ("Default value of parameter %s: %s"
                     % (name, par.defval.pretty()),
                     par.loc))
                errs.append(
                    ("does not match its type: %s" % (par.type.pretty(),),
                     par.loc))

    if errs:
        raise DeclError(errs)

# Read a FileDecl from the file f having the name filename.
# If the file had a declaration block, return (fdecl, n) where n is how
# many lines were consumed from f.
# Otherwise return None, with an unspecified number of lines read from f.
def get_file_decl(f, filename):
    try:
        r = parse_file(f, filename)
    except ParseError as e:
        raise DeclError([e.args])
    if r:
        (fdecl, _) = r
        check_file_decl_consistency(fdecl)
    return r

class Decl:
    def __init__(self, doc, params, results):
        self.doc = doc                     # string or None
        self.params = params               # {name -> Param}
        self.results = results             # {name -> Result}

# Return the file denoted by include_file inside the script script_file,
# using package_dirs as a list of directories to use for %simics%.
# If no file could be found, return None.
def find_file(script_file, include_file, package_dirs):
    if os.path.isabs(include_file):
        if os.path.isfile(include_file):
            return include_file
        else:
            return None
    else:
        if include_file.startswith("%simics%/"):
            rel_include = include_file[len("%simics%/"):]
            for package_dir in package_dirs:
                candidate = os.path.join(package_dir, rel_include)
                if os.path.isfile(candidate):
                    return candidate
            return None
        else:
            # Relative path: make it relative the script file.
            script_dir = os.path.dirname(os.path.abspath(script_file))
            abs_include = os.path.join(script_dir, include_file)
            if os.path.isfile(abs_include):
                return abs_include
            else:
                return None

# Convert a FileDecl to a Decl, resolving includes.
# Raise DeclError on failure.
def decl_from_filedecl(fdecl, script_file, package_dirs, used_files):
    if fdecl.substitute:
        # Read the substitution file, and then use it in place of the
        # fdecl at hand.
        s = fdecl.substitute
        subf = find_file(script_file, s.filename, package_dirs)
        if subf is None:
            raise DeclError([("file %s not found" % s.filename, s.loc)])
        if subf in used_files:
            raise DeclError([("circular use of file %s" % subf, s.loc)])
        with open(subf) as f:
            r = get_file_decl(f, subf)
        if r is None:
            raise DeclError([("file %s lacks script declaration" % subf,
                              s.loc)])
        (fdecl, _) = r
        script_file = subf

    params = fdecl.params.copy()
    for inc in fdecl.includes:
        incf = find_file(script_file, inc.filename, package_dirs)
        if incf is None:
            raise DeclError([("file %s not found" % inc.filename, inc.loc)])
        if incf in used_files:
            raise DeclError([("circular use of file %s" % incf, inc.loc)])
        with open(incf) as f:
            r = get_declspec_rec(f, incf, package_dirs, used_files + [incf])
        if r is None:
            raise DeclError([("file %s lacks script declaration" % incf,
                              inc.loc)])
        (included_decl, _) = r

        # Take all non-excluded parameters from the included script,
        # and detect conflicts.
        included_names = set()
        for param in list(included_decl.decl.params.values()):
            if param.name not in inc.omissions:
                if param.name in params:
                    raise DeclError([("duplicated parameter %s" % param.name,
                                      param.loc),
                                     ("previously declared here",
                                      params[param.name].loc),
                                     ("when processing this directive",
                                      inc.loc)])
                if param.name in inc.defaults:
                    param.defval = inc.defaults[param.name].defval
                params[param.name] = param
                included_names.add(param.name)

        orphaned_defaults = set(inc.defaults) - included_names
        if orphaned_defaults:
            raise DeclError([("default value for non-imported parameter %s"
                              % name,
                              inc.defaults[name].loc)
                             for name in sorted(orphaned_defaults)])

    return Decl(fdecl.doc, params, fdecl.results)


# Like get_declspec, but taking used_files as a list of files already
# included (to prevent recursion).
def get_declspec_rec(f, filename, package_dirs, used_files):
    r = get_file_decl(f, filename)
    if r is None:
        return None
    (fdecl, n) = r
    decl = decl_from_filedecl(fdecl, filename, package_dirs, used_files)
    return (DeclSpec(filename, decl), n)


def get_declspec(f, filename, package_dirs):
    """Read the declaration from the file f having the name filename.
    package_dirs is a list of directories to match for %simics% in
    "params from" directives.

    If the file had a declaration block, return (d, n) where d is a DeclSpec
    object and n how many lines were consumed from f.

    Otherwise, return None; an unspecified number of lines has then been
    read from f.

    Raise DeclError on error."""

    return get_declspec_rec(f, filename, package_dirs, [])


def arg_value(valstr):
    """Parse a string given as the value for a command-line parameter and
    return it as a Python value."""

    # Extend the set of permitted unquoted string values to include
    # most Unix and Windows file names (but without spaces), since
    # that is convenient when specifying them on the command line.

    # FIXME: should we be nicer still, and permit naked IP numbers too?
    # What about indexed CLI object names containing [] ?
    m = re.match(r"[a-zA-Z/\\_][a-zA-Z0-9/\\:._-]*$", valstr)
    if m and m.group(0) not in ("FALSE", "TRUE", "NIL"):
        return NameToken(m.group(0), None)

    toks = tokenise((s for s in [valstr]), "(argument)", all_input = True)
    val = parse_value(toks)
    t = next(toks)
    if not isinstance(t, EndToken):
        raise ParseError("Syntax error", ("(argument)", 0, 0))
    return val

def match_arg_value(ds, name, valstr):
    val = arg_value(valstr)
    if (ds is not None
        and name in ds.decl.params
        and isinstance(ds.decl.params[name].type, StringType)):
        val = StringValue(str(val.val), None)
    return val.val

# Check a file in a way that is suitable for a pre-commit hook.
# It performs as many checks as possible without accessing other files.
# Raise DeclError on error.
def check_single_file(filename):
    with open(filename, 'rb') as f:
        get_file_decl(f, filename)

# The default action of the script is to check the input files in isolation,
# in a way that is appropriate for a pre-commit hook.
def main():
    if len(sys.argv) <= 1:
        print(("Usage: %s SIMICS-SCRIPTS..." % (sys.argv[0],)), file=sys.stderr)
        sys.exit(1)

    ret = 0
    for filename in sys.argv[1:]:
        try:
            check_single_file(filename)
        except DeclError as e:
            print(e, file=sys.stderr)
            ret = 1
    sys.exit(ret)


__all__ = [
    'ParseError',
    'DeclError',
    'get_declspec',
    'match_arg_value',
    'generate_jdocu',
    ]

if __name__ == '__main__':
    main()
