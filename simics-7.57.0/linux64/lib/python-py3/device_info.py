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

__all__ = ('get_device_info', 'has_device_info', 'is_iomem_device')

import DML
import cli
import conf
import os
import itertools
import simics
from DML import get_device_info

def has_device_info(obj):
    '''Test if an object supports register view.'''
    return (simics.REGISTER_VIEW_INTERFACE
            in simics.VT_get_interfaces(obj.classname)
            or any(x[2] == simics.REGISTER_VIEW_INTERFACE
                   for x in simics.VT_get_port_interfaces(obj.classname))
            # Convert to tuple to check emptiness of generator
            or tuple(DML.bank_subobjects(obj)))

def get_first_register_view(obj):
    if hasattr(obj.iface, simics.REGISTER_VIEW_INTERFACE):
        return getattr(obj.iface, simics.REGISTER_VIEW_INTERFACE)
    for (pname, size, ifname) in simics.VT_get_port_interfaces(obj.classname):
        if ifname != simics.REGISTER_VIEW_INTERFACE or size < 1:
            continue
        if size == 1:
            return getattr(getattr(obj.ports, pname),
                           simics.REGISTER_VIEW_INTERFACE)
        return getattr(getattr(obj.ports, pname)[0],
                       simics.REGISTER_VIEW_INTERFACE)
    banks = DML.bank_subobjects(obj)
    return next(banks, default=None)

def is_device_big_endian(obj):
    rv = get_first_register_view(obj)
    if rv:
        return rv.big_endian_bitorder()
    return get_device_info(obj).be_bitorder

def is_iomem_device(obj):
    '''Quick test if an object can possibly supports register view.'''
    return (hasattr(obj.iface, simics.REGISTER_VIEW_INTERFACE)
            or hasattr(obj.iface, simics.IO_MEMORY_INTERFACE)
            or any(x[2] in (simics.REGISTER_VIEW_INTERFACE,
                            simics.IO_MEMORY_INTERFACE)
                   for x in simics.VT_get_port_interfaces(obj.classname)))

def field_lines(num_bits, this_field, fields):
    line = [' '] * num_bits
    # fill in reverse order to keep offsets intact
    for idx in reversed(range(len(fields))):
        field = fields[idx]
        if idx < this_field:
            gfx = '  '
        elif idx == this_field:
            gfx = '┘ '
        else:
            gfx = '│ '
        line[num_bits - field.msb - 1:num_bits - field.msb] = gfx
    # draw horizontal line until the up turn
    i = 0
    while line[i] != '┘':
        line[i] = '─'
        i+= 1
    return "".join(line)

def print_field(write, name, size, value, be_bitorder, fields):
    num_bits = size * 8
    field_descs = ["%s " % x.name for x in fields]
    desc_width = max([len(x) for x in field_descs]) + 1
    # pad field descriptors with a horizontal line and the bit range
    for i in range(len(field_descs)):
        field_descs[i] += '─' * (desc_width - len(field_descs[i]))
    bit_desc = ' (%d..%d) ' if size == 1 else ' (%2d..%2d) '
    for i in range(len(field_descs)):
        if be_bitorder:
            field_descs[i] += bit_desc % (num_bits - fields[i].msb - 1,
                                              num_bits - fields[i].lsb - 1)
        else:
            field_descs[i] += bit_desc % (fields[i].msb, fields[i].lsb)
    desc_width = len(field_descs[0])
    # pad binary value with zeroes up to highest bit
    val = cli.number_str(value, radix=2, group=0, use_prefix=False)
    val = '0' * (num_bits - len(val)) + val
    # print field values with spaces between
    write(' ' * (desc_width + 1))
    for field in fields:
        field_val = val[num_bits - field.msb - 1:num_bits - field.lsb]
        write(field_val + ' ')
    write('\n')
    # finally print the field names and horizontal lines
    for idx, field_desc in enumerate(field_descs):
        write(field_desc + '─' + field_lines(num_bits, idx, fields) + '\n')
