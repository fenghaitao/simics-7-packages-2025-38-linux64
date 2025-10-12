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

import unittest
import re
from operator import mul
import itertools
from functools import reduce, cache
from dataclasses import dataclass
import bisect

import device_info
import dmlxparser

try:
    import simics
    from simics import (SIM_set_mem_op_physical_address,
                        VT_io_memory_operation)
except ImportError:
    # OK if not running in Simics
    pass

class ParseError(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return self.msg

def is_port_mapping(map_line):
    return isinstance(map_line[1], list)

def mapping_dev_name(map_line):
    if is_port_mapping(map_line):
        return map_line[1][0].name
    else:
        return map_line[1].name

def get_mapped_address(device):
    dev_name = device.name
    map_objs = []

    # Find all objects where device is mapped
    for obj in simics.SIM_object_iterator(None):
        try:
            m = obj.map
            for line in m:
                if mapping_dev_name(line) == dev_name:
                    map_objs.append(obj)
        except AttributeError:
            pass

    if not map_objs:
        return [0]

    # Find out where objects are mapped in physical address space
    where_mapped = []
    for obj in map_objs:
        osets = get_mapped_address(obj)
        for line in obj.map:
            if mapping_dev_name(line) == dev_name:
                addr = int(line[0])
                for oset in osets:
                    where_mapped.append(addr + oset)

    return where_mapped

class Device:
    __slots__ = ('classname', 'desc', 'banks', 'be_bitorder')
    def __init__(self, classname, desc, banks, be_bitorder):
        self.classname = classname
        self.desc = desc
        self.banks = banks
        self.be_bitorder = be_bitorder

class Bank:
    __slots__ = ('name', 'desc', 'function',
                 '_regs_by_name', '_regs_by_offset',
                 'nregs', 'be_bitorder', 'rviface', '_internalizer')

    def __init__(self, name, desc, function,
                 be_bitorder, rviface, catalog_iface, internalizer=None):
        self.name = name
        self.desc = desc
        self.function = function
        self.nregs = (
            0 if rviface is None else rviface.number_of_registers())
        self.be_bitorder = be_bitorder
        self.rviface = rviface
        self._internalizer = internalizer or Internalizer()
        if catalog_iface is None:
            if rviface is None:
                self._regs_by_name = {}
                self._regs_by_offset = []
            else:
                self._regs_by_name = {self._reg(i).name: i
                                      for i in range(self.nregs)}
                self._regs_by_offset = sorted(
                    (offs, i) for i in range(self.nregs)
                # fisketur[syntax-error]
                    if (offs := self._reg(i).offset) is not None)
        else:
            self._regs_by_name = {name: i for (i, name) in enumerate(
                catalog_iface.register_names())}
            self._regs_by_offset = sorted(
                (offset, i) for (i, offset) in enumerate(
                    catalog_iface.register_offsets()))

    @cache
    def _reg(self, i):
        rinfo = self.rviface.register_info(i)
        bitfields = []
        if len(rinfo) > 4:
            for bf in rinfo[4]:
                if len(bf) > 3:
                    (n, d, lsb, msb) = bf
                else:
                    (n, d, lsb) = bf
                    msb = lsb
                bitfields.append(dmlxparser.Field(n, d, '', '', lsb, msb))
        return Register(self, rinfo[0], rinfo[1], False,
                     rinfo[2], rinfo[3], bitfields,
                     len(rinfo) > 5 and rinfo[5], i, self._internalizer)

    def reg_from_name(self, name):
        idx = self._regs_by_name.get(name)
        return None if idx is None else self._reg(idx)

    def reg_names(self):
        return self._regs_by_name.keys()

    def regs_overlapping(self, offset, size=1):
        '''Return all Register objects, in offset order, that overlap
        the given range'''
        low_idx = bisect.bisect_right(self._regs_by_offset, offset,
                                      key=lambda pair: pair[0])
        # low_idx is the index of the first register with offset > low,
        # so low_idx - 1 is the first index that may overlap. But avoid
        # using -1 as index.
        if low_idx != 0:
            low_idx -= 1
        for (offs, i) in self._regs_by_offset[low_idx:]:
            reg = self._reg(i)
            if (reg.offset + reg.size > offset
                and reg.offset < offset + size):
                yield reg

    # called from the GUI
    def regview(self, obj):
        for i in range(self.nregs):
            reg = self._reg(i)
            yield (reg.name, reg.offset, None,
                   self.rviface.get_register_value(i), reg)


class _test_bank(unittest.TestCase):
    @dataclass
    class MockRegViewIface:
        # (name, offset, size)
        regs: list[(str, int, int)]
        def number_of_registers(self):
            return len(self.regs)
        def register_info(self, i):
            (name, offset, size) = self.regs[i]
            return [name, '', size, offset]
    @dataclass
    class MockRegViewCatalogIface:
        # (name, offset, size)
        regs: list[(str, int, int)]
        def register_offsets(self):
            return [o for [_, o, _] in self.regs]
        def register_names(self):
            return [n for [n, o, _] in self.regs]
    def bank(self, regs: list[(str, int, int)]):
        import random
        regs = list(regs)
        random.shuffle(regs)
        return Bank(
            'b', '', 0, False, self.MockRegViewIface(regs),
            self.MockRegViewCatalogIface(regs))

    def test_regs_overlapping(self):
        def hits(reglist, offset, size):
            bank = self.bank([(f'r{o}', o, s) for (o, s) in reglist])
            return [r.offset for r in bank.regs_overlapping(offset, size)]
        self.assertEqual(hits([], 0, 1), [])
        self.assertEqual(hits([(0, 1)], 0, 1), [0])
        for left in [3, 4]:
            for right in [6, 7]:
                self.assertEqual(
                    hits([(0, 4), (4, 2), (6, 8)], left, right - left),
                    (([0] if left == 3 else []) + [4]
                     + ([6] if right == 7 else [])))

def _flatten_vals(vals):
    res = []
    for v in vals:
        if isinstance(v, (list, tuple)):
            res.extend(_flatten_vals(v))
        else:
            res.append(v)
    return res

class Internalizer:
    def __init__(self):
        self._identity_cache = {}
    def intern(self, obj):
        return self._identity_cache.setdefault(obj, obj)

@dataclass
class Register:
    __slots__ = ('bank', 'name', 'desc', 'unimpl', 'size', 'offset',
                 'fields', 'view_id', 'be_byte_order')
    def __init__(self, bank, name, desc, unimpl, size, offset, fields,
                 be_byte_order, view_id=None, internalizer=None):
        self.bank = bank
        self.name = name
        self.desc = desc
        self.unimpl = unimpl
        self.size = size  # register size
        self.offset = offset
        fields = (
            tuple(sorted(fields, key=lambda x: x.msb, reverse=True)) if fields
            else (self.dummy_field(size * 8 - 1, 0, name),))
        self.fields = fields if internalizer is None else internalizer.intern(fields)
        self.view_id = view_id
        self.be_byte_order = be_byte_order

    def dummy_field(self, msb, lsb, name):
        return dmlxparser.Field(name, "", "", "", lsb, msb)

def bank_subobjects(obj):
    banks = simics.SIM_object_descendant(obj, "bank")
    if banks is not None:
        for b in simics.SIM_object_iterator(banks):
            if hasattr(b.iface, simics.REGISTER_VIEW_INTERFACE):
                yield b

# Eventually we would like to exclusively create bank-info from bank
# objects directly
def get_device_info(obj):
    '''Load device info for a given object.'''
    # Since they are not allowed in DML hierarchical ports are not tracked,
    # meaning device.port.port.interface is not shown
    # name -> (register_view, register_view_catalog)
    views = {}

    regview_iface = simics.SIM_c_get_interface(
        obj, simics.REGISTER_VIEW_INTERFACE)
    catalog_iface = simics.SIM_c_get_interface(
        obj, simics.REGISTER_VIEW_CATALOG_INTERFACE)
    # Obtain anonymous bank, also covers case where obj is a bank object
    if regview_iface:
        views[''] = (regview_iface, catalog_iface)

    # Used to obtain banks from modules in 5, this should eventually be removed
    for (pname, size, ifname) in simics.VT_get_port_interfaces(obj.classname):
        if ifname != simics.REGISTER_VIEW_INTERFACE:
            continue
        if size == 1:
            views[pname] = (
                simics.SIM_get_port_interface(
                    obj, simics.REGISTER_VIEW_INTERFACE, pname),
                None)
            continue
        for i in range(size):
            views[f'{pname}[{i}]'] = (
                simics.SIM_get_port_interface(
                    obj, simics.REGISTER_VIEW_INTERFACE, f"{pname}[{i}]"),
                None)
    # Obtain views from subobjects under .bank, if any
    for b in bank_subobjects(obj):
        views[b.name.removeprefix(f'{obj.name}.bank.')] = (
            simics.SIM_c_get_interface(b, simics.REGISTER_VIEW_INTERFACE),
            simics.SIM_c_get_interface(
                b, simics.REGISTER_VIEW_CATALOG_INTERFACE))
    if not views:
        return None

    internalizer = Internalizer()
    banks = []
    for name in sorted(views):
        (iface, catalog_iface) = views[name]
        banks.append(Bank(
            name, iface.description(), 0,
            iface.big_endian_bitorder(), iface, catalog_iface,
            internalizer=internalizer))

    # patch register view info with bank function number info from xml
    # TODO: we want to get rid of function numbers, see SIMICS-22803
    from register_view import load_xml
    xml_info = load_xml(obj.classname)
    if xml_info:
        for b in banks:
            for xb in xml_info.banks:
                if b.name in xb.names:
                    b.function = (xb.function[xb.names.index(b.name)]
                                  if xb.function else 0)

    return Device(obj.classname, '', tuple(banks), banks[0].be_bitorder)
