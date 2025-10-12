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

import atexit
import codecs
import contextlib
import cmputil
import functools
import inspect
import io
import itertools
import keyword
import os
import pydoc
import re
import string
import sys
import datetime
import traceback
import types
import unittest
from functools import total_ordering
import conf
import simics
from simicsutils.internal import ensure_text, ensure_binary, is_config_file
import pathlib
import simicsutils.internal
import importlib
import unicodedata
import package_list
from collections.abc import Iterable

from simics import (
    SIM_get_object,
    conf_attribute_t,
    conf_object_t,
)

from alias_util import (
    obj_aliases,
    user_defined_aliases,
)

from deprecation import DEPRECATED
from legacy import LEGACY
from simicsutils.host import is_windows

from . import tokenizer, tee
from . import number_utils
from .documentation import doc

from .errors import (
    CliException,
    CliError,
    CliTabComplete,
    CliSyntaxError,
    CliTypeError,
    CliValueError,
    CliParseError,
    CliBreakError,
    CliContinueError,
    CliParseErrorInDocText,
    CliErrorInPolyToSpec,
    CliArgumentError,
    CliArgNameError,
    CliOutOfArgs,
    CliAmbiguousCommand,
    CliQuietError,
    CliCmdDefError,
)

string_types = (str, bytes)

from io import StringIO, BytesIO

VT_has_product = simics.get_compile_info

_case_sensitive_files = 'posix' in sys.builtin_module_names

class lenient_stream_writer:
    """A StreamWriter that will write strings unencoded, but will
    encode unicode strings appropriately.

    This is used for stderr encoding to match how sys.stdout works."""

    def __init__(self, writer):
        self.stream_writer = writer

    def write(self, msg):
        m = ensure_binary(msg)
        if isinstance(msg, string_types):
            self.stream_writer.stream.write(m)
            return
        self.stream_writer.write(m)

    def __getattr__(self, name, getattr = getattr):
        """Inherit everything else from the underlying stream"""
        return getattr(self.stream_writer, name)

stop_traceback_codes = set()
def stop_traceback(func):
    """Decorator which tells Simics to stop Python tracebacks at the
    decorated function."""
    stop_traceback_codes.add(func.__code__)
    return func


letters = string.ascii_letters

class command_return(
        metaclass=doc(
            'return interactive messages from commands',
            module = 'cli',
            see_also = ('cli.command_quiet_return, cli.command_verbose_return'),
            synopsis = """\
            command_return(message = None, value = None)""")):
    """Use this class to return from a command that returns one value
    (<param>value</param>) but (may) print something else
    (<param>message</param>) when run interactive.

    <param>message</param> and <param>value</param> may both be functions that
    take no arguments and return the message (a string) or a value,
    respectively.

    If it is a function, <param>message</param> is only evaluated if needed.

    Note that <param>value</param> (or, when a function, its return value) can
    only be of types directly supported by CLI."""

    def __init__(self, message = None, value = None):
        self._message = message
        self._value   = value

    def get_message(self):
        if self._message is None:
            return False
        if callable(self._message):
            return self._message()
        return self._message

    def get_value(self):
        if callable(self._value):
            return self._value()
        return self._value

    def is_quiet(self):
        """Should return True if no message or return value should be printed
        when used interactively."""
        return False

    def is_verbose(self):
        """Should return True if a no message or return value should be printed
        even when used non-interactively."""
        return False

class command_quiet_return(
        command_return,
        metaclass=doc(
            'suppress interactive messages from commands',
            module = 'cli',
            see_also = 'cli.command_return',
            synopsis = 'command_quiet_return(value)')):
    """Use this class to return from a command that returns a value but should
    not print anything when used interactively.

    <param>value</param> should either be the value returned, or a function
    taking no arguments that returns the actual value.

    Note that <param>value</param> can only be of types directly supported by
    CLI."""

    def __init__(self, value):
        command_return.__init__(self, value = value)

    def is_quiet(self):
        return True

class command_verbose_return(
        command_return,
        metaclass=doc(
            'always print return messages from commands',
            module = 'cli',
            see_also = 'cli.command_return',
            synopsis = 'command_verbose_return(message = None, value = None)')):
    """Use this class to return from a command that returns a value or message
    that should be printed even when used non-interactively, but not when used
    in an expression.

    The <param>value</param> and <param>message</param> parameters are
    identical to the same as for <class>cli.command_return</class>."""

    def is_verbose(self):
        return True


class Arg_type:
    def has_expander(self):
        return hasattr(self, "expand")

#
# <add id="cli argument types">
# <name>str_t</name>
# Accepts any one word or quoted string.
# </add>
class Arg_str(Arg_type):
    def desc(self): return "string"
    def value(self, tokens):
        if isinstance(tokens[0], tokenizer.string_token):
            return (tokens[0].value, 1)
        raise CliTypeError("not a string")
    def normalize_value(self, v):
        if isinstance(v, string_types):
            return v
        raise ValueError('not a string')
    def __repr__(self):
        return 'str_t'

str_t = Arg_str()

#
# <add id="cli argument types">
# <name>int_t</name>
# Accepts any integer (regardless of size).
# </add>
#
class Arg_int(Arg_type):
    def desc(self): return "integer"
    def value(self, tokens):
        if isinstance(tokens[0], (tokenizer.int_token, tokenizer.bool_token)):
            return (tokens[0].value, 1)
        raise CliTypeError("not an integer")
    def normalize_value(self, v):
        from scriptdecl import parse_suffixed_int
        if isinstance(v, int):
            return v
        elif isinstance(v, str):
            val = parse_suffixed_int(v)
            if val is not None:
                return val
        raise ValueError('not an integer')
    def __repr__(self):
        return 'int_t'

int_t = Arg_int()

#
# <add id="cli argument types">
# <name>uint_t</name>
# Accepts any unsigned (that is, non-negative) integer (regardless of
# size).
# </add>
#
class Arg_uint(Arg_type):
    def desc(self): return 'unsigned integer'
    def value(self, tokens):
        if isinstance(tokens[0], tokenizer.int_token):
            val = tokens[0].value
            if val >= 0:
                return (val, 1)
        raise CliTypeError('not an unsigned integer')
    def normalize_value(self, v):
        if not isinstance(v, int) or v < 0:
            raise ValueError('not an unsigned integer')
        return v
    def __repr__(self):
        return 'uint_t'

uint_t = Arg_uint()

#
# <add id="cli argument types">
# <name>list_t</name>
# Accepts a comma separated list of CLI types. Can also be given to
# any CLI argument that accepts more than one value as input.
# </add>
#
class Arg_list(Arg_type):
    def desc(self): return "list"
    def get_list_value(self, tokens):
        return [x.value for x in tokens]
    def value(self, tokens):
        if isinstance(tokens[0], tokenizer.list_token):
            return (self.get_list_value(tokens[0].tokens), 1)
        raise CliTypeError("not a list")
    def normalize_value(self, v):
        if isinstance(v, list):
            return [any_cli_value.normalize_value(e) for e in v]
        raise ValueError('not a list of cli-values')
    def __repr__(self):
        return 'list_t'

list_t = Arg_list()

# <add id="cli argument types">
# <name>range_t(min, max, desc, modulo=False)</name>
#
# Returns an argument which accepts any integer <i>x</i> between
# <i>min</i> and <i>max</i> inclusively. <i>desc</i> is the string
# returned as a description of the argument.
#
# Values outside the interval cause an error to be signalled if
# <i>modulo</i> is false, and a modulo-reduction to the specified
# interval otherwise.
# </add>
#
class range_t(Arg_type):
    def __init__(self, min, max, desc, name=None, modulo=False, positive=False):
        if positive:
            # for compatibility in user code only (probably not needed)
            modulo = True
            min = 0
        self.min = min
        self.max = max
        self.description = desc
        self.name = name if name else self.__class__.__name__
        self.modulo = modulo
    def desc(self): return self.description
    def value(self, tokens):
        if (isinstance(tokens[0], tokenizer.float_token)
            and tokens[0].value == int(tokens[0].value)):
            val = int(tokens[0].value)
        elif isinstance(tokens[0], tokenizer.int_token):
            val = tokens[0].value
        else:
            raise CliTypeError("not an integer")

        return (self.normalize(val, CliTypeError), 1)
    def range_msg(self, v):
        return (f'Value {v} outside interval [{self.min}..{self.max}] for'
                f" type '{self.name}'")
    def deprecation_warn_msg(self):
        return f"Modulo calculation for '{self.name}' has been deprecated."
    def deprecation_ref_msg(self):
        return f' Use a value in the range [{self.min}..{self.max}].'
    def deprecate(self, v):
        DEPRECATED(simics.SIM_VERSION_7, self.deprecation_warn_msg(),
                   self.deprecation_ref_msg())
    def modulo_value(self, v):
        width = self.max - self.min + 1
        return (v - self.min) % width + self.min
    def normalize_value(self, v):
        if not isinstance(v, int):
            raise ValueError('not an integer')
        return self.normalize(v, ValueError)
    def normalize(self, v, exception):
        if self.min <= v <= self.max:
            return v
        elif self.modulo:
            new_v = self.modulo_value(v)
            self.deprecate(v)
            return new_v
        else:
            raise exception(f'{self.range_msg(v)}.')
    def __repr__(self):
        return 'range_t'

uint64_max = (1 << 64) - 1
int64_max  = uint64_max // 2
int64_min  = -int64_max - 1

uint32_max = (1 << 32) - 1
int32_max  = uint32_max // 2
int32_min  = -int32_max - 1

uint16_max = (1 << 16) - 1
int16_max  = uint16_max // 2
int16_min  = -int16_max - 1

uint8_max = (1 << 8) - 1
int8_max  = uint8_max // 2
int8_min  = -int8_max - 1

#
# <add id="cli argument types">
# <name>int64_t</name>
# Accepts any unsigned integer that fits in 64 bits, modulo-reducing values
# outside into that range.
# </add>
#
int64_t = range_t(int64_min, uint64_max, "a 64-bit integer", modulo=True,
                  name='int64_t')

#
# <add id="cli argument types">
# <name>sint64_t</name>
# Accepts any signed integer that fits in 64 bits, modulo-reducing values
# outside into that range.
# </add>
#
sint64_t = range_t(int64_min, int64_max, "a 64-bit signed integer",
                   modulo=True, name='sint64_t')

#
# <add id="cli argument types">
# <name>uint64_t</name>
# Accepts any unsigned integer that fits in 64 bits, modulo-reducing values
# outside into that range.
# </add>
#
uint64_t = range_t(0, uint64_max, "a 64-bit unsigned integer", modulo=True,
                   name='uint64_t')

#
# <add id="cli argument types">
# <name>int32_t</name>
# Accepts any unsigned integer that fits in 32 bits, modulo-reducing values
# outside into that range.
# </add>
#
int32_t = range_t(int32_min, uint32_max, "a 32-bit integer", modulo=True,
                  name='int32_t')

#
# <add id="cli argument types">
# <name>sint32_t</name>
# Accepts any signed integer that fits in 32 bits, modulo-reducing values
# outside into that range.
# </add>
#
sint32_t = range_t(int32_min, int32_max, "a 32-bit signed integer",
                   modulo=True, name='sint32_t')

#
# <add id="cli argument types">
# <name>uint32_t</name>
# Accepts any unsigned integer that fits in 32 bits, modulo-reducing values
# outside into that range.
# </add>
#
uint32_t = range_t(0, uint32_max, "a 32-bit unsigned integer", modulo=True,
                   name='uint32_t')

#
# <add id="cli argument types">
# <name>int16_t</name>
# Accepts any unsigned integer that fits in 16 bits, modulo-reducing values
# outside into that range.
# </add>
#
int16_t = range_t(int16_min, uint16_max, "a 16-bit integer", modulo=True,
                  name='int16_t')

#
# <add id="cli argument types">
# <name>sint16_t</name>
# Accepts any signed integer that fits in 16 bits, modulo-reducing values
# outside into that range.
# </add>
#
sint16_t = range_t(int16_min, int16_max, "a 16-bit signed integer",
                   modulo=True, name='sint16_t')

#
# <add id="cli argument types">
# <name>uint16_t</name>
# Accepts any unsigned integer that fits in 16 bits, modulo-reducing values
# outside into that range.
# </add>
#
uint16_t = range_t(0, uint16_max, "a 16-bit unsigned integer", modulo=True,
                   name='uint16_t')

#
# <add id="cli argument types">
# <name>int8_t</name>
# Accepts any unsigned integer that fits in 8 bits, modulo-reducing values
# outside into that range.
# </add>
#
int8_t = range_t(int8_min, uint8_max, "an 8-bit integer", modulo=True,
                 name='int8_t')

#
# <add id="cli argument types">
# <name>sint8_t</name>
# Accepts any signed integer that fits in 8 bits, modulo-reducing values
# outside into that range.
# </add>
#
sint8_t = range_t(int8_min, int8_max, "an 8-bit signed integer", modulo=True,
                  name='sint8_t')

#
# <add id="cli argument types">
# <name>uint8_t</name>
# Accepts any unsigned integer that fits in 8 bits, modulo-reducing values
# outside into that range.
# </add>
#
uint8_t = range_t(0, uint8_max, "an 8-bit unsigned integer", modulo=True,
                  name='uint8_t')
#
# <add id="cli argument types">
# <name>integer_t</name>
# Accepts any unsigned integer that fits in 64 bits, modulo-reducing values
# outside into that range.
# </add>
#
integer_t = int64_t

#
# <add id="cli argument types">
# <name>float_t</name>
# Accepts floating-point numbers.
# </add>
#
class Arg_float(Arg_type):
    def desc(self): return "float"
    def value(self, tokens):
        t = tokens[0]
        if isinstance(t, tokenizer.float_token):
            return (t.value, 1)
        elif isinstance(t, tokenizer.int_token):
            return (float(t.value), 1)
        else:
            raise CliTypeError("not a float")
    def normalize_value(self, v):
        if isinstance(v, float):
            return v
        elif isinstance(v, int):
            return float(v)
        else:
            raise ValueError("not a float")
    def __repr__(self):
        return 'float_t'

float_t = Arg_float()

#
# <add id="cli argument types">
# <name>flag_t</name>
# Passes <tt>True</tt> to command function when flag is provided, <tt>False</tt>
# when flag is not provided.
# </add>
#
class Arg_flag(Arg_type):
    def desc(self): return "flag"
    def value(self, tokens):
        if isinstance(tokens[0], tokenizer.flag_token):
            return (True,1)
        else:
            raise CliTypeError("not a flag")
    def normalize_value(self, v):
        if isinstance(v, bool) or v in [0, 1]:
            return bool(v)
        else:
            raise ValueError("not a boolean")
    def __repr__(self):
        return 'flag_t'

flag_t = Arg_flag()

address_space_prefixes = ['v', 'p', 'l', 'li', 'ld', 'cs', 'ds', 'es', 'fs',
                          'gs', 'ss']
#
# <add id="cli argument types">
# <name>addr_t</name>
# Accepts a target machine address, optionally with an address space
# prefix, such as <tt>v:</tt> for virtual addresses or <tt>p:</tt> for
# physical.
# </add>
#
class Arg_addr(Arg_type):
    def desc(self): return "address"
    def value(self, tokens):
        if isinstance(tokens[0], tokenizer.address_token):
            if isinstance(tokens[1], tokenizer.int_token):
                addr = tokens[1].value
                if addr < 0:
                    raise CliTypeError("addresses cannot be negative")
                elif addr > uint64_max:
                    raise CliTypeError("addresses must fit in 64 bit integers")
                return ((tokens[0].value, addr), 2)
            else:
                raise CliSyntaxError("address had prefix but no number")
        elif isinstance(tokens[0], tokenizer.int_token):
            addr = tokens[0].value
            if addr < 0:
                raise CliTypeError("addresses cannot be negative")
            elif addr > uint64_max:
                addr &= 0xffffffffffffffff
            return (("", addr), 1)
        else:
            raise CliTypeError("not an address")
    def normalize_value(self, v):
        # We handle integers, (address-space, integer)-pairs and
        # 'address-space:integer' strings
        if isinstance(v, int):
            space = ''
            address = v
        elif isinstance(v, (tuple, list)):
            (space, address) = v
        elif isinstance(v, string_types):
            (space, address) = v.split(':')
            address = number_utils.str_number(address)
        else:
            raise ValueError('not an address')
        if not isinstance(space, string_types):
            raise ValueError('not a valid address space specifier')
        if not isinstance(address, int):
            raise ValueError('not a valid address')
        if address < 0:
            raise ValueError('addresses cannot be negative')
        if address > uint64_max:
            address &= 0xffffffffffffffff
        if space not in address_space_prefixes and space != '':
            raise ValueError('unknown address space prefix')
        return (space, address)
    def __repr__(self):
        return 'addr_t'

addr_t = Arg_addr()

# <add id="cli argument types">
# <name>ip_port_t</name>
#
# Accepts integers that are valid IP port numbers (that is, integers
# between 0 and 65535 inclusive).</add>
class ip_port_t(Arg_type):
    def desc(self): return 'IP port (0-65535)'
    def value(self, tokens):
        if isinstance(tokens[0], tokenizer.int_token):
            val = tokens[0].value
        else:
            raise CliTypeError('not an integer')
        if val < 0 or val > 0xffff:
            raise CliTypeError('not a valid IP port number')
        return (val, 1)
    def normalize_value(self, v):
        if not isinstance(v, int) or v < 0 or v > 0xffff:
            raise ValueError('not a valid IP port number')
        return int(v)
    def __repr__(self):
        return 'ip_port_t'

ip_port_t = ip_port_t()

class _DummyCommandHandler:
    def __init__(self, cmd_name):
        self.cmd = cmd_name

    def __call__(self, *_):
        raise CliError(
            "Arguments missing, or illegal use of the '{self.cmd}' command")

# Customer requested, see bug 14664 for details
new_filename_validators = []
def register_new_filename_validator(predicate):
    """Register 'predicate' as a validator for new filenames as
    allowed by 'filename_t' CLI arguments.

    When 'filename_t' is handed a non-existent file name,
    'predicate(filename)' is called. If it returns True, the name is
    allowed; if False, it is rejected.

    The argument to 'predicate' has had "~", "%script%", etc.
    expanded"""
    assert callable(predicate)
    new_filename_validators.append(predicate)

def expand_path_markers(path, use_simpath = True, keep_simics_ref = False,
                        cur_path = None):
    filename = os.path.expanduser(path)
    if '%script%' in filename:
        if cur_path:
            # Use explicit path if provided
            filename = filename.replace('%script%', cur_path)
        else:
            # Use path from current command
            filename = resolve_script_path(filename)

    if not keep_simics_ref and filename.startswith("%simics%"):
        # try project first, then fall back on packages
        if conf.sim.project:
            projfile = simics.SIM_native_path(
                conf.sim.project + filename[len("%simics%"):])
            found = os.path.exists(projfile)
            if found:
                return (True, projfile)

        filename = package_list.lookup_path_in_packages(
            filename[len("%simics%"):])

        # VT_lookup_path_in_package can return files that Python
        # doesn't recognize as file names, which causes problem
        # further down. Ergo, we check os.path.exists() as well.
        found = filename is not None and os.path.exists(filename)
    elif use_simpath:
        target = simics.SIM_lookup_file(filename)
        found = target != None
        if found:
            filename = target
    else:
        found = os.path.exists(simics.SIM_native_path(filename))
    return (found, filename)

def is_checkpoint_bundle(s):
    return simicsutils.internal.is_checkpoint_bundle(pathlib.Path(s))

# <add id="cli argument types">
# <name>filename_t(dirs=False, exist=False, simpath=False, checkpoint=False)</name>
# Generator function for filename arguments. If the <i>dirs</i>
# argument is false (which is default), no directories will be
# accepted. The <i>exist</i> flag, when set, forces the file to
# actually exist. If <i>simpath</i> is true, files will be checked for
# existence using <tt>SIM_lookup_file()</tt>, searching the Simics
# search path. <i>simpath</i> implies <i>exist</i>. On Windows, if Cygwin path
# conversion is performed (see <tt>SIM_native_path()</tt> for details), the
# filename will be converted to host native format.
# The <i>checkpoint</i> flag will constrain the argument to checkpoints,
# and treat existing checkpoints as opaque entities.
# </add>
class filename_t(Arg_type):
    def __init__(self, dirs=False, exist=False, simpath=False,
                 checkpoint=False, keep_simics_ref=False):
        self.allow_dirs = dirs
        self.must_exist = exist or simpath
        self.use_simpath = simpath
        self.checkpoint = checkpoint
        self.keep_simics_ref = keep_simics_ref
    def desc(self):
        if self.must_exist:
            if self.checkpoint:
                s = "an existing checkpoint"
            else:
                if not self.allow_dirs:
                    s = "an existing file"
                else:
                    s = "an existing file or directory"
        else:
            if self.checkpoint:
                s = "a checkpoint"
            else:
                if not self.allow_dirs:
                    s = "a filename"
                else:
                    s = "a file or directory"
        if self.use_simpath:
            s += " (in the Simics search path)"
        return s

    def acceptable_completion(self, name):
        p = os.path.expanduser(name)
        return not self.checkpoint or is_checkpoint_bundle(p)

    def is_ordinary_dir(self, name):
        p = os.path.expanduser(name)
        return (os.path.isdir(p)
                and not (self.checkpoint and is_checkpoint_bundle(p)))

    def expand(self, s):
        # Along with each completion string, return a flag indicating
        # whether it is a directory permitting further completion inside.
        return [(f, self.is_ordinary_dir(f))
                for f in file_expander(s) if self.acceptable_completion(f)]

    def normalize_filename(self, original_filename):
        if '\0' in original_filename:
            # catch zero bytes early as they work poorly with C strings
            raise CliError('Error: illegal filename %s' % (
                    tokenizer.repr_cli_string(original_filename),))

        try:
            found, filename = expand_path_markers(original_filename,
                                                  self.use_simpath,
                                                  self.keep_simics_ref)
        except UnicodeEncodeError:
            raise CliError('Failed converting filename "%s" to system encoding'
                           % original_filename)

        def explain_filename():
            if not filename:
                changed = False
            elif os.altsep:
                # ignore change between os.altsep and os.sep
                changed = (original_filename.replace(os.altsep, os.sep)
                           != filename.replace(os.altsep, os.sep))
            else:
                changed = original_filename != filename

            if changed:
                return ' (%s)' % filename
            return ''

        if not found:
            if self.must_exist:
                raise CliError("Error: file '%s'%s not found%s" % (
                        original_filename, explain_filename(),
                        " in the Simics search path" if self.use_simpath
                        else ""))
            elif filename is None:
                raise CliError("File '%s' not found" % (
                    original_filename,))
            elif not all(p(filename) for p in new_filename_validators):
                raise CliError('Error: %s is not a valid file name' % (
                        tokenizer.repr_cli_string(original_filename),))
        if self.checkpoint:
            def _is_ckpt(fn):
                if os.path.isfile(fn):
                    with open(fn, "rb") as f:
                        return is_config_file(f)
                else:
                    return False
            if (self.must_exist
                and not (is_checkpoint_bundle(filename) or _is_ckpt(filename))):
                raise CliError("Error: '%s' is not a checkpoint."
                               % (filename,))
        elif not self.allow_dirs and found and os.path.isdir(filename):
            raise CliError("Error: '%s'%s is a directory" % (
                original_filename, explain_filename()))
        return filename

    def value(self, tokens):
        if not isinstance(tokens[0], tokenizer.string_token) or not tokens[0].value:
            raise CliTypeError("not a valid filename")

        return (self.normalize_filename(tokens[0].value), 1)

    def normalize_value(self, v):
        if not isinstance(v, string_types):
            raise ValueError('filename not a string')
        try:
            return self.normalize_filename(v)
        except CliError as e:
            raise ValueError(e.args)

def expand_expression_to_dnf(s):
    '''The interfaces required/needed can be expressed as a string such
    as "(a | b) & c". Interface names, may not contain spaces. Only
    '&', '|' and parentheses (including nested) are supported.
    This function generates a Disjunctive Normal Form (DNF) list of tuples
    for all variants for the expression.'''

    # Checks that a string is in dnf format, e.g., "a&b|b&d|e"
    def is_dnf(s):
        if '(' in s:
            return False
        if ')' in s:
            return False
        return True

    # Return the position of a matching parenthesis to the one on position pos,
    # -1 if not found
    def find_matching_paren(s, pos):
        level = 0
        for i in range(pos + 1,len(s)):
            if s[i] == ')':
                if level == 0:
                    return i
                else:
                    level -= 1
            elif s[i] == '(':
                level += 1
        return -1

    # Return the leftmost parentheses expression, together with, the head and
    # tail e.g., "a&(b|c&d)|4" -> ("a&", (b|c&d), "|4"
    def get_paren_exp(s):
        p = s.find('(')
        q = find_matching_paren(s, p)

        if -1 in (p, q):
            raise TypeError

        hd = s[:p]    # everything before '('
        ex = s[p+1:q] # inside "()"
        tl = s[q+1:]  # everything after ')'

        return (hd, ex, tl)

    # Return the for first "and" cluster in the string, including
    # parentheses, e.g., "(a|b)&c&d|(f&g)" -> "(a|b)&c&d"
    def get_first_and_group(s):
        i = 0
        ret = ""
        while i < len(s):
            if s[i] == '|':
                return (ret, s[i:])
            elif s[i] == '(':
                q = find_matching_paren(s, i)
                ret += s[i:q+1]
                i = q + 1
            else:
                ret += s[i]
                i += 1
        return (ret, "")

    # Return the last "and" cluster in the string, parentheses not needed
    # (already processed), e.g., "a&b|b&c&d" -> "b&c&d"
    def get_last_and_group(s):
        i = len(s) - 1
        ret = ""
        while i >= 0:
            if s[i] == '|':
                return (s[:i+1], ret)
            else:
                ret = s[i] + ret
                i -= 1

        return ("", ret)

    def ends_with(s, c):
        assert s == "" or s[-1] == c

    def starts_with(s, c):
        assert s == "" or s[0] == c

    def convert_to_dnf(s):
        if is_dnf(s):
            return s
        (hd, exp, tl) = get_paren_exp(s)

        (b, lg) = get_last_and_group(hd)
        (fg, e) = get_first_and_group(tl)

        # assertions
        ends_with(b, '|')
        ends_with(lg, '&')
        starts_with(fg, '&')
        starts_with(e, '|')

        ors = convert_to_dnf(exp).split('|')
        ors_concat = [(lg + o + fg) for o in ors]

        return convert_to_dnf(b + '|'.join(ors_concat) + e)

    # We accept both empty strings and None
    if s == "" or s == None:
        return []

    s1 = s.replace(" ", "")
    dnf = convert_to_dnf(s1)

    return dnf


#
# <add id="cli argument types">
# <name>obj_t(desc, kind = None, want_port = False)</name>
# Returns an argument which accepts any object.
#
# <i>desc</i> is the string returned as a description of the argument.
# <i>kind</i> can be used to limit the accepted objects to only allow
# objects of a certain kind.  This parameter can either be a class
# name that the object should be an instance of, or the name of an
# interface that the object must implement, or a tuple of
# kinds. <i>want_port</i> indicates whether it should be allowed to
# specify an object and a port name, separated with a colon.  If a
# port is wanted, the argument will be a list [obj, port] instead of
# only the object.  </add>
#
class obj_t(Arg_type):
    def __init__(self, desc, kind = None, want_port = False,
                 cls = None, iface = None):
        def dnf_expand(spec):
            if isinstance(spec, tuple):
                return set.union(*[dnf_expand(w) for w in spec])
            elif not spec:
                return set()
            else:
                spec = spec.replace("-", "_")
                return set(expand_expression_to_dnf(spec).split("|"))
        def as_set(x):
            if not x:
                return set()
            return {x} if not isinstance(x, tuple) else set(x)

        self.description = desc
        self.want_port = want_port
        if isinstance(kind, types.FunctionType):
            self._func = kind
            self._classes = set()
            self._ifaces = set()
        else:
            self._func = None
            self._ifaces = dnf_expand(iface) | dnf_expand(kind)
            self._classes = as_set(cls) | as_set(kind)

    def desc(self): return self.description
    def expand(self, s):
        if self._func:
            r = _ObjFilterExpander(self._func).expand(s)
        else:
            r = _ObjExpander(self._ifaces, self._classes).expand(s)
            if self.want_port:
                r += _PortIfaceExpander(self._ifaces).expand(s)
                r = list(set(r))
        return r

    @property
    def kinds(self):
        # used by t30_frontend to generate object arguments for testing
        return tuple(self._ifaces | self._classes)

    def value(self, tokens):
        if not isinstance(tokens[0], tokenizer.string_token):
            raise CliTypeError("not a valid object")

        (objname, port) = (tokens[0].value, None)
        if self.want_port and ":" in objname:
            (objname, _, port) = objname.rpartition(":")

        try:
            obj = get_object(objname)
        except simics.SimExc_General:
            raise CliTypeError(f"not an object '{objname}'")

        if not (self._valid_obj(obj) if port is None
                else self._valid_port(obj, port)):
            raise CliTypeError("wrong object type")

        return ([obj, port] if self.want_port else obj, 1)

    def _valid_obj(self, obj):
        # returns True if object is of the appropriate type
        if self._func:
            return self._func(obj)
        def has_iface(iface):
            return all(hasattr(obj.iface, i) for i in iface.split("&"))
        return ((not self._classes and not self._ifaces)
                or obj.classname in self._classes
                or any(has_iface(i) for i in self._ifaces))

    def _valid_port(self, obj, port):
        # returns True if port is of the appropriate type
        match = re.match(r'([a-zA-Z_]\w*)\[(\d+)\]$', port)
        if match:
            (port_name, index) = (match.group(1), int(match.group(2)))
        else:
            (port_name, index) = (port, -1)
        iface_kind = [(iface, pn) for (name, pn, iface) in
                      simics.VT_get_port_interfaces(obj.classname)
                      if name == port_name]
        if not iface_kind:
            return False
        (iface, size) = iface_kind[0]
        if (index == -1) != (size == 1):
            return False
        if index >= size:
            return False
        return not self._ifaces or any(iface == i for i in self._ifaces)

    def normalize_value(self, v):
        if isinstance(v, string_types):  # support same strings as CLI does
            (objname, port) = (v, None)
            if self.want_port and ":" in objname:
                (objname, _, port) = objname.rpartition(":")
            try:
                obj = SIM_get_object(objname)
            except simics.SimExc_General:
                raise ValueError(f"not an object '{objname}'")
        elif isinstance(v, (tuple, list)):
            if not self.want_port:
                raise ValueError("wrong object type")
            (obj, port) = v
        else:
            (obj, port) = (v, None)
        if not isinstance(obj, conf_object_t):
            raise ValueError('not a conf_object_t')
        if not (port is None or isinstance(port, string_types)):
            raise ValueError('port not a string')

        if not (self._valid_obj(obj) if port is None
                else self._valid_port(obj, port)):
            raise ValueError("wrong object type")

        return [obj, port] if self.want_port else obj

# <add id="cli argument types">
# <name>string_set_t(strings)</name>
#
# Accepts only strings from the given set. <i>strings</i> can be any
# iterable, such as a tuple, list, or set, in which case the return
# value is the exact string the user gave; or a dictionary mapping
# acceptable user input strings to return values.
#
# The optional parameter <arg>visible</arg> is a list of strings. If
# given, only strings in this list will be suggested by the expander.
#
# </add>
class string_set_t(Arg_type):
    def __init__(self, strings, visible=None):
        if not hasattr(strings, 'keys'):
            # strings is not a dictionary; make it one
            strings = dict((x, x) for x in strings)
        self.strings = strings
        if visible == None:
            self.exp_strs = list(self.strings.keys())
        else:
            self.exp_strs = [x for x in visible if x in self.strings]
    def desc(self):
        return '|'.join(sorted(self.exp_strs))
    def expand(self, s):
        return get_completions(s, sorted(self.exp_strs))
    def value(self, tokens):
        (s, pos) = str_t.value(tokens)
        if s in self.strings:
            s = self.strings[s]
            return (s, pos)
        else:
            raise CliTypeError('illegal value')
    def normalize_value(self, v):
        if v in self.strings:
            return self.strings[v]
        else:
            raise ValueError('illegal value')

# <add id="cli argument types">
# <name>bool_t(true_str, false_str)</name>
#
# Generator function for boolean arguments. A boolean argument accepts
# the strings "TRUE" and "FALSE", as well as boolean integers (that
# is, the values 0 and 1). In addition, if the optional strings
# <arg>true_str</arg> and <arg>false_str</arg> are given, the boolean
# argument will accept them as well.  The argument passes True or
# False to the command function depending on which string (or value)
# was given.
#
# </add>
class bool_t(Arg_type):
    def __init__(self, true_str = 'TRUE', false_str = 'FALSE'):
        self.strings = {'TRUE' : True, 'FALSE': False}
        self.strings[true_str] = True
        self.strings[false_str] = False

    def desc(self):
        return '|'.join(sorted(self.strings.keys()))

    def expand(self, s):
        return get_completions(s, sorted(self.strings.keys()))

    def value(self, tokens):
        if isinstance(tokens[0], tokenizer.bool_token):
            return (tokens[0].value, 1)
        elif isinstance(tokens[0], tokenizer.int_token):
            return (tokens[0].value != 0, 1)
        elif (isinstance(tokens[0].value, string_types)
              and tokens[0].value in self.strings):
            return (self.strings[tokens[0].value], 1)
        else:
            raise CliTypeError('illegal value for bool')
    def normalize_value(self, v):
        if isinstance(v, string_types) and v in self.strings:
            return self.strings[v]
        if isinstance(v, int) and v in [0, 1]:
            return bool(v)
        if isinstance(v, bool):
            return v
        raise ValueError('illegal value for bool')

boolean_t = bool_t()

# <add id="cli argument types">
# <name>nil_t</name>
#
# Nil argument. Accepts NIL, zero or the empty string, and passes None to
# the command function. Not so usable by itself, but see e.g.
# <fun>poly_t</fun>.
#
# </add>
class nil_t(Arg_type):
    def desc(self):
        return 'NIL'
    def expand(self, s):
        return get_completions(s, ['NIL'])
    def value(self, tokens):
        if (isinstance(tokens[0], (tokenizer.nil_token, tokenizer.int_token, tokenizer.quoted_token))
            and not tokens[0].value):
            return (None, 1)
        else:
            raise CliTypeError('illegal value')
    def normalize_value(self, v):
        if v is None or (v == 0 and isinstance(v, int)
                         and not isinstance(v, bool)) or v == "":
            return None
        raise ValueError('not nil')

nil_t = nil_t()

# <add id="cli argument types">
# <name>poly_t(desc, type1, type2, ...)</name>
#
# Generates an argument with the given description that will match any
# of the given types; they will be tried one by one, in the order
# specified, and the first one that accepts the input will be used.
#
# </add>
class poly_t(Arg_type):
    def __init__(self, desc, *types):
        self.types = types
        self.description = desc
    def desc(self):
        return self.description
    def has_expander(self):
        return any(t.has_expander() for t in self.types)
    def expand(self, s):
        c = []
        for t in self.types:
            if t.has_expander():
                c.extend(t.expand(s))
        return c
    def value(self, tokens):
        for t in self.types:
            try:
                return t.value(tokens)
            except CliTypeError:
                pass
        raise CliTypeError('illegal value')
    def normalize_value(self, v):
        for t in self.types:
            try:
                return t.normalize_value(v)
            except (TypeError, ValueError):
                pass
        raise ValueError('illegal value %r' % (v,))

# A handler that matches all valid CLI argument values. The order here
# is such that numbers are preferred over addresses, addresses are
# preferred over strings and strings are preferred over objects
any_cli_value = poly_t('any CLI value', int_t, float_t, addr_t, str_t,
                       obj_t('any object'), boolean_t, nil_t, list_t)

# If the simulation stops, and it is not because a user initiated
# command finished, we should update the frontend processor to the
# processor we stopped on, if such a processor is available.
def command_finished():
    return any(k == 'finished' for k, *_ in simics.VT_get_stop_reasons())

def matches_request(obj, want_cpu, want_step, want_cycle):
    if want_cpu and not hasattr(obj.iface, "processor_info"):
        return False
    if want_step and not hasattr(obj.iface, "step"):
        return False
    if want_cycle and not hasattr(obj.iface, "cycle"):
        return False
    return True

class CurrentObject:
    def __init__(self):
        self.last_obj = None
        simics.SIM_register_attribute(
            "sim", "current_frontend_object",
            self.attr_get,
            self.attr_set,
            simics.Sim_Attr_Optional, "o|n",
            "Currently selected object in the"
            " command line environment.")

        # The use of Object_Pre_Delete hap doesn't work since during
        # the deletion Simics checks the sim->current_frontend_object
        # attribute value and the attribute getter finds not yet deleted CPU.
        simics.SIM_hap_add_callback(
                "Core_Conf_Object_Delete", self.del_obj, None)

    # Determine what to use as current frontend object.
    # Return None if there are no processors to use at all.
    def compute(self):
        # First, see if the last execution should make us use a new object.
        last_brk = simics.CORE_get_last_break_object()
        if (last_brk and hasattr(last_brk.iface, "processor_info")
            and not command_finished()):
            return last_brk

        # Otherwise, try the one we used the last time.
        if self.last_obj:
            assert hasattr(self.last_obj, "name")  # last_obj is not deleted
            return self.last_obj

        # If we didn't have one, use the processor_info object in the
        # current cell with the lowest processor number (for backward
        # compatibility).
        cpus = list(simics.SIM_object_iterator_for_interface(
            [simics.PROCESSOR_INFO_INTERFACE]))
        if cpus:
            return min(cpus, key = lambda o: getattr(o, "processor_number", 99))

        search_order = [
            [
                simics.EXECUTE_INTERFACE,
                simics.STEP_INTERFACE,
                simics.CYCLE_INTERFACE,
             ],
            [simics.EXECUTE_INTERFACE, simics.CYCLE_INTERFACE],
            [simics.STEP_INTERFACE],
            [simics.CYCLE_INTERFACE],
        ]
        for ifaces in search_order:
            objs = list(simics.SIM_object_iterator_for_interface(ifaces))
            if objs:
                return min(objs)

        # Give up.
        return None

    def get(self, cpu, step, cycle):
        obj = conf.sim.last_frontend_object
        if not obj:
            obj = self.compute()
            conf.sim.last_frontend_object = obj
        assert obj is None or hasattr(obj, "name")  # obj is not deleted
        self.last_obj = obj
        if obj and matches_request(obj, cpu, step, cycle):
            return obj
        else:
            return None

    def set(self, obj, silent=False):
        if not (hasattr(obj.iface, "processor_info")
                or hasattr(obj.iface, "step")
                or hasattr(obj.iface, "cycle")):
            return False
        conf.sim.last_frontend_object = obj
        if self.last_obj and obj != self.last_obj and not silent:
            print("Setting new inspection object: %s" % obj.name)
        self.last_obj = obj
        return True

    def attr_get(self, obj):
        return self.get(False, False, False)

    def attr_set(self, obj, val):
        if val and not self.set(val):
            return simics.Sim_Set_Illegal_Value
        return simics.Sim_Set_Ok

    def sim_stopped(self, data, obj, exc, err):
        self.set(self.compute())

    def del_obj(self, data, obj, obj_name):
        # If obj.last_obj was deleted it won't have "name" attribute.
        if not (self.last_obj is None or hasattr(self.last_obj, "name")):
            self.last_obj = None
            conf.sim.last_frontend_object = None

    def enable_stop_message(self):
        simics.SIM_hap_add_callback("Core_Simulation_Stopped",
                                    self.sim_stopped, None)

current_object = CurrentObject()
if not simics.SIM_get_batch_mode():
    current_object.enable_stop_message()

def set_current_frontend_object(obj, silent=False):
    """Set the currently selected frontend object. The object must implement
    one of the processor_info, step and cycle interfaces. If not, a CliError
    is raised."""
    if not current_object.set(obj, silent):
        raise CliError("The %s object does not implement any of the"
                       " processor_info, step, cycle interfaces" % obj.name)

def current_frontend_object(cpu = False, step = False, cycle = False):
    """Return the currently selected frontend object. The object will implement
    at least one of the processor_info, step and cycle interfaces. The cpu,
    step and cycle arguments can be used to specify which of the interfaces the
    calling code expects the object to implement. If it does not, a CliError
    is raised."""
    obj = current_object.get(cpu, step, cycle)
    if obj:
        return obj

    if not (cpu or step or cycle):
        raise CliError("No frontend object selected")
    ifaces = []
    if cpu and not current_cpu_obj_null():
        ifaces.append('processor_info')
    if step and not current_step_obj_null():
        ifaces.append('step')
    if cycle and not current_cycle_obj_null():
        ifaces.append('cycle')
    raise CliError("The frontend object does not implement the %s interface%s"
                   " required by the command"
                   % ("/".join(ifaces), "" if len(ifaces) == 1 else "s"))

def current_frontend_object_null(cpu = False, step = False, cycle = False):
    """Works like current_frontend_object, but returns None instead of raising
    CliError."""
    try:
        return current_frontend_object(cpu = cpu, step = step, cycle = cycle)
    except CliError:
        return None

# Helper functions when only one interface is needed (processor/step/cycle):

def current_cpu_obj():
    """Return the currently selected frontend object if it implements the
    processor_info interface. If not, a CliError is raised."""
    return current_frontend_object(cpu = True, step = False, cycle = False)

def current_step_obj():
    """Return the currently selected frontend object if it implements the
    step interface. If not, a CliError is raised."""
    return current_frontend_object(cpu = False, step = True, cycle = False)

def current_cycle_obj():
    """Return the currently selected frontend object if it implements the
    cycle interface. If not, a CliError is raised."""
    return current_frontend_object(cpu = False, step = False, cycle = True)

def current_cpu_obj_null():
    """Return the currently selected frontend object if it implements the
    processor_info interface. If not, None is returned."""
    return current_object.get(cpu = True, step = False, cycle = False)

def current_step_obj_null():
    """Return the currently selected frontend object if it implements the
    step interface. If not, None is returned."""
    return current_object.get(cpu = False, step = True, cycle = False)

def current_cycle_obj_null():
    """Return the currently selected frontend object if it implements the
    cycle interface. If not, None is returned."""
    return current_object.get(cpu = False, step = False, cycle = True)

def current_step_queue_null():
    """Similar to current_step_obj_null() but looks at both the currently
    selected frontend object and its queue object"""
    obj = current_frontend_object()
    if hasattr(obj.iface, "step"):
        return obj
    elif obj.queue and hasattr(obj.queue.iface, "step"):
        return obj.queue
    else:
        return None

def current_step_queue():
    """Similar to current_step_obj() but looks at both the currently
    selected frontend object and its queue object"""
    obj = current_step_queue_null()
    if obj:
        return obj
    # Trigger proper error message
    current_frontend_object(step = True)

def current_cycle_queue_null():
    """Similar to current_cycle_obj_null() but looks at both the currently
    selected frontend object and its queue object"""
    obj = current_frontend_object()
    if hasattr(obj.iface, "cycle"):
        return obj
    elif obj.queue and hasattr(obj.queue.iface, "cycle"):
        return obj.queue
    else:
        return None

def current_cycle_queue():
    """Similar to current_cycle_obj() but looks at both the currently
    selected frontend object and its queue object"""
    obj = current_cycle_queue_null()
    if obj:
        return obj
    # Trigger proper error message
    current_frontend_object(cycle = True)

def current_ps_queue_null():
    """Similar to current_cycle_queue_null(), but returns the 'ps' queue"""
    obj = current_frontend_object()
    if hasattr(obj, "vtime"):
        return obj.vtime.ps
    elif obj.queue and hasattr(obj.queue, "vtime"):
        return obj.queue.vtime.ps
    else:
        return None

# checks Simics isn't running
def assert_not_running():
    if simics.SIM_simics_is_running():
        raise CliError("This command cannot be used when Simics is running.")

def distributed_simulation():
    return (bool(list(simics.SIM_object_iterator_for_class(
        'remote_sync_domain')))
            or bool(list(simics.SIM_object_iterator_for_class(
                'remote_sync_server'))))

#
# Support for the change-namespace (cn) command, see commands.py
# Current component is the component for which slot names can be given
# to fetch the corresponding objects, see get_object.
#

# The "path" to the current component in the component hierarchy,
# top level first, e.g., ["system_cmp0", "board1, "cpu"] where
# cpu is the current component. If empty, no current component exists.
component_path = []

# same as SIM_get_object although it allows slot names to be given for
# the current component and object aliases
def get_object(name):
    "get top level object or object in slot for the current component"
    if name.startswith("."):
        return SIM_get_object(name[1:])

    # ugly: we allow absolute paths without . first
    obj = simics.VT_get_object_by_name(name)
    if not obj and component_path:
        obj = simics.SIM_object_descendant(current_component(), name)
    if not obj and name in user_defined_aliases():
        obj = simics.VT_get_object_by_name(user_defined_aliases()[name])
    if not obj:
        obj = obj_aliases().get_object(name)
    if not obj:
        raise simics.SimExc_General("No object '%s'" % name)
    return obj

def multiple_matches(all, subname):
    count = 0
    for n in all:
        if n.endswith(subname):
            count += 1
            if count > 1:
                return True
    return False

# Given a list of objects, return a list of hierarchical names
# where the beginning of the name has been stripped but still defines
# a unique suffix name among all objects currently in the
# configuration. Strip only entire namespaces.
def get_shortest_unique_object_names(objs):
    all_obj_names = [o.name for o in simics.SIM_object_iterator(None)]
    names = [o.name for o in objs]
    ret = []

    for oname in names:
        last_subname = oname
        parts = oname.split(".")

        for i in range(len(parts)):
            parts = parts[1:]
            subname = ".".join(parts)
            if multiple_matches(all_obj_names, subname):
                break
            last_subname = subname

        ret.append(last_subname)

    return ret

class _test_get_shortest_unique_object_names(unittest.TestCase):
    def test_unique(self):
        from simics import SIM_create_object
        o0 = SIM_create_object("namespace", "a")

        self.assertEqual(get_shortest_unique_object_names([o0]), ["a"])

        SIM_create_object("namespace", "a.b")
        SIM_create_object("namespace", "a.b.c")
        o1 = SIM_create_object("namespace", "a.b.c.d1")
        o2 = SIM_create_object("namespace", "a.b.c.d2")

        self.assertEqual(get_shortest_unique_object_names([o1, o2]),
                         ["d1", "d2"])

        SIM_create_object("namespace", "a.b.c2")
        o3 = SIM_create_object("namespace", "a.b.c2.d2")

        self.assertEqual(get_shortest_unique_object_names([o1, o2, o3]),
                         ["d1", "c.d2", "c2.d2"])

        SIM_create_object("namespace", "a2")
        SIM_create_object("namespace", "a2.b")
        SIM_create_object("namespace", "a2.b.c")
        o4 = SIM_create_object("namespace", "a2.b.c.d1")

        self.assertEqual(get_shortest_unique_object_names([o1, o4]),
                         ["a.b.c.d1", "a2.b.c.d1"])

def get_component_path():
    "return current component path"
    return component_path

def current_component():
    "get current component object"
    if len(component_path):
        return SIM_get_object(".".join(component_path))
    else:
        return None

def current_namespace():
    "get current namespace"
    return ".".join(component_path)

def _current_namespace_obj():
    return current_component()

def set_current_namespace(ns):
    "set current namespace"
    global component_path
    component_path = ns.split(".") if ns else []



# Return a dictionary mapping names in the current namespace to objects.
# The behavior can be modified as follows:
#   component - namespace to use instead of the current namespace
#   root      - consider root directory instead of current namespace
#   recursive - return all descendants
#   iface     - only return objects implementing specified interface
#   all       - consider all objects
#   ports     - include standard port object hierarchies when
#               the component argument is not None
#   include_root - when the component argument is not None, include the root
#                  object of the namespace, unless it is a component
def visible_objects(iface = "", all = False, component = None,
                    recursive = False, root = False, ports = False,
                    include_root = False):
    "get a dictionary of top level objects or slot objects"
    if all:
        (component, recursive) = (None, True)
    elif component == None and component_path and not root:
        component = SIM_get_object(".".join(component_path))

    if recursive:
        objs = simics.SIM_object_iterator(component)
    else:
        objs = simics.CORE_shallow_object_iterator(component, True)
        if component is not None and ports:
            for port in ["bank", "port", "impl"]:
                port_obj = simics.SIM_object_descendant(component, port)
                if port_obj:
                    objs = itertools.chain(
                        objs, simics.SIM_object_iterator(port_obj))

    stripstr = component.name + "." if component else None
    def relname(s):
        return s.replace(stripstr, "", 1) if stripstr else s

    if include_root and component is not None and not is_component(component):
        objs = itertools.chain([component], objs)
    d = dict((relname(o.name), o) for o in objs
             if not iface or hasattr(o.iface, iface))

    # add alias objects from user-defined object aliases
    if not root:
        d.update(user_defined_aliases().visible_objects(iface))
    return d


# collect all cpu names
def all_cpus():
    cl = []
    for o in list(visible_objects().values()):
        if hasattr(o.iface, "processor_info"):
            cl.append(o.name)
    return cl

def cpu_expander(comp):
    return get_completions(comp, all_cpus())

# generic expanders:
#
#  object_expander(kind) returns an expander for objects of the
#   given class or with a given interface

class _ObjExpander:
    def __init__(self, iface = None, cls = None):
        self._classes = cls
        self._ifaces = iface

    def expand(self, string):
        d = visible_objects(recursive = True)
        def has_iface(obj, iface):
            return all(hasattr(obj.iface, i) for i in iface.split("&"))
        return [name for (name, o) in d.items()
                if name.startswith(string)
                if ((not self._classes and not self._ifaces)
                    or o.classname in self._classes
                    or any(has_iface(o, i) for i in self._ifaces))]

class _PortIfaceExpander:
    def __init__(self, iface = None):
        self._ifaces = iface

    def expand(self, string):
        d = visible_objects(recursive = True)
        ret = []
        for (name, o) in d.items():
            for (p, _, i) in simics.VT_get_port_interfaces(o.classname):
                if not self._ifaces or i in self._ifaces:
                    s = name + ':' + p
                    if s.startswith(string):
                        ret.append(s)
                        continue
        return ret

class _ObjFilterExpander:
    def __init__(self, func = None):
        self._func = func

    def expand(self, string):
        d = visible_objects(recursive = True)
        return [name for (name, o) in d.items()
                if name.startswith(string)
                if self._func(o)]


@doc('standard expander for an object argument',
     module = 'cli')
def object_expander(kind):
    """For command writing: standard expander that can be use to provide
    argument completion on all objects of a given class or matching a given
    interface (<param>kind</param>).

    For example, to expand a string with the list of processor available in the
    machine, you would write:
    <pre>
      arg(str_t, "cpu", expander =  object_expander("processor_info"))
    </pre>

    To expand a string to all <class>gcache</class> objects:
    <pre>
      arg(str_t, "cache", expander = object_expander("gcache"))
    </pre>"""
    return _ObjExpander(cls = kind, iface = kind).expand

def pr(text):
    sys.stdout.write(text)

class Markup:
    """This class is used to embed markup (such as bold or italic) in
    a text string. Use the 'emit' method to print the text with a
    formatter.

    Example:
        m = Markup('This is a ', Markup.Bold('bold'), ' word.')
        m.emit(formatter)

        m = Markup('The ', Markup.Keyword('while'), ' keyword requires an',
                   ' iterator, ', Markup.Arg('$var'))
        m.emit(formatter)
    """

    def __init__(self, *markup):
        self.markup = markup

    def emit(self, formatter):
        def emit(m):
            if isinstance(m, Markup.Markup):
                return m.emit(formatter)
            else:
                return formatter.escape(m)
        return ''.join([emit(m) for m in self.markup])

    def __repr__(self):
        return 'Markup(%s)' % (', '.join([ repr(m) for m in self.markup ]))

    class Markup:
        """Abstract base class of the markup subtypes."""
        def __init__(self, msg):
            self.msg = msg
        def __repr__(self):
            return '%s(%s)' % (self.__class__.__name__, repr(self.msg))
        def emit(self, formatter):
            raise NotImplementedError

    class Bold(Markup):
        def emit(self, formatter):
            return formatter.bold(self.msg)
    class Italic(Markup):
        def emit(self, formatter):
            return formatter.italic(self.msg)

    class Keyword(Bold):
        pass
    class Arg(Italic):
        pass

class Formatter:
    def __init__(self, pr_func = pr):
        self.pr = pr_func

    def bold_start(self):
        return ""

    def bold_end(self):
        return ""

    def maybe_bold_start(self):
        return self.bold_start()

    def maybe_bold_end(self):
        return self.bold_end()

    def italic_start(self):
        return ""

    def italic_end(self):
        return ""

    def maybe_italic_start(self):
        return self.italic_start()

    def maybe_italic_end(self):
        return self.italic_end()

    def sup_start(self):
        return "^{"
    def sup_end(self):
        return "}"

    def sub_start(self):
        return "_{"
    def sub_end(self):
        return "}"

    def all_stop(self):
        return ""

    def bold(self, s):
        return self.bold_start() + s + self.bold_end()

    def italic(self, s):
        return self.italic_start() + s + self.italic_end()

    def escape(self, str):
        return str

    def suspend(self):
        return ""

    def resume(self):
        return ""

class Text_formatter(Formatter):
    pass

def filter_out_simics_markup(s):
    return re.sub('\033[^>]*>', '', s)

class esc_jdocu_formatter(Formatter):
    # escaped jdocu
    _bold_start   = '\033b>'
    _bold_end     = '\033/b>'
    _italic_start = '\033i>'
    _italic_end   = '\033/i>'
    def __init__(self, pr_func = pr):
        Formatter.__init__(self, pr_func)
        self.bold_active = False
        self.italic_active = False
    def bold_start(self):
        self.bold_active = True
        return self._bold_start
    def bold_end(self):
        self.bold_active = False
        return self._bold_end
    def italic_start(self):
        self.italic_active = True
        return self._italic_start
    def italic_end(self):
        self.italic_active = False
        return self._italic_end

    def sup_start(self):
        return "^{"
    def sup_end(self):
        return "}"

    def sub_start(self):
        return "_{"
    def sub_end(self):
        return "}"

    def suspend(self):
        s = ""
        if self.bold_active:
            s += self._bold_end
        if self.italic_active:
            s += self._italic_end
        return s
    def resume(self):
        s = ""
        if self.bold_active:
            s += self._bold_start
        if self.italic_active:
            s += self._italic_start
        return s

def html_escape(s):
    return (s.replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))

class HTML_formatter(Formatter):
    def __init__(self, pr_func = pr):
        Formatter.__init__(self, pr_func)
        self.bold_active = False
        self.italic_active = False
    def bold_start(self):
        self.bold_active = True
        return "<b>"
    def bold_end(self):
        self.bold_active = False
        return "</b>"
    def italic_start(self):
        self.italic_active = True
        return "<i>"
    def italic_end(self):
        self.italic_active = False
        return "</i>"
    def maybe_bold_start(self):
        if not self.bold_active:
            return self.bold_start()
        return ""
    def maybe_bold_end(self):
        if self.bold_active:
            return self.bold_end()
        return ""
    def maybe_italic_start(self):
        if not self.italic_active:
            return self.italic_start()
        return ""
    def maybe_italic_end(self):
        if self.italic_active:
            return self.italic_end()
        return ""

    def sup_start(self):
        return "<sup>"
    def sup_end(self):
        return "</sup>"

    def sub_start(self):
        return "<sub>"
    def sub_end(self):
        return "</sub>"

    def escape(self, s):
        return html_escape(s)

format_names = { "html": HTML_formatter,
                 "jdocu": HTML_formatter,
                 "text": Text_formatter(),
                 "esc-jdocu": esc_jdocu_formatter() }

def get_formatter(format = 'default'):
    if format == 'default':
        if stdout_output_mode.markup:
            format = 'esc-jdocu'
        else:
            format = 'text'

    f = format_names[format]
    if isinstance(f, Formatter):
        return f
    return f()

def format_synopses(cmd):
    """Returns the synopses of 'cmd' formatted for use in error
    messages."""
    synopses = get_synopses(cmd, 'esc-jdocu')
    if len(synopses) == 1:
        return 'SYNOPSIS: %s' % (synopses[0],)
    return 'SYNOPSIS:\n  ' + '\n  '.join(synopses)

def get_synopses(cmd, ftype):
    """Returns a list of the synopses of command 'cmd', each formatted using
    the formatter with name 'ftype'."""

    if cmd.synopses != None:
        formatter = get_formatter(ftype)
        return [ synopsis.emit(formatter) for synopsis in cmd.synopses ]

    return [ get_synopsis(cmd, 0, ftype) ]

def get_synopsis(cmd, max_len, ftype):
    """Returns (the first available) synopsis for command 'cmd',
    printing up to 'max_len' characters on each line, using the formatter
    with name 'ftype'."""

    formatter = get_formatter(ftype)

    if cmd.synopses:
        return cmd.synopses[0].emit(formatter)

    buf = ""

    if max_len == 0:
        max_len = len(cmd.name)

    command_name = formatter.bold(formatter.escape(cmd.name))

    for i, arg in enumerate(cmd.args):
        if cmd.internal_args and arg.name in cmd.internal_args:
            continue

        if i == cmd.infix:
            buf = buf + command_name + " " * (1 + max_len - len(cmd.name))
        if arg.doc:
            name = arg.doc
        elif arg.has_name():
            if arg.poly:
                name = "("
                for j in range(len(arg.name)):
                    if arg.handler[j] == flag_t:
                        name = name + arg.name[j] + "|"
                    elif (arg.handler[j] == str
                          or arg.handler[j] == str_t):
                        name += formatter.italic('"' + arg.name[j] + '"') + "|"
                    else:
                        name += formatter.italic(arg.name[j]) + "|"
                name = name[:-1] + ")"
            else:
                name = arg.name
        else:
            name = "arg" + str(i + 1)

        if arg.handler != flag_t and not isinstance(arg.handler, tuple):
            if arg.handler == str or arg.handler == str_t:
                name = '"'+name+'"'
            name = formatter.italic(name)

        if arg.handler == flag_t:
            buf = buf + "[" + name + "]"
        elif arg.spec == "?":
            if arg.poly and not arg.doc:
                buf = "%s[%s]" % (buf, name[1:-1])
            else:
                buf = "%s[%s]" % (buf, name)
        elif arg.spec == "+":
            buf = buf + "(" + name + " ... | list of " + name + ")"
        elif arg.spec == "*":
            buf = buf + "([ " + name + " ... ] | list of " + name + ")"
        else:
            buf = buf + name

        buf = buf + " "

    if not buf:
        return command_name
    else:
        return buf

#
# --- TERM ---
#

text_entities = {
    'lt'    : '<',
    'gt'    : '>',
    'amp'   : '&',
    'apos'  : "'",
    'ndash' : '-',
    'mdash' : '---',
    'logor' : '||',
    'rarr'  : '->',
    'copy'  : '(C)',
    'reg'   : '(R)',
    'times' : 'x',
    'nbsp'  : ' ',
    'quot'  : '"',
    'trade' : '™',
    'copyright' : '®',
    }

class _gfp_re:
    """Collection of regular expressions used by generic_format_print()."""
    pre    = re.compile(r'<pre(\s+size\s*=\s*"[^"]*")?\s*>')
    para   = re.compile(r"[ \t\r\f\v]*\n[ \t\r\f\v]*\n\s*")
    ws     = re.compile(r"\s+")
    br     = re.compile(r"<br/?>")
    italic = re.compile(r"<(/?)(i|arg|file|var|cite)>")
    bold   = re.compile(r"<(/?)(b|asm|class|em|fun|hap|iface|module|obj|param"
                        r"|reg|tt|type)>")
    sup    = re.compile(r"<(/?)sup>")
    sub    = re.compile(r"<(/?)sub>")
    cmd_class = re.compile(r'<(/?)cmd(?:\s+class\s*=\s*"([^"]*)")?\s*>')
    cmd_iface = re.compile(r'<(/?)cmd(?:\s+iface\s*=\s*"([^"]*)")?\s*>')
    normal = re.compile(r"<(/?)(math|attr)>")
    tag    = re.compile(r"(<[^>]*>)")
    entity = re.compile(r"&([a-z]+);")
    word   = re.compile(r"[^&<\s]*")
_gfp_re = _gfp_re()

def generic_format_print(formatter, text, indent, width, first_indent = None):

    class state:
        """This class keeps track of the current word or line/paragraph break
        being processed."""
        def __init__(self, first_indent, indent, width, formatter):
            self.items = []
            self.len  = 0
            self.prefix = ''
            self.col = self.current_indent = first_indent
            self.indent = indent
            self.width = width
            self.formatter = formatter

        def _add_item(self, item):
            self.flush_break()
            self.items.append(item)

        def _bold_start(self):
            self.formatter.pr(self.formatter.maybe_bold_start())
        def _bold_end(self):
            self.formatter.pr(self.formatter.maybe_bold_end())
        def _italic_start(self):
            self.formatter.pr(self.formatter.maybe_italic_start())
        def _italic_end(self):
            self.formatter.pr(self.formatter.maybe_italic_end())

        def _sup_start(self):
            self.formatter.pr(self.formatter.sup_start())
        def _sup_end(self):
            self.formatter.pr(self.formatter.sup_end())

        def _sub_start(self):
            self.formatter.pr(self.formatter.sub_start())
        def _sub_end(self):
            self.formatter.pr(self.formatter.sub_end())

        def add_text(self, s):
            """Add the string 's' to the current word."""
            self.len += len(s)
            self._add_item(s)
        def bold_start(self):
            """Add a bold start marker to the current word."""
            self._add_item(self._bold_start)
        def bold_end(self):
            """Add a bold end marker to the current word."""
            self._add_item(self._bold_end)
        def italic_start(self):
            """Add an italic start marker to the current word."""
            self._add_item(self._italic_start)
        def italic_end(self):
            """Add an italic end marker to the current word."""
            self._add_item(self._italic_end)

        def sup_start(self):
            "Add a superscript start marker to the current word."
            self._add_item(self._sup_start)
        def sup_end(self):
            "Add a superscript end marker to the current word."
            self._add_item(self._sup_end)

        def sub_start(self):
            "Add a subscript start marker to the current word."
            self._add_item(self._sub_start)
        def sub_end(self):
            "Add a subscript end marker to the current word."
            self._add_item(self._sub_end)

        def paragraph_break(self):
            """Insert paragraph break."""
            self.flush_word()
            if self.prefix != '':
                self.prefix = '\n\n'
        def line_break(self):
            """Insert line break."""
            self.flush_word()
            if self.prefix is None:
                self.prefix = '\n'
            else:
                # consecutive line breaks add up
                self.prefix += '\n'
        def line_break_if_needed(self):
            """Insert line break if there isn't one already."""
            self.flush_word()
            if self.prefix is None:
                self.prefix = '\n'

        def change_indent(self, mod):
            """Changes the indentation for the following paragraph by 'mod'
            spaces.
            Should be called just before paragraph_break() or line_break()."""
            self.flush_word()
            self.indent += mod

        def flush_break(self):
            """Print any pending paragraph/line break."""
            if not self.prefix:
                self.prefix = None
                return

            self.formatter.pr(self.prefix + ' ' * self.indent)
            self.col = self.current_indent = self.indent
            self.prefix = None

        def flush_word(self):
            """Print any pending word."""
            if not self.items:
                return
            items = self.items
            self.items = []
            if (self.col > self.current_indent
                and self.len > 0):
                if self.col + self.len + 1 > self.width:
                    self.col = self.current_indent = self.indent
                    self.formatter.pr(self.formatter.suspend() +
                                      "\n" + " " * self.indent +
                                      self.formatter.resume())
                else:
                    self.formatter.pr(' ')
                    self.col += 1
            for item in items:
                if isinstance(item, string_types):
                    self.formatter.pr(item)
                else:
                    item()
            self.col += self.len
            self.len = 0

        def flush(self):
            """Print any pending word or paragraph/line break."""
            self.flush_word()
            self.flush_break()

    if first_indent is None:
        first_indent = indent
    state = state(first_indent, indent, width, formatter)

    i = 0
    while i < len(text):

        # look for paragraph break (two or more blank lines)
        mo = _gfp_re.para.match(text, i)
        if mo:
            state.paragraph_break()
            i = mo.end()
            continue

        mo = _gfp_re.ws.match(text, i)
        if mo:
            state.flush_word()
            i = mo.end()
            continue

        # break line
        mo = _gfp_re.br.match(text, i)
        if mo:
            state.line_break()
            i = mo.end()
            continue

        # eat format strings
        if text[i] == "<":
            # pre
            m = _gfp_re.pre.match(text, i)
            if m:
                end = text.find('</pre>', m.end())
                if end < 0:
                    raise CliParseErrorInDocText('unterminated <pre>')

                pre_block = text[m.end():end]
                pre_block = pre_block.replace('\n', '<br/>')
                pre_block = pre_block.replace(' ', '&nbsp;')
                text = pre_block + text[end + len('</pre>'):]
                i = 0
                continue

            # italic
            mo = _gfp_re.italic.match(text, i)
            if mo:
                if mo.group(1) == '':
                    state.italic_start()
                else:
                    state.italic_end()
                i = mo.end()
                continue

            # bold
            mo = _gfp_re.bold.match(text, i)
            if mo:
                if mo.group(1) == '':
                    state.bold_start()
                else:
                    state.bold_end()
                i = mo.end()
                continue

            mo = _gfp_re.sup.match(text, i)
            if mo:
                if mo.group(1) == "":
                    state.sup_start()
                else:
                    state.sup_end()
                i = mo.end()
                continue

            mo = _gfp_re.sub.match(text, i)
            if mo:
                if mo.group(1) == "":
                    state.sub_start()
                else:
                    state.sub_end()
                i = mo.end()
                continue

            # cmd (bold)
            mo = (_gfp_re.cmd_class.match(text, i)
                  or _gfp_re.cmd_iface.match(text, i))
            if mo:
                if mo.group(1) == '':
                    state.bold_start()
                    if mo.group(2):
                        state.add_text('<%s>.' % (mo.group(2),))
                else:
                    state.bold_end()
                i = mo.end()
                continue

            # normal
            mo = _gfp_re.normal.match(text, i)
            if mo:
                i = mo.end()
                continue

            if text.startswith("<ul>", i):
                i += 4
                continue
            if text.startswith("</ul>", i):
                i += 5
                state.line_break()
                continue
            if text.startswith("<li>", i):
                i += 4
                state.line_break_if_needed()
                state.add_text("*")
                state.change_indent(2)
                continue
            if text.startswith("</li>", i):
                i += 5
                state.change_indent(-2)
                continue
            if text.startswith("<dt>", i):
                i += 4
                state.paragraph_break()
                continue
            if text.startswith("</dl>", i):
                i += 5
                state.paragraph_break()
                continue
            if text.startswith("</dt>", i):
                # indent and force newline after <dt>...</dt>
                i += 5
                state.change_indent(3)
                state.line_break()
                continue
            if text.startswith("</dd>", i):
                # unindent after <dd>...</dd>
                state.change_indent(-3)
                i += 5
                continue
            if text.startswith('</td>', i):
                state.flush_word()
                state.add_text(" ")
                i += 5
                continue
            if text.startswith('</tr>', i):
                i += 5
                state.line_break()
                continue
            if text.startswith('<table>', i):
                i += 7
                state.line_break()
                continue

            # match and skip all other tags
            mo = _gfp_re.tag.match(text, i)
            if not mo:
                raise Exception('incorrect tag at %r' % (text[i:i + 16],))
            i = mo.end()
            continue

        if text[i] == "&":
            mo = _gfp_re.entity.match(text, i)
            if mo:
                entity = mo.group(1)
                entity = text_entities.get(entity, "&" + entity + ";")
                state.add_text(entity)
                i = mo.end()
                continue

            # we need to detect when the text starts with &, but no
            # entity is found, otherwise we get an infinite loop.
            raise Exception('incorrect entity at %r' % (text[i:i + 16],))

        mo = _gfp_re.word.match(text, i)
        if mo:
            state.add_text(mo.group(0))
            i = mo.end()
            continue

        # this code can never be reached since _gfp_re.word will
        # always match
        raise CliParseErrorInDocText

    state.flush()

def format_print(text, indent = 0, width = -1, first_indent = None):
    """Print to the Simics console using standard reformatting rules.
    If the optional 'first_indent' variable is used, it is used for
    indentation of the first line; subsequent lines use 'indent'"""

    if width <= 0:
        width = terminal_width() + width
    generic_format_print(get_formatter(), text, indent, width,
                         first_indent = first_indent)

def get_format_string(text, mode = 'html', width = 10000, indent = 0):
    formatter = {
        'html' : HTML_formatter,
        'text' : Text_formatter,
        }[mode]
    ret = StringIO()
    def collect(s): ret.write(s)
    generic_format_print(formatter(collect), text, indent, width)
    return ret.getvalue()

class _test_get_format_string(unittest.TestCase):
    def test_nested_list(self):
        text = """\
A list
<ul>
<li>Item 1 and lets make it long so it needs to be wrapped across lines</li>
<li>Here is a nested list: <ul><li>Nested</li></ul>
</li>
And some text after"""

        expected = """\
A list
* Item 1 and lets make it long so it needs to be
  wrapped across lines
* Here is a nested list:
  * Nested
And some text after"""
        out = get_format_string(text, mode='text', width=50)
        self.assertEqual(out, expected)

#
# --- jDOCU ---
#

def one_c_type(c):
    ctypes = {"n": "void ", "i": "int ", "I": "int64 ",
              "e": "exception_type_t ", "o": "lang_void *", "s": "char *",
              "m": "generic_transaction_t *", "c": "conf_object_t *"}
    return ctypes.get(c, "&lt;unknown type %s&gt;" % c)

def hap_c_arguments(str, argnames, width = 60, indent = 0, breakline = "\n"):
    res = " " * indent + one_c_type(str[0]) + "(*)("
    indent = len(res)
    str = str[1:]
    if str == "":
        res = res + "void"
    else:
        col = indent
        while str != "":
            this = one_c_type(str[0]) + argnames[0]
            if col > indent and col + len(this) > width - 2:
                res = res + breakline + " " * indent
                col = indent
            res = res + this
            col = col + len(this)
            str = str[1:]
            argnames = argnames[1:]
            if str != "":
                res = res + ", "
                col = col + 2
    return res + ");"

#
# --- HTML ---
#

ignore_tags = ["<i>", "</i>", "<b>", "</b>", "<em>", "</em>", "<tt>", "</tt>"]

def ignore_tag(text):
    try:
        for tag in ignore_tags:
            f = 1
            for i in range(len(tag)):
                if tag[i] != text[i]:
                    f = 0
                    break
            if f:
                return len(tag)
        return 0
    except IndexError:
        return 0

_format_html_paragraph_matcher = re.compile(
                                   r"[ \t\r\f\v]*\n[ \t\r\f\v]*\n\s*").match
_format_jdocu_br_matcher = re.compile(r"<br/?>").match

def format_html(text):
    t = ""
    while(text):
        # look for line break (two or more blank lines)
        mo = _format_html_paragraph_matcher(text)
        if mo:
            t = t + "<br><br>\n"
            text = text[mo.end():]
            continue

        # break line
        mo = _format_jdocu_br_matcher(text)
        if mo:
            text = text[mo.end():]
            t = t + "<br>\n"
            continue

        if text[0] == "<":
            l = ignore_tag(text)
            if l:
                t = t + text[:l]
                text = text[l:]
            else:
                text = text[1:]
                t = t + "&lt;"
            continue

        if text[0] == ">":
            text = text[1:]
            t = t + "&gt;"
            continue

        if text[0] == "&":
            text = text[1:]
            t = t + "&amp;"
            continue

        mo = re.match(r"([^\n<>]+)", text)
        if mo:
            text = text[mo.end():]
            t = t + mo.group(1)
            continue

        t = t + text[0]
        text = text[1:]
    return t

def write_doc_item(file, heading, text):
    file.write("<dt><b>%s</b></dt>\n<dd>" % heading)
    file.write(format_html(text))
    file.write("</dd>\n")

class HTMLFormatter:
    def __init__(self, name):
        self.file = codecs.open(name, "w", encoding='UTF-8')

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.file.close()

    def write(self, what):
        self.file.write(what)

    def begin_document(self):
        self.write("<html>\n")
        self.write("<head>\n")
        self.write("<title>Simics commands</title>\n")
        self.write("</head>\n")
        self.write("<body>\n")

    def end_document(self):
        self.write("<body>\n")
        self.write("</html>\n")

    def write_list_of_commands(self, commands):
        self.write("<h1>List of commands</h1><br>\n")
        for cmd in commands:
            self.write("<a href=\"#"
                            + (cmd.doc_with if cmd.doc_with else cmd.name)
                            + "\">" + format_html(cmd.name) + "</a><br>\n")
        self.write("<hr WIDTH=\"100%\">\n")

    def write_item(self, heading, text):
        write_doc_item(self.file, heading, text)

    def begin_command(self, name):
        self.write("<a name=\"" + name + "\">\n")
        self.write("<dl>\n")

    def end_command(self):
        self.write("</dl>\n")
        self.write("<hr WIDTH=\"100%\">\n")

def format_commands_as_html(name):
    with HTMLFormatter(name) as formatter:
        format_commands(formatter)

def format_commands_as_cli():
    # For now do a very simple list of the commands and their short
    # description. We may want to print an extended format
    # (optionally) similarly to what is done by
    # format_commands_as_html.
    for cmd in simics_commands():
        print("%s - %s" % (cmd.name, cmd.short))

def format_commands(formatter):
    formatter.begin_document()

    formatter.write_list_of_commands(simics_commands())

    for cmd in simics_commands():
        if cmd.doc_with:
            # This is documented with another command
            continue

        formatter.begin_command(cmd.name)

        # find all commands that will doc with this one
        doc_with = sorted(all_commands.get_doc_group(cmd.name))

        text = cmd.name

        aliases = cmd.alias
        for c in doc_with:
            text = text + ", " + c.name
            aliases = aliases + c.alias

        if cmd.group_short:
            text = text + " - " + cmd.group_short
        elif cmd.short:
            text = text + " - " + cmd.short

        formatter.write_item("NAME", text)

        text = "<tt>" + get_synopsis(cmd, 0, "text")
        for c in doc_with:
            text = text + "<br>\n" + get_synopsis(c, 0, "text")
        text = text + "</tt>"

        formatter.write_item("SYNOPSIS", text)

        formatter.write_item("DESCRIPTION", cmd.doc)

        for di in cmd.doc_items:
            formatter.write_item(di[0], di[1])
        formatter.end_command()

    formatter.end_document()

class Command_list:
    def __init__(self):
        # The set of commands that are always available
        self.public_cmds = set()

        # A dictionary mapping command names to command objects.  This
        # includes mappings from command aliases as well.
        self.cmds_dict = {}

        # mapping from namespace to commands
        self.iface_cmds = {}
        self.class_cmds = {}

        # A mapping from a command name to the set of all commands
        # that should be documented together under that command,
        # including the original command itself.
        self.doc_groups = {}

        # Cached information
        self.sorted = None
        self.no_letter_cmds_cache = None

        # A flag determining if it is allowed to redefine commands
        self.allow_redefine = True

        # A set of approved as well as properly registered command categories.
        self.command_categories = set([
            "Breakpoints",
            "CLI",
            "Components",
            "Configuration",
            "Consoles",
            "Debugging",
            "Deprecated",
            "Disks",
            "Execution",
            "Files",
            "Graphics",
            "Help",
            "Image",
            "Inspection",
            "Instrumentation",
            "Links",
            "Logging",
            "Matic",
            "Memory",
            "Modules",
            "Networking",
            "Notifiers",
            "PCI",
            "Parameters",
            "Performance",
            "Probes",
            "Processors",
            "Profiling",
            "Python",
            "Recording",
            "Registers",
            "Snapshots",
            "SystemC",
            "Tracing",
            "USB",
            "VMP",
            "Virtio",
        ])

    def register_command_category(self, name):
        if name == None:
            return sorted(self.command_categories)
        if not isinstance(name, str) or len(name) < 3:
            raise CliError(f'"{name}" is not a valid string')
        else:
            self.command_categories.add(name)

    def add(self, cmd):
        # Check for command name conflicts
        if self.exists(cmd.name):
            if self.allow_redefine:
                simics.pr_err("redefining the '%s' command" % cmd.name)
            else:
                raise CliCmdDefError("command name conflict over "+cmd.name)
        for n in cmd.alias_names():
            if self.exists(n):
                if self.allow_redefine:
                    simics.pr_err("redefining the '%s' command" % n)
                else:
                    raise CliCmdDefError("command name conflict over "+n)

        if not cmd.hidden:
            if cmd.preview:
                tech_preview_cmds[cmd.preview].add(cmd)
            elif cmd.unsupported:
                unsupported_cmds[cmd.unsupported].add(cmd)
            else:
                self.public_cmds.add(cmd)

        self.cmds_dict[cmd.name] = cmd
        for a in cmd.alias_names():
            self.cmds_dict[a] = cmd

        if cmd.iface:
            self.iface_cmds.setdefault(cmd.iface, []).append(cmd)
        if cmd.cls:
            self.class_cmds.setdefault(cmd.cls, []).append(cmd)

        if cmd.doc_with:
            doc_group = cmd.doc_with
            if not self.exists(doc_group):
                raise CliCmdDefError(
                    f"doc_with points to unknown command '{str(cmd.doc_with)}'")
            # since the commands are documented together, inherit type from the
            # main command if it wasn't set explicitly
            if not cmd.type:
                cmd.type = self.cmds_dict[doc_group].type
        else:
            doc_group = cmd.name
        self.doc_groups.setdefault(doc_group, set()).add(cmd)

        self.drop_cache()

    def drop_cache(self):
        self.sorted = None
        self.no_letter_cmds_cache = None

    def __iter__(self):
        "Return an iterator that iterates over all known commands"
        return iter(set.union(*([self.public_cmds]
                                + [cmd_set for (preview, cmd_set)
                                   in tech_preview_cmds.items() if
                                   tech_preview_enabled(preview)]
                                + [cmd_set for (unsupported, cmd_set)
                                   in unsupported_cmds.items() if
                                   unsupported_enabled(unsupported)])))

    def get_sorted(self):
        "Return a sorted list of all known commands"
        if not self.sorted:
            self.sorted = sorted(self)
        return self.sorted

    def get(self, cmd_name):
        cmd = self.cmds_dict.get(cmd_name)
        if cmd:
            if cmd.preview and not tech_preview_enabled(cmd.preview):
                cmd = None
            elif cmd.unsupported and not unsupported_enabled(cmd.unsupported):
                cmd = None
        return cmd

    def exists(self, cmd_name):
        return cmd_name in self.cmds_dict

    def get_command_names(self):
        return list(self.cmds_dict.keys())

    def get_doc_group(self, cmd_name):
        """return a list of command objects that should be documented
        together with the command named 'cmd_name', including that command."""
        return self.doc_groups[cmd_name]

    def get_doc_groups(self):
        """Get a list of all documentation groups, i.e. the names of all
        commands that do not have doc_with set to point to another command."""
        return list(self.doc_groups.keys())

    def get_class_commands(self, cls):
        "Return a sequence of all namespace commands that apply to a class"
        commands = itertools.chain(
            self.class_cmds.get(cls, []),
            itertools.chain.from_iterable(
                self.iface_cmds.get(i, [])
                for i in simics.VT_get_interfaces(cls)))
        return [cmd for cmd in commands
                if ((not cmd.preview and not cmd.unsupported)
                    or (cmd.preview and tech_preview_enabled(cmd.preview))
                    or (cmd.unsupported
                        and unsupported_enabled(cmd.unsupported)))]

    def get_iface_commands(self, iface):
        """Return a sequence of all namespace commands that apply to an
        interface"""
        commands = self.iface_cmds.get(iface, [])
        return [cmd for cmd in commands
                if ((not cmd.preview and not cmd.unsupported)
                    or (cmd.preview and tech_preview_enabled(cmd.preview))
                    or (cmd.unsupported
                        and unsupported_enabled(cmd.unsupported)))]

    def get_object_commands(self, obj):
        "Return a sequence of all namespace commands that apply to an object"
        return self.get_class_commands(obj.classname)

    def no_letter_cmds(self):
        if not self.no_letter_cmds_cache:
            omit = set(["-", "/", "[", "~"])
            # sort by length to simplify longest matching command
            self.no_letter_cmds_cache = sorted([
                c.name for c in self if (re.match(r'[^a-zA-Z]+$', c.name)
                                         and c.name not in omit)],
                                               key=len,
                                               reverse=True)
        return self.no_letter_cmds_cache

    @staticmethod
    def class_exists(cls):
        return cls in simics.SIM_get_all_classes()

    def new_command(self, name, fun, args = [], doc = "",
                    type = None,
                    short = "", group_short = "", alias = [], doc_with = "",
                    doc_items = [], see_also = [],
                    synopsis = None, synopses = None,
                    namespace = "", namespace_copy = (),
                    preview = None, unsupported = None,
                    filename = "", linenumber = "", module = None,
                    object = None, repeat = None,
                    # The 'deprecated' argument points to replacement commands.
                    # It can be a string or a tuple of strings with command
                    # names; it also can be True if no replacement is available.
                    deprecated = None,
                    deprecated_version = None,
                    # The 'legacy' argument points to replacement commands.
                    # It can be a string or a tuple of strings with command
                    # names; it also can be True if no replacement is available.
                    # If legacy is set, legacy_version must also be set.
                    legacy = None,
                    legacy_version = None,
                    dynamic_args = None,
                    cls = None, iface = None, internal_args = None):
        if (not re.match(r'[a-zA-Z][a-zA-Z0-9_-]*$', name)
            and name not in ['#', '!', '@', '`']):
            raise CliCmdDefError("cli.new_command(): invalid command"
                                 " name ('{0}')".format(name))
        if legacy and not legacy_version:
            raise CliCmdDefError(
                "cli.new_command: 'legacy_version' must be specified since"
                " 'legacy' is specified for the command {name}.")
        if namespace:
            raise CliCmdDefError(
                "When defining {0}.{1}: The 'namespace' parameter to"
                " cli.new_command() is not supported. Use the 'cls' or 'iface'"
                " parameter instead.".format(namespace, name))
        if cls and iface:
            raise CliCmdDefError("cli.new_command(): At most one of the cls"
                                 " and iface parameters can be set")
        if cls and not self.class_exists(cls):
            raise CliCmdDefError("cli.new_command(): Attempt to define"
                                 " command %s.%s, but class %s does not"
                                 " exist" % (cls, name, cls))

        return self.add_command(name, fun, args = args, doc = doc, type = type,
                                pri = 0, infix = False, short = short,
                                group_short = group_short, alias = alias,
                                doc_with = doc_with, check_args = False,
                                doc_items = doc_items, see_also = see_also,
                                synopsis = synopsis, synopses = synopses,
                                namespace_copy = namespace_copy,
                                preview = preview, unsupported = unsupported,
                                filename = filename, linenumber = linenumber,
                                module = module, object = object,
                                repeat = repeat, deprecated = deprecated,
                                hidden = False,
                                deprecated_version = deprecated_version,
                                legacy = legacy,
                                legacy_version = legacy_version,
                                dynamic_args = dynamic_args, cls = cls,
                                iface = iface, internal_args = internal_args)

    def new_operator(self, name, fun, args = [], doc = "",
                     type = None, pri = 0, infix = False,
                     short = "", group_short = "",
                     check_args = True, see_also = [],
                     synopsis = None, synopses = None, hidden = False):

        # We do not want argument names for operators, messes up tab-completion
        for arg in args:
            if arg.has_name() and not arg.is_flag():
                raise CliError("Operator %s uses named arguments" % name)
        assert pri != 0 or infix
        if infix:
            check_args = False
        return self.add_command(name, fun, args = args, doc = doc, type = type,
                                pri = pri, infix = infix, short = short,
                                group_short = group_short, alias = [],
                                doc_with = "", check_args = check_args,
                                doc_items = [], see_also = see_also,
                                synopsis = synopsis, synopses = synopses,
                                hidden = hidden)

    def add_command(self, name, fun, args = [], doc = "",
                    type = None, pri = 0, infix = False,
                    short = "", group_short = "", alias = [], doc_with = "",
                    check_args = True, doc_items = [], see_also = [],
                    synopsis = None, synopses = None,
                    namespace_copy = (),
                    preview = None, unsupported = None,
                    filename = "", linenumber = "",
                    module = None,
                    object = None, repeat = None, deprecated = None,
                    hidden = False, deprecated_version = None,
                    legacy = None, legacy_version = None,
                    dynamic_args = None,
                    cls = None, iface = None, internal_args = None):

        if alias == "":
            alias = []

        if isinstance(alias, string_types):
            alias = [alias]

        for alias_name in alias:
            if obj_aliases().has_alias(alias_name):
                raise CliCmdDefError(
                    f"'{alias_name}' already exists as a built-in object alias")

        if isinstance(type, string_types):
            if type.startswith("tech preview:"):
                raise CliCmdDefError("Use the new_tech_preview_command")
            elif type.startswith("unsupported:"):
                raise CliCmdDefError("Use the new_unsupported_command")
            type = [type] if type else None  # Empty strings have been seen

        ignore_type = [
            # some tests using external-packages use these - SIMICS-22645
            "Command Line Interface",
            "DS17485 commands",
            "P4040",
            "P4080",
            "P5020",
            "PowerPC",
            "QorIQ T4",
            "breakpoint",
            "gic-commands",
            "inspect/change commands",
            "tm-snare commands",
            "x86ex-tlb commands",
            "zynqmp_rtc commands",
            ]

        if isinstance(type, Iterable):
            for t in type:
                if t in ignore_type:
                    continue
                if t not in all_commands.command_categories:
                    # In a future major this should raise a CliCmdError
                    simics.SIM_log_info(
                        2, conf.sim, 0,
                        f'In command "{name}", "{t}" is not a'
                        ' registered command category, use the'
                        ' cli.register_command_category function')
        elif type:
            simics.pr(f'In command "{name}", the "type" argument must be'
                      ' a list of strings\n')
            type = None

        if namespace_copy and not isinstance(namespace_copy, tuple):
            raise CliCmdDefError("namespace_copy must be a tuple of"
                                 " (namespace, fun)")

        # synopses is a list of sublists, each defining one synopsis.
        #
        # The elements of the sublists are either strings or
        # Markup.Markup objects.
        #
        # synopsis = xyz is shorthand for synopses = [ xyz ].
        if synopsis != None:
            if synopses != None:
                raise CliCmdDefError("at most one of 'synopsis' and 'synopses'"
                                     " may be set")
            synopses = [ synopsis ]
        if synopses:
            synopses = [ Markup(*synopsis) for synopsis in synopses ]

        for d in doc_items:
            if not (isinstance(d, tuple) and len(d) == 2
                and isinstance(d[0], string_types)
                    and isinstance(d[1], string_types)):
                raise CliCmdDefError("malformed doc_items")

        arg_names = set()
        for arg in args:
            if arg_names.intersection(arg.names()):
                raise CliCmdDefError("argument name must be unique")
            arg_names.update(arg.names())

        # Prepend replacements for legacy and deprecated commands to 'see_also'.
        for replacements in (legacy, deprecated):
            if not replacements:
                continue
            if not isinstance(replacements, (str, list,)):
                continue
            if isinstance(replacements, str):
                replacements = [replacements]
            see_also = self.prepend_items(see_also, replacements)

        cmd = cli_command(
            method = name, fun = fun, pri = pri, infix = infix,
            doc = doc, type = type, short = short,
            group_short = group_short, args = args, alias = alias,
            doc_with = doc_with, check_args = check_args,
            doc_items = doc_items, see_also = see_also, synopses = synopses,
            iface = iface, cls = cls,
            preview = preview, unsupported = unsupported,
            filename = filename, linenumber = linenumber,
            object = None,
            module = module if module
                     else simics.CORE_get_current_loading_module(),
            repeat = repeat, deprecated = deprecated, hidden = hidden,
            deprecated_version = deprecated_version, legacy = legacy,
            legacy_version = legacy_version, dynamic_args = dynamic_args,
            internal_args = internal_args)

        self.add(cmd)

        if len(namespace_copy) > 0:
            for entr in namespace_copy[:-1]:
                nsc = cmd.parameter_dict()
                nsc["fun"] = namespace_copy[-1]
                if doc:
                    nsc["doc"] = ""
                    nsc["doc_with"] = name
                nsc["args"] = args[1:]
                nsc["alias"] = alias
                nsc["iface"] = entr
                del nsc["is_alias_for"]
                nsc["name"] = cmd.method
                del nsc["method"]
                self.add_command(**nsc)

        simics.SIM_hap_occurred_always(cmd_hap, None, 0, [cmd.name])
        return cmd

    @staticmethod
    def prepend_items(existing, items):
        existing = list(existing)
        for d in reversed(items):
            if d not in existing:
                existing.insert(0, d)
        return existing

all_commands = Command_list()

class _test_new_command(unittest.TestCase):
    def setUp(self):
        self.commands = Command_list()
        self.commands.allow_redefine = False

    def cmdfun(self, *args):
        self.args = args

    def test_simple(self):
        self.commands.new_command("cmd1", self.cmdfun,
                                  [arg(int_t, "x")])
        cmd = self.commands.get("cmd1")
        self.assertEqual(cmd.name, "cmd1")

    def test_dup_argname(self):
        self.assertRaises(CliCmdDefError,
                          self.commands.new_command,
                          "cmd1", self.cmdfun,
                          [arg(int_t, "x"),
                           arg(int_t, "x")])

    def test_doc_group(self):
        cmd1 = self.commands.new_command("cmd1", self.cmdfun)
        cmd2 = self.commands.new_command("cmd2", self.cmdfun,
                                         doc_with = "cmd1")
        d = self.commands.get_doc_group("cmd1")
        self.assertEqual(d, set([cmd1, cmd2]))
        self.assertRaises(KeyError, self.commands.get_doc_group, "cmd2")
        self.assertRaises(CliCmdDefError,
                          self.commands.new_command,
                          "cmd3", self.cmdfun,
                          doc_with = "unknown")

    def test_redefine(self):
        self.commands.new_command("cmd1", self.cmdfun)
        self.assertRaises(CliCmdDefError,
                          self.commands.new_command,
                          "cmd1", self.cmdfun)

    def test_alias(self):
        cmd = self.commands.new_command("cmd1", self.cmdfun,
                                        alias = "cmdalias")
        # There should now be one command, with two names
        self.assertEqual(list(self.commands), [cmd])
        self.assertEqual(set(self.commands.get_command_names()),
                         set(("cmd1", "cmdalias")))
        self.assertEqual(self.commands.get("cmd1"), cmd)
        self.assertEqual(self.commands.get("cmdalias"), cmd)

    def test_for_forbidden_obj_alias(self):
        self.assertRaises(CliCmdDefError,
                          self.commands.new_command,
                          "cmd1", self.cmdfun,
                          [arg(int_t, "x"),
                           arg(int_t, "x")], alias = "cpu")

    def test_ns_alias(self):
        cmd = self.commands.new_command("cmd1", self.cmdfun,
                                        iface = "processor",
                                        alias = "cmdalias")
        # There should now be one command, with two names, both in the
        # namespace
        self.assertEqual(list(self.commands), [cmd])
        self.assertEqual(set(self.commands.get_command_names()),
                         set(("<processor>.cmd1", "<processor>.cmdalias")))
        self.assertEqual(self.commands.get("<processor>.cmd1"), cmd)
        self.assertEqual(self.commands.get("<processor>.cmdalias"), cmd)

    def test_nsc_alias(self):
        cmd = self.commands.new_command(
            "cmd1", self.cmdfun,
            namespace_copy = ("processor", self.cmdfun),
            alias = "cmdalias")
        # Have to get the namespace copy command separately
        ncmd = self.commands.get("<processor>.cmd1")
        # There should now be two commands, with two names each
        self.assertEqual(set(self.commands.get_command_names()),
                         set(("cmd1", "cmdalias",
                              "<processor>.cmd1", "<processor>.cmdalias")))
        self.assertTrue(ncmd)
        self.assertEqual(set(self.commands), set([cmd, ncmd]))
        self.assertEqual(self.commands.get("cmd1"), cmd)
        self.assertEqual(self.commands.get("cmdalias"), cmd)
        self.assertEqual(self.commands.get("<processor>.cmd1"), ncmd)
        self.assertEqual(self.commands.get("<processor>.cmdalias"), ncmd)

class _test_normalize_value(unittest.TestCase):
    def test_str_t(self):
        self.assertEqual(str_t.normalize_value('hello'), 'hello')
        self.assertEqual(str_t.normalize_value('hello'), 'hello')
        with self.assertRaises(ValueError):
            str_t.normalize_value(5)
    def test_int_t(self):
        for v in [-1, 0, 1, 1000000000000000000000000,
                  -1000000000000000000000000]:
            self.assertEqual(int_t.normalize_value(int(v)), v)
        with self.assertRaises(ValueError):
            int_t.normalize_value('hello')
    def test_uint_t(self):
        for v in [0, 1, 1000000000000000000000000]:
            self.assertEqual(int_t.normalize_value(int(v)), v)
        for v in [-1, -1000000000000000000000000, 'hello']:
            with self.assertRaises(ValueError):
                uint_t.normalize_value(v)
    def test_list_t(self):
        # Lists of cli values are acceptable, including lists of lists
        for v in [[], ['hello', 5], [5.0], [('v', 4711)], [None], [False],
                  [conf.sim], [[]], [['hello']]]:
            self.assertEqual(list_t.normalize_value(v), v)
        for (v, e) in [('v:4711', ('v', 4711)), ('sim', 'sim'),
                       (['v', 4711], ('v', 4711))]:
            self.assertEqual(list_t.normalize_value([v]), [e])
        # Non-list and lists of non-cli values are not acceptable
        for v in [None, 5, False, 'hello', [object()], [()]]:
            with self.assertRaises(ValueError):
                list_t.normalize_value(v)
    def test_range_t(self):
        for (min, max) in [(0, 10), (int64_min, int64_max),
                           (int64_min, uint64_max), (0, 0)]:
            range = range_t(min, max, '%d-%d' % (min, max))
            self.assertEqual(range.normalize_value(min), min)
            self.assertEqual(range.normalize_value(max), max)
            with self.assertRaises(ValueError):
                range.normalize_value(min - 1)
            with self.assertRaises(ValueError):
                range.normalize_value(max + 1)
            mod_range = range_t(min, max, '%d-%d' % (min, max), modulo=True)
            self.assertEqual(mod_range.normalize_value(min), min)
            self.assertEqual(mod_range.normalize_value(max), max)
            self.assertEqual(mod_range.normalize_value(min - 1), max)
            self.assertEqual(mod_range.normalize_value(max + 1), min)
            with self.assertRaises(ValueError):
                range.normalize_value('hello')
    def test_sign_invariant_range_types(self):
        # Test that the sign invariant fixed size argument has the full range
        # of unsigned and signed combined.
        def test_type(sign_invariant, other_type, limitation):
            got = getattr(sign_invariant, limitation)
            exp = getattr(other_type, limitation)
            self.assertEqual(
                got,
                exp,
                f"The type '{sign_invariant.name}' has {limitation}"
                f" {got} but should have the same"
                f" {limitation} as '{other_type.name}',"
                f" {exp}.")
        for (sign_invariant, signed, unsigned) in [
                [int8_t, sint8_t, uint8_t],
                [int16_t, sint16_t, uint16_t],
                [int32_t, sint32_t, uint32_t],
                [int64_t, sint64_t, uint64_t]]:
            test_type(sign_invariant, signed, 'min')
            test_type(sign_invariant, unsigned, 'max')

    def test_float_t(self):
        for v in [0, -1, 1, -1.0, 1.0, 0.0, sys.float_info.max,
                  sys.float_info.min, float('inf'), float('-inf')]:
            self.assertEqual(float_t.normalize_value(v), v)
        with self.assertRaises(ValueError):
            float_t.normalize_value('hello')
    def test_flag_t(self):
        for v in [True, False, 0, 1]:
            self.assertEqual(flag_t.normalize_value(v), bool(v))
        with self.assertRaises(ValueError):
            flag_t.normalize_value('hello')
    def test_addr_t(self):
        self.assertEqual(addr_t.normalize_value(42), ('', 42))
        self.assertEqual(addr_t.normalize_value(('', 42)), ('', 42))
        self.assertEqual(addr_t.normalize_value(('v', 42)), ('v', 42))
        self.assertEqual(addr_t.normalize_value(('v:42')), ('v', 42))
        self.assertEqual(addr_t.normalize_value(('v:0x42')), ('v', 0x42))
        for v in [(), 'ww:0x42', 'v:47:13', -10, (0, 42), (42, 'v'),
                  ('v', '42')]:
            with self.assertRaises(ValueError):
                addr_t.normalize_value(v)
    def test_ip_port_t(self):
        for v in [0, 1, 65535, 4711]:
            self.assertEqual(ip_port_t.normalize_value(v), v)
            self.assertEqual(ip_port_t.normalize_value(int(v)), v)
        for v in [-1, 65536, 'hello']:
            with self.assertRaises(ValueError):
                ip_port_t.normalize_value(v)
    def test_filename_t(self):
        filename = filename_t()
        dir_filename = filename_t(dirs=True)
        existing_filename = filename_t(exist=True)
        existing_dir_filename = filename_t(exist=True, dirs=True)
        sim_filename = filename_t(simpath=True)
        sim_dir_filename = filename_t(simpath=True, dirs=True)
        checkpoint_filename = filename_t(checkpoint=True)
        existing_checkpoint_filename = filename_t(checkpoint=True, exist=True)

        import tempfile
        non_existing = 'non-existing-file'
        sim_dir = '%simics%/bin'
        sim_file = '%simics%/scripts/addon-manager.py'
        missing_sim_file = '%simics%/missing-file.abc'
        (fd, existing) = tempfile.mkstemp()
        os.close(fd)
        existing_dir = tempfile.mkdtemp()
        existing_ckpt_dir = tempfile.mkdtemp()
        with open(os.path.join(existing_ckpt_dir, "config"), "w") as f:
            print("""# Test checkpoint
            OBJECT default_cell0 TYPE cell {
                   default_cell: TRUE
            }""", file=f)

        try:
            # Just validating and matching
            for (input, fn) in [
                    (non_existing, filename),
                    (non_existing, dir_filename),
                    (non_existing, checkpoint_filename),
                    (existing, filename),
                    (existing, dir_filename),
                    (existing_dir, dir_filename),
                    (existing, checkpoint_filename),
                    # TODO: Why is an existing dir accepted as a checkpoint?
                    (existing_dir, checkpoint_filename),
                    (existing_ckpt_dir, existing_checkpoint_filename),
            ]:
                self.assertEqual(fn.normalize_value(input), input)

            # Simpath translation
            for (input, fn) in [
                    (sim_file, sim_filename),
                    (sim_dir, sim_dir_filename),
                    (sim_file, sim_dir_filename),
                    ]:
                self.assertEqual(fn.normalize_value(input),
                                 simics.SIM_lookup_file(input))

            # Failing simpath translation and non-existing files
            for (input, fn) in [
                    (non_existing, existing_filename),
                    (non_existing, existing_dir_filename),
                    (non_existing, sim_filename),
                    (non_existing, sim_dir_filename),
                    (non_existing, existing_checkpoint_filename),
                    (sim_dir, sim_filename),
                    (existing_dir, sim_filename),
                    (existing_dir, existing_checkpoint_filename),
                    (missing_sim_file, filename),
                    (existing, existing_checkpoint_filename),
            ]:
                with self.assertRaises(ValueError):
                    fn.normalize_value(input)
        finally:
            os.remove(existing)
            os.rmdir(existing_dir)
    def test_obj_t(self):
        # Create an object of a particular class, with a particular
        # interface and a particular port for testing
        klass = simics.SIM_create_class(
            'm_class', simics.class_info_t(kind=simics.Sim_Class_Kind_Pseudo))
        simics.SIM_register_interface(klass, 'signal',
                                      simics.signal_interface_t())
        simics.SIM_register_port_interface(
            klass, 'int_register', simics.int_register_interface_t(), 'regs',
            'registers')
        obj = simics.SIM_create_object(klass, 'earth')

        try:
            # Test various obj_t variants that should match the object
            for t in [obj_t('any object'), obj_t('m_class', kind='m_class'),
                      obj_t('signal', kind='signal')]:
                ref_cli_val = t.value([tokenizer.string_token(obj.name)])[0]
                self.assertEqual(t.normalize_value(obj), ref_cli_val)
                self.assertEqual(t.normalize_value(obj.name), ref_cli_val)
                with self.assertRaises(ValueError):
                    t.normalize_value([obj, None])

            # Create a signal_port obj_t and test it against obj
            signal_port = obj_t('int-port', kind='signal', want_port=True)
            ref_cli_val = signal_port.value([tokenizer.string_token(obj.name)])[0]
            for v in [obj, [obj, None], (obj, None), obj.name]:
                self.assertEqual(signal_port.normalize_value(v), ref_cli_val)

            # Create an int_port and test both matches and misses against it
            int_port = obj_t('int-port', kind='int_register', want_port=True)
            ref_cli_val = int_port.value([tokenizer.string_token(f"{obj.name}:regs")])[0]
            for v in [[obj, 'regs'], (obj, 'regs'), '%s:regs' % obj.name]:
                self.assertEqual(int_port.normalize_value(v), ref_cli_val)
            for v in [conf.sim, obj, 'hello', [obj, 'foobar'], [obj, 17],
                      [obj], [obj.name, "regs"]]:
                with self.assertRaises(ValueError):
                    int_port.normalize_value(v)
        finally:
            simics.SIM_delete_object(obj)
    def test_string_set_t(self):
        d = {'hello': 42, 'world': False, 'eggs': 'eggs'}
        string_set = string_set_t(d)
        for (key, value) in list(d.items()):
            self.assertEqual(string_set.normalize_value(key), value)
        for v in [42, 'hi']:
            with self.assertRaises(ValueError):
                string_set.normalize_value(v)
    def test_bool_t(self):
        bools = bool_t('Hello', 'World')
        for v in [True, 1, 'TRUE', 'Hello']:
            self.assertTrue(bools.normalize_value(v))
        for v in [False, 0, 'FALSE', 'World']:
            self.assertFalse(bools.normalize_value(v))
        for v in ['Yes', 'No', None, [], 'True', 'False', 3, -1, 1.0, 0.0]:
            with self.assertRaises(ValueError):
                bools.normalize_value(v)
    def test_nil_t(self):
        for v in [None, 0, '']:
            self.assertEqual(nil_t.normalize_value(v), None)
        for v in ['nil', 'None', False, True, [], 0.0]:
            with self.assertRaises(ValueError):
                nil_t.normalize_value(v)
    def test_poly_t(self):
        poly = poly_t('various', string_set_t({'hello': 42}), str_t, boolean_t,
                      range_t(3, 5, '3-5'))
        for (k, v) in [('hello', 42), ('world', 'world'), (False, False),
                       (0, False), (3, 3), ('FALSE', 'FALSE')]:
            self.assertEqual(poly.normalize_value(k), v)
        for v in [conf.sim, [], 17]:
            with self.assertRaises(ValueError):
                poly.normalize_value(v)

class _test_filename_t_value(unittest.TestCase):
    def test_filename_t_tokens(self):
        filename_t().value(tokenizer.tokenize('"%simics%/scripts/addon-manager.py"'))
        token = tokenizer.tokenize('"%simics%/missing-file.abc"')
        self.assertRaises(CliError, filename_t().value, token)


# This function validates a single argument against its
# arg-specification
def validate(fun_name, arg, value, provided):

    def format_arg_name_for_err(arg):
        # Use the Python key name instead of the CLI argument name in messages.
        # Pick the key name that is a valid Python identifier
        if isinstance(arg.name, str):
            return get_key_names(arg.name)[-1]
        else:
            # Some arguments have multiple names in a tuple
            return tuple(get_key_names(n)[-1] for n in arg.name)

    def normalize_value(handler, v):
        if not hasattr(handler, 'normalize_value'):
            raise TypeError('custom CLI value type not handled by wrapper')
        try:
            ret_val = handler.normalize_value(v)
        except ValueError as e:
            # Append additional information to ease debugging
            raise ValueError(f"Parameter '{format_arg_name_for_err(arg)}',"
                             f" value '{repr(v)}': {e}")
        return ret_val

    def handle_poly(value):
        (handler, v, name) = value
        if not isinstance(handler, list):
            return (handler, normalize_value(handler, v), name)
        # For poly arguments with unnamed variants we have to try
        # the handlers until one matches (or we run out of variants)
        for variant in handler:
            try:
                normalized = normalize_value(variant, v)
                return (variant, normalized, '')
            except ValueError:
                pass
        raise ValueError('value does not match any poly variant')

    # Check that just one poly variant is provided
    if provided > 1:
        raise TypeError("%s() got multiple variants of argument %r"
                        % (fun_name, format_arg_name_for_err(arg)))

    # Check that all required arguments are provided
    if ((arg.spec in '1+') and provided == 0):
        raise TypeError("%s() did not get required keyword argument %r"
                        % (fun_name, format_arg_name_for_err(arg)))

    # Don't normalize or check default values
    if provided == 0:
        return value

    # Check and normalize value
    if (arg.spec in '*+') and arg.poly:
        # We handle '*' similar to '?' and '+' similar to
        # '1'. This means the client can only specify at most one
        # value from Python, not a list of values as from
        # CLI. This should be an acceptable limitation in this
        # obscure case.
        if isinstance(value, tuple):
            return [handle_poly(value)]
        return []
    elif arg.spec in '*+':
        if not isinstance(value, list):
            raise TypeError("%s() got non-list argument in %r"
                            % (fun_name, format_arg_name_for_err(arg)))
        if arg.spec == '+' and not len(value):
            raise TypeError("%s() got empty list in %r"
                            % (fun_name, format_arg_name_for_err(arg)))
        return [normalize_value(arg.handler, v) for v in value]
    elif arg.poly:
        return handle_poly(value)
    else:
        return normalize_value(arg.handler, value)

def describe_kw_parameter(spec, default_value):
    (i, arg, handler, name) = spec
    is_required = arg.spec in '1+'
    desc = "required" if is_required else "optional"
    if not isinstance(handler, tuple):  # for now, no info about polyvalues
        desc += ", " + handler.desc()
    if not is_required:
        desc += f", default value - {default_value!r}"
    return desc

def add_spec(key_spec, name, i, arg, handler):
    spec = (i, arg, handler, name)
    for key in get_key_names(name):
        key_spec[key] = spec

def get_key_names(name):
    """Return one or two keys to use for the given argument name.

    It returns two keys if the first key is a python keyword, which makes
    it hard to pass arguments using that key (you would have to use an
    explicit dictionary)."""
    key = name.replace('-', '_').replace(':', '_')
    if keyword.iskeyword(key):
        return [key, key + '_']
    return [key]

def add_arg_specs(start_idx, key_spec, arg_spec, args):
    for (i, arg) in enumerate(args):
        # Every argument name is only used once
        if arg.poly:
            for (name, handler) in zip(arg.name, arg.handler):
                if name:
                    add_spec(key_spec, name, i, arg, handler)
            if not all(arg.name):
                arg_spec.append(
                    (start_idx + i, arg,
                     [h for (n, h) in zip(arg.name, arg.handler)
                      if n == '']))
        elif arg.name:
            add_spec(key_spec, arg.name, start_idx + i, arg, arg.handler)
        else:
            arg_spec.append((start_idx + i, arg, arg.handler))

def wrap_cmd_fun(fun, cmd_args, dynamic_args, obj):

    def default(arg):
        if arg.handler == flag_t:
            return False
        elif arg.spec == '?':
            return arg.default
        elif arg.spec == '*':
            return []
        else:
            return None

    # First we build mappings from keywords and positions in the
    # wrapper arguments to positions and argument information. This is
    # used in the later translation of the arguments.
    key_spec = {}
    arg_spec = []

    add_arg_specs(0, key_spec, arg_spec, cmd_args)

    # Find the default values of all the arguments
    defaults = [default(arg) for arg in cmd_args]

    def f(*args, **kw):
        check_run_command_oec()
        if obj and not hasattr(obj, 'name'):  # ensure obj was not deleted
            raise CliError(f'Cannot run command for {obj!r}')

        cur_key_spec = dict(key_spec)
        cur_arg_spec = list(arg_spec)
        cur_args = list(cmd_args)
        cur_defaults = list(defaults)

        if dynamic_args:
            (arg_name, arg_generator) = dynamic_args
            if arg_name in kw or arg_name is None:
                dyn_args = arg_generator(kw[arg_name] if arg_name else None,
                                         False)
                cur_args += dyn_args
                cur_defaults += [default(arg) for arg in dyn_args]
                add_arg_specs(len(cmd_args),
                              cur_key_spec, cur_arg_spec, dyn_args)

        values = list(cur_defaults) # copy the list of defaults
        provided = [0] * len(cur_args)

        # Map keyword arguments to target arguments
        for (k, v) in list(kw.items()):
            if k not in cur_key_spec:
                raise TypeError('%s() got an unexpected keyword argument %r'
                                % (f.__name__, k))
            (i, arg, handler, name) = cur_key_spec[k]
            if arg.poly:
                v = (handler, v, name)
            values[i] = v
            provided[i] += 1

        # Map positional arguments to target arguments
        if len(args) > len(cur_arg_spec):
            raise TypeError('%s() takes at most %d unnamed arguments'
                            % (f.__name__, len(cur_arg_spec)))
        for (v, (i, arg, handler)) in zip(args, cur_arg_spec):
            if arg.poly:
                v = (handler, v, '')
            values[i] = v
            provided[i] += 1

        # Validate all the mapped arguments
        validated = [validate(f.__name__, arg, value, p)
                     for (arg, value, p) in zip(cur_args, values, provided)]

        global current_cmdinfo
        prev_cmdinfo = current_cmdinfo
        current_cmdinfo = cmdinfo_class()

        try:
            if obj:
                res = fun(obj, *validated)
            else:
                res = fun(*validated)
        finally:
            current_cmdinfo = prev_cmdinfo

        # Check that result is a valid CLI value: commands are allowed
        # to return only values which supported by Simics CLI.
        _ = value_to_token(res)

        # We unwrap command_return values as CLI commands Python wrappers
        # are intended for scripting and this is what happens when
        # a cli command is used in an expression. For interactive use,
        # just use the cli command directly.
        if isinstance(res, command_return):
            return res.get_value()
        return res
    return (f, arg_spec, key_spec, defaults)

def wrap_cli_cmd_impl(fun_name, cmd, obj):
    (f, arg_spec, key_spec, defaults) = wrap_cmd_fun(
        cmd.fun, cmd.args, cmd.dynamic_args, obj)
    f.__name__ = fun_name
    docstring = f"Function to run the '{cmd.name}' command."
    if not arg_spec and not key_spec:
        docstring += "\nThe function has no parameters."
    else:
        if arg_spec:
            docstring += (f"\nThe function accepts at most {len(arg_spec)}"
                          " positional parameter(s).")
        else:
            docstring += "\nNo positional parameters are accepted."
        if key_spec:
            docstring += (
                "\nThe following keyword-only parameter(s) are accepted:\n"
                + "\n".join(
                    f"- {key}: {describe_kw_parameter(spec, defaults[spec[0]])}"
                    for key, spec in key_spec.items()
                    if not keyword.iskeyword(key) # to not confuse users we just
                                                  # show argument aliases for
                                                  # Python keywords SIMICS-16434
                ))
        else:
            docstring += "\nNo keyword-only parameters are present."

        if cmd.dynamic_args:
            docstring += ("\n\nThis command also has dynamically generated"
                          " parameters, which are not included here.")

    # Add to the docstring information which can be useful for debugging:
    func = cmd.fun
    if isinstance(func, functools.partial):
        func = func.func
    try:
        func_file = inspect.getfile(func)
        func_sourcefile = inspect.getsourcefile(func)
    except TypeError:
        pass  # errors from inspect functions are just ignored
    else:
        func_line = (func.__code__.co_firstlineno
                     if hasattr(func, "__code__") else "unknown")
        docstring += (
            f"\n\nDebug info for the '{cmd.name}' command: the command runs"
            f" the '{func.__name__}' function from '{func_file}'"
            f" (source code file '{func_sourcefile}', line {func_line}).")
    f.__doc__ = docstring

    return f

class _test_wrap_cli_cmd_impl(unittest.TestCase):
    def setUp(self):
        self.commands = Command_list()
        self.commands.allow_redefine = False
        self.obj = types.SimpleNamespace(name = self.__class__.__name__)

    def cmdfun(self, *args):
        self.args = args

    def wrap(self, name, args):
        cmd = self.commands.new_command(name, self.cmdfun, args)
        return wrap_cli_cmd_impl(name, cmd, self.obj)

    def test_kw_arg_mapping(self):
        fun = self.wrap('c', [arg(int_t, 'a'), arg(flag_t, '-flag'),
                               arg((int_t, str_t), ('int', 'str'))])
        fun(a=1, _flag=True, int=2)
        self.assertEqual(self.args, (self.obj, 1, True, (int_t, 2, 'int')))
        fun(a=1, _flag=True, str='hi')
        self.assertEqual(self.args, (self.obj, 1, True, (str_t, 'hi', 'str')))

    def test_flags(self):
        fun = self.wrap('c', [arg(flag_t, '-a'), arg(flag_t, '-b')])
        fun(_a=False)
        self.assertEqual(self.args, (self.obj, False, False))
        fun(_b=True)
        self.assertEqual(self.args, (self.obj, False, True))

    def test_list_spec(self):
        fun = self.wrap('star', [arg(int_t, 'int', '*')])
        fun()
        self.assertEqual(self.args, (self.obj, []))
        fun(int = [])
        self.assertEqual(self.args, (self.obj, []))
        fun(int = [1, 2, 3])
        self.assertEqual(self.args, (self.obj, [1, 2, 3]))
        with self.assertRaises(TypeError):
            fun(int=1)

        fun = self.wrap('plus', [arg(int_t, 'int', '+')])
        with self.assertRaises(TypeError):
            fun()
        with self.assertRaises(TypeError):
            fun(int = [])
        fun(int = [1, 2, 3])
        self.assertEqual(self.args, (self.obj, [1, 2, 3]))
        with self.assertRaises(TypeError):
            fun(int=1)

    def test_poly_value(self):
        req = self.wrap('req', [arg((int_t, str_t, flag_t),
                                    ('int', 'str', '-flag'), '1')])
        with self.assertRaises(TypeError):
            req()
        req(_flag=False)
        self.assertEqual(self.args, (self.obj, (flag_t, False, '-flag')))
        opt = self.wrap('opt', [arg((int_t, str_t, flag_t),
                                    ('int', 'str', '-flag'), '?',
                                    (flag_t, False, '-flag'))])
        opt()
        self.assertEqual(self.args, (self.obj, (flag_t, False, '-flag')))
        opt(int=5)
        self.assertEqual(self.args, (self.obj, (int_t, 5, 'int')))
        with self.assertRaises(TypeError):
            opt(int=5, str='hi')

    def test_poly_list_spec(self):
        req = self.wrap('req', [arg((int_t, str_t, flag_t),
                                    ('int', 'str', '-flag'), '+')])
        with self.assertRaises(TypeError):
            req()
        req(_flag=False)
        self.assertEqual(self.args, (self.obj, [(flag_t, False, '-flag')]))
        with self.assertRaises(TypeError):
            req(int = 5, str = 'hi')

        opt = self.wrap('opt', [arg((int_t, str_t, flag_t),
                                    ('int', 'str', '-flag'), '*')])
        opt()
        self.assertEqual(self.args, (self.obj, []))
        opt(int=5)
        self.assertEqual(self.args, (self.obj, [(int_t, 5, 'int')]))
        with self.assertRaises(TypeError):
            opt(int=5, str='hi')

    def test_is_validated(self):
        fun = self.wrap('cmd', [arg(int_t, 'paramName')])
        with self.assertRaisesRegex(ValueError, 'paramName'):
            fun(paramName = 'hi')

    def test_check_required(self):
        fun = self.wrap('simple', [arg(int_t, 'a')])
        with self.assertRaises(TypeError):
            fun()
        fun = self.wrap('poly', [arg((int_t, str_t), ('a', 'b'))])
        with self.assertRaises(TypeError):
            fun()

    def test_check_required_keyword(self):
        fun = self.wrap('simple', [arg(int_t, 'class')])
        with self.assertRaisesRegex(
                TypeError,
                re.escape("simple() did not get required keyword argument"
                          " 'class_'")):
            fun()

        fun = self.wrap('poly', [arg((int_t, str_t), ('class', 'b'))])
        with self.assertRaisesRegex(
                TypeError,
                re.escape("poly() did not get required keyword argument"
                          " ('class_', 'b')")):
            fun()

    def test_unanamed_arg(self):
        fun = self.wrap('first', [arg(int_t)])
        fun(5)
        self.assertEqual(self.args, (self.obj, 5))
        fun = self.wrap('second', [arg(str_t, 'named', '?', 'hi'), arg(int_t)])
        fun(5)
        self.assertEqual(self.args, (self.obj, 'hi', 5))

    def test_unnamed_poly_arg(self):
        fun = self.wrap('first', [arg((int_t, str_t))])
        fun(5)
        self.assertEqual(self.args, (self.obj, (int_t, 5, '')))
        fun('hi')
        self.assertEqual(self.args, (self.obj, (str_t, 'hi', '')))

        fun = self.wrap('second', [arg(str_t, 'named', '?', 'hi'),
                                   arg((int_t, str_t))])
        fun(5)
        self.assertEqual(self.args, (self.obj, 'hi', (int_t, 5, '')))
        fun('hello')
        self.assertEqual(self.args, (self.obj, 'hi', (str_t, 'hello', '')))

    def test_some_unnamed_poly_arg(self):
        fun = self.wrap('first', [arg((int_t, str_t), ('', 's'))])
        fun(5)
        self.assertEqual(self.args, (self.obj, (int_t, 5, '')))
        fun(s='hi')
        self.assertEqual(self.args, (self.obj, (str_t, 'hi', 's')))
        with self.assertRaises(ValueError):
            fun('hi')

        fun = self.wrap('second', [arg(str_t, 'named', '?', 'hi'),
                                   arg((int_t, str_t), ('', 's'))])
        fun(5)
        self.assertEqual(self.args, (self.obj, 'hi', (int_t, 5, '')))
        fun(s = 'hello')
        self.assertEqual(self.args, (self.obj, 'hi', (str_t, 'hello', 's')))

    def test_unnamed_list_arg(self):
        fun = self.wrap('star', [arg(int_t, spec='*')])
        fun([1, 2, 3, 4])
        self.assertEqual(self.args, (self.obj, [1, 2, 3, 4]))
        fun()
        self.assertEqual(self.args, (self.obj, []))
        with self.assertRaises(TypeError):
            fun(1, 2, 3, 4)

        fun = self.wrap('plus', [arg(int_t, spec='+')])
        fun([1, 2, 3, 4])
        self.assertEqual(self.args, (self.obj, [1, 2, 3, 4]))
        with self.assertRaises(TypeError):
            fun()
        with self.assertRaises(TypeError):
            fun(1, 2, 3, 4)

    def test_unnamed_poly_list(self):
        req = self.wrap('req', [arg((int_t, str_t),
                                    spec='+')])
        with self.assertRaises(TypeError):
            req()
        req('hi')
        self.assertEqual(self.args, (self.obj, [(str_t, 'hi', '')]))
        with self.assertRaises(TypeError):
            req(5, 'hi')

        opt = self.wrap('opt', [arg((int_t, str_t), spec='*')])
        opt()
        self.assertEqual(self.args, (self.obj, []))
        opt(5)
        self.assertEqual(self.args, (self.obj, [(int_t, 5, '')]))
        with self.assertRaises(TypeError):
            opt(5, 'hi')

    def test_mixed_named_unnamed_poly_list(self):
        req = self.wrap('req', [arg((int_t, str_t), ('num', ''), spec='+')])
        with self.assertRaises(TypeError):
            req()
        req('hi')
        self.assertEqual(self.args, (self.obj, [(str_t, 'hi', '')]))
        req(num=5)
        self.assertEqual(self.args, (self.obj, [(int_t, 5, 'num')]))
        with self.assertRaises(TypeError):
            req('hi', num=5)

        opt = self.wrap('opt', [arg((int_t, str_t), ('num', ''), spec='*')])
        opt()
        self.assertEqual(self.args, (self.obj, []))
        opt('hi')
        self.assertEqual(self.args, (self.obj, [(str_t, 'hi', '')]))
        opt(num=5)
        self.assertEqual(self.args, (self.obj, [(int_t, 5, 'num')]))
        with self.assertRaises(TypeError):
            opt('hi', num=5)

    def test_command_return(self):
        cmd_result = None
        def impl(obj):
            return cmd_result
        cmd = self.commands.new_command('cmd', impl, [])
        fun = wrap_cli_cmd_impl('cmd', cmd, self.obj)
        cmd_result = None
        self.assertEqual(fun(), None)
        cmd_result = 5
        self.assertEqual(fun(), 5)
        cmd_result = command_return(value=7)
        self.assertEqual(fun(), 7)
        cmd_result = command_return(value=None)
        self.assertEqual(fun(), None)
        # Check an illegal return value for command (i.e. the value
        # not supported by Simics CLI):
        cmd_result = dict()
        with self.assertRaises(CliError):
            fun()

    def test_nonstandard_handler(self):
        class NonStandard:
            def has_expander(self):
                return False
        fun = self.wrap('cmd', [arg(NonStandard())])
        with self.assertRaises(TypeError):
            fun()

    def test_dont_validate_defaults(self):
        fun = self.wrap('cmd',
                        [arg(filename_t(), 'param-file', '?', 'autodetect'),
                         arg(poly_t('node spec', str_t, uint_t), 'node', '?',
                             None),
                         arg(str_t, 'version-string', '?', None),
                         arg(integer_t, 'base-address', '?', None),
                         arg(filename_t(exist=True), 'symbol-file', '?', None)
                         ])
        fun()
        self.assertEqual(self.args, (self.obj, 'autodetect', None, None, None,
                                     None))

    def test_flag_default(self):
        fun = self.wrap('cmd', [arg(flag_t, '-a'), arg(flag_t, '-b', '?',
                                                       'hello')])
        fun()
        self.assertEqual(self.args, (self.obj, 0, 0))

    def test_arg_aliases(self):
        fun = self.wrap('c', [arg(int_t, 'break')])
        fun(**{'break': 1})
        self.assertEqual(self.args, (self.obj, 1))
        fun(break_=1)
        self.assertEqual(self.args, (self.obj, 1))

def command_name_to_function_name(name):
    name = name.replace('-', '_')
    if keyword.iskeyword(name) or name == 'print':
        name += "_cmd"
    return name

class cli_command_list:
    '''This namespace provides Python functions to run
    Simics CLI commands defined for the object.'''

    def __init__(self, obj):
        self._obj = obj

    # For now we search through all commands and generate a wrapper function
    # on demand. In future, it would be nice to store a dict with wrappers in
    # the all_commands object.
    def __getattr__(self, name):
        if not hasattr(self._obj, 'name'):  # ensure obj was not deleted
            raise CliError(f'Associated object was deleted: {self._obj!r}')

        for cmd in all_commands.get_object_commands(self._obj):
            for m in cmd.all_methods():
                func_name = command_name_to_function_name(m)
                if func_name == name:
                    return wrap_cli_cmd_impl(func_name, cmd, self._obj)

        raise AttributeError(f"No command found for the '{name}' name"
                             f" in the {self._obj.name} object.")

    def __dir__(self):
        if not hasattr(self._obj, 'name'):  # ensure obj was not deleted
            raise CliError(f'Associated object was deleted: {self._obj!r}')

        return [command_name_to_function_name(m)
                for cmd in all_commands.get_object_commands(self._obj)
                for m in cmd.all_methods()]

class global_cli_commands_wrapper(
        metaclass = doc(
            'Namespace with functions to run global CLI commands',
            module = 'cli',
            name = 'global_cmds',
            synopsis = 'global_cmds.<i>wrapper_function(...)</i>')):
    '''The namespace provides wrapper Python functions to run global
    Simics CLI commands. A wrapper function name
    is usually the same as a name of the command it executes
    with hyphens replaced with underscores. The parameters of
    the wrapper functions are the same as of the corresponding command (again,
    with hyphens replaced with underscores). Command flags (the names of
    the corresponding function parameters start with an underscore)
    could be passes as Python Boolean values. In the rare cases that a wrapper
    function name or a wrapper function parameter name turns out to be
    a Python keyword, the <tt>_cmd</tt> suffix is added
    to the wrapper function name
    and the function parameter gets the <tt>_</tt> suffix.
    Wrapper functions return the value returned by the command
    which they execute.

    Please consult the docstring
    of the wrapper function and the respective command documentation
    for the information about function arguments and the returned value.'''

    def __init__(self):
        # dont_export_gcmds contains manually picked list of global commands
        # for which it doesn't make a lot of sense to provide wrappers.
        self.dont_export_gcmds = {
            'break-loop', 'continue-loop'}

    def get_all_accessible_global_commands(self):
        return (cmd for cmd in all_commands if
                not (cmd.iface or cmd.cls)  # filter out namespace cmds
                and not isinstance(cmd.fun, _DummyCommandHandler)
                and cmd.method not in self.dont_export_gcmds)

    # For now we search through all commands and generate a wrapper function
    # on demand. In future, it would be nice to store a dict with wrappers in
    # the all_commands object. Anyway, the lru_cache makes things quite fast:
    @functools.lru_cache(maxsize = 128)
    def __getattr__(self, name):
        for cmd in self.get_all_accessible_global_commands():
            for m in cmd.all_methods():
                func_name = command_name_to_function_name(m)
                if func_name == name:
                    return wrap_cli_cmd_impl(func_name, cmd, None)

        raise AttributeError(f"No global command found for the '{name}' name")

    def __dir__(self):
        return [command_name_to_function_name(m)
                for cmd in self.get_all_accessible_global_commands()
                for m in cmd.all_methods()
                if m != "-" and m.replace('-', '_').isidentifier()]

global_cmds = global_cli_commands_wrapper()

@doc('define a new CLI command',
     module = 'cli')
def new_command(name, fun, args = [], **kwargs):
    """Define a new CLI command. A complete explanation of
    <fun>new_command</fun> and its parameters is available in
    <cite>Simics Model Builder User's Guide</cite>, in the
    <cite>Adding New Commands</cite> chapter."""
    all_commands.new_command(name, fun, args, **kwargs)

@doc('register a command category',
     module = 'cli')
def register_command_category(name = None):
    """Register a command category for the 'type' argument given to the
    <fun>new_command</fun> function. Command categories are optional but may
    be useful if many commands are defined for a particular use case that is
    of general interest.

    <param>name</param> should be at least 3 characters long and preferably
    just one capitalized word, a noun.

    <em>Notice</em>: Do not register any command category for a class, as those
    are listed on the class itself.

    Invoke this function without any argument to print the standard
    categories, assuming no modules or targets have been loaded."""
    return all_commands.register_command_category(name)

# internal
def new_operator(name, fun, args = [], **kwargs):
    all_commands.new_operator(name, fun, args, **kwargs)

def simics_commands():
    return all_commands.get_sorted()

def get_simics_command(name):
    return all_commands.get(name)

def simics_command_exists(key):
    return all_commands.exists(key)

@doc('define a new unsupported CLI command',
     module = 'cli')
def new_unsupported_command(name, feature, fun, args = [], doc = "", **kwargs):
    """Define a new unsupported CLI command."""

    if not unsupported_exists(feature):
        raise CliCmdDefError(f"No such unsupported feature '{feature}'")

    kwargs["unsupported"] = feature
    all_commands.new_command(name, fun, args, doc, **kwargs)


@doc('define a new CLI tech preview command',
     module = 'cli')
def new_tech_preview_command(name, feature, fun, args=[], doc="", **kwargs):
    """Define a new tech preview CLI command."""

    if not tech_preview_exists(feature):
        raise CliCmdDefError(f"No such Technology Preview '{feature}'")

    kwargs["preview"] = feature
    all_commands.new_command(name, fun, args, doc, **kwargs)

# Commands only available when a tech preview is enabled (dict of sets)
tech_preview_cmds = {}
# Keep track of all enabled technology previews.
enabled_tech_previews = set()

def tech_preview_exists(preview):
    return preview in tech_preview_cmds

def add_tech_preview(preview):
    if not tech_preview_exists(preview):
        tech_preview_cmds[preview] = set()

def tech_preview_enabled(preview):
    assert tech_preview_exists(preview)
    return preview in enabled_tech_previews

def tech_preview_info():
    ret = []
    for (preview, cmd_set) in tech_preview_cmds.items():
        cmd_name_set = [x.name for x in cmd_set]
        ret.append((preview, tech_preview_enabled(preview), cmd_name_set))
    return ret

def enable_tech_preview(preview, verbose = False):
    assert tech_preview_exists(preview)
    enabled_tech_previews.add(preview)
    if verbose and tech_preview_cmds[preview]:
        print("Enabling the following commands:")
        for cmd in tech_preview_cmds[preview]:
            print(cmd.name)
        print()
    all_commands.drop_cache()

def disable_tech_preview(preview):
    assert tech_preview_exists(preview)
    enabled_tech_previews.discard(preview)
    all_commands.drop_cache()

# Commands only available when an unsupported feature is enabled (dict of sets)
unsupported_cmds = {}
# Keep track of all enabled technology previews.
enabled_unsupported = set()

def unsupported_exists(feature):
    return feature in unsupported_cmds

def add_unsupported(feature):
    if not unsupported_exists(feature):
        unsupported_cmds[feature] = set()

def unsupported_enabled(feature):
    assert unsupported_exists(feature)
    return feature in enabled_unsupported

def unsupported_info():
    ret = []
    for (feature, cmd_set) in unsupported_cmds.items():
        cmd_name_set = [x.name for x in cmd_set]
        ret.append((feature, unsupported_enabled(feature), cmd_name_set))
    return ret

def enable_unsupported(feature, verbose = False):
    assert unsupported_exists(feature)
    enabled_unsupported.add(feature)
    if verbose and unsupported_cmds[feature]:
        print("Enabling the following commands:")
        for cmd in unsupported_cmds[feature]:
            print(cmd.name)
        print()
    all_commands.drop_cache()

def disable_unsupported(feature):
    assert unsupported_exists(feature)
    enabled_unsupported.discard(feature)
    all_commands.drop_cache()

add_unsupported("internals")

# ---------------- front end vars -----------------

try:
    cmd_hap = simics.SIM_hap_add_type(
        "CLI_Command_Added", "s", "command_name", None,
        "Triggered when a CLI command is defined.", 0)
except simics.SimExc_General as ex:
    print("Failed installing CLI_Command_Added hap: %s" % ex)

class simenv_class:
    def __init__(self, parent, real_parent, env = {}):
        object.__setattr__(self, '__variables__', env.copy())
        object.__setattr__(self, '__parent__', parent)
        object.__setattr__(self, '__real_parent__', real_parent)

    def duplicate_environment(self):
        parent = None
        if self.__parent__:
            parent = self.__parent__.duplicate_environment()
        return simenv_class(parent, self.__real_parent__, self.__variables__)

    def get_all_variables(self):
        all = self.__variables__.copy()
        if self.__parent__:
            all.update(self.__parent__.get_all_variables())
        return all

    def verify_cli_value(self, value):
        try:
            value_to_token(value)
        except CliError:
            raise CliError("{} is not a valid CLI value".format(value))

    def set_variable_value(self, name, value, local):
        if local:
            self.verify_cli_value(value)
            self.__variables__[name] = value
        else:
            self.__setattr__(name, value)

    def remove_variable(self, name):
        if name in self.__variables__:
            del self.__variables__[name]
        elif self.__parent__:
            return self.__parent__.remove_variable(name)

    def __getattr__(self, name):
        if name in self.__variables__:
            return self.__variables__[name]
        elif self.__parent__:
            return getattr(self.__parent__, name)
        elif name.startswith('__'):
            #unknown internal attribute
            raise AttributeError("'simenv' object has no attribute '%s'"
                                 % name)
        else:
            raise AttributeError('No CLI variable "%s"' % name)

    def __setattr__(self, name, value):
        if name in self.__variables__ or self.__parent__ == None:
            self.verify_cli_value(value)
            self.__variables__[name] = value
        else:
            setattr(self.__parent__, name, value)

current_locals = simenv_class(None, None)

def getenv(data, o, idx):
    DEPRECATED(simics.SIM_VERSION_7, "The sim->env attribute is deprecated.",
               "Use the simenv Python object instead.")
    if idx is None:
        result = {}
        for var in current_locals.get_all_variables():
            result[var] = getattr(current_locals, var)
        return result
    return getattr(current_locals, idx)

def setenv(data, o, val, idx):
    DEPRECATED(simics.SIM_VERSION_7, "The sim->env attribute is deprecated.",
               "Use the simenv Python object instead.")
    if idx is None:
        return simics.Sim_Set_Illegal_Index
    setattr(current_locals, idx, val)
    return simics.Sim_Set_Ok

simics.SIM_register_typed_attribute(
    "sim", "env",
    getenv, 0, setenv, 0,
    simics.Sim_Attr_Pseudo | simics.Sim_Attr_String_Indexed | simics.Sim_Attr_Internal,
    None, "a",
    "get/set CLI variable in the current scope")


# If name is not None, return name, or None if it's already taken. If
# name is None, return "stemN" for the lowest integer N such that the
# name "stemN" isn't taken.
def new_object_name(name, stem):
    def name_taken(name):
        try:
            SIM_get_object(name)
            return True
        except simics.SimExc_General:
            return False
    if name != None and name_taken(name):
        return None
    count = 0
    while name == None:
        name = "%s%d" % (stem, count)
        if name_taken(name):
            name = None
            count += 1
    return name

def command_sort_category(n):
    l = len(n)
    if l == 0:
        return 0
    for i in range(l):
        if n[i] in letters:
            return 2
    return 1

@total_ordering
class cli_command:
    parameters = ('fun', 'pri', 'infix', 'doc', 'type',
                  'short', 'group_short', 'args', 'alias', 'doc_with',
                  'synopses',
                  'check_args', 'doc_items', 'see_also', 'method',
                  'cls', 'iface', 'preview', 'unsupported',
                  'filename', 'linenumber',
                  'object', 'repeat', 'deprecated', 'is_alias_for', 'module',
                  'hidden', 'deprecated_version', 'legacy', 'legacy_version',
                  'dynamic_args', 'internal_args')
    def __init__(self, **kwargs):
        # If this is set, it means that this command is a "namespace
        # copy" of the referenced command.
        self.is_alias_for = None
        self.deprecated_warned = False
        self.legacy_warned = False
        for key,value in kwargs.items():
            setattr(self, key, value)
        # Cannot register a command both on a class and an interface
        # simultaneously, except through the legacy 'namespace' parameter
        # which sets both to the same string.
        assert not self.cls or not self.iface or self.cls == self.iface
    def __repr__(self):
        return "cli_command(%r)" % self.name
    def __getitem__(self, key):
        raise Exception("cmd[%r]" % key)
    def __setitem__(self, key, value):
        raise Exception("cmd[%r] = ..." % key)
    def __hash__(self):
        return hash(self.__repr__())
    def _get_name(self):
        namespace = self.cls or self.iface
        if namespace:
            return "<%s>.%s" % (namespace, self.method)
        else:
            return self.method
    name = property(_get_name)

    def parameter_dict(self):
        return dict((k, getattr(self, k)) for k in self.parameters)
    def __lt__(self, other):
        self_cat = command_sort_category(self.name)
        other_cat = command_sort_category(other.name)
        if self_cat == other_cat:
            return self.name < other.name
        else:
            return self_cat < other_cat
    def __eq__(self, other):
        self_cat = command_sort_category(self.name)
        other_cat = command_sort_category(other.name)
        if self_cat == other_cat:
            return self.name == other.name
        else:
            return False
    def __ne__(self, other):
        return not (self == other)
    def alias_names(self):
        namespace = self.cls or self.iface
        if namespace:
            return ["<%s>.%s" % (namespace, n) for n in self.alias]
        else:
            return self.alias[:]
    def all_methods(self):
        return [self.method] + self.alias

    def is_deprecated(self):
        return (self.deprecated
                and (self.deprecated_version is None
                     or self.deprecated_version <= conf.sim.version))

    def is_legacy(self):
        return (self.legacy
                and (self.legacy_version is None
                     or self.legacy_version <= conf.sim.version))

    @stop_traceback
    def call(self, args, obj = None):
        if obj != None:
            args = [obj] + args
        return self.fun(*args)

try:
    import pwd
    getpwall = pwd.getpwall
    getpwnam = pwd.getpwnam
except ImportError:
    def getpwall(): return []
    def getpwnam(user): raise KeyError("getpwnam not implemented")

def get_all_user_names():
    return [p[0] for p in getpwall()]

def get_user_home_dir(user):
    try:
        return getpwnam(user)[5]
    except KeyError:
        return None

def files_in_dir(dir):
    try:
        return [f for f in os.listdir(str(dir))]
    except Exception:                   # FIXME: what exception, exactly?
        return []

def file_expander(partial_name):
    txt = partial_name
    if txt and txt[0] == "~":
        pos = txt.find(os.sep, 1)
        if os.altsep:
            altpos = txt.find(os.altsep, 1)
            if altpos >= 0 and (pos < 0 or altpos < pos):
                pos = altpos

        if pos < 0:
            # no dir separator after ~ - expand all user names
            user = txt[1:]
            users = get_all_user_names()
            if os.getenv('HOME'):
                users.append('')
            return ['~' + u for u in users if u.startswith(user)]

        user = txt[1:pos]

        # default to not modifying the prefix
        home = txt[:pos]
        if user:
            h = get_user_home_dir(user)
            if h:
                home = h
        else:
            home_env = os.getenv('HOME')
            if home_env:
                home = home_env
        txt = home + txt[pos:]

    pos = txt.rfind(os.sep)
    if os.altsep:
        altpos = txt.rfind(os.altsep, 0)
        if altpos > pos:
            pos = altpos

    if pos < 0:
        dirname = os.curdir
        filename = txt
    else:
        dirname = txt[:pos]
        filename = txt[pos + 1:]

    dirname += os.sep

    files = [f for f in files_in_dir(dirname)
             if (f.startswith(filename)
                 or (not _case_sensitive_files
                     and f.lower().startswith(filename.lower())))]
    if filename:
        path = partial_name[:-len(filename)]
    else:
        path = partial_name
    return [path + f for f in files]

class arg(
        metaclass=doc(
            'class defining a command argument',
            module = 'cli',
            synopsis = """\
            arg(handler, name = "", spec = "1", default = None,
            data = None, doc = "", expander = None, pars = [])""")):
    """Define a CLI command argument when using <fun>new_command</fun>. A
    complete explanation of <fun>new_command</fun> and <fun>arg</fun> is
    available in <cite>Simics Model Builder User's Guide</cite>, in the
    <cite>Adding New Commands</cite> chapter."""

    __slots__ = ('handler', 'name', 'spec', 'default', 'data', 'doc',
                 'expander', 'pars', 'num', 'poly')

    def __init__(self, handler, name = "", spec = "1", default = None,
                 data = None, doc = "", expander = None, pars = []):

        if spec == "":
            spec = "1"

        # TODO: move this to the type definitions somehow
        if handler == flag_t:
            if not arg.name:
                raise CliCmdDefError("flag argument must have a name")
            if not tokenizer.is_flag_token(name):
                raise CliCmdDefError(
                    "flag name must begin with '-' followed by a letter and may"
                    " only contain letters, digits and hyphens: " + name)
            if spec == "1":
                spec = "?"
            elif spec != "?":
                raise CliCmdDefError("flags must have spec '1' or '?'")
            default = False

        elif not isinstance(name, tuple) and name.startswith('-'):
            raise CliCmdDefError("only flag argument names can begin with '-'")

        if spec not in ("1", "?", "*", "+"):
            raise CliCmdDefError("unknown spec: %r" % spec)

        if isinstance(handler, tuple):
            self.poly = True

            if not name:
                name = ('',) * len(handler)

            if not isinstance(name, tuple):
                raise CliCmdDefError("name must also be a tuple"
                                     " when the handler is a tuple")
            nonnull_names = tuple(n for n in name if n)
            if len(nonnull_names) != len(set(nonnull_names)):
                raise CliCmdDefError("argument name must be unique")

            if expander and not isinstance(expander, tuple):
                raise CliCmdDefError("expander must also be a tuple"
                                     " when the handler is a tuple")
            if not expander:
                expander = (None,) * len(handler)

            for n, h in zip(name, handler):
                if h == flag_t:
                    if not n:
                        raise CliCmdDefError("flag argument must have a name")
                    if not tokenizer.is_flag_token(n):
                        raise CliCmdDefError(
                            "flag name must begin with '-' followed by a letter"
                            " and may only contain letters, digits and hyphens:"
                            " " + n)
                elif n.startswith('-'):
                    raise CliCmdDefError("only flag argument names can begin "
                                         "with '-'")
        else:
            self.poly = False
            if isinstance(name, tuple):
                raise CliCmdDefError("name must not be a tuple"
                                     " when the handler is not a tuple")
            if isinstance(expander, tuple):
                raise CliCmdDefError("expander must not be a tuple"
                                     " when the handler is not a tuple")

            # Normalize so that they are always tuples
            #handler = (handler,)
            #name = (name,)
            #expander = (expander,)

        # Figure out expanders from the type, if not explicitly given
        if self.poly:
            expanders = list(expander)
            for i in range(len(handler)):
                if not expanders[i] and handler[i].has_expander():
                    expanders[i] = handler[i].expand
            expander = tuple(expanders)
        else:
            if not expander and handler.has_expander():
                expander = handler.expand

        self.handler = handler
        self.name = name
        self.default = default
        self.data = data
        self.spec = spec
        self.doc = doc
        self.expander = expander
        self.pars = pars

        self.num = None

    def names(self):
        if self.poly:
            names = self.name
        else:
            names = (self.name,)
        # Filter out unnamed args
        return tuple(n for n in names if n)

    def clone(self):
        c = object.__new__(arg)
        c.handler = self.handler
        c.name = self.name
        c.spec = self.spec
        c.default = self.default
        c.data = self.data
        c.doc = self.doc
        c.expander = self.expander
        c.pars = self.pars
        c.num = self.num
        c.poly = self.poly
        return c

    def has_name(self):
        if isinstance(self.name, tuple):
            return any(self.name)
        else:
            return bool(self.name)

    def is_flag(self):
        if isinstance(self.name, tuple):
            return any(x.startswith('-') for x in self.name)
        else:
            return self.name.startswith('-')

    def call_expander(self, comp, obj, cmd = None, prev_args = None):
        if not prev_args and cmd:
            prev_args = [None] * len(cmd.args)
        if self.poly:
            expanders = self.expander
        else:
            expanders = [self.expander]
        comps = []
        for exp in expanders:
            if not exp:
                continue
            if cmd:
                # Expanders may take one, two or three args. The third argument
                # is a list of command argument values from the command line.
                (args, _, _, _, _, _, _) = inspect.getfullargspec(exp)
                # getargspec return a 'self' args for bound methods,
                # although it isn't used when calling it
                if inspect.ismethod(exp):
                    args.pop(0)
                if len(args) == 3:
                    expansion = exp(comp, obj, prev_args)
                elif len(args) == 2:
                    expansion = exp(comp, obj)
                else:
                    expansion = exp(comp)
            else:
                expansion = exp(comp)
            if not isinstance(expansion, list):
                raise CliError('Argument expander of %s did not return a list'
                               % cmd.name)
            comps.extend(expansion)
        return comps

class _test_arg(unittest.TestCase):
    def test_flags(self):
        # flags get some special treatment
        arg(flag_t, "-f")
        self.assertRaises(CliCmdDefError, arg, flag_t, "f")
        self.assertRaises(CliCmdDefError, arg, flag_t, "-f", "*")
        self.assertEqual(arg(flag_t, "-f").spec, "?")
        self.assertEqual(arg(flag_t, "-f", "1").spec, "?")

    def test_spec(self):
        self.assertEqual(arg(int_t, "x").spec, "1")
        self.assertEqual(arg(int_t, "x", "1").spec, "1")
        self.assertEqual(arg(int_t, "x", "?").spec, "?")
        self.assertEqual(arg(int_t, "x", "*").spec, "*")
        self.assertEqual(arg(int_t, "x", "+").spec, "+")
        self.assertRaises(CliCmdDefError, arg, int_t, "x", "!")

    def test_nonpolly(self):
        a = arg(int_t, "x")
        self.assertFalse(a.poly)
        self.assertEqual(a.name, "x")

    def test_polly1(self):
        self.assertRaises(CliCmdDefError, arg, (int_t, int_t), "x")
        self.assertRaises(CliCmdDefError, arg, int_t, ("x", "y"))
        self.assertRaises(CliCmdDefError, arg, int_t, "x",
                          expander = (None, None))

    def test_polly2(self):
        a = arg((int_t, int_t), ("x", "y"), expander = (None, None))
        self.assertTrue(a.poly)
        self.assertEqual(a.name, ("x", "y"))

    def test_polly3(self):
        a = arg((int_t, int_t), ("x", "y"))
        self.assertTrue(a.poly)
        self.assertEqual(a.expander, (None, None))

    def test_polly_dup(self):
        self.assertRaises(CliCmdDefError, arg, (int_t, str_t), ("x", "x"))

    def test_completer(self):
        a = arg(string_set_t(["aaaa", "aabb", "bbbb"]))
        self.assertEqual(a.call_expander("", None),
                         ["aaaa", "aabb", "bbbb"])
        self.assertEqual(a.call_expander("a", None),
                         ["aaaa", "aabb"])
        self.assertEqual(a.call_expander("aaa", None),
                         ["aaaa"])
        self.assertEqual(a.call_expander("b", None),
                         ["bbbb"])
        self.assertEqual(a.call_expander("c", None),
                         [])

    def test_poly_completer(self):
        a = arg((boolean_t, string_set_t(["foo", "bar"])), ('xx', 'yy'))
        self.assertEqual(a.call_expander("", None),
                         ["FALSE", "TRUE", "bar", "foo"])
        self.assertEqual(a.call_expander("x", None),
                         [])
        self.assertEqual(a.call_expander("T", None),
                         ["TRUE"])
        self.assertEqual(a.call_expander("f", None),
                         ["foo"])
        a = poly_to_spec(a, "yy")
        self.assertEqual(a.call_expander("", None),
                         ["bar", "foo"])

def istabcomplete(tokens, i):
    return (isinstance(tokens[i], tokenizer.string_token)
            and (tokens[i].value.endswith("\a")
                 or (tokens[i].value.endswith('->')
                     and len(tokens) > i + 1
                     and isinstance(tokens[i + 1], tokenizer.string_token)
                     and tokens[i + 1].value.endswith("\a"))))

def get_arg_description(handler):
    if isinstance(handler, tuple):
        return " or ".join(h.desc() for h in handler)
    else:
        return handler.desc()

def find_arg(name, arglist):
    for i,a in enumerate(arglist):
        if name in a.names():
            return (a, i)
    return (None, 0)

def poly_to_spec(arg, spec):
    for i in range(len(arg.name)):
        if arg.name[i] == spec:
            arg.name = (spec,)
            arg.handler = (arg.handler[i],)
            if arg.expander:
                arg.expander = (arg.expander[i],)
            return arg
    raise CliErrorInPolyToSpec


# Handle the "cmd arg = ..." case
def handle_named_arg(cmdinfo, cmd, obj, retlist, used_args, arglist, tokens):
    name = tokens[0].value

    (arg, i) = find_arg(name, arglist)

    if arg:
        used_args.append(arg)
        del arglist[i]
        tokens = tokens[2:]
        cmdinfo.set_current_line(tokens[0])
        retentry = arg.num

        if arg.poly:
            arg = poly_to_spec(arg, name)

        # tab completion stuff
        if istabcomplete(tokens, 0):
            comp = tokens[0].value[:-1]
            comps = arg.call_expander(comp, obj, cmd, retlist)

            if comps:
                raise CliTabComplete(comps)
            if (arg.spec == "?"
                and not comp
                and not isinstance(arg.default, tuple)):
                if isinstance(arg.default, str):
                    if arg.default == "":
                        raise CliTabComplete([])
                    else:
                        raise CliTabComplete([arg.default])
                elif isinstance(arg.default, int):
                    raise CliTabComplete([str(arg.default)])
                else:
                    raise CliTabComplete([])
            raise CliTabComplete([])

        if arg.spec == "?":
            # require argument now when name has been specified
            arg.spec = "1"

        if arg.spec == "*":
            # require at lease one argument now when name has been specified
            arg.spec = "+"
    else:
        (arg, _) = find_arg(name, used_args)
        if arg:
            raise CliArgNameError(
                "argument '%s' specified twice for command '%s'" % (
                    name, cmd.name))
        (arg, _) = find_arg(name, cmd.args)
        if arg and arg.poly:
            raise CliArgNameError(
                "%s argument(s)/flag(s) of '%s' are mutually exclusive" % (
                    ", ".join("'%s'" % (n,) for n in arg.names()), cmd.name))
        raise CliArgNameError(
            "unknown argument name '%s' in '%s'" % (name, cmd.name))
    return tokens, retentry, arg

# Handle the "cmd -flag" case
def handle_flag_arg(cmd, used_args, arglist, tokens):
    flagname = tokens[0].value

    (arg, i) = find_arg(flagname, arglist)

    if arg:
        used_args.append(arg)
        del arglist[i]
        retentry = arg.num
        if arg.poly:
            arg = poly_to_spec(arg, flagname)
    else:
        (arg, _) = find_arg(flagname, used_args)
        if arg:
            raise CliArgNameError(
                "flag '%s' specified twice for command '%s'" % (
                    flagname, cmd.name))
        (arg, _) = find_arg(flagname, cmd.args)
        if arg and arg.poly:
            raise CliArgNameError(
                "%s argument(s)/flag(s) of '%s' are mutually exclusive" % (
                    ", ".join("'%s'" % (n,) for n in arg.names()), cmd.name))
        raise CliArgNameError(
            "unknown flag '%s' in '%s'" % (flagname, cmd.name))
    return retentry, arg

# True if arg_type includes sub_type, either as itself or as subtype in a poly
def hastype(arg_type, sub_type):
    if isinstance(arg_type, sub_type):
        return True
    if isinstance(arg_type, poly_t):
        for t in arg_type.types:
            if hastype(t, sub_type):
                return True
    return False

# Converts a CLI list token (first token in tokens) to values accepted
# by "+" or "*" arguments. Each value will be checked by the handler
# of arg. This means you can use a CLI list instead of repeated args
# for the command.  Useful for using other command to return a list
# that can be fed a "+" or "*" argument
def accept_list_as_glob_args(arg, tokens, cmd, processed_args):
    list_tokens = tokens[0].tokens
    for t in list_tokens:
        try:
            arg.handler.value([t]) # check token
        except CliTypeError:
            raise CliOutOfArgs(
                ("argument %d (%s) given to '%s'"
                 " has the wrong type, list of %s expected") %
                (processed_args + 1, tokens[0].string(),
                 cmd.name, get_arg_description(arg.handler)))

    (val, pos) = list_t.value(tokens)

    # Convert list of strings to objects if we expect objects and it is an object
    if hastype(arg.handler, obj_t):
        def getobj(s):
            return (get_object(s)
                    if isinstance(s, str) and object_exists(s) else s)
        val = [getobj(s) for s in val]

    return (val, pos)

# Calls the argument handler for the argument which interprets tokens and
# returns the argument value.
# Handles poly arguments for which it chooses the correct handler.
# Also, the "*" and "+" argtypes are handled by iterating until the token
# list is exhausted. Takes care of tab completion for "*" and "+" as well.
def call_argument_handler_for_arg(cmd, cmdinfo, obj, arg, arglist,
                                  processed_args,
                                  retentry, retlist, require_next, tokens):
    # In case of "*" or "+" we loop until all tokens are
    # consumed. For normal arguments only one loop iteration is needed.

    anslist = [] # for storing all values for "*" and "+"
    arglist_non_internal = []
    for a in arglist:
        if cmd.internal_args is None or a.name not in cmd.internal_args:
            arglist_non_internal.append(a)
    while True:
        if istabcomplete(tokens, 0):
            comp = tokens[0].value.rstrip('\a')
            retlist[arg.num] = anslist
            comps = arg.call_expander(comp, obj, cmd, retlist)

            # At least one "*" or "+" argument given, allow the user to
            # now break the list and enter other arguments again. Add
            # these to the completion list
            if anslist:
                comps += arg_completer(comp, arglist_non_internal)

            raise CliTabComplete(comps)

        try:
            accept_list = False
            if arg.poly: # this is the old style for "poly" values
                for h in range(len(arg.handler)):
                    try:
                        (val, pos) = arg.handler[h].value(tokens)
                        val = (arg.handler[h], val, arg.name[h])
                        break
                    except CliTypeError:
                        continue
                else:
                    raise CliTypeError
            elif ((arg.spec in ["+", "*"]) and not hastype(arg.handler, Arg_list)
                  and isinstance(tokens[0], tokenizer.list_token)):
                # accept a list instead of repeated ("+", "*") args
                (val, pos) = accept_list_as_glob_args(
                    arg, tokens, cmd, processed_args)
                accept_list = True
            else:
                # call the argtypes handler with rest of tokens
                (val, pos) = arg.handler.value(tokens)

            processed_args = processed_args + 1
            tokens = tokens[pos:]
            if len(tokens):
                cmdinfo.set_current_line(tokens[0])

            # if we accepted a list we extend the anslist as expected for +/*
            if accept_list:
                anslist.extend(val)
            else:
                anslist.append(val)

            require_next = 0

            if arg.spec != "+" and arg.spec != "*":
                break

            if anslist and len(tokens) > 1 and get_unquoted(tokens[1]) == '=':
                raise CliTypeError # simulate out of args for + and *

        except CliValueError:
            raise CliOutOfArgs(("argument %d (%s) given to '%s'"
                                " has the wrong type") %
                               (processed_args + 1, tokens[0].string(),
                                cmd.name))

        except CliTypeError:
            if arg.spec == "?" and not require_next:
                # last arg and wrong type
                if not arglist and not isinstance(tokens[0],
                                                  tokenizer.separator_token):
                    raise CliOutOfArgs(("argument %d ('%s') given to '%s'"
                                        " has the wrong type.") % (
                            processed_args + 1,
                            tokens[0].string(),
                            cmd.name))
                else:
                    val = arg.default
                break
            elif arg.spec == "+":
                if not anslist:
                    raise CliOutOfArgs(("out of arguments for"
                                        " command '%s';\n"
                                        "expecting %s list.\n%s") % (
                            cmd.name,
                            get_arg_description(arg.handler),
                            format_synopses(cmd)))
                else:
                    val = anslist
                    break
            elif arg.spec == "*":
                val = anslist
                break
            else:
                if isinstance(tokens[0], tokenizer.separator_token):
                    raise CliOutOfArgs(("argument number %d is missing"
                                        " in '%s';\n%s expected\n%s") % (
                            retentry + 1,
                            cmd.name,
                            get_arg_description(arg.handler),
                            format_synopses(cmd)))
                else:
                    raise CliOutOfArgs(("argument %d (%s) given to '%s'"
                                        " has the wrong type;\n"
                                        "%s expected\n%s") % (
                            processed_args + 1,
                            tokens[0].string(),
                            cmd.name,
                            get_arg_description(arg.handler),
                            format_synopses(cmd)))

    return val, require_next, processed_args, tokens

# Expand 'comp' with any any completions based on the named CLI
# arguments in arglist.
def arg_completer(comp, arglist):
    comps = []
    for a in arglist:
        if a.poly:
            for i in range(len(a.handler)):
                if a.name[i] and a.name[i].startswith(comp):
                    comps.append(a.name[i]
                                 + ("" if a.handler[i] == flag_t
                                    else " ="))
        else:
            if a.name and a.name.startswith(comp):
                comps.append(a.name + ("" if a.handler == flag_t
                                       else " ="))
    return comps

# Tab complete the argument name (or flag). If name not started, complete all
# the arguments.
# If name does not match any arg name (or flags) get the completions for
# the first argument expander instead, i.e., possible values for the arg.
def tab_complete_arg_or_all(cmd, obj, retlist, arg, arglist, tokens):
    comp = tokens[0].value.rstrip('\a')
    arglist_non_internal = []
    for a in arglist:
        if cmd.internal_args is None or a.name not in cmd.internal_args:
            arglist_non_internal.append(a)

    comps = arg_completer(comp, arglist_non_internal)
    if comps:
        raise CliTabComplete(comps)

    comps = arg.call_expander(comp, obj, cmd, retlist)
    if comps:
        raise CliTabComplete(comps)

    # if optional argument, skip this and go on and try complete next arg
    if arg.spec == "?":
        return arglist[1:]

    raise CliTabComplete([])

# Tries to match the tokens from the command line with the arguments defined
# for the command. Also handles tab completions if the last token is a
# tab complete token.
# obj is the object of the command, or None if it is a global (non-namespace)
# command.
def arg_interpreter(cmdinfo, cmd, obj, arglist, tokens, no_execute):
    used_args = []
    processed_args = 0
    require_next = 0

    if cmd.dynamic_args:
        (arg_name, arg_generator) = cmd.dynamic_args
        if arg_name is None: # Always call method
            arglist += arg_generator(None, no_execute)
        else:
            arg = None
            if arg_name.startswith('-'):
                for x in tokens:
                    if x.string() == arg_name:
                        arg = True
                        break
            else:
                idx = -1
                for i, x in enumerate(tokens):
                    if x.string() in (arg_name, f'"{arg_name}"'):
                        idx = i
                        break
                if idx >= 0:  # Syntax "cmd arg_name = arg" has been used
                    if len(tokens) >= idx + 3:
                        eq = tokens[idx + 1].string()
                        if eq in ('=', '"="'):
                            arg = tokens[idx + 2].string()[1:-1]
                else:  # possibly syntax "cmd arg" has been used
                    v = [x.string() for x in tokens
                         if (not x.string().startswith('-')
                         and not x.string() in (arg_name, '=', f'"{arg_name}"', '"="'))]
                    if v:
                        arg = v[0][1:-1]

            arglist += arg_generator(arg, no_execute) if arg else []

    # add argument number to args
    for i,a in enumerate(arglist):
        a.num = i

    # add end token since this function expects it
    tokens.append(tokenizer.separator_token())

    tokenlen = len(tokens)

    # Create a list that is passed to the arg expanders that contains already
    # handled arguments values.
    retlist = [[] if arg.spec in ["+", "*"] else None for arg in arglist ]

    while arglist:
        cmdinfo.set_current_line(tokens[0])

        if isinstance(tokens[0], tokenizer.void_token):
            tokens[0] = tokenizer.nil_token(None, tokens[0].line)

        # Try to find a command argument that matches the first token(s).
        # Named args and flags does not need to be processed in order.

        if len(tokens) > 1 and get_unquoted(tokens[1]) == '=':
            (tokens, retentry, arg) = handle_named_arg(cmdinfo, cmd, obj,
                                                       retlist, used_args,
                                                       arglist, tokens)

        elif isinstance(tokens[0], tokenizer.flag_token):
            (retentry, arg) = handle_flag_arg(cmd, used_args, arglist, tokens)
        else:
            # no named arg or flag, take the first
            arg = arglist[0]

            # completion stuff
            if istabcomplete(tokens, 0):
                arglist = tab_complete_arg_or_all(cmd, obj, retlist,
                                                  arg, arglist, tokens)
                continue # will only continue if arg is optional

            used_args.append(arg)
            arglist = arglist[1:]
            retentry = arg.num

        (val, require_next, processed_args, tokens) = \
              call_argument_handler_for_arg(cmd, cmdinfo, obj, arg, arglist,
                                            processed_args, retentry, retlist,
                                            require_next, tokens)

        retlist[retentry] = val

    if tokens and istabcomplete(tokens, 0):
        raise CliTabComplete([])

    if cmd.check_args and not isinstance(tokens[0], tokenizer.separator_token):
        raise CliParseError("too many arguments for command '%s'\n%s" % (
                cmd.name, format_synopses(cmd)))

    assert isinstance(tokens[-1], tokenizer.separator_token)
    tokens.pop()
    return (retlist, tokenlen - len(tokens))

_translator = b"#()[]{}'\"\\\n"
_translator = bytes.maketrans(_translator, b"#" * len(_translator))

# Check whether a string is a complete command or whether more lines might
# follow. Return the length of the prefix that is a complete command,
# or 0 if no complete command can be determined at this point of time.
# If force_python is true, the string is interpreted as Python instead of CLI.
def complete_command_prefix(cmd, force_python = False):
    parens = ""
    esc = 0
    quoted = 0
    bol_index = 0
    comment = -1
    parens_at_bol = 0
    python = cmd.startswith('@') or force_python

    if len(cmd) > 2:
        decorator = (cmd[0] == '@' and force_python) or cmd[1] == '@'
    else:
        decorator = False
    def is_ws(c):
        return ' ' == c or '\t' == c

    def leftparem(c):
        try:
            dict = {')': '(', ']': '[', '}': '{'}
            return dict[c]
        except KeyError:
            return 0

    # translate "#()[]{}'\"\\\n" into "#"
    q = bytes(cmd, 'ascii', 'replace').translate(_translator).decode("ascii")
    i = 0
    while True:
        ind = q.find("#", i)
        if ind > i:
            esc = 0
        elif ind == -1:
            break
        i = ind
        c = cmd[i]
        if c == '#':
            if not quoted:
                comment = i
                # skip to end of line
                newline_index = cmd.find("\n", i + 1)
                i = newline_index - 1 if newline_index != -1 else len(cmd) - 1
        elif c in "([{":
            if not quoted:
                parens += c
            esc = 0
        elif c in ")]}":
            esc = 0
            if not quoted:
                # pop off from the parentheses stack until a match is found
                while len(parens):
                    pop = parens[-1]
                    parens = parens[0:-1]
                    if pop == leftparem(c):
                        break
        elif c in "\"'":
            if not quoted:
                quoted = c
            elif quoted == c and not esc:
                quoted = 0
            esc = 0
        elif c == '\\':
            esc = quoted and not esc
        elif c == '\n':
            # End of a line: see if more commands may follow
            if bol_index == 0:
                parens_at_bol = len(parens)

            if not python:
                if len(parens) == 0:
                    return i + 1
            elif (not is_ws(cmd[bol_index])) and parens_at_bol == 0:
                # Python line
                if comment < 0:
                    eol = i
                else:
                    eol = comment
                # Line did not begin with whitespace and there
                # were no unbalanced parentheses.
                # Check if it ends with a colon
                j = eol - 1
                while j >= bol_index and is_ws(cmd[j]):
                    j = j - 1
                # j is index to last non-whitespace char
                if not decorator and (j < bol_index or cmd[j] != ':'):
                    # line did not end with a colon
                    if bol_index > 0:
                        # preceding lines form a command
                        return bol_index
                    # line is a one-line command
                    return i + 1
            # line began with whitespace, or there were unbalanced
            # parentheses
            bol_index = i + 1
            comment = -1
            parens_at_bol = len(parens)
        i = i + 1
    return 0

def test_complete_command_prefix():
    def expect(s, expected):
        actual = complete_command_prefix(s)
        if actual != expected:
            raise Exception("complete_command_prefix(%r) = %r, expected %r"
                            % (s, actual, expected))
    expect("abc\n", 4)
    expect("@abc\n", 5)
    expect("@if x:\n", 0)
    expect("@if x:\n y\n", 0)
    expect("@if x:\n y\n@z\n", 10)
    expect("@if x:\n y\nelse:\n", 0)
    expect("@if x:\n y\nelse:\n z\n", 0)
    expect(" xyz\n", 5)                                   # bug 4016
    expect("help foo:\n", 10)                             # bug 4154
    expect("@f([[1:2]])\n", 12)
    expect("@f([1],\n", 0)
    expect("if $x [\n", 0)
    expect("if $x [\n y\n", 0)
    expect("if $x [\n y\n]\n", 13)                        # bug 7159
    expect("if $x [\n y\n];foo\n", 17)                    # bug 7159
    expect("@a = f(r'\\)')\n", 14)                        # bug 9374
    expect("# A comment line with no newline.", 0)        # bug 19779
    expect("@('\"')\n", 7)                                # bug 25054

# simple test that we always can run, other tests in t28
test_complete_command_prefix()


def copy_arg_list(org):
    new = []
    for arg in org:
        new.append(arg.clone())
    return new

def matches_class_or_iface(object, typename):
    """Return true if typename matches an object's class name or if the object
    implements an interface named typename"""
    return (object.classname == typename
            or hasattr(object.iface, typename.replace("-", "_")))

def get_command_names(commands):
    """Convert an iterable of command objects to a list of their names"""
    return list(name for cmd in commands
                for name in cmd.all_methods())

def get_global_commands(include_deprecated = True, include_legacy = True):
    """Get a list of all global (i.e. non-namespace) commands."""
    return list(cmd for cmd in simics_commands()
                if (not cmd.cls and not cmd.iface
                    and (include_deprecated or not cmd.is_deprecated())
                    and (include_legacy or not cmd.is_legacy())))

def get_global_command_names():
    """Get a list of all global (i.e. non-namespace) commands names."""
    return get_command_names(get_global_commands())

def get_class_commands(cls):
    return all_commands.get_class_commands(cls)

def get_iface_commands(iface):
    return all_commands.get_iface_commands(iface)

def get_object_commands(obj):
    return all_commands.get_object_commands(obj)

def get_current_locals():
    return current_locals

class cli_variable_class(
        metaclass=doc('CLI variable namespace',
                      module = 'cli',
                      name = 'simenv',
                      synopsis = 'simenv.<i>variable</i>')):
    """The <class>simenv</class> namespace provides access to the CLI variables
    in the Simics Python interpreter. If the variable <var>$foo</var> was
    defined in CLI, <var>simenv.foo</var> will represent the same variable in
    Python.

    Running <tt>del simenv.foo</tt> will unset that variable. The return value
    from the <fun>dir</fun> function will also include defined variables. The
    <fun>repr</fun> function will return the dictionary of variable and value
    pairs as a string.
    """

    def __delattr__(self, name):
        if not name in self.__iter__():
            raise AttributeError(f"No variable '{name}' is defined")
        get_current_locals().remove_variable(name)

    def __dir__(self):
        return set(super(cli_variable_class, self).__dir__()
                   + list(iter(self)))

    def __getattribute__(self, name):
        if name.startswith('__'):
            return object.__getattribute__(self, name)
        else:
            return getattr(get_current_locals(), name)

    def __setattr__(self, name, value):
        check_variable_name(name, "setattr")
        get_current_locals().set_variable_value(name, value, 0)

    def __getitem__(self, name):
        return self.__getattribute__(name)

    def __setitem__(self, name, value):
        return self.__setattr__(name, value)

    def __delitem__(self, name):
        return self.__delattr__(name)

    def __len__(self):
        return len(get_current_locals().get_all_variables())

    def __iter__(self):
        return iter(get_current_locals().get_all_variables())

    def __repr__(self):
        return repr(get_current_locals().get_all_variables())

simenv = cli_variable_class()

class _test_simenv(unittest.TestCase):
    def test_attr_access(self):
        global simenv
        orig_len = len(simenv)
        simenv.abba = 1
        self.assertEqual(simenv.abba, 1)
        simenv.bebba = 2
        self.assertEqual(len(simenv) - orig_len, 2)
        del simenv.abba
        del simenv.bebba
        self.assertEqual(len(simenv), orig_len)

    def test_indexed_access(self):
        global simenv
        orig_len = len(simenv)
        simenv['cebba'] = 3
        self.assertEqual(simenv['cebba'], 3)
        self.assertEqual(len(simenv) - orig_len, 1)
        del simenv['cebba']
        self.assertEqual(len(simenv), orig_len)

    def test_access_both_methods(self):
        global simenv
        # Test setting with attribute, but retrieve and delete indexed.
        orig_len = len(simenv)
        simenv.coco = 1
        self.assertEqual(simenv['coco'], 1)
        self.assertEqual(len(simenv) - orig_len, 1)
        del simenv['coco']
        self.assertEqual(len(simenv), orig_len)

        # Test setting indexed, but retrieve and delete with attribute.
        simenv['banan'] = 2
        self.assertEqual(simenv.banan, 2)
        self.assertEqual(len(simenv) - orig_len, 1)
        del simenv.banan
        self.assertEqual(len(simenv), orig_len)


def run(cmdinfo, text):
    result = evaluate_one(cmdinfo, tokenizer.tokenize(text))
    if cmdinfo.get_cmdline().get_interactive() or result.verbose():
        result.print_token()
    return result

def run_and_report(cmdinfo, cmd_func):
    msg = ''
    is_command_ok = False
    is_error = True
    value = None

    try:
        # one of run() and evaluate_one()
        token = cmd_func()
        value = token.get_py_value(use_return_message = False)
    except CliSyntaxError as ex:
        msg = "Syntax error: %s" % ex
    except CliParseError as ex:
        msg = "Parse error: %s" % ex
    except (CliArgNameError, CliOutOfArgs) as ex:
        msg = "Argument error: %s" % ex
    except (
            CliAmbiguousCommand, CliError,
            simics.SimExc_Index, simics.SimExc_General, simics.CriticalErrors,
    ) as ex:
        msg = "%s" % ex
    except CliBreakError:
        msg = "break-loop used outside of loop"
    except CliContinueError:
        msg = "continue-loop used outside of loop"
    except CliQuietError as ex:
        msg = "%s" % ex.value() if ex.value() is not None else None
        is_error = False
    except Exception:
        (extype, val, tb) = sys.exc_info()
        msg = get_error_tb(extype, val, tb, True)
    else:
        is_command_ok = True
        is_error = False

    if msg and not stdout_output_mode.markup:
        msg = filter_out_simics_markup(msg)

    return (is_command_ok, is_error, msg, value)

# Keep track of the local variable scope that was currently active when a
# script-branch is being scheduled to run. This scope has to be restored again
# both when the script-branch suspends and when it ends.
pre_branch_context_tuple = (None, None)

def script_branch_func(cmdinfo, tokens):
    # This function is executed in a script branch thread.

    global current_locals, current_cmdinfo, pre_branch_context_tuple

    pre_branch_context_tuple = (current_locals, current_cmdinfo)

    (is_command_ok, is_error, msg, _) = run_and_report(
        cmdinfo, lambda: evaluate_one(cmdinfo, tokens, local = True))

    (current_locals, current_cmdinfo) = pre_branch_context_tuple

    if not is_command_ok:
        if not is_error:
            if msg:
                print(msg)
        else:
            cmd = cmdinfo.get_command()
            if cmd:
                err_msg = (f"[{cmdinfo.get_file()}:{cmdinfo.get_line()}]"
                         f" error in '{cmd}' command: {msg}")
            else:
                err_msg = (f"[{cmdinfo.get_file()}:{cmdinfo.get_line()}]"
                         f" error parsing command: {msg}")
            print(f"*** {err_msg}") # use same *** error markup as pr_err
            simics.CORE_python_flush()
            simics.CORE_error_interrupt("Error in script-branch")

def start_script_branch(cmdinfo, tokens, desc):
    filename = current_cmdinfo.get_full_file()
    line = current_cmdinfo.get_line()
    return create_branch(lambda: script_branch_func(cmdinfo, tokens),
                         desc, None, filename, line, True)

class output_modes:
    class __output_mode:
        def __init__(self, name, format, markup):
            self.__name   = name
            self.__format = bool(format)
            self.__markup = bool(markup)
        def __str__(self):
            return 'output_modes.%s' % self.__name
        def __repr__(self):
            return self.__str__()
        def format(self):
            """True if output should be formatted for human reading
            (e.g., multi-column output)."""
            return self.__format
        format = property(format, doc = format.__doc__)

        def markup(self):
            """True if output should include Simics-internal markup."""
            return self.__markup
        markup = property(markup, doc = markup.__doc__)

    regular          = __output_mode('regular', True, True)
    formatted_text   = __output_mode('formatted_text', True, False)
    unformatted_text = __output_mode('unformatted_text', False, False)

    @classmethod
    def is_instance(cls, x):
        """Returns True if 'x' is a valid output mode."""
        return isinstance(x, cls.__output_mode)

# top of this stack is (sys.stdout, stdout_output_mode)
stdout_stack = []
stdout_output_mode = output_modes.formatted_text

def enable_cli_markup():
    'Call this to enable Simics-internal markup of output.'
    push_stdout(pop_stdout(), output_modes.regular)

class push_stdout:
    """Pushes "f" on top of the stdout stack. Must be balanced with a
    call to pop_stdout(), or called with a "with" statement. Sets
    "stdout_output_mode" according to "output_mode"; defaults to
    regular, formatted output with markup."""
    def __init__(self, f, output_mode = output_modes.regular):

        assert output_modes.is_instance(output_mode)

        global stdout_output_mode
        stdout_stack.append((sys.stdout, stdout_output_mode))
        sys.stdout = f
        stdout_output_mode = output_mode

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pop_stdout()

def pop_stdout():
    """Pops and returns the topmost file on the stdout stack,
    previously pushed with push_stdout()."""
    global stdout_output_mode
    sys.stdout.flush()
    previous = sys.stdout
    sys.stdout, stdout_output_mode = stdout_stack.pop()
    return previous

def check_run_command_oec():
    if simics.VT_outside_execution_context_violation():
        raise CliError(
            'Simics CLI commands should not be called when simulation is'
            ' running. This means that calls to run_command (or other ways'
            ' to call CLI commands) are not allowed when simulation is running.'
            ' Instead of running CLI commands one can consider accessing'
            ' the objects and attributes directly, or, alternatively,'
            ' delay the execution of CLI commands with'
            ' the SIM_run_alone Simics API function')

@doc('run a CLI command',
     module = 'cli')
def run_command(text):
    """Runs a CLI command, or a CLI expression, as if it has been entered at the
    prompt. Errors are reported using CliError exception, and any return value
    from the command is returned by this function to Python.

    Use <fun>quiet_run_command</fun> if you need to suppress or catch
    messages printed."""
    from targets import target_commands
    if target_commands.config:
        target_commands.config.add_cmd(text)

    cmdinfo = cmdinfo_class()
    cmdinfo.get_cmdline().set_last_command(text)
    try:
        token = evaluate_one(cmdinfo, tokenizer.tokenize(text))
    except CliError:
        raise
    except CliBreakError:
        raise CliError("break-loop used outside of loop")
    except CliContinueError:
        raise CliError("continue-loop used outside of loop")
    except CliException as ex:
        raise CliError("%s" % ex)
    return token.get_py_value(use_return_message = True)

def run_command_retval(text):
    # same as run_command but do not print returned messages
    cmdinfo = cmdinfo_class()
    cmdinfo.get_cmdline().set_last_command(text)
    try:
        token = evaluate_one(cmdinfo, tokenizer.tokenize(text))
    except CliBreakError:
        raise CliError("break-loop used outside of loop")
    except CliContinueError:
        raise CliError("continue-loop used outside of loop")
    return token.get_py_value(use_return_message = False)

# similar to quiet_run_command but run a function instead of a command
def quiet_run_function(fun, output_mode = output_modes.formatted_text):
    with push_stdout(StringIO(), output_mode):
        result = fun()
        output = sys.stdout.getvalue()
    return (result, output)

@doc('run a CLI command and return output',
     module = 'cli')
def quiet_run_command(text, output_mode = output_modes.formatted_text):
    """Runs a CLI command, or a CLI expression, as if it has been
    entered at the prompt. Errors are reported using CliError
    exception.

    The <fun>quiet_run_command</fun> function is similar to
    <fun>run_command</fun> but returns a tuple with the command
    return value as first entry, and the command output text as the second.
    Please note that sometimes unrelated output might be included, e.g.,
    for commands that advance the virtual time or in some other way may allow
    other commands to run in parallel with them.

    Set 'output_mode' to one of the output modes:
    <dl>
      <dt><b>output_modes.regular</b></dt>
        <dd>formatted text with Simics-internal markup</dd>
      <dt><b>output_modes.formatted_text</b></dt>
        <dd>formatted text without markup</dd>
      <dt><b>output_modes.unformatted_text</b></dt>
        <dd>unformatted text without markup</dd>
    </dl>"""
    return quiet_run_function(lambda: run_command(text), output_mode)

def push_file_scope(local, assignments):
    global current_locals
    if assignments is not None:
        # Introduce a clean environment only consisting of the given
        # assignments.
        current_locals = simenv_class(None, current_locals)
        for v in assignments:
            current_locals.set_variable_value(v, assignments[v], True)
    else:
        if local:
            new_locals = current_locals.duplicate_environment()
        else:
            new_locals = current_locals
        current_locals = simenv_class(new_locals, current_locals)
    return current_locals

def pop_file_scope(locals):
    global current_locals
    # restore the previous local scope
    current_locals = locals.__real_parent__

def get_script_stack(full_file=False):
    cmdinfo = current_cmdinfo
    stack = []
    while cmdinfo:
        if full_file:
            f = cmdinfo.get_full_file() or cmdinfo.get_file()
        else:
            f = cmdinfo.get_file()
        l = cmdinfo.get_line()
        if (not stack or stack[-1] != [f, l]) and f != "<cmdline>":
            stack.append([f, l])
        cmdinfo = cmdinfo.parent
    return stack

def get_line_from_file(file_name, line_num):
    """Returns the line_num (starts on zero) from 'file_name' if possible, else
    None is returned."""
    assert line_num >= 0
    if not os.path.exists(file_name):
        return None
    if not os.path.isfile(file_name):
        return None
    with open(file_name, 'r') as f:
        if not f.readable:
            return None
        lines = f.readlines()
        if line_num >= len(lines):
            return None
        return lines[line_num].rstrip('\n')

def print_script_stack(stack):
    """Print the script stack in a format similar to how the Python call stack
    is printed."""
    print("Simics script traceback (most recent call last):")
    for (file_name, line) in stack:
        print(f'  File "{file_name}", line {line}')
        line = get_line_from_file(file_name, line - 1)
        if line:
            print(f'    {line}')

def set_error_variable(name, val):
    if name in current_locals.get_all_variables():
        olderr = getattr(current_locals, name)
        setattr(current_locals, name, val)
        return (1, olderr)
    else:
        current_locals.set_variable_value(name, val, 1)
        return (False, )

def restore_error_variable(name, info):
    if info[0]:
        setattr(current_locals, name, info[1])
    else:
        current_locals.remove_variable(name)

cli_errors = {'command' : [''],
              'message' : [''],
              'file'    : [''],
              'line'    : ['']}


def set_cli_error(msg, line, file, cmd):
    cli_errors['command'].append(cmd)
    cli_errors['message'].append(msg)
    cli_errors['file'].append(file)
    cli_errors['line'].append(line)

def restore_cli_error():
    for kind in cli_errors:
        cli_errors[kind].pop()

def get_cli_error(kind):
    return cli_errors[kind][-1]

def format_attribute(val, show_unicode = False):
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    elif isinstance(val, int):
        return number_utils.number_str(val)
    elif isinstance(val, string_types):
        return tokenizer.repr_cli_string(val, show_unicode = show_unicode)
    elif isinstance(val, float):
        return repr(val)
    elif isinstance(val, conf_object_t):
        return val.name
    elif isinstance(val, tuple):
        return repr(val)
    elif isinstance(val, type(None)):
        return "NIL"
    # TODO: get reference to configuration attribute type and use different
    # types for list and dict attributes in the Python wrapper
    elif isinstance(val, (conf_attribute_t, list, dict)):
        sep = ''
        try:
            _ = list(val.keys())
            is_dict = True
        except AttributeError:
            is_dict = False
        if is_dict:
            ret ='{'
            for k,v in list(val.items()):
                ret += '%s"%s": %s' % (sep, k, format_attribute(
                    v, show_unicode = show_unicode))
                sep = ', '
            ret += '}'
        else:
            ret ='['
            for v in val:
                ret += "%s%s" % (sep, format_attribute(
                    v, show_unicode = show_unicode))
                sep = ', '
            ret += ']'
        return ret
    else:
        raise CliError("Unknown attribute type: %s" % type(val))

def value_to_token(val, seen_ids = None):
    if isinstance(val, command_return):
        cliret = val
        val = cliret.get_value()
    else:
        cliret = None

    if isinstance(val, bool):
        ret = tokenizer.bool_token(val)
    elif isinstance(val, int):
        ret = tokenizer.int_token(val)
    elif isinstance(val, string_types):
        ret = tokenizer.quoted_token(val)
    elif isinstance(val, bytes):
        ret = tokenizer.quoted_token(val)
    elif isinstance(val, float):
        ret = tokenizer.float_token(val)
    elif isinstance(val, conf_object_t):
        if val.classname == "index-map":
            # convert namespace dictionary into sparse list
            d = dict((int(o.name.rpartition("[")[2][:-1]), o)
                     for o in simics.SIM_shallow_object_iterator(val))
            if not d:
                ret = tokenizer.list_token([])
            else:
                ret = tokenizer.list_token([value_to_token(d.get(i, None))
                                  for i in range(max(d) + 1)])
        else:
            ret = tokenizer.quoted_token(val.name)
    elif seen_ids is not None and id(val) in seen_ids:
        raise CliError("Cannot convert circular Python %s to CLI value" % (
                type(val).__name__,))
    elif isinstance(val, dict):
        raise CliError("Cannot convert Python dict to CLI value")
    elif isinstance(val, list):
        if seen_ids is None:
            seen_ids = set()
        seen_ids.add(id(val))
        ret = []
        for l in val:
            ret.append(value_to_token(l, seen_ids))
        ret = tokenizer.list_token(ret)
        seen_ids.remove(id(val))
    elif isinstance(val, conf_attribute_t):
        # convert to native Python types
        ret = value_to_token(val.copy())
    elif isinstance(val, type(None)):
        if not cliret:
            # make sure None is quiet as return value from command
            cliret = command_quiet_return(None)
        ret = tokenizer.nil_token(None)
    else:
        raise CliError("Cannot convert Python %s to CLI value" % (
                type(val).__name__,))
    ret.cliret = cliret
    return ret

def old_is_component(s, c):
    try:
        obj = get_object(s)
        return is_component(obj) and obj.iface.component.has_slot(c)
    except (simics.SimExc_General, KeyError):
        return False

def old_is_drive(s, c):
    return len(s) == 1

def object_exists(name):
    try:
        get_object(name)
        return True
    except simics.SimExc_General:
        return False

def is_component(obj):
    if isinstance(obj, conf_object_t):
        return hasattr(obj.iface, 'component')
    elif isinstance(obj, simics.pre_conf_object):
        try:
            simics.SIM_get_class_interface(obj.classname, 'component')
            return True
        except (LookupError, simics.SimExc_Lookup):
            # LookupError if unknown class, SimExc_Lookup if no interface
            return False
    return False

def is_top_component(obj):
    if isinstance(obj, conf_object_t):
        return hasattr(obj.iface, 'component') and obj.top_level
    elif isinstance(obj, simics.pre_conf_object):
        try:
            simics.SIM_get_class_interface(obj.classname, 'component')
            raise CliError("No way to tell if %r is top-component" % obj)
        except simics.SimExc_Lookup:
            return False
    return False

def is_connector(obj):
    if isinstance(obj, conf_object_t):
        return hasattr(obj.iface, 'connector')
    elif isinstance(obj, simics.pre_conf_object):
        try:
            simics.SIM_get_class_interface(obj.classname, 'connector')
            return True
        except simics.SimExc_Lookup:
            return False
    return False

def strip_tab(n):
    if len(n) and n[-1] == "\a":
        return n[:-1]
    else:
        return n

# return a (cmd, obj) tuple corresponding to the specified namespace command.
# Returns (None, None) if no command was found and raises CliParseError
# if an invalid namespace part is found.
def _get_namespace_command(ns_cmd):
    (ns, _, cmdname) = ns_cmd.rpartition(".")
    if not ns:
        return (None, None)
    try:
        obj = get_object(ns)
    except simics.SimExc_General:
        raise CliParseError('No name space "%s"' % ns)

    for cmd in all_commands.get_object_commands(obj):
        for method in cmd.all_methods():
            if method == cmdname:
                return (cmd, obj)
    return (None, None)


# return a list with relative object names, e.g.
# ["apic[0][0]", "apic[0][1]", "pic"]
def _sub_obj_names(obj):
    if obj and obj.classname == "index-map":
        return []
    objs = []
    for o in simics.CORE_shallow_object_iterator(obj, True):
        name = o.name
        if obj is None:
            objs.append(name)
        else:
            i = name.rfind(".")
            assert i >= 0
            objs.append(name[i + 1:])
    return objs

# return completions if name matches an object exactly
def _obj_match_completions(name):
    try:
        obj = get_object(name) if name else _current_namespace_obj()
    except simics.SimExc_General:
        return []
    if obj and obj.classname == "index-map":
        return []
    if name:
        ret = ["{}->".format(name), "{}.".format(name)]
        ret += ["{}.{}.".format(name, c) for c in _sub_obj_names(obj)]
    else:
        ret = ["{}.".format(c) for c in _sub_obj_names(obj)]
    return ret

# return completions for the specified namespace and base
def _obj_completions(ns, base):
    try:
        obj = get_object(ns) if ns else _current_namespace_obj()
    except simics.SimExc_General:
        return []
    if ns:
        ret = ["{}.{}.".format(ns, c) for c in _sub_obj_names(obj)
               if c.startswith(base)]
        ret.extend("{}.{}".format(ns, m)
                   for cmd in all_commands.get_object_commands(obj)
                   if not (cmd.is_deprecated() or cmd.is_legacy())
                   for m in cmd.all_methods()
                   if m.startswith(base))
    else:
        ret = ["{}.".format(c) for c in _sub_obj_names(obj)
               if c.startswith(base)]
        ret.extend(user_defined_aliases().completions(base, False))
        ret.extend(obj_aliases().completions(base, False))
    return ret

# return tab completions for objects, global commands or
# namespace commands starting with base
def _obj_or_cmd_completions(base):
    # add completions for exact object matches
    completions = _obj_match_completions(base)

    pos = base.rfind(".")
    if pos < 0:
        # add non-deprecated non-legacy global command completions
        for cmd in simics_commands():
            if not (cmd.cls or cmd.iface or cmd.is_deprecated()
                    or cmd.is_legacy()):
                completions += get_completions(base, cmd.all_methods())

        # add object completions
        completions += _obj_completions("", base)

        # add object alias completions
        completions += obj_aliases().completions(base, False)
    else:
        (ns, name) = (base[:pos], base[pos + 1:])
        # add object completions
        completions += _obj_completions(ns, name)
    return completions


def replace_alias(s, a, alias):
    l = len(a)
    if s.startswith(a) and (s == a
                            or s[l:].startswith(".")
                            or s[l:].startswith("->")):
        return alias + s[l:]
    else:
        return s

def handle_hi_pri_commands(sub, cmdinfo):
    if (len(sub) >= 5
        and isinstance(sub[0], tokenizer.unquoted_token)
        and sub[1].value == "["
        and sub[0].value.find(".") > 0):
        # let "." have higher pri then [ in cmp.obj[N] by failing here
        return None, 0

    hi_pri_pos = 0
    hi_pri = -1000000
    found = None

    for i in range(len(sub)):
        if isinstance(sub[i], tokenizer.unquoted_token):
            cmdinfo.set_current_line(sub[i])
            cmd = all_commands.get(sub[i].value)
        else:
            cmd = None
        if cmd and ((i == 0 and not cmd.infix)
                    or cmd.infix
                    or cmd.name in ["%","~", "python", "$", "@", "defined"]):
            cmd_pri = cmd.pri
            # special case for -> and [ when used in assignment
            if cmd.name == '=' and found and found.name in ('->', '['):
                hi_pri = all_commands.get("=").pri
            if cmd_pri > hi_pri:
                # higher priority operator
                hi_pri_pos = i
                hi_pri = cmd_pri
                found = cmd
    return found, hi_pri_pos

def get_unquoted(token):
    if isinstance(token, tokenizer.unquoted_token):
        return token.value
    return None

def find_block_token(tokens, statement):
    for i in range(len(tokens)):
        if isinstance(tokens[i], tokenizer.block_token):
            return i
    raise CliParseError("missing { in %s statement" % statement)

def nested_array_to_list(tokens):
    pos = 0
    indexes = []
    while pos + 1 < len(tokens):
        if not get_unquoted(tokens[pos]) == '[':
            break
        elif not isinstance(tokens[pos + 1], tokenizer.int_token):
            break
        indexes.append(tokens[pos + 1].value)
        pos += 2
    if pos:
        tokens[1:pos] = [tokenizer.list_token([tokenizer.int_token(x) for x in indexes])]
    return tokens

def joiner(sep, last_sep, lst):
    if isinstance(lst, string_types): return lst
    if len(lst) > 1:
        return sep.join(lst[:-1]) + last_sep + lst[-1]
    return sep.join(lst)


def token_includes_unicode_punctuation(token):
    # Most common alternative punctuation characters that causes support issues
    unicode_punctuation_chars = (0x2013,  # U+2013, EN DASH
                                 0x2014,  # U+2014, EM DASH
                                 0x2018,  # U+2018, LEFT SINGLE QUOTATION MARK
                                 0x2019,  # U+2019, RIGHT SINGLE QUOTATION MARK
                                 0x201C,  # U+201C, LEFT DOUBLE QUOTATION MARK
                                 0x201D,  # U+201D, RIGHT DOUBLE QUOTATION MARK
                                 )
    for ch in str(token):
        if ord(ch) in unicode_punctuation_chars:
            return True
    return False

def expand_non_ascii_token(token):
    def ok_ch(ch):
        return ch.isascii() or not token_includes_unicode_punctuation(ch)

    return "".join([ch if ok_ch(ch) else "{%s}" % unicodedata.name(ch)
                    for ch in str(token)])

def check_tokens_for_unicode(cmdinfo, tokens):
    for i, token in enumerate(tokens):

        # Only examine "first-level" tokens, if there are block or expression
        # tokens in this list they will be expanded in the evaluation and end up
        # here again as "first-level" tokens.
        # flag_tokens are examined because they are a special case of unquoted
        # tokens that start with a dash character.
        if not isinstance(token, tokenizer.unquoted_token):
            continue
        if token.value.startswith("@"): # skip python inline
            break
        if isinstance(token, tokenizer.unicode_token):
            if token_includes_unicode_punctuation(token):
                kind = "command" if i == 0 else "argument"
                place = f"[{cmdinfo.get_file()}:{cmdinfo.get_line()}] " if cmdinfo.get_dir() else ""
                err_line = f"{place}{kind} {expand_non_ascii_token(token)} contains"
                err_line +=" commonly confusing unicode character(s) without quoting."
                print(f"NOTE: {err_line}")

def get_command_location_fmt(cmdinfo):
    pos = "%s:%d" % (cmdinfo.get_file(), cmdinfo.get_line())
    return "[{pos}] ".format(pos=pos)

def warn_deprecation(cmdinfo, found, is_interactive):
    loc = "" if is_interactive else get_command_location_fmt(cmdinfo)
    if found.deprecated is True:
        replacement = "No replacement available"
    else:
        replacement = joiner(", ", " or ", found.deprecated)
        replacement = f"Use {replacement} instead"
    msg = f"{loc}The '{found.name}' command is deprecated"
    DEPRECATED(found.deprecated_version or simics.SIM_VERSION_4_8,
               msg, replacement)

def warn_legacy(cmdinfo, found, is_interactive):
    loc = "" if is_interactive else get_command_location_fmt(cmdinfo)
    if found.legacy is True:
        replacement = "No replacement available"
    else:
        replacement = joiner(", ", " or ", found.legacy)
        replacement = f"Use {replacement} instead"
    msg = f"{loc}The '{found.name}' command is legacy"
    LEGACY(found.legacy_version, msg, replacement)

# should only be called from evaluate_one()
def real_evaluate_one(cmdinfo, tokens, no_execute = False):
    while tokens:
        end = -1
        discard_result = False

        cmdinfo.set_current_line(tokens[0])

       # The following section should be rewritten, see SIMICS-8802

        # if is handled here or by the if command
        if get_unquoted(tokens[0]) == 'script-branch':
            if len(tokens) > 1 and isinstance(tokens[1], tokenizer.quoted_token):
                # optional script-branch description
                sb_desc = tokens[1].value
                tokens[0:2] = tokens[0:1]
            else:
                sb_desc = None
            if len(tokens) < 2 or not isinstance(tokens[1], tokenizer.block_token):
                raise CliParseError("missing { in script-branch statement")
            tokens[0:2] = [tokenizer.int_token(start_script_branch(cmdinfo,
                                                         tokens[1].tokens,
                                                         sb_desc))]

        elif get_unquoted(tokens[0]) == 'try':
            if len(tokens) < 2 or not isinstance(tokens[1], tokenizer.block_token):
                raise CliParseError("missing { in try statement")

            if len(tokens) < 3 or not get_unquoted(tokens[2]) == 'except':
                raise CliSyntaxError("missing except in try statement")

            if len(tokens) < 4 or not isinstance(tokens[3], tokenizer.block_token):
                raise CliSyntaxError("missing { in except statement")

            try:
                ret = evaluate_one(cmdinfo, tokens[1].tokens, no_execute, True)
            except (CliBreakError, CliContinueError) as ex:
                raise ex
            except CliException as ex:
                if isinstance(ex, CliQuietError) and ex.is_script_branch_interrupt:
                    # try/except should not catch interrupted script branches
                    raise
                cmd = cmdinfo.get_command()
                if not cmd:
                    cmd = ''
                sfile = cmdinfo.get_file()
                if not sfile:
                    sfile = ''
                line = cmdinfo.get_line()

                set_cli_error(str(ex), line, sfile, cmd)
                ret = evaluate_one(cmdinfo, tokens[3].tokens, no_execute, True)
                restore_cli_error()
            tokens[0:4] = [ret]

        elif get_unquoted(tokens[0]) == 'foreach':
            if (len(tokens) < 3
                or not get_unquoted(tokens[1]) == '$'
                or not isinstance(tokens[2], tokenizer.string_token)):
                raise CliSyntaxError("Missing iteration variable in foreach "
                                     "statement")
            iterator = tokens[2].value

            if len(tokens) < 4 or not get_unquoted(tokens[3]) == 'in':
                raise CliSyntaxError("Missing 'in' in foreach statement")

            if len(tokens) < 6: # at least two items long
                raise CliSyntaxError("Missing list or list variable in "
                                     "foreach statement")

            if isinstance(tokens[4], (tokenizer.list_token, tokenizer.exp_token)):
                list_res = evaluate_one(cmdinfo, tokens[4:5], no_execute)
                if not isinstance(list_res, tokenizer.list_token):
                    raise CliSyntaxError("List missing in foreach statement")
                iter_list = list_res.value
                exppos = 5
            elif (get_unquoted(tokens[4]) == '$'
                  and isinstance(tokens[5], tokenizer.string_token)):
                val = getattr(get_current_locals(), tokens[5].value)
                if isinstance(val, list):
                    iter_list = val
                else:
                    raise CliSyntaxError("$%s in foreach statement is not a "
                                         "list." % tokens[5].value)
                exppos = 6
            else:
                raise CliSyntaxError("Missing list or list variable in "
                                     "foreach statement")

            if not isinstance(tokens[exppos], tokenizer.block_token):
                raise CliSyntaxError("missing { in foreach statement")

            restore_iterator = None
            ret = None
            for iter_value in iter_list:
                old = set_error_variable(iterator, iter_value)
                if not restore_iterator:
                    restore_iterator = old
                # print return value from previous iteration
                if ret is not None and ret.verbose():
                    ret.print_token()
                try:
                    ret = evaluate_one(cmdinfo, tokens[exppos].tokens,
                                       no_execute, True)
                except CliBreakError:
                    break
                except CliContinueError:
                    continue

            if restore_iterator:
                restore_error_variable(iterator, restore_iterator)
            # For now only use the last return value
            if ret is not None:
                tokens[0:exppos + 1] = [ret]
            else:
                tokens[0:exppos + 1] = [tokenizer.void_token()]

        elif get_unquoted(tokens[0]) in ('if', 'while'):
            if len(tokens) < 2:
                raise CliSyntaxError("conditional missing in %s missing"
                                     % tokens[0].value)
            cmpend = find_block_token(tokens, tokens[1].value)

            if cmpend == 1:
                raise CliSyntaxError("conditional missing in %s missing"
                                     % tokens[0].value)

            expend = cmpend + 1
            elsend = expend
            cmptok = tokens[1:cmpend]
            exptok = tokens[cmpend:cmpend + 1]
            elstok = None

            check_if = tokens[0].value == 'if'
            ifexpend = expend

            while (check_if
                   and len(tokens) >= (ifexpend + 1) # minimal is else and ()
                   and get_unquoted(tokens[ifexpend]) == 'else'):
                if len(tokens) == (ifexpend + 1):
                    raise CliSyntaxError("empty else statement")
                if get_unquoted(tokens[ifexpend + 1]) == 'if':
                    blk_off = 2
                else:
                    check_if = False
                    blk_off = 1
                elsend = (elsend + blk_off
                          + find_block_token(tokens[ifexpend + blk_off:],
                                             'else')) + 1
                elstok = tokens[cmpend + 2:elsend]
                ifexpend = elsend

            ret = None
            if tokens[0].value == 'if':
                # if statement
                res = evaluate_one(cmdinfo, cmptok, no_execute)
                if res.value:
                    ret = evaluate_one(cmdinfo, exptok, no_execute, True)
                elif elstok:
                    ret = evaluate_one(cmdinfo, elstok, no_execute, True)
            else:
                # while statement
                while evaluate_one(cmdinfo, cmptok, no_execute).value:
                    # print return value from previous iteration
                    if ret is not None and ret.verbose():
                        ret.print_token()
                    try:
                        ret = evaluate_one(cmdinfo, exptok, no_execute, True)
                    except CliBreakError:
                        break
                    except CliContinueError:
                        continue

            if ret is not None:
                tokens[0:elsend] = [ret]
            else:
                tokens[0:elsend] = []

        # end of if/while/etc handling (see also see SIMICS-8802)

        cmdinfo.set_async_command(True)
        for i in range(0, len(tokens)):
            if isinstance(tokens[i], tokenizer.separator_token):
                # do not run the command asynchronous if followed by ;
                cmdinfo.set_async_command(False)
                end = i
                discard_result = True
                break

        if end < 0:
            end = len(tokens)
        sub = tokens[0:end]
        tokens = tokens[end + 1:]

        if not sub:
            continue

        # Check for non-ASCII characters
        # As far as I understand at this point sub holds the tokens
        # for one "operation".
        # help & friend operations are excluded from the check.
        if not no_execute:
            if not get_unquoted(sub[0]) in ("help", "h", "man", "apropos", "a"):
                check_tokens_for_unicode(cmdinfo, sub)

        # remove all expressions
        i = 0
        while i < len(sub):
            if isinstance(sub[i], (tokenizer.exp_token, tokenizer.block_token)):
                res = evaluate_one(cmdinfo, sub[i].tokens, no_execute, True)
                assert isinstance(res, tokenizer.cli_token)
                del sub[i]
                if (len(sub) > i
                    and isinstance(sub[i], tokenizer.unquoted_token)
                    and sub[i].value.startswith('.')
                    and not (i > 0 and get_unquoted(sub[i - 1]) == '[')):
                    retval = res.value
                    sub[i].value = ((str(retval) if retval else '')
                                    + sub[i].value)
                    i -= 1
                else:
                    sub.insert(i, res)
            elif isinstance(sub[i], tokenizer.list_token):
                for j in range(len(sub[i].tokens)):
                    sub[i].tokens[j] = evaluate_one(cmdinfo,
                                                    [sub[i].tokens[j]],
                                                    no_execute)
            i += 1
            #continue

        if isinstance(sub[0], tokenizer.unquoted_token):
            new_sub0 = None
            for a in user_defined_aliases():
                if sub[0].value.startswith(a):
                    new_sub0 = replace_alias(sub[0].value, a, user_defined_aliases()[a])
                    break

            if new_sub0 is None:
                base = sub[0].value.rstrip('\a')
                matching_alias_names = [x for x in user_defined_aliases() if (
                    base.startswith(x))]
                if len(matching_alias_names) == 1:
                    alias_name = matching_alias_names[0]
                    alias_value = user_defined_aliases()[alias_name]
                    obj = simics.VT_get_object_by_name(alias_value)
                    if obj:
                        if base == alias_name:
                            sub[0].value = f'{alias_value}\a'
                        else:
                            for sep in ['.', '->']:
                                split = base.split(sep)
                                if split[0] == alias_name:
                                    new_sub0 = sep.join([alias_value] + split[1:]) + '\a'
                                    break
            if new_sub0:
                sub[0].value = new_sub0



        # help and apropos are handled special here, this allows
        # help x->y for example
        if get_unquoted(sub[0]) in ("help", "h", "man", "apropos", "a"):
            e = 1

            is_help = True
            if len(sub) > 1 and isinstance(sub[1], tokenizer.string_token):
                next_cmd = all_commands.get(sub[1].value)
                if (next_cmd and next_cmd.infix
                    and len(sub) > 2
                    and isinstance(sub[2], tokenizer.string_token)
                    and not next_cmd.name ==  "<"):
                    is_help = False

            # merge everything except options
            def isopt(optstr):
                return (len(optstr) >= 2
                        and optstr[0] == '-'
                        and optstr[1] in letters)

            arg = ''
            while is_help and e < len(sub):

                if (isinstance(sub[e], tokenizer.string_token)
                    and e + 1 < len(sub)
                    and get_unquoted(sub[e + 1]) == "="):
                    # skip 'arg =' for the command itself
                    e += 2
                    continue

                if istabcomplete(sub, e) and len(sub[e].value) == 1:
                    # do not merge single tab-complete with the string
                    break

                if isopt(str(sub[e].value)):
                    if arg:
                        sub[e:e] = [tokenizer.quoted_token(arg)]
                        arg = ''
                    e += 1
                else:
                    if get_unquoted(sub[e]) == '[':
                        # Re-insert right bracket that was previously
                        # discarded -- we need it now since we're
                        # turning the expression back into a string.
                        # We know it should be precisely two steps
                        # after the left bracket, because the
                        # expression in the brackets has previously
                        # been evaluated down to one token. (The
                        # exception is if the user has typed 'help
                        # "["', in which case the closing parenthesis
                        # will follow.)
                        if e + 1 < len(sub):
                            sub.insert(e + 2, tokenizer.unquoted_token(']'))

                    if arg:
                        if (arg[-1] in letters
                            and str(sub[e].value)[0] in letters):
                            arg += ' '
                    arg += str(sub[e].value)
                    del sub[e]
            if arg:
                sub[e:e] = [tokenizer.quoted_token(arg)]
        while True:
            object = None
            # now, find command with highest priority, this only
            # applies to non-namespace infix commands
            if len(sub):
                cmdinfo.set_current_line(sub[0])

            (found, i) = handle_hi_pri_commands(sub, cmdinfo)

            # only allow assignment in position 1, i.e. ( foo = 1 ... )
            # required not to mess up with named args
            if found and found.name == "=" and i != 1:
                found = None

            # tokenizer handles "$<var> = " as a special case, that we have
            # to workaround if used as attribute name in  "<obj>->$<var> ="
            if (found and found.name == '->' and len(sub) > 2
                and isinstance(sub[2], tokenizer.string_token)
                and sub[2].value.startswith('$')):
                sub[2:3] = [tokenizer.exp_token([tokenizer.unquoted_token('$', sub[2].line),
                                       tokenizer.unquoted_token(sub[2].value[1:],
                                                      sub[2].line)])]
                break

            # handle ':' (concatenates its argument as unquoted strings)
            if found and found.name == ':':
                (first, last) = (max(i - 1, 0), min(i + 1, len(sub) - 1))
                if ((first == i or isinstance(sub[first], tokenizer.string_token))
                    and (last == i or isinstance(sub[last], tokenizer.string_token))):
                    s = "".join(x.value for x in sub[first:last + 1])
                    (cmpname, _, subname) = s.partition(":")
                    if not old_is_drive(cmpname, subname):
                        repl = [tokenizer.unquoted_token(s)]
                        if sub[first:last + 1] != repl: # ensure progress
                            sub[first:last + 1] = repl
                            continue

            if found and found.name == '->':
                # handle e.g. object->name.command by splitting name.command
                if (len(sub) > i + 1 and isinstance(sub[i + 1], tokenizer.string_token)
                    and '.' in sub[i + 1].value):
                    split = sub[i + 1].value.split('.', 1)
                    sub[i + 1:i + 2] = [tokenizer.unquoted_token(split[0],
                                                       sub[i + 1].line),
                                        tokenizer.unquoted_token('.' + split[1],
                                                       sub[i + 1].line)]

                assign_flags = {'=' : '-w', '+=' : '-i', '-=' : '-d'}
                op = get_unquoted(sub[i + 2]) if len(sub) > i + 2 else None
                if op and op in assign_flags:
                    sub[i + 2:i + 3] = [tokenizer.list_token([]),
                                        tokenizer.flag_token(assign_flags[op])]
                elif len(sub) > i + 2 and get_unquoted(sub[i + 2]) == '[':
                    sub[i + 2:] = nested_array_to_list(sub[i + 2:])
                    op = get_unquoted(sub[i + 4]) if len(sub) > i + 4 else None
                    if op and op in assign_flags:
                        sub[i + 4:i + 5] = [tokenizer.flag_token(assign_flags[op])]
                    else:
                        sub[i + 4:i + 4] = [tokenizer.flag_token('-r'), tokenizer.int_token(0)]
                    sub.pop(i + 2) # remove '['
                else:
                    sub[i + 2:i + 2] = [tokenizer.list_token([]),
                                        tokenizer.flag_token('-r'), tokenizer.int_token(0)]

            if found and found.name == '[':
                assign_flags = {'=' : '-w', '+=' : '-i', '-=' : '-d'}
                sub[i:] = nested_array_to_list(sub[i:])
                op = get_unquoted(sub[i + 2]) if len(sub) > i + 2 else None
                if op and op in assign_flags:
                    sub[i + 2:i + 3] = [tokenizer.flag_token(assign_flags[op])]
                else:
                    sub[i + 2:i + 2] = [tokenizer.flag_token('-r'), tokenizer.int_token(0)]

            # handle objects and namespace commands
            if not found and isinstance(sub[0], tokenizer.unquoted_token):
                name = strip_tab(sub[0].value)
                i = 0
                if istabcomplete(sub, 0):
                    raise CliTabComplete(_obj_or_cmd_completions(name))
                try:
                    object = get_object(name)
                except simics.SimExc_General:
                    (found, object) = _get_namespace_command(name)

            if not found:
                if object:
                    sub[0:1] = [value_to_token(object)]
                    continue

                if (len(sub) == 1
                    and isinstance(sub[0], tokenizer.value_token)
                    and not isinstance(sub[0], tokenizer.unquoted_token)):
                    break

                cmdinfo.set_current_line(sub[0])

                if isinstance(sub[0], tokenizer.unquoted_token):
                    if obj_aliases().has_alias(sub[0].value):
                        msg = obj_aliases().get_alias(sub[0].value).missing_msg()
                    else:
                        msg = "unknown command '" + sub[0].value + "'."
                    raise CliError(msg)

                msg = f"Garbage ('{sub[-1]}' string) at end of command input"
                if cmdinfo and cmdinfo.get_cmdline():
                    last_command = cmdinfo.get_cmdline().get_last_command()
                    msg += f" while parsing the '{last_command}' command"
                raise CliParseError(msg)

            if (len(sub) > 2
                and get_unquoted(sub[1]) == '->'
                and istabcomplete(sub, 2)):

                cmdinfo.set_current_line(sub[0])

                # only for tab-completion of obj->attr
                name = sub[0].value
                attr = sub[2].value[:-1]
                if not name or not isinstance(name, string_types):
                    raise CliTabComplete([])
                if not object_exists(name):
                    raise CliParseError('No name space "%s"' % name)
                object = get_object(name)
                attrs = get_completions(
                    attr, simics.VT_get_attributes(object.classname))
                raise CliTabComplete([name + '->' + x for x in attrs])

            del sub[i]
            if found.infix and i >= found.infix:
                i = i - found.infix

            cmdinfo.set_command(found.name)

            (args, num) = arg_interpreter(cmdinfo, found, object,
                                          copy_arg_list(found.args),
                                          sub[i:], no_execute)
            del sub[i:i+num - 1]

            if no_execute:
                sub[i:i] = [tokenizer.void_token()]
                continue

            is_interactive = cmdinfo.get_cmdline().get_interactive()
            if (is_interactive and found.repeat
                and cmdinfo.get_cmdline().get_is_repeat()):
                args = ([object] if object else []) + args
                retval = found.repeat(*args)
            else:
                if cmdinfo.get_cmdline().get_interactive() and found.repeat:
                    cmdinfo.get_cmdline().set_may_repeat(True)
                if found.deprecated and not found.deprecated_warned:
                    warn_deprecation(cmdinfo, found, is_interactive)
                    found.deprecated_warned = True
                if found.legacy and not found.legacy_warned:
                    warn_legacy(cmdinfo, found, is_interactive)
                    found.legacy_warned = True
                retval = found.call(args, object)

            cmdinfo.set_command('')

            do_break = True

            merge_before = (i > 0
                            and isinstance(sub[i - 1], tokenizer.unquoted_token)
                            and (sub[i - 1].value.endswith('.')))

            merge_after = (len(sub[i:])
                           and isinstance(sub[i], tokenizer.unquoted_token)
                           and (sub[i].value.startswith('.')))

            if merge_before or merge_after:
                if isinstance(retval, command_return):
                    retval = retval.get_value()
                if isinstance(retval, conf_object_t):
                    retval = retval.name
                retval = str(retval) if retval else ''
                if merge_after and not retval:
                    raise CliParseError('Empty name space')
                if merge_before and merge_after:
                    sub[i - 1].value = sub[i - 1].value + retval + sub[i].value
                    del sub[i]
                elif merge_before:
                    sub[i - 1].value = sub[i - 1].value + retval
                else: # merge_after
                    sub[i].value = retval + sub[i].value
                if len(sub) == 1:
                    do_break = False
            else:
                sub[i:i] = [value_to_token(retval)]
            if len(sub) <= 1 and do_break:
                # single token, return it
                break

        result = sub[0]

        if discard_result:
            if cmdinfo.get_cmdline().get_interactive() or result.verbose():
                result.print_token()
            elif result.value and len(tokens) == 0:
                # handle case when while/if line ends with the expression and
                # the { is on the following line (bug 24220)
                tokens.insert(0, result)
            continue

        tokens.insert(0, result)
        break

    if len(tokens) == 1:
        return tokens[0]
    elif not tokens:
        return tokenizer.void_token()
    else:
        assert 0

def evaluate_one(cmdinfo, tokens, no_execute = False, local = False):
    global current_locals, current_cmdinfo

    check_run_command_oec()

    saved_context_tuple = (current_locals, current_cmdinfo)

    if local:
        current_locals = simenv_class(current_locals, current_locals)
    if cmdinfo != current_cmdinfo:
        cmdinfo.parent = current_cmdinfo  # keep call stack for debug
        current_cmdinfo = cmdinfo
    try:
        val = real_evaluate_one(cmdinfo, [t.copy() for t in tokens], no_execute)
    finally:
        (current_locals, current_cmdinfo) = saved_context_tuple

    return val

def get_completions(prefix, valid_values):
    return [v for v in valid_values if v.startswith(prefix)]

# this is used as a blocklist of types for which we show '.' as a
# possible tab completion suffix
_function_types = (
    type(get_completions),
    type(lenient_stream_writer.write),
    type(eval))

def _py_complete_getitem(ns, k):
    try:
        if k.startswith("[") and k.endswith("]"):
            s = k[1:-1]
            if len(s) > 1 and s[0] in "\"'" and s[0] == s[-1]:
                return ns.__getitem__(s[1:-1])
            else:
                return ns.__getitem__(int(s))
        else:
            return getattr(ns, k)
    except:
        return None

# Add completion for simple python expressions immediately
# following the '@' sign, for example @conf.cpu0.<tab>
def python_tab_complete(text, python_mode = False):
    import builtins, __main__
    if not text or text == '@':
        return []

    parts = text.replace("[", ".[").split(".")
    parts[0] = parts[0].lstrip("@")
    if parts[-1].endswith("]"):
        parts.append("")
    last = parts.pop()
    base = text[0:text.rfind(last)]

    if ".[" in text:
        return []
    for ns in (__main__, builtins):
        for p in parts:
            if not p:
                return []
            ns = _py_complete_getitem(ns, p)
            if ns is None:
                break
        else:
            break
    else:
        if parts:
            return []
        ns = __main__

    if isinstance(ns, conf_object_t) and ns.classname == 'index-map':
        if text.endswith("."):
            return []
        subs = ["[{}".format(o.name.rpartition("[")[2])
                for o in simics.SIM_shallow_object_iterator(ns)]
        comp = [s for s in subs if s.startswith(last)]
    else:
        comp = set(s for s in dir(ns) if s.startswith(last))
        if not parts:
            import keyword
            comp.update(s for s in dir(builtins) if s.startswith(last))
            comp.update(s for s in keyword.kwlist if s.startswith(last))
        prefix = '.' if base.endswith(']') else ''
        comp = list(prefix + s for s in comp)

    prefix = common_prefix(comp, False)

    # add 'foo.bar.' if there exists any 'foo.bar.x' that doesn't start with
    # underscore, 'foo.bar[' if it has __getitem__, and 'foo.bar(' if it is
    # callable
    if prefix in comp:
        if last == prefix:
            comp.remove(last)
        o = _py_complete_getitem(ns, prefix)
        if o is None and not parts:
            o = _py_complete_getitem(builtins, prefix)
        if o is not None:
            if (type(o) not in _function_types
                and not (isinstance(o, conf_object_t)
                         and o.classname == 'index-map')
                and any(not x.startswith('_') for x in dir(o))):
                comp.append(prefix + '.')
            if callable(o):
                comp.extend([prefix, prefix + '('])
            if (hasattr(o, '__getitem__')
                and not (isinstance(o, conf_object_t)
                         and o.classname != 'index-map')):
                comp.extend([prefix + '['] * 2)

    return [base + s for s in comp]

class _test_python_tab_complete(unittest.TestCase):
    def gives(self, typed, expected):
        for prefix in ('', '@'):
            result = python_tab_complete(prefix + typed, prefix == '')
            self.assertEqual(set(result), set(prefix + s for s in expected))

    def test_keywords(self):
        self.gives('whil', ['while'])

    def test_builtin_functions(self):
        self.gives('copyri', ['copyright', 'copyright(', 'copyright.'])
        self.gives('copyright', ['copyright', 'copyright(', 'copyright.'])

    def test_builtin_types(self):
        pass

    def test_builtin_constants(self):
        self.gives('Tru', ['True', 'True.'])

    def test_hierarchical(self):
        import __main__, math
        __main__.math = math
        self.gives('math.pi', ['math.pi.'])
        self.gives('math.asin', ['math.asin', 'math.asin(', 'math.asinh'])

    def test_arrays(self):
        import __main__
        __main__.unittest_array = []
        __main__.unittest_dict = {}
        self.gives('unittest_arr', ['unittest_array',
                                    'unittest_array.', 'unittest_array['])
        self.gives('unittest_array', ['unittest_array.', 'unittest_array['])
        self.gives('unittest_dict', ['unittest_dict.',
                                     'unittest_dict['])

    def test_empty_arrays(self):
        import __main__
        __main__.unittest_array = []
        __main__.unittest_dict = {}
        result = python_tab_complete("@unittest_array.", True)
        self.assertGreater(len(result), 0)
        result = python_tab_complete("@unittest_dict.", True)
        self.assertGreater(len(result), 0)

    def test_numbers(self):
        import __main__
        __main__.unittest_number = 3.14
        self.gives('unittest_numb', ['unittest_number', 'unittest_number.'])
        self.gives('unittest_number', ['unittest_number.'])

def generic_tab_complete(text, python_mode):
    if text and (text[0] == '@' or python_mode):
        return python_tab_complete(text, python_mode)
    try:
        evaluate_one(cmdinfo_class(), tokenizer.tokenize(text + "\a", True),
                     no_execute = True)
    except CliTabComplete as ex:
        return ex.value()
    except CliException:
        # ignore parse/argument errors when doing tab-completion
        pass
    except Exception as ex:
        simics.pr_err("Unexpected exception"
                      " on tab completion: {0}.\n{1}".format(
                          ex, traceback.format_exc()))
    return []

def completion_key(v):
    if isinstance(v, (list, tuple)):
        return v[0]
    return v

# Generate tab completions of a command line (up to the insertion point)
# as a list. Return [completions, is_filename_completion] where the second
# element is a flag indicating whether the completion was on file names.
def tab_completions(line, python_mode = False):
    completions = generic_tab_complete(line, python_mode)
    # file name completers return a tuple (string, dir-flag)
    is_file_compl = bool(completions and isinstance(completions[0],
                                                    (list, tuple)))
    ret = [sorted(completions, key=completion_key), is_file_compl]
    return ret

# keep information about a specific command line

cmdlines = {}

class cmdline_class:
    def __init__(self, id, interactive, asynch, primary):
        self.id = id
        self.set_size(80, 24)
        self.last_command = ''
        self.interactive = interactive
        self.asynch = asynch
        self.may_repeat = False # if last line contained repeating command
        self.is_repeat = False # current line is a repeat of last
        self.repeat_data = {} # repeat data per command
        self.primary = primary

    def get_id(self):
        return self.id

    def set_size(self, width, height):
        self.width = width
        self.height = height

    def get_height(self):
        return self.height

    def get_width(self):
        return self.width

    def set_last_command(self, cmd):
        self.last_command = cmd

    def get_last_command(self):
        return self.last_command

    def set_may_repeat(self, value):
        self.may_repeat = value

    def get_may_repeat(self):
        return self.may_repeat

    def set_is_repeat(self, value):
        self.is_repeat = value

    def get_is_repeat(self):
        return self.is_repeat

    def set_repeat_data(self, cmd_key, data):
        self.repeat_data[cmd_key] = data

    def get_repeat_data(self, cmd_key):
        return self.repeat_data[cmd_key]

    def get_interactive(self):
        return self.interactive

    def set_interactive(self, value):
        self.interactive = value

    def get_async(self):
        return self.asynch and not os.getenv("SIMICS_DISABLE_ASYNC_CMDLINE")

    def get_primary(self):
        return self.primary

def register_cmdline(id, interactive, asynch, primary):
    assert not id in cmdlines
    cmdlines[id] = cmdline_class(id, interactive, asynch, primary)
    return cmdlines[id]

def get_cmdline(id):
    return cmdlines[id]

def cmdline_set_size(id, width, height):
    get_cmdline(id).set_size(width, height)

def other_cmdline_active(id):
    # default cmdline is not treated as other command-line (async output)
    return current_cmdline.id >= 0 and current_cmdline.id != id

def get_current_cmdline():
    return current_cmdline.get_id()

def current_cmdline_interactive():
    return current_cmdline.get_interactive()

def set_cmdline(id):
    global current_cmdline
    old = current_cmdline.get_id()
    current_cmdline = get_cmdline(id)
    return old

def disable_command_repeat():
    current_cmdline.set_may_repeat(False)

def set_repeat_data(cmd_key, data):
    current_cmdline.set_repeat_data(cmd_key, data)

def get_repeat_data(cmd_key):
    return current_cmdline.get_repeat_data(cmd_key)

def get_primary_cmdline():
    for i in cmdlines:
        c = get_cmdline(i)
        if c.get_primary():
            return c

class cmdinfo_class:
    default_cmdline = register_cmdline(-1, False, False, True)

    def __init__(self, cmdline = None):
        if not cmdline:
            self.cmdline = self.default_cmdline
        else:
            self.cmdline = cmdline
        self.set_file_info(None, '<cmdline>', 0)
        self.offset = 0
        self.command = ''
        self.async_command = True
        self.parent = None

    def __repr__(self):
        return "<%s/%s:%s %s>" % (self.dir, self.file, self.line, self.command)

    def get_cmdline(self):
        return self.cmdline

    def set_file_info(self, dir, file, line):
        assert not dir or file
        self.dir = dir
        self.file = file
        self.line = line

    def get_dir(self):
        return self.dir

    def get_file(self):
        return self.file

    def get_full_file(self):
        if self.dir:
            return os.path.join(self.dir, self.file)
        return None

    def get_line(self):
        return self.line + self.offset

    def set_current_line(self, token):
        if token.line != -1:
            self.offset = token.line

    def set_command(self, command):
        self.command = command

    def get_command(self):
        return self.command

    def is_async_command(self):
        return self.async_command

    def set_async_command(self, val):
        self.async_command = val

current_cmdinfo = None

def get_current_cmdinfo():
    return current_cmdinfo

current_cmdline = cmdinfo_class.default_cmdline

@doc('check if current command is run interactively',
     module = 'cli')
def interactive_command():
    """Returns true if the current command was run interactively by the user
    and false if run from a script. This function may only be called by CLI
    commands."""
    if not current_cmdinfo:
        raise CliError("interactive_command() called outside command")
    return current_cmdinfo.get_cmdline().get_interactive()

@contextlib.contextmanager
def set_interactive_command_ctx(new_interactive):
    """Internal function that lets parts of a command run with interactive state
    temporarily set to 'new_interactive'."""
    if not current_cmdinfo:
        raise CliError("set_interactive_command_ctx() called outside command")
    cmdinfo = current_cmdinfo
    old_interactive = cmdinfo.get_cmdline().get_interactive()
    cmdinfo.get_cmdline().set_interactive(new_interactive)
    try:
        yield cmdinfo
    finally:
        cmdinfo.get_cmdline().set_interactive(old_interactive)

def async_cmdline():
    if not current_cmdinfo:
        raise CliError("async_cmdline() called outside command")
    return (current_cmdinfo.get_cmdline().get_async()
            if current_cmdinfo.is_async_command() else False)

def primary_cmdline():
    if not current_cmdinfo:
        raise CliError("primary_cmdline() called outside command")
    return current_cmdinfo.get_cmdline().get_primary()

def terminal_width():
    return current_cmdline.width

def terminal_height():
    return current_cmdline.height

def resolve_script_path(path):
    if not current_cmdinfo:
        raise CliError("%script% used outside command")
    if not current_cmdinfo.get_dir():
        raise CliError("%script% used outside script")
    return path.replace('%script%', current_cmdinfo.get_dir())

def get_script_pos():
    if current_cmdinfo:
        path = current_cmdinfo.get_full_file() or current_cmdinfo.get_file()
        return (path, current_cmdinfo.get_line())
    return None

def common_eval_cli_line(cmdinfo, text):
    from targets import target_commands
    global current_cmdline
    previous_cmdline = current_cmdline
    current_cmdline = cmdinfo.get_cmdline()

    # if we got a repeat command (empty text) then check and re-use the
    # previous command if running interactively

    if ((text == ''
         and current_cmdline.get_interactive()
         and current_cmdline.get_may_repeat())
        or text == 'cli-repeat-last-command'):
        text = current_cmdline.get_last_command()
        # use cli-repeat-last-command in log file to signal repeat of previous
        simics.VT_logit('cli-repeat-last-command\n')
        current_cmdline.set_is_repeat(True)
    else:
        current_cmdline.set_is_repeat(False)
        current_cmdline.set_may_repeat(False)
        simics.VT_logit(text + '\n')

    try:
        if text == "":
            return (True, False, '')

        if target_commands.config:
            target_commands.config.add_cmd(text)
        current_cmdline.set_last_command(text)

        (is_ok, is_err, msg, _) = run_and_report(
            cmdinfo, lambda: run(cmdinfo, text))
        return (is_ok, is_err, msg)
    finally:
        current_cmdline = previous_cmdline

# Called by Simics command file handler, returns [is_command_ok, is_error,
# msg, line, command]
def cmdfile_run_command(file, line, text):
    assert os.path.isabs(file)
    file_dir = os.path.dirname(file)
    file = os.path.basename(file)
    cmdinfo = cmdinfo_class()
    cmdinfo.set_file_info(file_dir, file, line)
    try:
        ret = list(common_eval_cli_line(cmdinfo, text.strip()))
    except Exception as ex:
        traceback.print_exc(file = sys.stdout)
        ret = [False, True, "Unexpected exception in CLI: %s" % ex]
    return ret + [cmdinfo.get_line(), cmdinfo.get_command()]

# Called by Simics command line handler, returns error string
def cmdline_run_command(id, text):
    for tee_info in tee.all_tee_objs:
        prompt = conf.sim.prompt
        tee_info.write('%s> ' % prompt
                       + text.replace('\n',
                                      ('\n%s ' % ('.' * (len(prompt) + 1),)))
                       + '\n')
    try:
        cmdinfo = cmdinfo_class(get_cmdline(id))
        (is_command_ok, is_error, msg) = common_eval_cli_line(cmdinfo, text)
        if not is_command_ok:
            cmdinfo.get_cmdline().set_may_repeat(False)
        result = msg
    except Exception as ex:
        traceback.print_exc(file = sys.stdout)
        result = "Unexpected exception in CLI: %s" % ex

    if result:
        for tee_info in tee.all_tee_objs:
            tee_info.write(result + '\n')
    return result

# called by SIM_run_command(), returns ok flag followed by value or error msg
# should probably be merged with common_eval_cli_line()
def internal_run_command(text):
    from targets import target_commands
    cmdinfo = cmdinfo_class()

    global current_cmdline
    previous_cmdline = current_cmdline
    current_cmdline = cmdinfo.get_cmdline()
    if target_commands.config:
        target_commands.config.add_cmd(text)

    try:
        current_cmdline.set_last_command(text)
        (is_command_ok, is_error, msg, value) = run_and_report(
            cmdinfo, lambda: run(cmdinfo, text))
    except Exception as ex:
        traceback.print_exc(file = sys.stdout)
        return [False, "Unexpected exception in CLI: %s" % ex]
    finally:
        current_cmdline = previous_cmdline
    # interrupt of single command is not an error is single command case
    return [is_command_ok or not msg, msg if not is_command_ok else value]

def unicode_some_str(value):
    return str(value)

# Allow printing of tracebacks with standard Python exceptions with
# unicode/utf-8 strings. See tests in t165 for more info.
traceback._some_str = unicode_some_str

def format_frame_source(frame):
    """Thin wrapper to avoid Python boilerplate in python-frontend.c"""
    import linecache
    filename = frame.f_code.co_filename
    func = frame.f_code.co_name

    output = f'  File "{filename}", line {frame.f_lineno}, in {func}\n'
    linecache.checkcache(filename)
    line = linecache.getline(filename, frame.f_lineno, frame.f_globals)
    if line:
        return f"{output}    {line.strip()}\n"
    else:
        return output

def format_frames(frame):
    frame_data = []
    back = frame.f_back
    if not (back is None or simics.CORE_is_active_frame(back)):
        frame_data.append(format_frames(back))
    frame_data.append(format_frame_source(frame))
    return "".join(frame_data)

# called by Simics to get stack trace
def get_error_tb(extype, value, tb, with_tb):

    # Returns the number of most recent stack entries to show for
    # trace back 'tb'. Cf. stop_traceback()
    def get_num_frames_to_show(tb):
        if tb is None:
            return 0xffff
        num_frames_to_print = 0
        while True:
            num_frames_to_print += 1
            (frame_co, tb) = (tb.tb_frame.f_code, tb.tb_next)
            if tb is None:
                break
            if frame_co in stop_traceback_codes:
                num_frames_to_print = 0
        return num_frames_to_print

    if with_tb:
        with StringIO() as f:
            traceback.print_exception(
                extype, value, tb, limit=-get_num_frames_to_show(tb), file=f)
            return f.getvalue().strip()
    if extype is not None or value is not None:
        lines = traceback.format_exception_only(extype, value)
        if lines and ':' in lines[0]:
            lines[0] = lines[0].split(':', 1)[1].lstrip()
        return ''.join(lines).strip()
    return ''

def stack_frame_limit(f):
    """Returns a pair (number, stop): the number of frames to print
    starting from the frame 'f', and whether we hit a @stop_traceback
    function"""

    # Print everything down to, but not including, the first
    # @stop_traceback function, but always print at least one frame.
    if f and f.f_code in stop_traceback_codes:
        return (1, True)
    for limit in itertools.count():
        if f is None or f.f_code in stop_traceback_codes:
            return (limit, f is not None)
        f = f.f_back

class _test_stack_frame_limit(unittest.TestCase):
    def test_stack_frame_limit(self):
        def fun2():
            frame = inspect.currentframe()
            try:
                limit, stop = stack_frame_limit(frame)
                stack = "".join(traceback.format_stack(frame, limit))
            finally:
                del frame
            self.assertTrue(stop)
            self.assertTrue('fun2' in stack)
            self.assertFalse('fun1' in stack)
        @stop_traceback
        def fun1():
            fun2()
        fun1()

        @stop_traceback
        def fun0():
            frame = inspect.currentframe()
            try:
                limit, stop = stack_frame_limit(frame)
                stack = "".join(traceback.format_stack(frame, limit))
            finally:
                del frame
            self.assertTrue(stop)
            self.assertTrue('fun0' in stack)
            self.assertFalse('test_stack_frame_limit' in stack)
        fun0()

        self.assertTrue(stack_frame_limit(None) == (0, False))

def print_py_stack():
    """Prints the current call stack, truncating output appropriately.
    Cf. stop_traceback()."""
    print("Python traceback (most recent call last):", file=sys.stderr)
    top_f = inspect.currentframe()
    try:
        limit = stack_frame_limit(top_f)
        limit = limit[0]
        traceback.print_stack(top_f, limit=limit)
    finally:
        del top_f

def simics_print_stack():
    """Prints the script call stack (if available) and the Python call stack."""
    script_stack = list(reversed(get_script_stack(full_file=True)))
    if script_stack:
        print_script_stack(script_stack)
    else:
        print_py_stack()

# Support for Script branches

def cli_sb_wait(command, wait_id, use_obj,
                caller, filename, line, wait_data):
    global current_locals, current_cmdinfo, pre_branch_context_tuple

    if simics.CORE_is_cli_script_branch():
        cli_branch_context = (current_locals, current_cmdinfo)
        # back to the locals in active when the script-branch was scheduled
        (current_locals, current_cmdinfo) = pre_branch_context_tuple
    try:
        simics.VT_wait_in_script_branch(
            command, wait_id, False, False, use_obj,
            caller, filename, line, wait_data)
    except simics.SimExc_Break:
        # NB: CliQuietError which is raised here is documented in
        # sb_interrupt_branch documentation - so the exception type
        # is not completely internal, but it is a part of Simics API.
        # is_script_branch_interrupt is set so that exception handlers
        # that are interested in the information can detect that
        # a script branch was interrupted.
        raise CliQuietError("Command '%s' interrupted." % command,
                            is_script_branch_interrupt=True)
    except simics.SimExc_General as ex:
        raise CliError(str(ex))
    finally:
        if simics.CORE_is_cli_script_branch():
            # branch restarted, update variable scope
            pre_branch_context_tuple = (current_locals, current_cmdinfo)
            (current_locals, current_cmdinfo) = cli_branch_context

def create_branch(func, desc, caller, filename, line, cli = False):
    try:
        id = simics.CORE_create_script_branch(
            func, desc, cli, caller, filename, line)
    except simics.SimExc_General as ex:
        raise CliError(ex)
    return id

class unused_arg:
    pass

def fmt_value(value, recursive = False, indent = ''):
    """Format 'value' for human-readable output in 'info' commands.
    'indent' is the indentation used on any newline-separated line except the
    first."""
    if isinstance(value, conf_attribute_t):
        # Create common Python type from Simics attribute type
        value = value.copy()
    if isinstance(value, conf_object_t):
        return value.name
    elif isinstance(value, list):
        if value:
            l = [ fmt_value(v, recursive = True) for v in value ]
            if recursive:
                return "(" + ", ".join(l) + ")"
            else:
                return ("\n" + indent).join(l)
        else:
            return "none"
    elif isinstance(value, type(None)):
        return "none"
    elif isinstance(value, str):
        return value
    else:
        return str(value)

def print_info(info, key_width = None):
    if key_width is None:
        key_width = 4 + max([len(k) for (_, data) in info for (k, _) in data]
                            + [0])

    for section, data in info:
        print()
        if section:
            print("%s:" % section)
        value_indent = ' ' * (key_width + 3)
        for key, value in data:
            value = fmt_value(value, indent = value_indent)
            print_wrap_code('%*s : %s' % (key_width, key, value),
                            terminal_width(),
                            continuation_indent = value_indent,
                            honor_leading_indent = False)

Just_Right  = 0
Just_Center = 1
Just_Left   = 2

_just_dict = {
    Just_Left:   Just_Left,
    Just_Center: Just_Center,
    Just_Right:  Just_Right,
    'l':         Just_Left,
    'c':         Just_Center,
    'r':         Just_Right }

def print_columns(just, data, has_title = True, column_space = 2,
                  wrap_space = " | ", outfile = None):
    """Print 'data' in nicely formatted columns. 'data' is a list of
    lists, where each entry in the "outer" list is a data row. Each
    entry in the inner list is a field in a column.

    Each column has a justification (Just_Right, Just_Center, or
    Just_Left) in the 'just' list, which must have the same number of
    entries as every inner list of 'data'. 'just' can also be a string
    of the characters 'r', 'c', and 'l'.

    If 'has_title' is True, data[0] is considered to contain column
    titles.

    'column_space' is the number of spaces to add between each column.

    'wrap_space' is the text added between any "outer" columns.

    The inner lists can optionally contain one extra element which
    will be printed on a line of its own after the "real" line. If
    such elements are present, column wrapping will never be done.

    'data' can also contain strings, which are automatically converted
    to lists containing just that string.

    Output is sent to 'outfile', or sys.stdout if not specified."""

    def fix_fields(x):
        def fix_elements(y):
            if not isinstance(y, string_types):
                return str(y)
            return y

        if not isinstance(x, (list, tuple)):
            x = [ x ]
        return list(map(fix_elements, x))

    title_rows = 1 if has_title else 0

    just = [_just_dict[x] for x in just]
    cols = len(just)
    data = list(map(fix_fields, data))

    # has_extra is True if additional fields are present, which will
    # be printed on lines of their own
    has_extra = False
    for col in data:
        if len(col) == cols:
            continue
        assert len(col) == cols + 1
        has_extra = True

    if len(data) <= title_rows:
        return

    def get_number_of_rows(columns):
        """Returns the number of data rows needed to print the data in
        'columns' columns."""
        return (len(data) - title_rows + columns - 1) // columns

    def get_number_of_columns(rows):
        """Returns the number of columns needed to print the data in
        'rows' data rows."""
        return (len(data) - title_rows  + rows - 1) // rows

    def get_column_configuration(rows, columns):
        """Returns a list of subcolumn width if the data can be
        presented in 'rows' rows and 'columns' columns; False if it
        does not fit."""

        subcolumn_widths = [ len(data[0][c]) if title_rows else 0
                             for c in range(cols) ]
        # column_widths[N][M] is the width of subcolumn M of data
        # column N
        column_widths = [ list(subcolumn_widths)
                          for c in range(columns) ]

        for i, line in enumerate(itertools.islice(data, title_rows, None)):
            column = i // rows
            for subcol in range(cols):
                entry = data[i + title_rows][subcol]
                column_widths[column][subcol] = max(
                    len(entry),
                    column_widths[column][subcol])

        if columns == 1:
            return column_widths
        total_width = (sum(sum(x) for x in column_widths)
                       + columns * column_space * (cols - 1)
                       + len(wrap_space) * (columns - 1))
        if total_width < terminal_width():
            return column_widths
        return False

    # max_column_widths[N] is the widest entry in subcolumn N
    max_column_widths = [functools.reduce(max,
                                          (len(line[col]) for line in data), 0)
                         for col in range(cols)]
    max_line_width = sum(max_column_widths) + column_space * (cols - 1)

    if has_extra or not stdout_output_mode.format:
        max_columns = 1
    else:
        max_columns = len(data) - title_rows

    # start_columns is a conservative guess at the smallest number of
    # columns to present the data in
    start_columns = max(min(max_columns,
                            ((terminal_width() - 1 + len(wrap_space))
                             // (max_line_width + len(wrap_space)))),
                        1)
    ncolumns = start_columns
    nrows    = get_number_of_rows(ncolumns)
    ncolumns = get_number_of_columns(nrows)

    while ncolumns <= max_columns:
        cconfig = get_column_configuration(nrows, ncolumns)
        if not cconfig:
            break
        column_configuration = cconfig
        columns = ncolumns
        rows    = nrows
        if columns < rows:
            ncolumns = columns + 1
            nrows    = get_number_of_rows(ncolumns)
        else:
            nrows    = rows - 1
            if nrows < 1:
                break
            ncolumns = get_number_of_columns(nrows)
    assert column_configuration

    outfile_dest = sys.stdout if outfile is None else outfile
    outfile = StringIO()  # in-memory buffer: output on Windows may be slow
    for row in range(0, rows + title_rows):
        for col in range(0, columns):
            if row == 0 and title_rows:
                field = data[0]
            else:
                f = col * rows + row
                if f >= len(data):
                    field = [""] * cols
                else:
                    field = data[f]

            if col > 0:
                outfile.write(wrap_space)
            for i in range(0, cols):
                if i > 0:
                    outfile.write(" " * column_space)
                spc = column_configuration[col][i] - len(field[i])
                if just[i] == Just_Right:
                    outfile.write(" " * spc + field[i])
                elif just[i] == Just_Center:
                    outfile.write(" " * (spc // 2) + field[i])
                    if col < columns - 1 or i < cols - 1:
                        outfile.write(" " * ((spc + 1) // 2))
                else:
                    outfile.write(field[i])
                    if col < columns - 1 or i < cols - 1:
                        outfile.write(" " * spc)

            if len(field) > cols:
                outfile.write("\n" + field[cols])
        outfile.write('\n')

        if row == 0 and title_rows:
            for c in range(columns):
                outfile.write('-' * (sum(column_configuration[c])
                                     + (cols - 1) * column_space))
                if c == columns - 1:
                    continue
                outfile.write('-' * (len(wrap_space) // 2))
                outfile.write('+')
                outfile.write('-' * ((len(wrap_space) - 1) // 2))
            outfile.write('\n')
    outfile_dest.write(outfile.getvalue())
    outfile.close()

class _test_print_columns(unittest.TestCase):
    def t(self, expect, *args, **kwargs):
        ofile = StringIO()
        print_columns(outfile = ofile, *args, **kwargs)
        self.assertEqual(ofile.getvalue(), expect)

    def test_empty(self):
        self.t('', [], [])
        self.t('', [], [], has_title = False)
        for n in range(3):
            self.t('', [Just_Left] * n, [])
            self.t('', 'l' * n, [])
            self.t('', [Just_Left] * n, [ [ 'title' ] * n ])

    def test_one(self):
        for t in False, True:
            prefix = 'Title\n-----\n' if t else ''
            title =  ['Title'] if t else []
            self.t(prefix + 'a\n',    [Just_Left], title + ['a'],
                   has_title = t)
            self.t(prefix + '4711\n', [Just_Left], title + [[4711]],
                   has_title = t)
            self.t(prefix + 'a\n',    [Just_Left], title + [['a']],
                   has_title = t)

    def test_two(self):
        self.t('T | T\n--+--\nx | y\n',     [ Just_Left ],
               [ [ 'T' ], 'x', 'y' ])
        self.t('T   | T\n----+--\napa | y\n', [ Just_Left ],
               [ [ 'T' ], [ 'apa' ], [ 'y' ] ])

        s50 = 'x' * 50
        s10 = 'y' * 10
        self.t(s50 + ' | ' + s10 + '\n',
               [ Just_Left ], [ s50, s10 ], has_title = False)
        self.t(s50 + '\nextra\n' + s10 + '\n',
               'l', [ [ s50, 'extra' ], s10 ], has_title = False)

def print_wrap_code_line(line, width, output = pr,
                         continuation_indent = '    ',
                         honor_leading_indent = True):

    """Prints 'line', a string without any newline characters, with word
    wrap at 'width' characters, by doing one or more calls to
    'output(msg)'.

    If the line needs to wrap, subsequent lines are indented by
    'continuation_indent'. If 'honor_leading_indent' is true, the
    indentation of the first line is first prepended to
    'continuation_indent'.

    The output will be terminated by a newline."""

    length = len(line)
    start = idx = 0
    end = width

    # find indentation of the entire line
    while idx < length and line[idx].isspace():
        idx += 1
    if idx == length:
        # entire line contains only whitespace
        output('\n')
        return

    if honor_leading_indent:
        # subsequent lines shall have this indentation
        continuation_indent = line[:idx] + continuation_indent

    prefix = ''

    while True:
        # each line shall contain at least one word
        while idx < length and not line[idx].isspace():
            idx += 1

        while True:
            word_end = idx

            while idx < length and line[idx].isspace():
                idx += 1
            space_end = idx

            while idx < length and not line[idx].isspace():
                idx += 1

            # break before this word if we run over 'end', and this
            # word would be farther to the left on the line after
            # indentation
            if idx > end and (space_end - start) > len(continuation_indent):
                if prefix:
                    output(prefix)
                output(line[start:word_end])
                output('\n')

                start = space_end
                if start == length:
                    return

                prefix = continuation_indent
                end = start + width - len(prefix)
                break

            if idx == length:
                if prefix:
                    output(prefix)
                output(line[start:])
                output('\n')
                return

class _test_print_wrap_code_line(unittest.TestCase):
    def gives(self, code, width, indent, expect):
        result = ['']
        def output(str):
            result[0] += str
        print_wrap_code_line(code, width, output = output,
                                continuation_indent = indent)
        self.assertEqual(result[0], expect + '\n')

    def test_nowrap(self):
        self.gives('test ing this', 40, 'indent', 'test ing this')
        self.gives('     ing this', 40, 'indent', '     ing this')
        self.gives('test   ing   this', 40, 'indent', 'test   ing   this')
        self.gives('test ing this', 13, 'indent', 'test ing this')
        self.gives('     ing this', 13, 'indent', '     ing this')
        self.gives('test ing this        ', 13, 'indent', 'test ing this')
        self.gives('test ing       this', 19, 'indent',
                   'test ing       this')

    def test_wrap(self):
        self.gives('test ing this', 12, 'INDENT', 'test ing\nINDENTthis')
        self.gives('test ing this', 2, 'INDENT', 'test ing\nINDENTthis')
        self.gives('test ing this', 2, 'X', 'test\nXing\nXthis')
        self.gives('test ing this', 0, 'INDENT', 'test ing\nINDENTthis')
        self.gives('test ing this', 0, 'X', 'test\nXing\nXthis')

        self.gives('abc de fg hij kl mn op', 6, 'I',
                   'abc de\nIfg\nIhij\nIkl mn\nIop')

        self.gives('abcdefghi abcdefghi abcdefghi', 1, '12345678',
                   'abcdefghi\n12345678abcdefghi\n12345678abcdefghi')

        self.gives('a bc  a bc def ghij klmno', 6, 'XX',
                   'a bc\nXXa bc\nXXdef\nXXghij\nXXklmno')

    def test_indented(self):
        self.gives('    test ing this', 12, 'INDENT',
                   '    test ing\n    INDENTthis')

    def test_empty(self):
        self.gives('', 40, 'INDENT', '')
        self.gives('', 0, 'INDENT', '')

        self.gives('          ', 40, 'INDENT', '')
        self.gives('          ', 0, 'INDENT', '')

def print_wrap_code(code, width, output = pr, continuation_indent = '    ',
                    honor_leading_indent = True):
    """Print a piece of program code, and break the line at a word boundary if
    it is wider than 'width'.

    The continuation lines (not-first lines produced by line wrap) are indented
    using 'continuation_indent', treating 'honor_leading_indent' as in
    print_wrap_code_line().

    output(str) is called in order to print the resulting text."""
    for line in code.splitlines():
        if len(line) <= width:
            output(line)
            output('\n')
            continue

        print_wrap_code_line(line, width, output,
                             continuation_indent = continuation_indent,
                             honor_leading_indent = honor_leading_indent)

class _test_wrap_code(unittest.TestCase):
    def gives(self, code, width, indent, expect):
        result = ['']
        def output(str):
            result[0] += str
        print_wrap_code(code, width, output = output,
                        continuation_indent = indent)
        self.assertEqual(result[0], expect)

    def test_nowrap(self):
        self.gives('test ing this', 40, 'indent', 'test ing this\n')
        self.gives('     ing this', 40, 'indent', '     ing this\n')
        self.gives('test ing this', 13, 'indent', 'test ing this\n')
        self.gives('     ing this', 13, 'indent', '     ing this\n')

    def test_multiline(self):
        self.gives('testing\nthis', 100, '   ', 'testing\nthis\n')
        self.gives('testing this\nthing here', 100, '   ',
                   'testing this\nthing here\n')

        self.gives('test ing\nthis thing', 8, 'XX',
                   'test ing\nthis\nXXthing\n')

        self.gives('test ing    \n    this     thing', 10, 'XX',
                   'test ing\n    this\n    XXthing\n')

    def test_wrap_no_indent(self):
        self.gives('test ing this', 8, '', 'test ing\nthis\n')
        self.gives('test ing this', 7, '', 'test\ning\nthis\n')
        self.gives('testing a b thing', 7, '',
                   'testing\na b\nthing\n')

    def test_wrap_indent(self):
        self.gives('test ing this', 8, 'INDENT', 'test ing\nINDENTthis\n')
        self.gives('test ing this', 7, 'INDENT', 'test ing\nINDENTthis\n')
        self.gives('test ing this', 7, 'X', 'test\nXing\nXthis\n')
        self.gives('testing a b thing', 7, 'IND',
              'testing\nINDa b\nINDthing\n')

    def test_zero_width(self):
        self.gives('test ing this', 0, 'INDENT', 'test ing\nINDENTthis\n')
        self.gives('test ing this', 0, 'X', 'test\nXing\nXthis\n')

    def test_empty(self):
        self.gives('', 40, 'INDENT', '')
        self.gives('', 0, 'INDENT', '')

        # a bit quirky, but...
        self.gives('          ', 40, 'INDENT', '          \n')
        self.gives('          ', 0, 'INDENT', '\n')

def detuplify(l):
    if isinstance(l, conf_attribute_t):
        # Create common Python type from Simics attribute type
        l = l.copy()

    if isinstance(l, (tuple, list)):
        return [ detuplify(e) for e in l ]
    elif isinstance(l, bool):
        return str(l)
    elif isinstance(l, string_types + (int, float,)):
        return l
    elif isinstance(l, conf_object_t):
        return "object:" + l.name
    else:
        return repr(l)

# hack to share commands.py (source) files between modules
def get_last_loaded_module():
    return (simics.CORE_get_current_loading_module()
            or simics.CORE_get_last_loaded_module())

# Avoid reusing names since it causes problems with links for example that
# create a hash based on the initial name. Far from fool proof, but it is needed
# to keep compatibility with customers setups in Simics 4.6.
next_name_id = {}

@doc('return a non-allocated object name',
     module = 'cli')
def get_available_object_name(prefix):
    """Return an object name suitable for creating a new object (i.e., that has
    not been used yet) by adding a suffix to <param>prefix</param>."""
    if old_object_naming:
        return old_get_available_object_name(prefix)
    while True:
        i = next_name_id.get(prefix, 0)
        next_name_id[prefix] = i + 1
        name = prefix + str(i)
        if not object_exists(name):
            return name

# Make it possible to use old behavior of get_available_object_name() in 5
# Should only be used if critical scripts expect the old behavior.
old_object_naming = False

def use_old_object_naming(enable = True):
    global old_object_naming
    old_object_naming = enable

def old_get_available_object_name(prefix):
    i = 0
    while True:
        try:
            name = prefix + str(i)
            SIM_get_object(name)
        except simics.SimExc_General:
            # This name is unused
            return name
        i += 1

@doc('return an object in a component',
     module = 'cli',
     return_value = 'object or pre-object')
def get_component_object(cmp_obj, slot):
    """Return the object named <param>slot</param> inside the
    <param>cmp_obj</param> component. The <param>slot</param> parameter is
    the name by which the component knows the object, not the global name of
    the object.

    The function will raise a <em>CliError</em> if the object can not be found
    in the component."""
    try:
        return cmputil.cmp_get_indexed_slot(cmp_obj, slot)
    except cmputil.CmpUtilException as msg:
        raise CliError('get_component_object failed %s' % (msg,))

#
# -------------------- class-specific stuff --------------------
#

class ClassFunctionMap:
    def __init__(self):
        # Maps from (class name, function name) to function
        self.__funcs = {}
    def add(self, class_name, function_name, func):
        key = (class_name, function_name)
        if key in self.__funcs:
            print("Duplicate definitions of %s in %s" % (function_name,
                                                         class_name))
        self.__funcs[key] = func
    def get(self, class_name, function_name):
        return self.__funcs.get((class_name, function_name))

class _test_class_function_mape(unittest.TestCase):
    def setUp(self):
        self.map = ClassFunctionMap()

    def test_simple(self):
        self.map.add('fooclass', 'funnyfun', get_last_loaded_module)
        self.assertEqual(self.map.get('fooclass', 'funnyfun'),
                         get_last_loaded_module)
        self.assertEqual(self.map.get('fooclass', 'notfunnyfun'),
                         None)

class_funcs = ClassFunctionMap()

def add_class_func(cls, name, f):
    class_funcs.add(cls, name, f)

def get_obj_func(obj, function_name):
    return class_funcs.get(obj.class_data.name, function_name)

def info_cmd(obj):
    title = "Information about %s [class %s]" % (obj.name, obj.classname)
    print(title)
    print("=" * len(title))
    try:
        fn = get_obj_func(obj, 'get_info')
        info = fn(obj)

        if info:
            print_info(info)
        else:
            print("No information available")
    except CliError:
        raise
    except Exception as ex:
        raise CliError("Error getting info: %s" % ex)

def status_cmd(obj):
    title = "Status of %s [class %s]" % (obj.name, obj.classname)
    print(title)
    print("=" * len(title))
    try:
        fn = get_obj_func(obj, 'get_status')
        info = fn(obj)
        if info:
            print_info(info)
        else:
            print("No status available")
    except CliError:
        raise
    except Exception as ex:
        raise CliError("Error getting status: %s" % ex)

@doc('define a new info command',
     module = 'cli',
     see_also = 'cli.new_status_command')
def new_info_command(cls, get_info, ctype = None, doc = None):
    """Define a new <cmd>info</cmd> command for a given object.
    <param>cls</param> is the class for which the <cmd>info</cmd> command
    should be registered. <param>get_info</param> is a function returning the
    information to be printed. <param>get_info()</param> should return a data
    structure of the following kind:
    <pre>
      [(SectionName1, [(DataName1.1, DataValue1.1),
                       (DataName1.2, DataValue1.2), ...]),
       (SectionName2, [(DataName2.1, DataValue2.1),
                       (DataName2.2, DataValue2.2), ...]),
       ...]</pre>

    Each section will be printed separately. Each piece of data will be printed
    on one line. If no sections are necessary, just provide <tt>None</tt> as
    the only section's name, followed by the list of data."""
    if doc == None:
        doc = ("Print detailed information about the configuration"
               " of the object.")
    new_command("info", info_cmd,
                [],
                type = ctype,
                short = "print information about the object",
                cls = cls,
                doc = doc)
    class_funcs.add(cls, 'get_info', get_info)

@doc('define a new status command',
     module = 'cli',
     see_also = 'cli.new_info_command')
def new_status_command(cls, get_status, ctype = None, doc = None):
    """Define a new <cmd>status</cmd> command for a given object.
    <param>cls</param> is the class for which the <cmd>status</cmd> command
    should be registered. <param>get_status</param> is a function returning the
    information to be printed. <param>get_status()</param> should return a data
    structure of the same kind as in <fun>new_info_command()</fun>."""
    if doc == None:
        doc = ("Print detailed information about the current status"
               " of the object.")
    new_command("status", status_cmd,
                [],
                type = ctype,
                short = "print status of the object",
                cls = cls,
                doc = doc)
    class_funcs.add(cls, 'get_status', get_status)

# This function is kindof unnecessary, really
def new_info_commands(cls, get_info, get_status):
    new_info_command(cls, get_info)
    new_status_command(cls, get_status)

_import_python_file_modules = {}
# import Python file contained in 'path', named 'filename' as a Python module
# called 'modname', if the Python module was not already imported
# before. Return the module object obtained or raise an exception.
def import_python_file(modname, filename, path):
    import imp
    abspath = os.path.abspath(os.path.join(path, filename))
    moduleobj = _import_python_file_modules.get(abspath)
    if moduleobj:
        return moduleobj
    moduleobj = sys.modules.get(modname)
    if moduleobj:
        # this could be problematic: for some reason, the ought-to-be
        # module-relative module was (probably) loaded using a normal
        # 'import'; be forgiving...
        oldmoduleobj = _import_python_file_modules.get(abspath)
        if oldmoduleobj:
            # this assertion could in theory trigger during regular
            # use, but the assumption is that it would be much more
            # harmful not to get an error when there is a possibility
            # you imported the wrong module
            assert moduleobj == oldmoduleobj
        else:
            _import_python_file_modules[abspath] = oldmoduleobj
        return moduleobj

    module_file = None
    imp.acquire_lock()
    try:
        (module_file, pathname, desc) = imp.find_module(filename, [path])
        moduleobj = imp.load_module(modname,
                                    module_file,
                                    pathname,
                                    desc)
        _import_python_file_modules[abspath] = moduleobj
    finally:
        imp.release_lock()
        if module_file:
            module_file.close()
    return moduleobj

def normalize_module_name(n):
    return n.replace('-', '_').replace('+', '__')

#
# Import commands/gcommands file for a module into Python
#

# An abstraction for this is needed in order to provide a correct
# traceback if either startup or simics_start exists but raises an
# ImportError
def module_exists(module):
    '''Return true if the given module seems to exist. Must be on the
    form x.y.z.'''
    import imp
    (simmod, pkg, mod) = module.split('.')
    try:
        (f, _, _) = imp.find_module(
            mod, getattr(__import__(simmod, level=0), pkg).__path__)
    except ImportError:
        return False
    else:
        f.close()
        return True

def import_raw_module_commands(module, glob):
    scriptmod = normalize_module_name(module)
    modname = "simmod.%s.%s" % (scriptmod, "simics_start" if glob
                                else "module_load")
    return importlib.import_module(modname)

def import_python_file_no_retval(modname, filename, path):
    import_python_file(modname, filename, path)

def module_relative_import(mod, submodule_of = None):
    """Loads Python module 'mod' from the 'python' subdirectory of the
    currently loading module's directory.

    If 'submodule_of' is set, name it as if it were a submodule of
    'submodule_of'. This only takes effect if the module file had not
    been loaded previously."""
    module = simics.CORE_get_module_path(get_last_loaded_module())
    modname = mod if submodule_of is None else '%s.%s' % (submodule_of, mod)
    python_dir = "python-py3"
    return import_python_file(modname, mod,
                              os.path.join(os.path.dirname(module), python_dir))

#
# Import command for a module and complete the initialisation
#
def __simics_import_module_commands(module):
    if not simics.CORE_module_has_commands(module, 0):
        return
    import_raw_module_commands(module, 0)

def check_for_gcommands():
    for name in [x[0] for x in simics.SIM_get_all_modules()]:
        if not simics.CORE_module_has_commands(name, 1):
            continue
        simics.CORE_push_current_loading_module(name)
        try:
            import_raw_module_commands(name, 1)
        except Exception:
            traceback.print_exc(file = sys.stderr)
            simics.SIM_log_error(
                conf.sim, 0,
                "Problem importing simmod.%s.simics_start:" % (name,)
                + " Unhandled Python exception")
        finally:
            simics.CORE_pop_current_loading_module()

def common_prefix(strs, ignore_case):
    """Returns the longest common prefix of the strings in strs.
    If ignoring case, the case of the prefix is undefined."""

    if not strs:
        return ''

    first = strs[0]
    maxl = min([ len(s) for s in strs ])
    i = 0
    while i < maxl:
        for j in range(1, len(strs)):
            if ignore_case:
                if first[i].lower() != strs[j][i].lower():
                    return first[:i]
            else:
                if first[i] != strs[j][i]:
                    return first[:i]
        i += 1
    return first[:i]

class _test_common_prefix(unittest.TestCase):
    def cp(self, strings, expected_prefix, ignore_case):
        actual = common_prefix(strings, ignore_case)
        if ignore_case:
            self.assertEqual(actual.lower(), expected_prefix.lower())
        else:
            self.assertEqual(actual, expected_prefix)

    def common_cases(self, ignore_case):
        self.cp(["abcd", "xyz", "abcd"], "", ignore_case)
        self.cp(["abcd", "acbd", "abcd"], "a", ignore_case)
        self.cp(["abcd", "abcd", "abcd"], "abcd", ignore_case)
        self.cp(["R2D2", "R2E2", "R2D3"], "R2", ignore_case)
        self.cp([], "", ignore_case)
        self.cp(["smurf"], "smurf", ignore_case)
        self.cp(["xy", "xyz", "xyz"], "xy", ignore_case)
        self.cp(["ab", "", "ab"], "", ignore_case)

    def test_case_sensitive(self):
        self.common_cases(False)
        self.cp(["ABCD", "AbCD", "ABcd"], "A", False)
        self.cp(["AbCD", "ABce", "aBcd"], "", False)
        self.cp(["XYZ"], "XYZ", False)

    def test_case_insensitive(self):
        self.common_cases(True)
        self.cp(["ABCD", "AbCD", "ABcd"], "abcd", True)
        self.cp(["AbCD", "ABce", "aBcd"], "abc", True)
        self.cp(["XYZ"], "xyz", True)

class simics_output_file(io.TextIOBase):
    def __init__(self, buffered):
        """Create new "file" for writing to the Simics console. If
        "buffered", output is not automatically flushed."""
        self.buffered = buffered

    def write(self, str):
        simics.CORE_python_write(str)
        if not self.buffered:
            simics.CORE_python_flush()

    def flush(self):
        super().flush()
        simics.CORE_python_flush()

    # Avoid using the simics module when this object is deleted, since that may
    # happen after the simics module has been destroyed if Python >= 3.13.
    # Instead make sure to call flush() before popping stdout.
    def __del__(self):
        super().flush()

class unbuffered_stderr:
    def write(self, str):
        sys.__stderr__.write(str)
        sys.__stderr__.flush()

    def flush(self):
        sys.__stderr__.flush()

    def fileno(self):
        return sys.__stderr__.fileno()

# do this last in case there is a load error in this file
push_stdout(simics_output_file(True), output_modes.formatted_text)
atexit.register(pop_stdout)
# on Windows, sys.__stderr__ is not correctly buffered and line
# buffering doesn't work at all, so make it completely unbuffered
# instead (on all platforms for conformity)
sys.stderr = unbuffered_stderr()

# force help() to use Simics stdout
pydoc.help = pydoc.Helper(sys.stdin, sys.stdout)

# disable the interactive use of the help() function; bug 6372
pydoc.help.getline = lambda prompt: None

def format_seconds(s):
    si_seconds = ["s", "ms", "\N{MICRO SIGN}s", "ns", "ps"]
    si = 0
    while s < 1.0 and si < len(si_seconds) - 1:
        # avoid floating point rounding errors - SIMICS-17483
        s = (1000000.0 * s) / 1000.0
        si += 1
    return str(s) + " " + si_seconds[si]

# Return a function suitable for passing to new_command when defining
# an enable or disable command. The argument is a class:
#
#     class Discombobulator:
#         def __init__(self, *the_args_from_new_command):
#             """Called with the args from new_command."""
#         def what(self):
#             """Return a string describing what is being enabled or
#             disabled."""
#             return "Discombobulator"
#         def is_enabled(self):
#             """Should return True if the discombobulator is enabled,
#             False if it's disabled, BOTH_ENABLED_AND_DISABLED if
#             it's both (e.g. if there is a set of discombobulators
#             that can be individually enabled and disabled, and the
#             set is currently empty), or None if it's neither (e.g.
#             if there is a set of discombobulators that can be
#             individually enabled and disabled, and the set currently
#             contains both enabled and disabled discombobulators)."""
#         def set_enabled(self, enable):
#             """Perform the actual enabling (if enable is true) or
#             disabling (if enable is false). Will only be called if
#             necessary."""
#         def done(self):
#             """Called at the end, whether or not it was necessary to
#             call .set_enabled."""
#
# If called interactively, the command will print messages such as
# "Discombobulator enabled." or "Discombobulator already enabled.". If
# the Discombobulator object has an .extra_msg property (which must be
# a string), it will be appended on a line of its own.
BOTH_ENABLED_AND_DISABLED = object()
def enable_cmd(Thing): return _able_cmd(Thing, True)
def disable_cmd(Thing): return _able_cmd(Thing, False)
def _able_cmd(Thing, enable):
    assert isinstance(enable, bool)
    assert callable(Thing.what)
    assert callable(Thing.is_enabled)
    assert callable(Thing.set_enabled)
    def f(*args):
        t = Thing(*args)
        verb = "enabled" if enable else "disabled"
        if t.is_enabled() in (enable, BOTH_ENABLED_AND_DISABLED):
            msg = "%s already %s." % (t.what(), verb)
        else:
            msg = "%s %s." % (t.what(), verb)
            t.set_enabled(enable)
            assert t.is_enabled() in (enable, BOTH_ENABLED_AND_DISABLED)
        getattr(t, "done", lambda: None)()
        extra_msg = getattr(t, "extra_msg", None)
        if extra_msg:
            msg += "\n" + extra_msg
        return command_return(msg)
    return f

def check_variable_name(name, cmd):
    if name == "0":
        raise CliError("Empty variable name (0) in \"%s\" command." % cmd)
    elif not re.match("([a-zA-Z_][a-zA-Z0-9_]*)", name):
        raise CliError("Illegal variable name \"%s\" in "
                       "\"%s\" command." % (name, cmd))
    elif name.startswith('__'):
        raise CliError("CLI variable name may not start with __")
