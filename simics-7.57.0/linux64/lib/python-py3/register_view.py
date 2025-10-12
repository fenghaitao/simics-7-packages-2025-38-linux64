# © 2018 Intel Corporation
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
from functools import reduce
import dataclasses
from traceback import print_exc
import itertools

import simics
import conf
import dmlxparser

def desc(d):
    return d if d else ''



def lookup_di_file(classname, suffix, mode):
    matching_modules = [m for m in simics.SIM_get_all_modules()
                        if classname in m[7]]
    # If we have multiple matching modules, pick the loaded one
    # if possible, otherwise just pick any
    module_path = next((m[1] for m in matching_modules if m[2]),
                       matching_modules[0][1] if matching_modules else None)
    if module_path:
        try:
            return open(os.path.join(os.path.dirname(module_path),
                                     "%s.%s" % (classname.replace('-', '_'),
                                                suffix)), mode)
        except IOError:
            pass
    return None


def load_xml(classname):
    f = lookup_di_file(classname, 'xml', 'r')
    if f:
        try:
            return dmlxparser.parse(f)
        except dmlxparser.ParseError as err:
            simics.SIM_log_message(conf.sim, 3, 0, 0, f'XML parse error: {err}')
        finally:
            f.close()
    else:
        return None

# We make use of the fact that the fields parameter is optional and
# avoid returning the default field which is imposed on registers
# without user-provided fields
def only_default_field(r):
    return len(r.fields) == 1 and r.fields[0].name == '_'.join(r.names)

def mapped_register_instances(regs, be_byte_order):
    return [
        [name, desc(r.desc), r.size, ofs,
         [] if only_default_field(r) else [[f.name, desc(f.desc), f.lsb, f.msb]
                                           for f in r.fields],
         be_byte_order]
        for r in regs for (name, ofs) in zip(r.names, r.offset)
        if ofs >= 0]

@dataclasses.dataclass
class CacheEntry:
    desc: str = ''
    big_endian_bitorder: bool = False
    regs: list = dataclasses.field(default_factory=list)

def get_bank_info(banks, port_name):
    for bank in banks:
        if port_name in bank.names:
            return bank
    print("failed to find", port_name)
    assert False

# We cache only the relevant data for a particular bank. Device info
# is (again) parsed from disk if the interface is asked for the info
# of another bank. If necessary, we could cache the device info.
# Note that port_name is used to index into information obtained from the
# dml-backend, parsed through DML.py. Which is why lookup is made
# on fully-qualified port names, rather than regular bank names
cache = {}
def get_cached_bank_info(class_name, port_name):
    if (class_name, port_name) not in cache:
        di = load_xml(class_name)
        bi = get_bank_info(di.banks, port_name) if di else None

        ce = CacheEntry()
        if bi:
            ce.desc = bi.desc if bi.desc else ''
            ce.big_endian_bitorder = di.be_bitorder

            regs = mapped_register_instances(bi.regs, bi.bigendian)
            regs.sort(key = lambda r: r[3])  # sort on offset
            ce.regs = regs

        cache[(class_name, port_name)] = ce
    return cache[(class_name, port_name)]

def description(class_name, port_name):
    try:
        return get_cached_bank_info(class_name, port_name).desc
    except Exception :
        print_exc()
        return ''

def big_endian_bitorder(class_name, port_name):
    try:
        return get_cached_bank_info(class_name, port_name).big_endian_bitorder
    except Exception :
        print_exc()
        return False

def number_of_registers(class_name, port_name):
    try:
        return len(get_cached_bank_info(class_name, port_name).regs)
    except Exception :
        print_exc()
        return 0

def register_info(class_name, port_name, reg):
    try:
        regs = get_cached_bank_info(class_name, port_name).regs
        return regs[reg] if reg < len(regs) else None
    except Exception :
        print_exc()
        return None

def read_access(obj, io_memory, offset, size, big_endian_byteorder, function):
    op = simics.generic_transaction_t()
    simics.SIM_set_mem_op_physical_address(op, offset)
    simics.SIM_set_mem_op_type(op, simics.Sim_Trans_Load)
    simics.SIM_set_mem_op_inquiry(op, True)

    map_info = simics.map_info_t()
    map_info.function = function

    try:
        val = list(simics.VT_io_memory_operation(obj, io_memory, op,
                                                 b'\0' * size,
                                                 map_info))
    except simics.SimExc_Memory:
        simics.SIM_log_error(obj, 0,
                            "Cannot get register due to exception (defaulting to 0)")
        return 0

    if not big_endian_byteorder:
        val.reverse()
    return reduce(lambda a, b: (a << 8) | b, val, 0)

def get_register_value(class_name, bank_name, port_name,
                       reg, device, function, _):
    rinfo = register_info(class_name, port_name, reg)
    if not rinfo:
        return 0
    (_, _, size, offset, _, be_byte_order) = rinfo
    io = simics.SIM_c_get_port_interface(device, 'io_memory', port_name)
    if not io:
        return 0

    return read_access(device, io, offset, size, be_byte_order, function)

def write_access(obj, io_memory, offset, size, big_endian_byteorder,
                 function, value):
    val = [bytes((((value >> (8 * i)) & 0xff),)) for i in range(size)]
    if big_endian_byteorder:
        val.reverse()

    op = simics.generic_transaction_t()
    simics.SIM_set_mem_op_physical_address(op, offset)
    simics.SIM_set_mem_op_type(op, simics.Sim_Trans_Store)
    simics.SIM_set_mem_op_inquiry(op, True)

    map_info = simics.map_info_t()
    map_info.function = function

    try:
        simics.VT_io_memory_operation(obj, io_memory, op,
                                      b''.join(val),
                                      map_info)
    except simics.SimExc_Memory:
        simics.SIM_log_error(obj, 0,
                            "Cannot set register due to exception")

def set_register_value(class_name, bank_name, port_name,
                       reg, device, function, _, value):
    rinfo = register_info(class_name, port_name, reg)
    if not rinfo:
        return
    (_, _, size, offset, _, be_byte_order) = rinfo
    io = simics.SIM_c_get_port_interface(device, 'io_memory', port_name)
    if not io:
        return

    write_access(device, io, offset,size, be_byte_order, function, value)
