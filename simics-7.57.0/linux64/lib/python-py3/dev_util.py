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

import os
import unittest
import simics
from functools import wraps
from types import SimpleNamespace
from deprecation import DEPRECATED
import itertools
import functools


__all__ = [
    "Error", "InvalidBitfieldException", "RangeError", "MemoryError",

    "Bitfield", "Bitfield_LE", "Bitfield_BE",
    "AbstractRegister", "Register", "Register_LE", "Register_BE", "GRegister",
    "IRegister", "bank_regs",

    "Dev", "Iface", "iface", "Memory",

    "Layout", "Layout_LE", "Layout_BE",

    "value_to_tuple_be", "value_to_tuple_le", "tuple_to_value_be",
    "tuple_to_value_le",
]

# <add id="dev_util">
# <name>dev_util</name>
#
# A Python module for writing device model tests. Has three major
# parts: classes for accessing device registers, classes for writing
# device stubs, and classes for handling simulated memory and data
# structures in it. It also contains some auxiliary utilities.
#
# It uses the Simics API and can only be used by Python code running
# in Simics.
#
# </add>

# <add id="dev_util.Error">
# Baseclass of all exceptions specified in this module.
# </add>
class Error(Exception): pass

# <add id="dev_util.InvalidBitfieldException">
# Signals that a bitfield's parameters are invalid.
# </add>
class InvalidBitfieldException(Error): pass

# <add id="dev_util.RangeError">
# Signals that a value is out of range for a bitfield.
# </add>
class RangeError(Error):
    def __init__(self, msg, re = None):
        m = ""
        if re != None:
            (v, l, h) = re
            m = ("Value out of range - %s not in [%s,%s]: "
                 % (str(v), str(l), str(h)))
        Error.__init__(self, m + msg)

# fisketur[redef-builtin]
# <add id="dev_util.MemoryError">
# Signals that a memory operation failed.
# </add>
class MemoryError(Error): pass

# <add id="dev_util.Bitfield">
# Utility for bitfield manipulations.
# </add>
class Bitfield:

    # <add id="dev_util.Bitfield">
    # Constructor arguments:
    # <dl>
    # <dt>fields</dt>
    # <dd>a dict on the following format,
    # where sub-field is of type fields:
    # <pre>
    # {'field-name' : bit-number,
    #  'field-name' : (start-bit, stop-bit),
    #  'field-name' : (start-bit, sub-field)
    # }
    # </pre>
    # </dd>
    # <dt>ones</dt>
    # <dd>a bitmask that will be OR:ed in the complete bitfield value</dd>
    # <dt>little-endian</dt>
    # <dd>set to True for a little-endian bitorder field and False for
    #     big-endian bitorder fields</dd>
    # <dt>bits</dt>
    # <dd>the total size (in bits) of the fields; required by, as well as
    #     only allowed for, big-endian fields</dd>
    # <dt>**kwargs</dt>
    # <dd>as <arg>fields</arg>, but specified using keyword arguments</dd>
    # </dl>
    # </add>
    def __init__(self, fields=None, ones=0, little_endian=True,
                 bits=None, **kwargs):
        if not little_endian:
            # Need to know our size in big-endian mode
            assert bits

        if fields is None and not kwargs:
            raise TypeError('__init__() missing fields argument(s)')
        if fields and kwargs:
            raise TypeError(
                "keyword arguments not allowed when 'fields' argument is used")

        fields = self.mk_bitfield_map({**(fields or {}), **kwargs})

        # Create a dictionary consisting of {field : (start-bit, end-bit)}
        self.field_ranges = {}
        for key in fields:
            val = fields[key]
            if isinstance(val, int):
                val = (val, val)

            assert isinstance(val, tuple) and len(val) == 2

            self.field_ranges[key] = (min(val[0], val[1]), max(val[0], val[1]))

        if not little_endian:
            for key in self.field_ranges:
                (start, stop) = self.field_ranges[key]
                self.field_ranges[key] = (bits - 1 - stop, bits - 1 - start)

        # Verify there are no overlaps
        overlap = {}
        for (key, (start, end)) in list(self.field_ranges.items()):
            for i in range(start, end + 1):
                if i in overlap:
                    msg = ('Overlap in bitfield. Fields %s and %s overlap'
                           % (key, overlap[i]) + " at bit %s" % i)
                    raise InvalidBitfieldException(msg)
                overlap[i] = key

        self.ones = ones

    # <add id="dev_util.Bitfield.mk_bitfield_map">
    # Convert a nested layout type to a map suitable for construction
    # of a dev_util.Bitfield object.
    # </add>
    def mk_bitfield_map(self, m, prefix = "", oset = 0):
        bfm = {}

        for (k, v) in list(m.items()):
            if not isinstance(v, tuple):
                bfm[prefix + k] = v + oset
                continue

            if isinstance(v[1], int):
                bfm[prefix + k] = (v[0] + oset, v[1] + oset)
                continue

            # We have a nested map
            rbfm = self.mk_bitfield_map(v[1], prefix + k + "_", oset + v[0])
            for (kk, vv) in list(rbfm.items()):
                bfm[kk] = vv

        return bfm

    def _expand_key(self, prefix, value):
        if isinstance(value, dict):
            for (k, v) in value.items():
                if isinstance(k, str):
                    yield from self._expand_key(f'{prefix}.{k}', v)
                else:
                    yield from self._expand_key(f'{prefix}[{k}]', v)
        elif isinstance(value, list):
            for (i, v) in enumerate(value):
                yield from self._expand_key(f'{prefix}[{i}]', v)
        else:
            yield (prefix, value)

    # <add id="dev_util.Bitfield.value"> Returns the value of the
    # fields given by **kwargs. For example, pass <tt>foo=5</tt> to
    # return the value when field <tt>"foo"</tt> is 5. If the value is
    # a list or dict rather than an integer, then a field array is
    # assumed; e.g. <tt>foo=[1,2]</tt> is a shorthand for setting
    # field <tt>"foo[0]"</tt> to 1 and field <tt>"foo[1]"</tt> to 2,
    # and <tt>foo={1:4}</tt> is a shorthand for setting field
    # <tt>"foo[1]"</tt> to 4.
    #
    # An optional positional argument can be
    # supplied, to provide the values of bits not covered by the given
    # fields.
    # </add>
    def value(self, *args, **kwargs):
        # TODO: in python 3.9 we can change arg syntax to
        # (self, value=0, /, **kwargs)
        if len(args) == 0:
            value = 0
        elif len(args) == 1:
            [value] = args
        else:
            raise TypeError('unexpected positional arg')
        for (k, v) in kwargs.items():
            for (fname, fval) in self._expand_key(k, v):
                (start, stop) = self.field_ranges[fname]
                bits = stop + 1 - start
                if not (0 <= fval < 1 << bits):
                    raise RangeError(f"Value to large for bitfield '{fname}'.",
                                     (fval, 0, (1 << bits) - 1))

                # Insert field into final value
                value &= ~(((1 << bits) - 1) << start)
                value |= fval << start
        return value | self.ones

    # <add id="dev_util.Bitfield.mask">
    # Returns a mask from the fields in dict.
    # </add>
    def mask(self, **dict):
        mask = 0
        for key in dict:
            (start, stop) = self.field_ranges[key]
            bits = stop + 1 - start

            mask |= ((1 << bits) - 1) << start
        return mask

    # <add id="dev_util.Bitfield.fields">
    # Returns a dict consisting of all fields and their values,
    # taken from the value argument.
    # </add>
    def fields(self, value):
        return dict((key,
                     (value & ((1 << (ranges[1] + 1)) - 1)) >> ranges[0])
                    for (key, ranges) in self.field_ranges.items())

# <add id="dev_util.Bitfeild_LE">
# Little-endian bitfield.
# </add>
class Bitfield_LE(Bitfield):
    # <add id="dev_util.Bitfield_LE">
    # Constructor arguments:
    # <dl>
    # <dt>fields</dt>
    # <dd>a dict on the following format,
    # where sub-field is of type fields:
    # <pre>
    # {'field-name' : bit-number,
    #  'field-name' : (start-bit, stop-bit),
    #  'field-name' : (start-bit, sub-field)
    # }
    # </pre>
    # </dd>
    # <dt>ones</dt>
    # <dd>a bitmask that will be OR:ed in the complete bitfield value</dd>
    # <dt>**kwargs</dt>
    # <dd>as <arg>fields</arg>, but specified using keyword arguments</dd>
    # </dl>

    # </add>
    def __init__(self, fields=None, ones=0, **kwargs):
        Bitfield.__init__(self, fields, ones, little_endian=True, **kwargs)

# <add id="dev_util.Bitfield_BE">
# Bit-endian bitfield.
# </add>
class Bitfield_BE(Bitfield):
    # <add id="dev_util.Bitfield_BE">
    # Constructor arguments:
    # <dl>
    # <dt>fields</dt>
    # <dd>a dict on the following format,
    # where sub-field is of type fields:
    # <pre>
    # {'field-name' : bit-number,
    #  'field-name' : (start-bit, stop-bit),
    #  'field-name' : (start-bit, sub-field)
    # }
    # </pre>
    # </dd>
    # <dt>ones</dt>
    # <dd>a bitmask that will be OR:ed in the complete bitfield value</dd>
    # <dt>bits</dt>
    # <dd>the total size (in bits) of the fields; required by big-endian
    #     fields</dd>
    # <dt>**kwargs</dt>
    # <dd>as <arg>fields</arg>, but specified using keyword arguments</dd>
    # </dl>
    # </add>
    def __init__(self, fields=None, ones=0, bits=None, **kwargs):
        assert bits != None
        Bitfield.__init__(self, fields, ones, little_endian=False,
                          bits=bits, **kwargs)

class TestBitfield(unittest.TestCase):
    def test_le(self):
        bf = Bitfield_LE({'a': 0, 'b': (31, 24)}, ones=0x0f000f00)
        self.assertEqual(bf.value(), 0x0f000f00)
        # bits in 'ones' override explicitly given field values
        self.assertEqual(bf.value(a=1, b=0xaa), 0xaf000f01)
        with self.assertRaises(KeyError):
            bf.value(c=0)
        bf.value(b=255)
        with self.assertRaises(RangeError):
            bf.value(b=256)
        bf.value(b=0)
        with self.assertRaises(RangeError):
            bf.value(b=-1)
        # value from positional arg overrides bits not covered by explicit
        # fields, but are overridden by bits in 'ones'.
        self.assertEqual(bf.value(0x5555555555, b=0xaa), 0x55af555f55)

    def test_be(self):
        with self.assertRaises(AssertionError):
            # missing 'bits'
            Bitfield_BE({'a': 0, 'b': (24, 31)}, ones=0x00f000f0)
        bf = Bitfield_BE({'a': 0, 'b': (24, 31)}, ones=0x00f000f0, bits=32)
        self.assertEqual(bf.value(a=1, b=0xaa), 0x80f000fa)

    def test_value_expansion(self):
        bf = Bitfield_LE({'a[0][0]': (3, 0),
                          'a[0][1]': (7, 4),
                          'a[0][2]': (11, 8),
                          'a[1][0]': (15, 12),
                          'a[1][1]': (19, 16),
                          'a[1][2]': (23, 20),
                          'b.c':     (27, 24)})
        self.assertEqual(bf.value(a={0: {0: 1, 2: 2},
                                     1: {1: 3, 2: 4}}),
                         0x0430201)
        self.assertEqual(bf.value(a=[[1,2], [4,5,6]]),
                         0x0654021)
        self.assertEqual(bf.value(a=[{0: 1, 2: 2}, {1: 3, 2: 4}], b={'c': 5}),
                         0x5430201)
        self.assertEqual(bf.value(a={1: [4, 5]}),
                         0x0054000)

class LegacyField:
    '''Forward compatibility class for bank_regs-style access
    (reg.field.NAME.read()) within legacy Register classes
    '''
    def __init__(self, read_write_reg, lsb, bits):
        assert lsb >= 0, lsb
        assert bits > 0, bits
        self.lsb = lsb
        self.bits = bits
        self.reg = read_write_reg
    def read(self):
        return (self.reg.read() >> self.lsb) & ((1 << self.bits) - 1)
    def __setattr__(self, attr, value):
        if attr == "val":
            # .val accessor only available through bank_regs(), not when
            # using the legacy Register_LE construct
            raise AttributeError(
                f"AttributeError: '{type(self)}' object has no attribute 'val'")
        super().__setattr__(attr, value)

class READ: '''Singleton value passed as write(READ, name=val), denoting that
read() should be called to retrieve the base value'''
READ = READ()
class VAL:  '''Singleton value passed as write(VAL, name=val), denoting that
.val should be read to retrieve the base value'''
VAL = VAL()

# <add id="dev_util.AbstractRegister">
# Abstract register class.
#
# This class handles generic register stuff, like bitfield mapping
# and value construction/deconstruction. It depends on a subclass to
# implement the backend for data storage.
#
# Subclasses are expected to implement two functions:
#
# <dl>
# <dt>raw_read(self)</dt>
# <dd>should return a byte string from storage</dd>
# <dt>raw_write(self, bytes)</dt>
# <dd>should write the <var>bytes</var> byte string to storage</dd>
# </dl>
#
# Optionally, a bitfield can be applied to a register. For such a register,
# a specific field can be read through <tt>reg.field.FIELDNAME.read()</tt>. The
# <fun>write()</fun> method also has support for bitfields. Please see the
# documentation for <fun>write()</fun> for more information.
#
# There is an alternative deprecated shorthand for accessing fields:
# <tt>reg.FIELDNAME</tt> triggers a read that filters out the given
# field, and similarly, <tt>reg.FIELDNAME = value</tt> reads the
# field, adjusts the given field, and writes back the value. This
# syntax is deprecated, because it is not consistent with the API
# exposed by register objects that both support accesses with and
# without side-effects.
#
# </add>
class AbstractRegister:
    tuple_based = True

    # <add id="dev_util.AbstractRegister">
    # Constructor arguments:
    # <dl>
    # <dt>size</dt>
    # <dd>the size in bytes of the register</dd>
    # <dt>bitfield</dt>
    # <dd>optional, if set should be an instance of Bitfield</dd>
    # <dt>little_endian</dt>
    # <dd>should be set to True for a little-endian byte-order
    #     register, or False for a big-endian register</dd>
    # </dl>
    # </add>
    def __init__(self, size=4, bitfield=None,
                 little_endian=True):

        # implicitly create bitfield instance. The main purpose of
        # this is to make it easier to create device-specific register
        # subclasses with standard settings for endianness etc.
        if bitfield != None and isinstance(bitfield, tuple):
            (fields, ones, bf_little_endian) = bitfield
            # allow (None, 0, *) <=> None
            if (fields == None):
                bitfield = None
            else:
                bitfield = Bitfield(fields, bits = size * 8, ones = ones,
                                    little_endian = bf_little_endian)

        self.size = size                    # Size of register, in bytes
        self.little_endian = little_endian  # Byte order is little endian?

        # Verify the bitfield field names and bit ranges
        # Do this before saving the bitfield.
        if bitfield:
            for fname, (msb, lsb) in bitfield.field_ranges.items():
                if (msb + 1) > size * 8:
                    raise InvalidBitfieldException(
                        f"Bitfield '{fname}' @ [{msb}:{lsb}] does not fit in"
                        + f" {size}-byte register")
                if fname in self.__dict__:
                    raise InvalidBitfieldException(
                        f"Bitfield named '{fname}' is not allowed since "
                        + "it is an internal attribute.")

        self.bitfield = bitfield            # Bitfield specification
        self.endian = 'little' if self.little_endian else 'big'

        if bitfield and 'field' not in bitfield.field_ranges:
            self.field = _unflatten([
                (split_name(fname),
                 LegacyField(self, lsb, msb + 1 - lsb))
                for (fname, (lsb, msb)) in (
                        bitfield.field_ranges.items())])

    def __dir__(self):
        dir = super(AbstractRegister, self).__dir__()
        if self.bitfield:
            dir.extend(self.bitfield.field_ranges)
        return dir
    def __getattribute__(self, attr):
        '''Allow user to read a field using normal attribute accesses'''
        # optimized for the common case, which is method lookup
        getattribute = super(AbstractRegister, self).__getattribute__
        try:
            return getattribute(attr)
        except AttributeError:
            bf = getattribute('bitfield')
            if bf and attr in bf.field_ranges:
                return bf.fields(self.read())[attr]
            raise

    def __setattr__(self, attr, value):
        '''Allow user to write a field using normal attribute accesses'''
        try:
            bf = self.bitfield
        except AttributeError:
            bf = None
        if attr == 'val' and 'val' not in bf.field_ranges:
            # Catch when a user accustomed to BankRegister tries to set .val;
            # this is not supported in Register objects.
            raise AttributeError(
                f"AttributeError: '{type(self)}' object has no attribute 'val'")

        if not bf or attr not in bf.field_ranges:
            super(AbstractRegister, self).__setattr__(attr, value)
        else:
            self.write(READ, **{attr : value})

    # <add id="dev_util.AbstractRegister.fields">
    # Shortcut to read the bitfield representation of a device register.
    # </add>
    def fields(self):
        return self.bitfield.fields(self.read())

    # <add id="dev_util.AbstractRegister.read">
    # Read value.
    # </add>
    def read(self):
        if self.tuple_based:
            return int.from_bytes(self.raw_read(), self.endian)
        else:
            return self.raw_read()

    # <add id="dev_util.AbstractRegister.write">
    # Write value. The value will be truncated to the register size.
    #
    # You can either pass a single integer, or pass the fields as
    # arguments, i.e., <tt>write(field0=1, field1=23)</tt>. For field
    # arrays, the syntax <tt>write(field=[1,23])</tt> or
    # <tt>write(field={0: 1, 1: 23})</tt> can be used to set the fields named
    # <tt>field[0]</tt> and <tt>field[1]</tt>.
    #
    # If only a subset of fields is given, a positional arg should
    # also be passed for the base value, which defines what to write to
    # remaining bits. The value READ denotes that the <tt>read()</tt> method is
    # called to retrieve the base value.
    # </add>
    def write(self, *args, **fields):
        if len(args) == 0:
            # Reuse old register value by default
            val = self.read()
        elif len(args) == 1:
            [val] = args
            if val is READ:
                val = self.read()
            elif val is VAL:
                raise Error(f'write(VAL) not supported in {type(self)}')
        else:
            raise TypeError(
                'write() takes at most 2 argument (%d given)'
                % (len(args) + 1,))
        # Truncate to register size
        val &= ((1 << (8 * self.size)) - 1)
        # Set bitfield values
        if self.bitfield is not None:
            val = self.bitfield.value(val, **fields)

        if self.tuple_based:
            self.raw_write(val.to_bytes(
                self.size, 'little' if self.little_endian else 'big'))
        else:
            self.raw_write(val)

class TestAbstractRegisterNonTuple(unittest.TestCase):
    def testInvalidBitfield(self):
        # Test that it is impossible to create a register with a bitfield name
        # that clashes with internal variable names.
        self.assertRaises(InvalidBitfieldException,
                          AbstractRegister,
                          size=4, bitfield=Bitfield_LE({'size' : 0}),
                          little_endian=True)
        # Test that it's impossible to create a register with a
        # bitfield that doesn't fit in the register.
        self.assertRaises(InvalidBitfieldException,
                          AbstractRegister,
                          size=4, bitfield=Bitfield_LE({'bad': 32}),
                          little_endian=True)

    class TestRegister(AbstractRegister):
        tuple_based = False
        writes = []
        def raw_read(self):
            return 0xdeadbeef
        def raw_write(self, value):
            self.writes.append(value)
    def test_access(self):
        def assert_and_pop(ls, value):
            self.assertEqual(ls, value)
            del ls[:]
        self.assertEqual(self.TestRegister().read(), 0xdeadbeef)
        self.TestRegister().write()
        assert_and_pop(self.TestRegister.writes, [0xdeadbeef])
        self.TestRegister().write(0x11223344)
        assert_and_pop(self.TestRegister.writes, [0x11223344])
        self.TestRegister(size=1).write()
        assert_and_pop(self.TestRegister.writes, [0xef])
        self.TestRegister(size=1).write(0x11223344)
        assert_and_pop(self.TestRegister.writes, [0x44])
        bf = Bitfield_LE({'a': 0, 'b': (31, 24)})
        self.assertEqual(self.TestRegister(bitfield=bf).fields(),
                         {'a': 1, 'b': 0xde})
        self.TestRegister(bitfield=bf).write(a=0,b=0)
        assert_and_pop(self.TestRegister.writes, [0xadbeee])
        self.TestRegister(bitfield=bf).write(0xf0f0f0f0, a=1,b=0xcc)
        assert_and_pop(self.TestRegister.writes, [0xccf0f0f1])
        # convenience accessors
        self.assertEqual(self.TestRegister(bitfield=bf).a, 1)
        self.assertEqual(self.TestRegister(bitfield=bf).b, 0xde)
        self.TestRegister(bitfield=bf).b = 0x11
        assert_and_pop(self.TestRegister.writes, [0x11adbeef])
        self.assertIn('a', dir(self.TestRegister(bitfield=bf)))
        self.assertIn('b', dir(self.TestRegister(bitfield=bf)))

        # bank_regs style read/write access works
        farr = self.TestRegister(bitfield=Bitfield_LE(
            {'a.b[0]': (7, 0), 'a.b[1]': (15, 8)}))
        b0 = farr.field.a.b[0]
        self.assertEqual(b0.read(), 0xef)
        farr.write(READ, a={'b': [0x11, 0x22]})
        self.assertEqual(self.TestRegister.writes, [0xdead2211])
        del self.TestRegister.writes[:]
        # bank_regs style val/set does not work
        def nothing(x): pass
        with self.assertRaises(AttributeError):
            nothing(farr.set)
        with self.assertRaises(AttributeError):
            nothing(farr.val)
        with self.assertRaises(AttributeError):
            farr.val = 0
        with self.assertRaises(Error):
            farr.write(VAL)
        with self.assertRaises(AttributeError):
            nothing(b0.val)
        with self.assertRaises(AttributeError):
            b0.val = 0
        with self.assertRaises(AttributeError):
            nothing(b0.write)

class TestAbstractRegister(unittest.TestCase):
    class TestRegister(AbstractRegister):
        writes = []
        def raw_read(self):
            return b'\xef\xbe\xad\xde'
        def raw_write(self, value):
            self.writes.append(value)
    def test_access(self):
        def assert_and_pop(ls, value):
            self.assertEqual(ls, value)
            del ls[:]

        self.assertEqual(self.TestRegister().read(), 0xdeadbeef)
        self.TestRegister().write()
        # value is 0xdeadbeef, this is its little-endian representation
        assert_and_pop(self.TestRegister.writes, [b'\xef\xbe\xad\xde'])
        self.TestRegister(little_endian=False).write()
        self.assertEqual(self.TestRegister(little_endian=False).read(),
                         0xefbeadde)
        # value is 0xefbeadde, this is its big-endian representation
        assert_and_pop(self.TestRegister.writes, [b'\xef\xbe\xad\xde'])

        self.TestRegister().write(0x11223344)
        assert_and_pop(self.TestRegister.writes, [b'\x44\x33\x22\x11'])
        self.TestRegister().write(-6)
        assert_and_pop(self.TestRegister.writes, [b'\xfa\xff\xff\xff'])

def wrap_register_init(init):
    '''Given a Register.__init__ function taking bank and offset args,
    return a function that also accepts the compatibility signature
    with one tuple argument (obj, port|fun, offset) instead of two
    arguments. We use a wrapper indirection because it would otherwise
    be hard to make the offset arg conditionally positional, without messing up
    the signature
    '''
    @wraps(init)
    def wrapped(self, *args, **kwargs):
        if isinstance(args[0], tuple):
            (obj, port_or_function, ofs) = args[0]
            if isinstance(port_or_function, int):
                port = None
                function = port_or_function
            else:
                port = port_or_function
                function = 0
                if not isinstance(port, str):
                    # we used to permit (but not document) the format
                    # (obj, (port, index), offset)
                    (name, index) = port
                    port = "%s[%d]" % (name, index)
            if not simics.SIM_c_get_port_interface(obj, 'io_memory', port):
                raise Exception(
                    'Legacy format for Register constructor arguments'
                    + ' unsupported for banks implementing the'
                    + ' transaction interface. Please change'
                    + ' Register((obj, "bankname", offset))'
                    + ' into Register(obj.bank.bankname, offset)')
            init(self, obj, (port, function, ofs), *args[1:], **kwargs)
        else:
            init(self, *args, **kwargs)
    return wrapped

# <add id="dev_util.Register">
# This class allows you to easily access a device register.
# </add>
class Register(AbstractRegister):
    @wrap_register_init
    # <add id="dev_util.Register">
    # The bank argument is normally the bank object. However, for
    # backward compatibility it can also be a tuple (obj, bank, ofs);
    # in this case the <param>offset</param> argument should be left
    # out. The tuple denotes:
    # <dl>
    # <dt>obj</dt>
    # <dd>the (simics) object implementing the register</dd>
    # <dt>bank</dt>
    # <dd>the port-name or function number of the bank containing the
    #     register (function 0 if omitted).</dd>
    # <dt>offset</dt>
    # <dd>the register offset in said bank</dd>
    # </dl>
    # The tuple syntax was useful in old Simics versions where
    # banks were not separate objects. It should be avoided in new versions.
    #
    # The initiator argument denotes the initiator of transactions
    # accessing the register.
    # See the AbstractRegister documentation for information about the rest
    # of the parameters.
    # </add>
    def __init__(self, bank, offset, size=4, bitfield=None,
                 little_endian=True, initiator=None):

        super(Register, self).__init__(size=size, bitfield=bitfield,
                                       little_endian=little_endian)

        self.obj = bank
        if isinstance(offset, tuple):
            # internal back-door to let legacy glue express function
            # and port
            (port, function, offset) = offset
            if function:
                # legacy function number: use legacy memop so the
                # function can be passed in a map_info_t. This is
                # inconvenient, but doing it through transaction_t
                # would be worse (requires a memory-space indirection)
                self.ofs = offset
                map_info = simics.map_info_t(
                    base = 0,
                    start = 0,
                    length = size,
                    function = function)
                read_memop = simics.generic_transaction_t()
                simics.SIM_set_mem_op_initiator(
                    read_memop, simics.Sim_Initiator_CPU, initiator)
                simics.SIM_set_mem_op_physical_address(read_memop, offset)
                simics.SIM_set_mem_op_type(read_memop, simics.Sim_Trans_Load)
                io_mem_iface = simics.SIM_get_port_interface(
                    bank, 'io_memory', port)
                def raw_read():
                    try:
                        return simics.VT_io_memory_operation(
                            bank, io_mem_iface, read_memop, b'\0' * size,
                            map_info)
                    except simics.SimExc_Memory as exc:
                        raise MemoryError(f'register read failed: {exc}')
                self.raw_read = raw_read
                write_memop = simics.generic_transaction_t()
                simics.SIM_set_mem_op_initiator(
                    write_memop, simics.Sim_Initiator_CPU, initiator)
                simics.SIM_set_mem_op_physical_address(write_memop, offset)
                simics.SIM_set_mem_op_type(write_memop, simics.Sim_Trans_Store)
                def raw_write(value):
                    try:
                        simics.VT_io_memory_operation(
                            bank, io_mem_iface, write_memop, value, map_info)
                    except simics.SimExc_Memory as exc:
                        raise MemoryError('register write failed: ' + str(exc))
                self.raw_write = raw_write
        else:
            port = None

        self.ofs = offset
        mt = simics.SIM_new_map_target(bank, port, None)
        self.read_transaction = simics.transaction_t(read=True, size=size,
                                                     initiator=initiator)
        self.write_transaction = simics.transaction_t(read=False, size=size,
                                                      initiator=initiator)
        self._update_accessors(mt, self.ofs,
                               self.read_transaction, self.write_transaction)
        # expose RegisterBank fields
        if self.bitfield is None or 'offset' not in self.bitfield.field_ranges:
            self.offset = offset
        if self.bitfield is None or 'bank' not in self.bitfield.field_ranges:
            self.bank = bank

    # Performance hack: Avoid expensive dictionary lookups by
    # creating method-like functions that only reference locals
    def _update_accessors(self, mt, offset,
                          read_transaction, write_transaction):
        issue = simics.SIM_issue_transaction
        ok = simics.Sim_PE_No_Exception
        zeros = b'\0' * read_transaction.size
        # <add id="dev_util.Register.raw_read">
        # Read raw data from the register.
        # </add>
        def raw_read():
            read_transaction.data = zeros
            exc = issue(mt, read_transaction, offset)
            if exc != ok:
                raise MemoryError(f'register read failed: {exc}')
            return read_transaction.data

        self._raw_read = raw_read

        # <add id="dev_util.Register.raw_write">
        # Write raw data to the register.
        # </add>
        def raw_write(value):
            write_transaction.data = value
            exc = issue(mt, write_transaction, offset)
            if exc != ok:
                raise MemoryError(f'register write failed: {exc}')

        self._raw_write = raw_write

    def raw_read(self):
        return self._raw_read()

    def raw_write(self, val):
        return self._raw_write(val)

# <add id="dev_util.Register_LE">
# Little-endian device register.
# </add>
class Register_LE(Register):

    # <add id="dev_util.Register_LE">
    # All arguments have the same semantics as in dev_util.Register.
    # </add>
    @wrap_register_init
    def __init__(self, bank, offset, size=4, bitfield=None, initiator=None):
        super(Register_LE, self).__init__(
            bank, offset, size, bitfield, little_endian=True,
            initiator=initiator)

# <add id="dev_util.Register_BE">
# Big-endian device register.
# </add>
class Register_BE(Register):

    # <add id="dev_util.Register_BE">
    # All arguments have the same semantics as in dev_util.Register.
    # </add>
    @wrap_register_init
    def __init__(self, bank, offset, size=4, bitfield=None, initiator=None):
        super(Register_BE, self).__init__(
            bank, offset, size, bitfield, little_endian=False,
            initiator=initiator)

class ViewRegister(AbstractRegister):
    '''Perform an inquiry read based directly through the register_view
    interface'''
    tuple_based = False

    def __init__(self, bank, num, size=4, bitfield=None):
        self.bank = bank
        self._rv = bank.iface.register_view
        self._num = num
        super(ViewRegister, self).__init__(size=size, bitfield=bitfield)
    def raw_read(self):
        return self._rv.get_register_value(self._num)
    def raw_write(self, value):
        self._rv.set_register_value(self._num, value)
    @property
    def name(self):
        return self._rv.register_info(self._num)[0]

def split_name(name):
    ret = []
    for group in name.split('.'):
        (g, *indices) = group.split('[')
        assert g
        indices = tuple(int(index[:-1]) for index in indices)
        ret.append((g, indices))
    return ret

class TestSplitName(unittest.TestCase):
    def test(self):
        self.assertEqual(split_name('x'), [('x', ())])
        self.assertEqual(split_name('x.y'), [('x', ()), ('y', ())])
        self.assertEqual(split_name('x[1]'), [('x', (1,))])
        self.assertEqual(split_name('aa[1].bb.c[2][3].d'),
                         [('aa', (1,)), ('bb', ()), ('c', (2, 3)), ('d', ())])

class Field:
    '''One field, as created by bank_regs()'''
    def __init__(self, reg, lsb, bits, name):
        assert lsb >= 0, lsb
        assert bits > 0, bits
        # reg.val getattr/setattr are also required, but a hasattr assertion
        # is too expensive (would trigger a device access)
        assert hasattr(reg, 'read')
        self.lsb = lsb
        self.bits = bits
        self.reg = reg
        self.name = name
    def read(self):
        return (self.reg.read() >> self.lsb) & ((1 << self.bits) - 1)
    @property
    def val(self):
        return (self.reg.val >> self.lsb) & ((1 << self.bits) - 1)
    @val.setter
    def val(self, value):
        old = self.reg.val
        mask = ((1 << self.bits) - 1) << self.lsb
        new_val = (old & ~mask) | ((value << self.lsb) & mask)
        self.reg.val = new_val

class BankRegister:
    '''One register, as created by bank_regs()'''
    def __init__(self, read_write_reg, get_set_reg):
        assert read_write_reg.size == get_set_reg.size
        assert (
            read_write_reg.bitfield is get_set_reg.bitfield is None
            or read_write_reg.bitfield.field_ranges
            == get_set_reg.bitfield.field_ranges)
        self.read_write_reg = read_write_reg
        self.get_set_reg = get_set_reg
        # fields decoded: {ident: [(coord, lsb, bitsize), ...]}
        # where "foo[3].bar" gives ident="foo" and coord=[3, "bar"]
        if read_write_reg.bitfield:
            coords = [
                (split_name(fname),
                 Field(self, lsb, msb + 1 - lsb, fname))
                for (fname, (lsb, msb)) in (
                        read_write_reg.bitfield.field_ranges.items())]
            field = _unflatten(coords)
            self.field = field
            assert field.__dict__.keys().isdisjoint(dir(self))

    def read(self):
        return self.read_write_reg.read()
    def write(self, *args, **kwargs):
        if args:
            [val] = args
            if val is VAL:
                args = (self.val,)
        else:
            # only complain if we are providing too few kwargs;
            # if we provide too many or some incorrect kwargs,
            # then the bitfield will provide a better error message
            if len(self.bitfield.field_ranges) > sum(
                    1 for (k, v) in kwargs.items()
                    for _ in self.bitfield._expand_key(k, v)):
                if os.environ.get('DISABLE_DEV_UTIL_LEGACY'):
                    raise Error('write() requires either a positional value arg'
                                + ' or one keyword arg for every field')
        self.read_write_reg.write(*args, **kwargs)
    def set(self, *args, **kwargs):
        self.get_set_reg.write(*args, **kwargs)
    @property
    def val(self):
        return self.get_set_reg.read()
    @val.setter
    def val(self, value):
        self.get_set_reg.write(value)

    @property
    def bank(self):
        return self.get_set_reg.bank
    @property
    def size(self):
        return self.read_write_reg.size
    @property
    def name(self):
        return self.get_set_reg.name
    @property
    def offset(self):
        return self.read_write_reg.ofs
    @property
    def bitfield(self):
        return self.read_write_reg.bitfield
    def __setattr__(self, attr, value):
        '''Temporary hack to permit the legacy reg.FIELD=value syntax'''
        field = getattr(self, 'field', None)
        if field and hasattr(field, attr):
            DEPRECATED(simics.SIM_VERSION_7,
                       f'The "reg.{attr} = {value}" syntax is deprecated.',
                       f'Use "reg.write(READ, {attr}={value})" instead.')
            if os.environ.get('DISABLE_DEV_UTIL_LEGACY'):
                raise Error(f'please change "reg.{attr} = {value}"'
                            f' into "reg.write(READ, {attr}={value})"')
            self.write(READ, **{attr: value})
        super().__setattr__(attr, value)
    def __getattr__(self, attr):
        try:
            field = self.__getattribute__('field')
        except AttributeError:
            field = None
        if hasattr(field, attr):
            DEPRECATED(simics.SIM_VERSION_7,
                       f'The "reg.{attr}" syntax is deprecated.',
                       f'Use .field.{attr}.read() instead.')
            if os.environ.get('DISABLE_DEV_UTIL_LEGACY'):
                raise Error(f'Please replace .{attr} with .field.{attr}.read()')
            return getattr(field, attr).read()

        return self.__getattribute__(attr)

def _unflatten(flat):
    '''Given a list of pairs ([("x", (4, 5)), ("y", ())], obj),
    return an object o such that o.x[4][5].y == obj'''
    if len(flat) == 1:
        [(keys, val)] = flat
        if not keys:
            # leaf
            return val
    groups = {}
    for (keys, val) in flat:
        assert keys # cannot have both ("a", x) and ("a.b", y)
        (group, coord) = keys[0]
        groups.setdefault(group, {}).setdefault(coord, []).append(
            (keys[1:], val))
    ret = {}
    for (group, coords) in groups.items():
        if len(coords) == 1:
            [(coord, sub)] = coords.items()
            if not coord:
                ret[group] = _unflatten(sub)
                continue
        index_dict = {}
        for (coord, sub) in coords.items():
            # there can only be one instance if coords is empty,
            # because we can't both have "group[0]" and
            # "group.reg". This brings us to the 'continue' above
            assert coord
            d = index_dict
            for index in coord[:-1]:
                d = d.setdefault(index, {})
            d[coord[-1]] = _unflatten(sub)
        ret[group] = index_dict
    return SimpleNamespace(**ret)

class TestUnflatten(unittest.TestCase):
    def test(self):
        self.assertEqual(_unflatten([((), b'x')]), b'x')
        o = _unflatten([([('a', ())], b'0'),
                            ([('b', ())], b'1')])
        self.assertEqual((o.a, o.b), (b'0', b'1'))
        o = _unflatten([([('a', (1, 2))], b'0'),
                            ([('a', (0, 3))], b'1')])
        self.assertEqual((o.a[1][2], o.a[0][3]), (b'0', b'1'))
        o = _unflatten([
            ([('g', (1, 2)), ('g', ()), ('r1', ())], b'1'),
            ([('g', (1, 2)), ('g', ()), ('r2', ())], b'2')])
        self.assertEqual(o.g[1][2].g.r1, b'1')
        self.assertEqual(o.g[1][2].g.r2, b'2')

# Extract the first name segment of a register name.
# Carefully optimized for speed, since this is one of few operations
# done eagerly for all registers in a bank. Alternatives based on
# str.index, str.split or re.match are all slower.
def _find_stem(s):
    i1 = s.find('[')
    i2 = s.find('.')
    if i1 != -1:
        if i2 != -1:
            return s[:min(i1, i2)]
        else:
            return s[:i1]
    else:
        return s if i2 == -1 else s[:i2]

class TestFindStem(unittest.TestCase):
    def test(self):
        self.assertEqual(_find_stem(''), '')
        self.assertEqual(_find_stem('a'), 'a')
        self.assertEqual(_find_stem('abc.def[3][4]'), 'abc')
        self.assertEqual(_find_stem('abc[3].def[4]'), 'abc')
        self.assertEqual(_find_stem('def.abc'), 'def')
        self.assertEqual(_find_stem('abc[def]'), 'abc')

class LazyNamespace(SimpleNamespace):
    def __init__(self, **kwargs):
        lazy = {}
        eager = {}
        for (k, v) in kwargs.items():
            if callable(v):
                lazy[k] = v
                # to preserve iteration order
                eager[k] = None
            else:
                eager[k] = v
        if lazy:
            super().__init__(__lazy__=lazy, **eager)
        else:
            super().__init__(**eager)
    def __getattribute__(self, attr):
        d = super().__dict__
        lazy = d.get('__lazy__')
        if lazy is not None and attr in lazy:
            d[attr] = lazy.pop(attr)()
            if not lazy:
                del d['__lazy__']
        return super().__getattribute__(attr)
    @property
    def __dict__(self):
        d = super().__dict__
        lazy = d.get('__lazy__')
        if lazy is not None:
            for (k, v) in lazy.items():
                d[k] = v()
            del d['__lazy__']
        return d
    def __eq__(self, other):
        if isinstance(other, LazyNamespace):
            return self.__dict__ == other.__dict__
        else:
            return NotImplemented
    def __ne__(self, other):
        if isinstance(other, LazyNamespace):
            return self.__dict__ != other.__dict__
        else:
            return NotImplemented

class TestLazyNamespace(unittest.TestCase):
    def return_five(self):
        return 5

    def test(self):
        x = 0
        def inc():
            nonlocal x
            x += 1
            return x
        ns = LazyNamespace(a=0, b=inc, c=lambda: inc)
        self.assertEqual(ns.a, 0)
        self.assertEqual(ns.b, 1)
        # not called again
        self.assertEqual(ns.__dict__['b'], 1)
        self.assertEqual(ns.c, inc)
        ns = LazyNamespace(a=inc, b=0)
        self.assertEqual([k for k in dir(ns) if not k.startswith('_')],
                         ['a', 'b'])
        self.assertEqual(x, 2)
        # not called again
        self.assertEqual(ns.a, 2)

        self.assertEqual(
            dict(LazyNamespace(a=0, b=inc).__dict__.items()),
            {'a': 0, 'b': 3})

        ns = LazyNamespace(__repr__=lambda: "hello")
        self.assertEqual(ns.__repr__, 'hello')

        # The crude laziness mechanism sometimes shines through. This
        # can possibly be useful for debugging, but I consider it
        # mostly as an undocumented implementation detail rather than
        # a feature.
        ns = LazyNamespace(a=list, b=set, c=3)
        self.assertEqual(
            repr(ns),
            "LazyNamespace(__lazy__={'a': <class 'list'>, 'b': <class 'set'>},"
            " a=None, b=None, c=3)")
        _ = ns.a
        self.assertEqual(
            repr(ns),
            "LazyNamespace(__lazy__={'b': <class 'set'>}, a=[], b=None, c=3)")
        _ = ns.b
        self.assertEqual(
            repr(ns), "LazyNamespace(a=[], b=set(), c=3)")
        self.assertEqual(repr(LazyNamespace(a=1)), "LazyNamespace(a=1)")

        # This is how equality happens to work in a bunch of weird
        # corners. Equality is mainly intended for use within dev_util
        # unit tests.
        def one():
            return 1
        for (equal, different) in [(lambda a, b: self.assertTrue(a == b),
                                    lambda a, b: self.assertFalse(a == b)),
                                   (lambda a, b: self.assertFalse(a != b),
                                    lambda a, b: self.assertTrue(a != b))]:
            equal(LazyNamespace(a=one), LazyNamespace(a=one))
            equal(LazyNamespace(a=1), LazyNamespace(a=one))
            equal(LazyNamespace(a=one), LazyNamespace(a=1))
            equal(LazyNamespace(a=1), SimpleNamespace(a=1))
            equal(SimpleNamespace(a=1), LazyNamespace(a=1))
            different(LazyNamespace(a=one), SimpleNamespace(a=1))
            different(SimpleNamespace(a=1), LazyNamespace(a=one))
            class SimpleNamespaceSubclass(SimpleNamespace): pass
            equal(SimpleNamespaceSubclass(a=1), LazyNamespace(a=1))
            equal(LazyNamespace(a=1), SimpleNamespaceSubclass(a=1))

# <add id="dev_util.bank_regs">
# Given a bank object, return a structure containing
# objects to access its registers.  The returned structure can be a
# hierarchy of objects; e.g., if a register instance is named
# <tt>"g[2][3].r[1]"</tt>, and the returned structure is <tt>o</tt>,
# then the corresponding register object can be obtained as
# <tt>o.g[2][3].g[1]</tt>.  The set of registers is extracted using
# the <iface>register_view</iface> interface, and uses offsets and
# bitfields as returned by that interface.
# The <tt>inquiry</tt> argument is deprecated and should not be used.
# If <tt>prefix</tt> is
# given, then the returned structure will only contain registers whose
# full name matches this prefix.
#
# The returned register objects have methods <tt>read()</tt> and
# <tt>write()</tt> that work like their <tt>AbstractRegister</tt>
# counterparts, reading and writing the register with side-effects.
# The register value can be read and written without side-effects
# objects by getting and setting a property <tt>.val</tt>, or by
# calling a method <tt>set()</tt>. The latter accepts keyword
# arguments for fields just like the <tt>write()</tt> method; bits not
# covered by fields are retrieved by reading <tt>.val</tt>.  The
# positional argument of the <tt>write()</tt> method is required and
# may be either an integer, or <tt>READ</tt> to denote that previous
# values are retrieved using <tt>read()</tt>, or <tt>VAL</tt> to denote that
# they are retrieved using <tt>.val</tt>.
#
# In addition to the <tt>val</tt> property and <tt>set</tt>,
# <tt>read</tt> and <tt>write</tt> methods mentioned above, register
# objects also have the following properties:
# <ul>
#   <li><tt>bank</tt>: The Simics configuration object of the bank</li>
#   <li><tt>size</tt>, <tt>offset</tt>: the register's location within
#       the bank</li>
#   <li><tt>bitfield</tt>: a <tt>dev_util.Bitfield</tt> describing the </li>
#   <li><tt>name</tt>: the name of the register, relative to the bank.</li>
# </ul>
#
# Objects that represent the fields of a register can be retrieved as
# <tt>reg.field.FIELDNAME</tt>; e.g., if a register <tt>reg</tt> has a
# field named <tt>"a.b[2]"</tt> then the field object is accessed as
# <tt>reg.field.a.b[2]</tt>. The field object has one method
# <tt>read()</tt> for performing a full-register read with
# side-effects and returning the bits corresponding to the field, and
# a property <tt>.val</tt> that allows side-effect free access to the
# field's bits. Field objects provide a <tt>read</tt> method, which reads
# the parent register and returns the bits corresponding to the field,
# but it does not have a <tt>write</tt> method;
# writes must be done from the register object to ensure that
# remaining bits are explicitly specified. Field objects also provide
# the following properties:
# <ul>
#   <li><tt>reg</tt>: The parent register object</li>
#   <li><tt>lsb</tt>, <tt>bits</tt>: the bit range within the parent register</li>
#   <li><tt>name</tt>: the name of the field, relative to the parent register</li>
# </ul>
# </add>
def bank_regs(bank, inquiry=False, prefix=''):
    if inquiry:
        DEPRECATED(simics.SIM_VERSION_7,
                   'The inquiry flag to bank_regs is deprecated.',
                   'Use the .val accessors instead.')
        if os.environ.get('DISABLE_DEV_UTIL_LEGACY'):
            raise Error('The inquiry flag to bank_regs is deprecated.'
                        ' Use the .val accessors instead.')
    rv = bank.iface.register_view
    idx_iface = simics.SIM_c_get_interface(bank, 'register_view_catalog')
    if idx_iface is None:
        regnames = [rv.register_info(i)[0]
                    for i in range(rv.number_of_registers())]
    else:
        regnames = idx_iface.register_names()
    if prefix:
        name_to_idx = {name: i for (i, name) in enumerate(regnames) if name.startswith(prefix)}
        regnames = list(name_to_idx)
    else:
        name_to_idx = {n: i for (i, n) in enumerate(regnames)}
    regnames.sort()

    # regnames is the set of register names that start with prefix
    def decode(prefix: str, regnames: list[str]):
        if prefix == regnames[0]:
            assert len(regnames) == 1
            i = name_to_idx[prefix]
            (name, _, size, offset, *args) = rv.register_info(i)
            bf = Bitfield_LE({
                name: tuple(msb + [lsb]) for (name, _, lsb, *msb) in args.pop(0)
            }) if args else None
            big_endian = args[0] if args else False
            reg = ViewRegister(bank, i, size, bf)
            if not inquiry:
                reg = BankRegister(
                    (Register_BE if big_endian else Register_LE)(
                        bank, offset, size, bf),
                    reg)
            return reg
        sep = regnames[0][len(prefix)]
        if sep == '[':
            skip = len(prefix) + 1
            def items():
                nonlocal skip
                def index(s):
                    assert s[skip - 1] == '['
                    tail = s[skip:]
                    end = tail.index(']')
                    return tail[:end]
                for (stem, sub_regnames) in itertools.groupby(
                        regnames, index):
                    i = int(stem)
                    yield (i, decode(f'{prefix}[{stem}]', list(sub_regnames)))
            return dict(items())
        else:
            assert sep == '.'
            skip = len(prefix) + 1
            return LazyNamespace(**{
                stem: functools.partial(
                    decode, f'{prefix}.{stem}', list(subitems))
                for (stem, subitems) in itertools.groupby(
                        regnames, lambda s: _find_stem(s[skip:]))})

    return LazyNamespace(
        **{stem: functools.partial(decode, stem, list(items))
           for (stem, items) in itertools.groupby(regnames, _find_stem)})

# <add id="dev_util.namespace_map">
# Given a structure of nested namespace and dictionary objects, like
# the one returned by <tt>bank_regs</tt>, or the <tt>field</tt> member
# of register objects, applies the function <tt>fun</tt> on each leaf
# node, i.e. each node that isn't a <tt>SimpleNamespace</tt> or
# <tt>dict</tt> object. Returns a new copy of the namespace structure,
# where all leaves are replaced with the corresponding return value of
# <tt>fun</tt>.
# Function applications of <tt>fun</tt> may happen lazily, upon
# access of namespace or dictionary members.
# </add>
def namespace_map(fun, ns):
    if isinstance(ns, SimpleNamespace):
        return LazyNamespace(
            **{name: functools.partial(namespace_map, fun, sub)
               for (name, sub) in ns.__dict__.items()})
    elif isinstance(ns, dict):
        return {k: namespace_map(fun, v) for (k, v) in ns.items()}
    else:
        return fun(ns)

class TestNamespaceMap(unittest.TestCase):
    def test(self):
        self.assertEqual(namespace_map(lambda x: (x,), None), (None,))
        self.assertEqual(
            namespace_map(
                lambda x: (x,),
                {1: LazyNamespace(a=lambda: 2), 3: SimpleNamespace(b=4)}),
            {1: LazyNamespace(a=(2,)), 3: LazyNamespace(b=(4,))})
        self.assertEqual(
            namespace_map(
                lambda x: (x,),
                LazyNamespace(a=lambda: {1: 2}, b={3: 4})),
            LazyNamespace(a={1: (2,)}, b={3: (4,)}))


# <add id="dev_util.GRegister">
# This class allows provides a standalone register.
# </add>
class GRegister(AbstractRegister):
    tuple_based = False

    def __init__(self, size=4, bitfield=None, init=0):
        super(GRegister, self).__init__(size, bitfield,
                                        little_endian=None) # Does not apply
        self.contents = init

    # <add id="dev_util.GRegister.raw_read">
    # Reads the raw contents of the register.
    # </add>
    def raw_read(self):
        return self.contents

    # <add id="dev_util.GRegister.raw_write">
    # Write the raw contents of the register.
    # </add>
    def raw_write(self, value):
        self.contents = value

# <add id="dev_util.IRegister">
# This class allows you to easily access registers through the
# <iface>int_register</iface> interface. If the object <obj>obj</obj> does
# not implement the <iface>processor_info</iface> you have to specify the
# size in <param>size</param>.
# </add>
class IRegister(AbstractRegister):
    tuple_based = False

    def __init__(self, data, size=None, bitfield=None):
        (obj, port, reg_name) = data
        if size is None:
            if not hasattr(obj.iface, 'processor_info'):
                raise Exception(
                    "Object does not implement the processor_info interface. "
                    + "You have to specify the size manually")
            bits = obj.iface.processor_info.get_logical_address_width()
            size = bits // 8

        super(IRegister, self).__init__(size=size, bitfield=bitfield,
                                        little_endian=None)  # Don't care
        self.obj = obj
        self.port = port
        self.iface = simics.SIM_get_port_interface(obj, 'int_register', port)
        self.rname = reg_name
        self.rnum = self.iface.get_number(reg_name)

    # <add id="dev_util.IRegister.raw_read">
    # Reads the raw contents of the register.
    # </add>
    def raw_read(self):
        return self.iface.read(self.rnum)

    # <add id="dev_util.IRegister.raw_write">
    # Write the raw contents of the register.
    # </add>
    def raw_write(self, value):
        self.iface.write(self.rnum, value)


# <add id="dev_util.Layout">
# This class implements a memory layout.
#
# Testing devices that does DMA transfers usually requires setting up
# DMA descriptors. These can often be seen as register sets located in
# memory. This class allows you to define the layout of those registers,
# including bitfields within the registers.
#
# Registers without bitfields can be accessed through:
# <pre><v>layout</v>.<v>reg-name</v></pre>
#
# while registers with bitfields can be accessed through:
# <pre><v>layout</v>.<v>reg-name</v>.<v>field-name</v></pre>
# or
# <pre>
# <v>layout</v>.<v>reg-name</v>.read(),
# <v>layout</v>.<v>reg-name</v>.write()
# </pre>
#
# Layouts are mapped ontop of Memory, i.e. NOT ontop of normal Simics RAM.
# </add>
class Layout:

    class Register(AbstractRegister):
        def __init__(self, layout, name, size, fields, little_endian):
            AbstractRegister.__init__(self, size=size, bitfield=fields,
                                      little_endian=little_endian)
            self.layout = layout
            self.name = name

        def raw_read(self):
            (ofs, size, _) = self.layout.regs[self.name]
            assert size == self.size
            return bytes(self.layout.mem.read(self.layout.ofs + ofs, size))

        def raw_write(self, bytes):
            (ofs, size, _) = self.layout.regs[self.name]
            assert len(bytes) == size
            self.layout.mem.write(self.layout.ofs + ofs, bytes)

    class MemoryWrapper:
        def __init__(self, obj):
            self.mt = simics.SIM_new_map_target(obj, None, None)

        def read(self, addr, n):
            t = simics.transaction_t(read=True, size=n)
            exc = simics.SIM_issue_transaction(self.mt, t, addr)
            if exc != simics.Sim_PE_No_Exception:
                raise simics.SimExc_Memory
            return tuple(t.data)

        def write(self, addr, data):
            t = simics.transaction_t(write=True, data=bytes(data))
            exc = simics.SIM_issue_transaction(self.mt, t, addr)
            if exc != simics.Sim_PE_No_Exception:
                raise simics.SimExc_Memory

    # <add id="dev_util.Layout">
    # Constructor arguments:
    # <dl>
    # <dt>mem</dt><dd>An object that is a valid "map target"</dd>
    # <dt>ofs</dt><dd>the byte offset (i.e. the location of the layout)</dd>
    # <dt>little_endian</dt>
    # <dd>determines the byte order of the registers in the layout</dd>
    # <dt>regs</dt>
    # <dd>a dictionary on the following form:
    # <pre>
    # {'reg-name' : (offset, size),
    #  'reg-name' : (offset, size, bitfield)}
    # </pre>
    # </dd>
    # <dt>offset</dt><dd>the register offset into the layout</dd>
    # <dt>size</dt><dd>the size in bytes of the register</dd>
    # <dt>bitfield</dt><dd>optional and should be an instance of Bitfield</dd>
    # </dl>
    # </add>
    def __init__(self, mem, ofs, regs, little_endian):
        if callable(getattr(mem, 'read', None)):
            self.mem = mem
        else:
            try:
                self.mem = Layout.MemoryWrapper(mem)
            except simics.SimExc_Lookup:
                raise Exception(f'Unsupported memory object {mem!r}')
        self.ofs = ofs
        self.little_endian = little_endian

        # Create a dict that maps regs -> (ofs, size, have_fields)
        self.regs = {}
        for reg in regs:
            try:
                # Register with a bitfield
                (ofs, size, bitfield) = regs[reg]
            except ValueError:
                # Register without a bitfield
                (ofs, size) = regs[reg]
                bitfield = None

            if not bitfield:
                # Registers without bitfields are handled in attribute get/set
                have_fields = False
            else:
                # Create a register instance with the bitfield mapped on top
                setattr(self, reg, Layout.Register(
                    self, reg, size, fields=bitfield,
                    little_endian=little_endian))
                have_fields = True

            self.regs[reg] = (ofs, size, have_fields)

        # Verify that we don't have any overlaps
        overlap = {}
        for reg in regs:
            try:
                (ofs, _, _) = regs[reg]
            except ValueError:
                (ofs, _) = regs[reg]
            (_, size, _) = self.regs[reg]

            if size <= 0:
                raise Exception('registers %r in layout have illegal size %d'
                                % (reg, size))

            for i in range(size):
                if (ofs + i) in overlap:
                    raise Exception('overlapping registers in layout. '
                                    + 'Registers %r and %r overlap.'
                                    % (overlap[ofs + i], reg))
                overlap[ofs + i] = reg

    def __str__(self):
        return "<%s at %s:0x%x>"%(type(self).__name__, self.mem, self.ofs)

    # <add id="dev_util.Layout.clear">
    # Set all of the fields in this layout to 0.
    # </add>
    def clear(self):
        # Determine size of layout by looking for the register with the
        # highest offset
        max_ofs = 0
        for (ofs, size, have_fields) in list(self.regs.values()):
            if (ofs + size) > max_ofs:
                max_ofs = ofs + size

        self.write(0, 0, max_ofs)

    def __getattribute__(self, attr):
        '''Allows direct access to a register within the layout'''
        regs = super(Layout, self).__getattribute__('regs')
        if not regs or not attr in regs:
            return super(Layout, self).__getattribute__(attr)
        else:
            (ofs, size, have_fields) = regs[attr]
            if have_fields:
                return super(Layout, self).__getattribute__(attr)
            return self.read(ofs, size)

    def __setattr__(self, attr, value):
        '''Allows direct access to a register within the layout'''
        try:
            regs = self.regs
        except AttributeError:
            regs = None

        if not regs or not attr in regs:
            super(Layout, self).__setattr__(attr, value)
        else:
            (ofs, size, have_fields) = regs[attr]
            if have_fields:
                raise Exception('cannot write directly to register with '
                                'bitfields')
            self.write(ofs, value, size)

    # <add id="dev_util.Layout.read">
    # Returns the value at <var>ofs</var>.
    # </add>
    def read(self, ofs, size):
        return int.from_bytes(self.mem.read(self.ofs + ofs, size),
                              'little' if self.little_endian else 'big')

    # <add id="dev_util.Layout.write">
    # Writes <var>value</var> to <var>ofs</var>.
    # </add>
    def write(self, ofs, value, size):
        self.mem.write(self.ofs + ofs, value.to_bytes(
            size, 'little' if self.little_endian else 'big', signed=value < 0))


class TestLayout(unittest.TestCase):
    def test_layout(self):
        m = Memory()
        l = Layout(m.obj, 3, {'foo': (4, 2)}, True)
        l.foo = 0xabcd
        self.assertEqual(m.mem, [(7, [0xcd, 0xab])])
        self.assertEqual(l.foo, 0xabcd)

        m = Memory()
        l = Layout(m, 7, {'bar': (11, 2)}, False)
        l.bar = 0xabcd
        self.assertEqual(m.mem, [(18, [0xab, 0xcd])])
        self.assertEqual(l.bar, 0xabcd)

        m = Memory()
        m.mem = [(0, [0x0c, 0x13])]
        l = Layout(m, 0, {
                'reg': (0, 2, Bitfield_LE({'field': (13, 12)}))}, True)
        l.reg.field = 2
        self.assertEqual(m.mem, [(0, [0x0c, 0x23])])
        self.assertEqual(l.reg.field, 2)

        m = Memory()
        l = Layout(m, 0, {}, True)
        l.write(1, 0xdead, 2)
        self.assertEqual(m.mem, [(1, [0xad, 0xde])])
        self.assertEqual(l.read(1, 2), 0xdead)
        l.write(1, -2, 3)
        self.assertEqual(m.mem, [(1, [0xfe, 0xff, 0xff])])

        m = Memory()
        l = Layout(m, 0, {}, False)
        l.write(1, 0xdead, 2)
        self.assertEqual(m.mem, [(1, [0xde, 0xad])])
        self.assertEqual(l.read(1, 2), 0xdead)
        l.write(1, -2, 3)
        self.assertEqual(m.mem, [(1, [0xff, 0xff, 0xfe])])

    def test_layout_ms(self):
        img = simics.SIM_create_object("image", "img", size=0x1000)
        ram = simics.SIM_create_object("ram", "ram", image=img)
        ms = simics.SIM_create_object("memory-space", 'ms')
        ms.default_target = [ram, 0, 0, None]

        layout = Layout(ms, 3, {'foo': (4, 2)}, True)
        layout.foo = 0xabcd
        self.assertEqual(img.iface.image.get(7, 2), bytes([0xcd, 0xab]))
        self.assertEqual(layout.foo, 0xabcd)

        layout = Layout(ms, 7, {'bar': (11, 2)}, False)
        layout.bar = 0xabcd
        self.assertEqual(img.iface.image.get(18, 2), bytes([0xab, 0xcd]))
        self.assertEqual(layout.bar, 0xabcd)

        img.iface.image.set(0, bytes([0x0c, 0x13]))
        layout = Layout(
            ms, 0, {'reg': (0, 2, Bitfield_LE({'field': (13, 12)}))}, True)
        layout.reg.field = 2
        self.assertEqual(img.iface.image.get(0, 2), bytes([0x0c, 0x23]))
        self.assertEqual(layout.reg.field, 2)


# <add id="dev_util.Layout_LE">
# Little-endian layout.
# </add>
class Layout_LE(Layout):
    def __init__(self, mem, ofs, regs):
        super(Layout_LE, self).__init__(mem, ofs, regs, little_endian=True)

# <add id="dev_util.Layout_BE">
# Big-endian layout.
# </add>
class Layout_BE(Layout):
    def __init__(self, mem, ofs, regs):
        super(Layout_BE, self).__init__(mem, ofs, regs, little_endian=False)

# <add id="dev_util.value_to_tuple_be">
# Deprecated, use <tt>tuple(val.to_bytes(bytes, 'big'))</tt> instead.
# </add>
def value_to_tuple_be(val, bytes):
    DEPRECATED(simics.SIM_VERSION_7,
               "dev_util.value_to_tuple_be is deprecated.",
               "Use 'tuple(val.to_bytes(bytes, 'big'))' instead.")
    val &= (1 << (bytes * 8)) - 1
    return tuple(val.to_bytes(bytes, 'big'))

# <add id="dev_util.value_to_tuple_le">
# Deprecated, use <tt>tuple(val.to_bytes(bytes, 'little'))</tt> instead.
# </add>
def value_to_tuple_le(val, bytes):
    DEPRECATED(simics.SIM_VERSION_7,
               "dev_util.value_to_tuple_le is deprecated.",
               "Use 'tuple(val.to_bytes(bytes, 'little'))' instead.")
    val &= (1 << (bytes * 8)) - 1
    return tuple(val.to_bytes(bytes, 'little'))

# <add id="dev_util.tuple_to_value_be">
# Deprecated, use <tt>int.from_bytes(t, 'big')</tt> instead.
# </add>
def tuple_to_value_be(t):
    DEPRECATED(simics.SIM_VERSION_7,
               "dev_util.tuple_to_value_to_be is deprecated.",
               "Use 'int.from_bytes(t, 'big')' instead.")
    return int.from_bytes(t, 'big')

# <add id="dev_util.tuple_to_value_le">
# Deprecated, use <tt>int.from_bytes(t, 'little')</tt> instead.
# </add>
def tuple_to_value_le(t):
    DEPRECATED(simics.SIM_VERSION_7,
               "dev_util.tuple_to_value_to_le is deprecated.",
               "Use 'int.from_bytes(t, 'little')' instead.")
    return int.from_bytes(t, 'little')

class Test_tuple_value_conversion(unittest.TestCase):
    def test_tuple_value_conversion(self):
        self.assertEqual(tuple_to_value_le((1, 2, 3, 4)), 0x04030201)
        self.assertEqual(tuple_to_value_be((1, 2, 3, 4)), 0x01020304)
        self.assertEqual(value_to_tuple_le(0x04030201, 4), (1, 2, 3, 4))
        self.assertEqual(value_to_tuple_be(0x01020304, 4), (1, 2, 3, 4))
        self.assertEqual(value_to_tuple_le(0x04030201, 3), (1, 2, 3))
        self.assertEqual(value_to_tuple_be(0x01020304, 3), (2, 3, 4))
        self.assertEqual(value_to_tuple_be(
                0x0102030405060708090a0b0c0d0e0f101112131415, 21),
                          tuple(range(1, 22)))
        self.assertEqual(
            tuple_to_value_be(range(1, 22)),
            0x0102030405060708090a0b0c0d0e0f101112131415)
        self.assertEqual(value_to_tuple_le(-2, 3), (0xfe, 0xff, 0xff))
        self.assertEqual(value_to_tuple_be(-2, 3), (0xff, 0xff, 0xfe))


# <add id="dev_util.Memory">
# Deprecated.
# Legacy wrapper around an instance of the <tt>sparse-memory</tt> class.
# Provides an interface compatible with the deprecated Memory class.
#
# The <var>obj</var> attribute contains an instance of <tt>memory-space</tt>,
# mapping to the memory. The <var>real_obj</var> attribute contains
# an instance of the 'sparse-memory' class. The <var>mem</var>
# attribute is an alias to the <var>mem</var> attribute of
# <var>real_obj</var>.
# </add>
class Memory:
    def __init__(self):
        DEPRECATED(simics.SIM_VERSION_7,
                   'The dev_util.Memory Python class is deprecated.',
                   'Use the sparse-memory Simics class instead.')
        self.real_obj = simics.SIM_create_object(
            'sparse-memory', None, ignore_zero_sized_read=True)
        self.obj = simics.SIM_create_object(
            'memory-space', None, default_target=[self.real_obj, 0, 0, None])
        self.mt = simics.SIM_new_map_target(self.real_obj, None, None)

    def __getattr__(self, attr):
        if attr == 'mem':
            return [(a, list(d)) for a, d in self.real_obj.mem]
        raise AttributeError(f"'Memory' object has no attribute {attr}")

    def __setattr__(self, attr, val):
        if attr == 'mem':
            self.real_obj.mem = [[a, tuple(d)] for a, d in val]
        else:
            super(Memory, self).__setattr__(attr, val)

    # <add id="dev_util.Memory.read">
    # Read bytes from this memory.
    #
    # Arguments:
    # <dl>
    # <dt>addr</dt>
    # <dd>the start address of the range to read</dd>
    # <dt>n</dt>
    # <dd>length in bytes of the range to read</dd>
    # </dl>
    #
    # Throws an exception if any byte in the read range is empty.
    # </add>
    def read(self, addr, n):
        t = simics.transaction_t(read=True, size=n)
        exc = simics.SIM_issue_transaction(self.mt, t, addr)
        if exc != simics.Sim_PE_No_Exception:
            raise simics.SimExc_Memory
        return list(t.data)

    # <add id="dev_util.Memory.write">
    # Write bytes to this memory.
    #
    # Arguments:
    # <dl>
    # <dt>addr</dt>
    # <dd>the start address of the range to write</dd>
    # <dt>data</dt>
    # <dd>the bytes to write</dd>
    # </dl>
    #
    # Fills in empty slots in the memory and overwrites already existing data.
    # </add>
    def write(self, addr, data):
        t = simics.transaction_t(write=True, data=bytes(data))
        exc = simics.SIM_issue_transaction(self.mt, t, addr)
        if exc != simics.Sim_PE_No_Exception:
            raise simics.SimExc_Memory

    # <add id="dev_util.Memory.clear">
    # Clear the contents of the memory.
    # </add>
    def clear(self, *args):
        self.real_obj.mem = []

    # <add id="dev_util.Memory.is_range_touched">
    # Return True if any of this memory's slots in the range contain data.
    # </add>
    def is_range_touched(self, start, length):
        def overlaps(s1, l1, s2, l2):
            return not (s1 + l1 <= s2) and not (s2 + l2 <= s1)

        for chunk_start, chunk in self.real_obj.mem:
            if overlaps(chunk_start, len(chunk), start, length):
                return True
        return False


class TestMemory(unittest.TestCase):
    def testMemory(self):
        m = Memory()
        self.assertEqual(m.read(42, 0), [])
        m.write(5, (11, 22, 33))
        self.assertEqual(m.mem, [(5, [11, 22, 33])])
        m.write(6, (23,))
        self.assertEqual(m.mem, [(5, [11, 23, 33])])
        m.write(6, (24, 25, 26))
        self.assertEqual(m.mem, [(5, [11, 24, 25, 26])])
        m.write(2, (3, 4))
        self.assertEqual(m.mem, [(2, [3, 4]), (5, [11, 24, 25, 26])])
        m.write(4, (17,))
        self.assertEqual(m.mem, [(2, [3, 4, 17, 11, 24, 25, 26])])
        m.write(1, tuple(range(20)))
        self.assertEqual(m.mem, [(1, list(range(20)))])
        self.assertEqual(m.read(2, 3), [1, 2, 3])

# <add id="dev_util.Dev">
# Deprecated.
# </add>

# <add id="dev_util.Iface">
# Deprecated.
# </add>

# <add id="dev_util.iface">
# Deprecated.
# </add>

from dev_util_internal import (Dev,
                               Iface,
                               iface,
                               SimpleInterrupt,
                               SerialDevice,
                               SerialPeripheralInterfaceSlave,
                               Signal,
                               MultiLevelSignal,
                               FrequencyListener,
                               ScaleFactorListener,
                               SimpleDispatcher,
                               I2cDevice,
                               I2cBus,
                               I2cLink,
                               Mii,
                               MiiManagement,
                               Mdio45Bus,
                               Mdio45Phy,
                               Microwire,
                               Ieee_802_3_mac,
                               Ieee_802_3_mac_v3,
                               Ieee_802_3_phy,
                               Ieee_802_3_phy_v2,
                               Ieee_802_3_phy_v3,
                               IoMemory,
                               PciBus,
                               PciBridge,
                               PciExpress,
                               PciUpstream,
                               PciDownstream,
                               Translate,
                               MemorySpace,
                               FirewireDevice,
                               FirewireBus,
                               CacheControl,
                               MapDemap,
                               StepQueue,
                               CycleQueue,
                               ProcessorInfo,
                               Ppc,
                               Sata)
