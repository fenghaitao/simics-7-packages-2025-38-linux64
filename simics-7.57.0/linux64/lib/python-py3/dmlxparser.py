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

# DML Xml parser

__all__ = ('parse', 'ParseError')

from collections import namedtuple
import itertools
import functools
import operator
import xml.etree.cElementTree as ET

class ParseError(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return self.msg


Dev = namedtuple('Dev', 'name desc documentation limitations banks be_bitorder')
# Note; tuple entry 'dimensions' is called 'vsize' in xml for legacy reasons
Bank = namedtuple('Bank', 'names desc documentation limitations regs dimensions bigendian function')
# Note; tuple entry 'dimensions' is called 'vsize' in xml for legacy reasons
Reg = namedtuple('Reg', 'names desc documentation limitations size offset fields')
Field = namedtuple('Field', 'name desc documentation limitations lsb msb')

def _get_int_list(string):
    return tuple(int(s) for s in string.split())

def _make_field(e):
    return Field(e.get('name'), e.get('desc'),
                 e.get('documentation'), e.get('limitations'),
                 int(e.get('lsb')),
                 int(e.get('msb')))

def add_suffixes(prefixes, name, dimsizes):
    suffixes = [
        name + ''.join(indices)
        for indices in itertools.product(*(
                (f'[{i}]' for i in range(dimsize))
                for dimsize in dimsizes))]
    return [prefix + suffix
            for prefix in prefixes
            for suffix in suffixes]

def _make_register(e, nbanks, group_prefixes):
    dimsizes = _get_int_list(e.get('vsize', ''))
    names = add_suffixes(group_prefixes, e.get('name'), dimsizes)
    offsets = _get_int_list(e.get('offset', ''))
    assert len(offsets) == len(names) * nbanks
    return Reg(names,
               e.get('desc'), e.get('documentation'),
               e.get('limitations'), int(e.get('size')),
               # weird: offsets are specified separately across
               # bank array indices, even though DMLC guarantees
               # that offsets don't depend on the bank index
               offsets[:len(names)],
               tuple(sorted((_make_field(se) for se in e.findall('field')),
                            key=lambda field: field.msb, reverse=True)),
               )

def _make_register_group(e, nbanks, parent_prefixes):
    dims = _get_int_list(e.get('vsize', ''))
    group_prefixes = [
        p + '.' for p in add_suffixes(
            parent_prefixes, e.get('name'), dims)]
    regs = []
    for se in list(e):
        if se.tag == 'register':
            regs.append(_make_register(se, nbanks, group_prefixes))
        elif se.tag == 'group':
            regs.extend(_make_register_group(
                se, nbanks, group_prefixes))
    return regs

def _make_bank(e):
    regs = []
    dimsizes = _get_int_list(e.get('vsize', ''))
    nbanks = functools.reduce(operator.mul, dimsizes, 1)
    for se in e:
        if se.tag == 'register':
            regs.append(_make_register(se, nbanks, ['']))
        elif se.tag == 'group':
            regs.extend(_make_register_group(se, nbanks, ['']))
    names = add_suffixes([''], e.get('name', ''), dimsizes)
    return Bank(names, e.get('desc'), e.get('documentation'),
                e.get('limitations'), tuple(regs),
                dimsizes,
                e.get('byte_order') == 'big-endian',
                _get_int_list(e.get('function', '')))

def _make_dev(e):
    return Dev(e.get('name'), e.get('desc'),
               e.get('documentation'), e.get('limitations'),
               tuple(_make_bank(se) for se in e.findall('bank')),
               e.get('bitorder') == 'be')

# Returns a tree of named tuples (see top of module)
# dev > bank > registers (groups flattened) > fields
def parse(source):
    try:
        return _make_dev(ET.parse(source).getroot())  # nosec: we trust XML data
    except (TypeError, ValueError, ET.ParseError) as err:
        raise ParseError(str(err))
