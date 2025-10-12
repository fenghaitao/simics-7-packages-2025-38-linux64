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


import codecs
import datetime
import importlib
import io
import inspect
import math
import os
import platform
import re
import sys
import time
import unittest
import table
import __main__
from enum import Enum
import simics
import simics_common
from console_switch import (
    get_cur_con,
    set_cur_con,
    con_preview_name,
)

from simics import (
    pr,
    SIM_get_all_classes,
    SIM_get_object,
    SIM_lookup_file,
    SIM_native_path,
    SIM_object_iterator,
    VT_get_simulation_time,

    SIM_VERSION_6,
    SIM_VERSION_7,
    Sim_Access_Execute,

    Column_Key_Alignment,
    Column_Key_Hide_Homogeneous,
    Column_Key_Int_Grouping,
    Column_Key_Int_Radix,
    Column_Key_Name,
    Table_Key_Columns,
)

from cli import (
    add_tech_preview,
    CliError,
    CliQuietError,
    Markup,
    command_quiet_return,
    command_return,
    command_verbose_return,
    current_frontend_object,
    disable_cmd,
    enable_cmd,
    get_completions,
    interactive_command,
    new_command,
    new_info_command,
    new_operator,
    new_status_command,
    new_unsupported_command,
    number_str,
    object_expander,
    print_columns,
    simics_print_stack,

    arg,
    bool_t,
    filename_t,
    flag_t,
    float_t,
    int_t,
    list_t,
    nil_t,
    obj_t,
    poly_t,
    sint32_t,
    str_t,
    string_set_t,
    uint_t,

    # script-branch related imports:
    check_script_branch_command,
    sb_in_main_branch,
    sb_run_in_main_branch,
    sb_signal_waiting,
    sb_wait,

    # For backward compatibility, we import {get,set}_repeat_data at the top
    # level since until very recently they were used from the commands module
    # by the isctlm-tools module which is shipped not in Simics base package:
    get_repeat_data,
    set_repeat_data,
)

import threading
import cli
import cli_impl
from deprecation import DEPRECATED
import refmanual
import simicsutils
from simicsutils.internal import ensure_text
import target_info
import conf

class physmem_source:
    def __init__(self, obj):
        self.obj = obj
        self.unhandled = self.outside = self.tag_unavailable = 0

    def addr_prefix(self):
        return "p:"

    def get_byte_from_word(self, addr):
        for s in (2, 4, 8):
            a = addr & ~(s - 1)
            try:
                bytes = self.obj.iface.memory_space.read(None, a, s, True)
            except simics.SimExc_Memory:
                continue
            return bytes[addr - a]
        return None

    def get_byte(self, addr):
        try:
            [byte] = self.obj.iface.memory_space.read(None, addr, 1, True)
        except simics.SimExc_InquiryUnhandled:
            self.unhandled = 1
            return "??"
        except simics.SimExc_Memory:
            byte = self.get_byte_from_word(addr)
            if byte is None:
                self.outside = 1
                return "**"
        return byte

    def have_tag(self, addr):
        try:
            return simics.CORE_read_phys_memory_tags_mask(self.obj, addr, 1)
        except simics.SimExc_InquiryUnhandled:
            return 0
        except simics.SimExc_Memory:
            return 0

    def get_tag(self, addr):
        try:
            if simics.CORE_read_phys_memory_tags_mask(self.obj, addr, 1):
                return "%d" % simics.SIM_read_phys_memory_tags(
                    self.obj, addr, 1)
            else:
                self.tag_unavailable = 1
                return '/'
        except simics.SimExc_InquiryUnhandled:
            return '?'
        except simics.SimExc_Memory:
            return '*'

    def finish(self):
        if self.outside:
            pr("addresses marked \"**\" are outside physical memory\n")
        if self.unhandled:
            pr("addresses marked \"??\" do not support inquiry\n")
        if self.tag_unavailable:
            pr("addresses marked \"/\" do not have tags\n")

def y_or_ies(n):
    "Returns 'y' if n == 1; 'ies' otherwise"

    if n == 1:
        return 'y'
    return 'ies'

# Given a sub-object, return the "device"
#
# This is the single point of reference for the definition of a device in
# Simics. The definition is as follows:
#    a device is the object that has register banks in it.
#
# NOTE: For DML devices, this equals SIM_port_object_parent(bank) but for
# SystemC hierarchies it's harder to tell for sure. We have decided to use the
# same heuristic, but it might be possible to extend this later on with
# meta-data mark-up to single out the Device from sub-objects.
def get_device(bank):
    # TODO(ah): workaround for now to make the bank-coverage-tool look-n-feel
    # consistent with the definition. When we have implemented the SystemC
    # proxy objects as port-objects or we have some meta-data markup this code
    # can be removed.
    if hasattr(bank.iface, 'sc_object'):
        return simics.SIM_object_parent(bank)
    device = simics.SIM_port_object_parent(bank)
    return device if device else bank

def internal_classes():
    return ['index-map']

def conf_class_expander(instantiated = False):
    '''Returns a tab completer for all classes, or if 'instantiated' is True, all
    classes that have existing objects.'''

    def complete(prefix):
        if instantiated:
            classes = {o.classname for o in SIM_object_iterator(None)}
        else:
            classes = set(SIM_get_all_classes())

        # Hide helper classes from tab completion
        classes -= set(internal_classes())
        return get_completions(prefix, classes)
    return complete

def iface_expander(prefix):
    return get_completions(prefix, sorted(all_known_interfaces()))

def class_exists(classname):
    try:
        simics.SIM_get_class(classname)
    except simics.SimExc_General:
        return False
    return True

def all_known_interfaces():
    return set.union(*(set(simics.VT_get_interfaces(c))
                       for c in SIM_get_all_classes()))

def common_exp_regs(prefix, obj, arg, catchable_only):
    # obj is set for namespace commands, i.e <obj>.read-reg
    # arg contains command arguments, i.e. [obj, reg]
    if not obj and arg[0]:
        obj = arg[0]
    elif not obj:
        obj = current_frontend_object()
    if hasattr(obj.iface, "int_register"):
        regs = [obj.iface.int_register.get_name(r)
                for r in obj.iface.int_register.all_registers()
                if not catchable_only
                or obj.iface.int_register.register_info(
                    r, simics.Sim_RegInfo_Catchable)]
    else:
        regs = []
    return cli.get_completions(prefix, regs)

# Opcode print function for targets with four-byte instructions. Print
# the opcode as a word rather than as a sequence of bytes.
def fourbyte_get_opcode(cpu, d):
    if cpu.iface.processor_info.get_endian() == simics.Sim_Endian_Big:
        data = (d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3]
    else:
        data = (d[3] << 24) | (d[2] << 16) | (d[1] << 8) | d[0]
    word = "0x%08x" % data
    return "%-*s" % (10, word)

# Print address profile views set for this processor.
aprof_column_size = {}
def get_aprof_views(cpu, vaddr, paddr, length):
    ret = " "
    for ap, view in cpu.aprof_views:
        ifc = ap.iface.address_profiler
        if ifc.physical_addresses(view):
            start = paddr
        else:
            start = vaddr
        id = (ap.name, view)
        if start != None:
            count = ifc.sum(view, start, start + length - 1)
            aprof_column_size[id] = max(aprof_column_size.get(id, 1),
                                        len("%d" % count))
            ret += "%*d " % (aprof_column_size[id], count)
        else:
            # Profiler is indexed by an address we can't compute.
            ret += "%*s " % (aprof_column_size.get(id, 1), "?")
    return ret

# Utility function commonly used by processor when implementing pregs
def in_columns(lst):
    ret = ""
    col_width = max(list(map(len, lst))) + 1
    ncols = max(1, 80 // col_width)
    nrows = (len(lst) + ncols - 1) // ncols
    for i in range(nrows):
        for j in range(ncols):
            index = i + j * nrows
            if index < len(lst):
                ret += lst[index] + " "
        ret += "\n"
    return ret

# Return a function suitable for get_disassembly in the processor_cli
# interface.  default_instr_len(address) says how many bytes an
# instruction is considered to be if that could not be determined by
# the disassembly function. disasm is the disassembly function to use.
# virtual_address_prefix is the prefix to use when printing virtual
# addresses. get_opcode is the function that formats the opcode
# bytes. It takes the cpu and a list of bytes. For backwards
# compatibility it can also take (cpu, paddr, size), and the intent is
# that the function should read phys mem, but that is really wrong if
# the opcode spans a page boundary.
# address_filter is applied to the address before it is used.
def make_disassembly_fun(default_instr_len = 4,
                         disasm = None,
                         virtual_address_prefix = "v",
                         get_opcode = fourbyte_get_opcode,
                         address_filter = lambda address: address):

    # default_instr_len can be either a function or a number. If it is
    # a number, make a function that returns that number.
    try:
        deflen = int(default_instr_len)
        default_instr_len = lambda address: deflen
    except:
        pass

    # Translate address to (virtual, physical) pair, setting virtual
    # address to None if the address is physical. May raise an
    # Exception.
    def translate_address(cpu, prefix, address):
        if prefix == "v" or prefix == "": # address is virtual
            vaddr = address
            tagged_addr = cpu.iface.processor_info.logical_to_physical(
                vaddr, Sim_Access_Execute)
            if not tagged_addr.valid:
                raise Exception("whole instruction not mapped")
            else:
                paddr = tagged_addr.address
        else: # address is physical
            vaddr = None # no way to get a well-defined virtual address
            paddr = address
        return (vaddr, paddr)

    def instruction_read_byte(cpu, paddr):
        space = cpu.physical_memory
        if not hasattr(space.iface, simics.TRANSACTION_INTERFACE):
            return simics.SIM_read_phys_memory(cpu, paddr, 1)
        t = simics.transaction_t(size = 1,
                                 fetch = True,
                                 inquiry = True,
                                 initiator = None)
        ex = space.iface.transaction.issue(t, paddr)
        if ex != simics.Sim_PE_No_Exception:
            raise simics.SimExc_Memory
        return t.data[0]

    def common_disassemble(cpu, prefix, address):
        bytes = []
        ofs = 0
        ins_len = default_instr_len(address)
        while True:
            for i in range(ins_len):
                _, paddr = translate_address(cpu, prefix, address+ofs+i)
                bytes.append(instruction_read_byte(cpu, paddr))

            elements = cpu.iface.processor_info.disassemble(address, tuple(bytes), -1)
            if elements[0] > 0: # check length
                return elements[0], elements[1], bytes
            ofs += ins_len

    if disasm == None:
        disasm = common_disassemble

    # Return the smallest number of hex digits sufficient to represent
    # the given number of bits.
    def bits_to_hex_digits(bits):
        return int((bits + 3)/4)

    def get_turbo_str(cpu, paddr, vaddr):
        if not hasattr(cpu, "turbo_blocks"):
            return ""
        if paddr:
            this_addr = paddr
        else:
            this_addr = vaddr

        for b in cpu.turbo_blocks:
            if paddr:
                addr = b[3]
            else:
                addr = b[2]
            target_len = b[4]
            if addr == this_addr:
                return "T"
            elif addr < this_addr and this_addr < addr + target_len:
                return "|"
        return " "

    def get_opcode_string(cpu, data, paddr, length):
        (args, _, _, _, _, _, _) = inspect.getfullargspec(get_opcode)
        if len(args) == 3 or data is None:
            # for compatibility if used by external customers
            # keep old type of get_opcode with three args
            return " %s " % get_opcode(cpu, paddr, length)
        else:
            return " %s " % get_opcode(cpu, data)

    # A local_print_disassemble_line function. To be returned.
    def lpdl_fun(cpu, prefix, address, print_cpu, name):
        ret = ""
        if print_cpu:
            ret += "[%s] " % cpu.name
        address = address_filter(address)
        paddr_bits = cpu.iface.processor_info.get_physical_address_width()
        vaddr_bits = cpu.iface.processor_info.get_logical_address_width()
        length = default_instr_len(address)

        try:
            vaddr, paddr = translate_address(cpu, prefix, address)
        except Exception as ex:
            # Could not get physical address.
            paddr_err_string = str(ex)
            paddr = None
            vaddr = address

        if vaddr != None:
            ret += "%s:0x%0*x " % (virtual_address_prefix,
                                   bits_to_hex_digits(vaddr_bits), vaddr)
        if paddr is None:
            ret += "<%s>" % paddr_err_string
            return (length, ret)
        if vaddr == None or disassembly_settings["physaddr"]:
            ret += "p:0x%0*x " % (bits_to_hex_digits(paddr_bits), paddr)
        length = -1

        try:
            dis = disasm(cpu, prefix, address)
            if len(dis) == 3:
                (length, asm, data) = dis
            else:
                (length, asm) = dis
                data = None
            if name != None:
                asm = name
        except simics.SimExc_Memory:
            asm = "<whole instruction not in memory>"
        except Exception as ex:
            asm = "<%s>" % ex

        if length > 0:
            if hasattr(cpu, "aprof_views") and len(cpu.aprof_views) > 0:
                ret += get_aprof_views(cpu, vaddr, paddr, 1)
            if disassembly_settings["opcode"]:
                ret += get_opcode_string(cpu, data, paddr, length)

        if disassembly_settings["turbo"]:
            ret += get_turbo_str(cpu, paddr, vaddr)

        ret += " %s" % (asm,)
        return (length, ret)

    return lpdl_fun

disassembly_settings = {
    "opcode":         0,
    "physaddr":       1,
    "partial-opcode": 1,
    "turbo":          0,
    }
disassembly_setting_desc = {
    "opcode":         "Print opcode bytes                              ",
    "physaddr":       "Print physical translation of virtual address   ",
    "partial-opcode": "Show only part of the opcode (VLIW only)        ",
    "turbo":          "Show information about generated code (internal)",
    }

def disassemble_settings_cmd(opcode, physaddr, partial_opcode, turbo):
    if (opcode is None and physaddr is None and partial_opcode is None
        and turbo is None):
        print("Current disassemble settings:")
        for name in list(disassembly_settings.keys()):
            print("  %s  %s" % (disassembly_setting_desc[name],
                                ["off", "on"][disassembly_settings[name]]))
    if opcode is not None:
        disassembly_settings["opcode"] = opcode
    if physaddr is not None:
        disassembly_settings["physaddr"] = physaddr
    if partial_opcode is not None:
        disassembly_settings["partial-opcode"] = partial_opcode
    if turbo is not None:
        disassembly_settings["turbo"] = turbo


new_command("disassemble-settings", disassemble_settings_cmd,
            [arg(bool_t("on", "off"), "opcode", "?", None),
             arg(bool_t("on", "off"), "physaddr", "?", None),
             arg(bool_t("on", "off"), "partial-opcode", "?", None),
             arg(bool_t("on", "off"), "turbo", "?", None)],
            type = ["Execution", "Memory"],
            short = "change disassembly output settings",
            see_also = ["disassemble"],
            doc = """
Change disassemble output settings. Each of these settings can be set
to <tt>on</tt> or <tt>off</tt>.

<arg>opcode</arg> indicates whether to print the raw bytes of the
instruction in addition to the disassembly. If <arg>partial-opcode</arg>
is set, and the opcode encodes more than one instruction (which can be
the case on VLIW architectures), the opcode bytes will be divided
among the instructions so that the entire opcode has been printed
exactly once when all the instructions have been disassembled. If
<arg>partial-opcode</arg> is not set, the entire opcode will be printed
for every instruction.

<arg>physaddr</arg> indicates whether to compute and display the physical
address if the virtual address was specified (if the physical address
was specified, the virtual address is never printed).

<arg>turbo</arg> will show information about generated code (internal).

Without arguments, the current settings will be shown.""")

def space_info(m, mem_on, io_on):
    dis = 0
    if m[5] & 4:
        name = "Expansion ROM"
        if not (m[5] & 1):
            dis = 1
    elif m[3] == 0: # memory
        if m[5] & 2:
            name = "64-bit Memory"
        else:
            name = "Memory"
        if not mem_on:
            dis = 1
    elif m[3] == 1: # I/O
        name = "IO"
        if not mem_on:
            dis = 1
    else:
        name = "Unknown"
    if not dis:
        desc = "base 0x%x size 0x%x (function %d)" % (m[1], m[2], m[4])
    else:
        desc = "base 0x%x size 0x%x (disabled)" % (m[1], m[2])
    return ("%s BAR 0x%x" % (name, m[0]), desc)

def get_pci_info(obj):
    try:
        rom = obj.expansion_rom
    except:
        # C++ implementations lack this attribute
        rom = None
    if rom and isinstance(rom, list):
        rom = "%s, function %d (0x%x bytes)" % (
            rom[0].name, rom[2], rom[1])
    elif rom and hasattr(obj, "expansion_rom_size"):
        rom = "%s (0x%x bytes)" % (
            rom.name, obj.expansion_rom_size)
    else:
        rom = "none"
    try:
        maps = obj.mappings
    except:
        # C++ implementations lack this attribute
        maps = []
    io_on = obj.config_registers[1] & 1
    mem_on = obj.config_registers[1] & 2
    infos = []
    for m in maps:
        infos.append(space_info(m, mem_on, io_on))
    memory_mappings = [(None,
                        [ ("Memory mappings",
                           "enabled" if mem_on else "disabled"),
                          ("IO mappings", "enabled" if io_on else "disabled")])]
    if len(infos):
        memory_mappings += [("Supported Mappings", infos)]

    return [ ("PCI information",
              [ ("PCI bus", obj.pci_bus),
                ("Expansion ROM", rom),
                ])] + memory_mappings

def get_pci_status(obj):
    return []

#
# -------------------- -> --------------------
#

# Index value with indices, and return the indexed value.
# Only if indices is empty can value be a scalar.
def get_multi_indexed(value, indices):
    for index in indices:
        value = value[index]
    return value

# Index value with indices, and set the indexed location to new_value.
# Indices must be nonemtpy, and value must be a list.
def set_multi_indexed(value, indices, new_value):
    for index in indices[:-1]:
        value = value[index]
    value[indices[-1]] = new_value

def conf_obj_exists(name):
    try:
        SIM_get_object(name)
    except simics.SimExc_General:
        return False
    return True

def attribute_cmd(objname, attr, idx, rw, v):
    try:
        obj = cli.get_object(objname)
    except simics.SimExc_General:
        raise CliError('There is no object called "%s"' % objname)

    def get_at_indices(value, indices):
        try:
            return get_multi_indexed(value, indices)
        except (IndexError, TypeError) as ex:
            raise CliError("Failed indexing attribute %s of %s: %s"
                           % (attr, obj.name, ex))

    def set_at_indices(value, indices, new_value):
        try:
            set_multi_indexed(value, indices, new_value)
        except (IndexError, TypeError) as ex:
            raise CliError("Failed indexing attribute %s of %s: %s"
                           % (attr, obj.name, ex))

    def get_attr(index):
        try:
            return simics.SIM_get_attribute_idx(obj, attr, index)
        except simics.SimExc_General as ex:
            raise CliError("Reading attribute %s of %s: %s"
                           % (attr, obj.name, ex))

    def set_attr(index, value):
        try:
            simics.SIM_set_attribute_idx(obj, attr, index, value)
        except simics.SimExc_General as ex:
            raise CliError("Setting attribute %s of %s: %s"
                           % (attr, obj.name, ex))

    try:
        aa = simics.SIM_get_attribute_attributes(obj.class_data, attr)
    except simics.SimExc_Lookup:
        raise CliError('The "%s" object has no attribute "%s"'
                       % (obj.name, attr))
    is_indexed = aa & simics.Sim_Attr_Integer_Indexed

    opflag = rw[2]
    if opflag == "-r":
        # read obj->attr
        if is_indexed and idx:
            # For indexed attributes, use the first index as attribute index.
            attr_index = idx[0]
            idx = idx[1:]
        else:
            attr_index = None

        attr_val = get_attr(attr_index)
        val = get_at_indices(attr_val, idx)

        try:
            ret_val = cli_impl.value_to_token(val).get_py_value(False)
        except CliError:
            # The value could not be translated to CLI.
            print(cli.format_attribute(val))
            ret_val = None
        return ret_val

    elif opflag == "-w":
        # obj->attr = value
        (_, val, _) = v

        if is_indexed and idx:
            attr_index = idx[0]
            idx = idx[1:]
        else:
            attr_index = None
        if idx:
            # Set only part of the attribute value.
            attr_val = get_attr(attr_index)
            set_at_indices(attr_val, idx, val)
            set_attr(attr_index, attr_val)
        else:
            # Set the whole value (possibly attribute-indexed).

            try:
                simics.SIM_set_attribute_idx(obj, attr, attr_index, val)
            except simics.SimExc_General as ex:
                # Hack: CLI has no object data type, but we permit
                # assignments where the value names an object. For
                # compatibility, we also allow 0 to be used instead of NIL.
                attr_type = simics.VT_get_attribute_type(obj.classname, attr)
                alt_value = -1
                if isinstance(val, str) and conf_obj_exists(val):
                    alt_value = SIM_get_object(val)
                elif isinstance(val, (int, float)) and val == 0:
                    alt_value = None
                if (alt_value != -1
                    and simics.DBG_check_typing_system(
                        attr_type, alt_value) == 0):
                    set_attr(attr_index, alt_value)
                else:
                    raise CliError("Setting attribute %s of %s: %s"
                                   % (attr, obj.name, ex))
            except TypeError as ex:
                raise CliError("Setting attribute %s of %s: %s"
                               % (attr, obj.name, ex))

    else:
        assert opflag in {"-i", "-d"}
        # obj->attr ±= value
        (_, val, _) = v

        if is_indexed and idx:
            attr_index = idx[0]
            idx = idx[1:]
        else:
            attr_index = None

        attr_val = get_attr(attr_index)

        old_indexed_val = get_at_indices(attr_val, idx)

        # We only permit: int ± int, float ± int, float ± float,
        # string + string and list + list.
        if not ((isinstance(old_indexed_val, int)
                 and isinstance(val, int))
                or (isinstance(old_indexed_val, float)
                    and isinstance(val, (int, float)))
                or (opflag == "-i"
                    and ((isinstance(old_indexed_val, list)
                          and isinstance(val, list))
                         or (isinstance(old_indexed_val, str)
                             and isinstance(val, str))))):
            raise CliError("Setting attribute %s of %s: bad types for %s"
                           % (attr, obj.name, {"-i": "+=", "-d": "-="}[opflag]))
        if opflag == "-i":
            new_indexed_val = old_indexed_val + val
        else:
            new_indexed_val = old_indexed_val - val

        if idx:
            set_at_indices(attr_val, idx, new_indexed_val)
        else:
            attr_val = new_indexed_val

        set_attr(attr_index, attr_val)


markup_arrow = [ Markup.Arg('object'), Markup.Keyword('->'),
                 Markup.Arg('attribute') ]
new_operator("->", attribute_cmd,
             [arg(str_t, doc = 'object'),
              arg(str_t, doc = 'attribute'),
              arg(list_t),
              arg((flag_t, flag_t, flag_t, flag_t),
                  ('-r', '-w', '-d', '-i'), doc = ' '),
              arg((int_t, str_t, float_t, list_t, nil_t), doc = ' ',
                  # empty expander to override the nil_t expander SIMICS-15906
                  expander = (lambda x: [],) * 5)],
             type = ["CLI"],
             pri = 700, infix = 1,
             group_short = "access object attribute",
             short = "access object attribute",
             synopses = [ markup_arrow,
                          markup_arrow + [ ' ', Markup.Keyword('='), ' ',
                                           Markup.Arg('expression') ] ],
             doc = """
Access the attribute <arg>attribute</arg> in <arg>object</arg>. Only
object, string, float, integer, boolean, nil and list attributes can be
returned by the command.

When reading other attribute types, they will be printed but the
command will not return anything.""")

#
# -------------------- + --------------------
#

def plus(a, b):
    if a[0] == b[0]:
        return a[1] + b[1]
    elif str_t in (a[0], b[0]):
        return str(a[1]) + str(b[1])
    elif int_t in (a[0], b[0]) and float_t in (a[0], b[0]):
        return a[1] + b[1]
    else:
        raise CliError("Cannot add values of types %s and %s." % (
            a[0].desc(), b[0].desc()))

new_operator("+", plus, [arg((int_t, str_t, list_t, float_t)),
                         arg((int_t, str_t, list_t, float_t))],
             type = ["CLI"],
             pri = 150, infix = 1,
             group_short = "arithmetic addition",
             short = "arithmetic addition, string and list concatenation",
             doc = """
Arithmetic addition, string and list concatenation of <arg>arg1</arg> and
<arg>arg2</arg>.
""")

#
# -------------------- - --------------------
#

def minus(a, b):
    return a[1] - b[1]

new_operator("-", minus, [arg((int_t, float_t)),
                          arg((int_t, float_t))],
             type = ["CLI"],
             pri = 150, infix = 1,
             short="arithmetic subtraction",
             doc="""
Arithmetic subtraction of <arg>arg1</arg> and <arg>arg2</arg>.
""")

#
# -------------------- * --------------------
#

def muls(a, b):
    if ((a[0] == list_t and not b[0] == int_t)
        or (b[0] == list_t and not a[0] == int_t)):
        raise CliError("A list can only be multiplied with an integer")
    return a[1] * b[1]

new_operator("*", muls,  [arg((int_t, float_t, list_t)),
                          arg((int_t, float_t, list_t))],
             type = ["CLI"],
             pri = 200, infix = 1, short="arithmetic multiplication",
             doc="""
Arithmetic multiplication of <arg>arg1</arg> and <arg>arg2</arg>.
""")

#
# -------------------- / --------------------
#

def div(a, b):
    if b[1] == 0:
        raise CliError("Division by zero")
    if a[0] == int_t and b[0] == int_t:
        return a[1] // b[1]
    else:
        return a[1] / b[1]

new_operator("/", div, [arg((int_t, float_t)),
                        arg((int_t, float_t))],
             type = ["CLI"],
             pri = 200, infix = 1, short="arithmetic division",
             doc="""
Arithmetic division of <arg>arg1</arg> and <arg>arg2</arg>.
""")

#
# -------------------- & --------------------
#

def and_cmd(a, b):
    return a & b

new_operator("&", and_cmd, [arg(int_t), arg(int_t)],
             type = ["CLI"],
             pri = 80, infix = 1, group_short = "various bitwise operators",
             short="bitwise AND operation", doc = """
Bitwise AND operation of <arg>arg1</arg> and <arg>arg2</arg>.
""")


#
# -------------------- | --------------------
#

def or_cmd(a, b):
    return a | b

new_operator("|", or_cmd, [arg(int_t), arg(int_t)],
             type = ["CLI"],
             pri = 60, infix = 1, short="bitwise OR operation",
             doc="""
Bitwise OR operation of <arg>arg1</arg> and <arg>arg2</arg>.
""")

#
# -------------------- ^ --------------------
#

def xor_cmd(a, b):
    return a ^ b

new_operator("^", xor_cmd, [arg(int_t), arg(int_t)],
             type = ["CLI"],
             pri = 70, infix = 1, short="bitwise XOR operation",
             doc="""
Bitwise XOR operation of <arg>arg1</arg> and <arg>arg2</arg>.
""")

#
# -------------------- >> --------------------
#

def shr_cmd(a, b):
    if b < 0:
        return a << -b
    return a >> b

new_operator(">>", shr_cmd, [arg(int_t), arg(int_t)],
             type = ["CLI"],
             pri = 100, infix = 1, short="bitwise right shift",
             doc="""
Bitwise shift of the <arg>arg1</arg> value, <arg>arg2</arg> bits to the right.
""")

#
# -------------------- << --------------------
#

def shl_cmd(a, b):
    if b < 0:
        return a >> -b
    return a << b

new_operator("<<", shl_cmd, [arg(int_t), arg(int_t)],
             type = ["CLI"],
             pri = 100, infix = 1, short="bitwise left shift",
             doc="""
Bitwise shift of the <arg>arg1</arg> value, <arg>arg2</arg> bits to the left.
""")


#
# -------------------- ~ --------------------
#

def not_cmd(a):
    return ~a

new_operator("~", not_cmd, [arg(int_t)],
             type = ["CLI"],
             pri = 250, short="bitwise not",
             doc="""
Bitwise not of <arg>arg1</arg>.
""")

#
# -------------------- : --------------------
#

def colon(x, y):
    # Operator defined by the grammar but not used for anything. Currently :
    # can be found in Windows paths, obj:port and in string arguments
    return str(x[1]) + ':' + str(y[1])

def colon_expander(sub, obj, arg):
    (argtype, comp) = arg[0][:2]
    if argtype == str_t and cli.old_is_drive(comp, sub):
        return cli_impl.file_expander(comp + ':' + sub)
    else:
        return []

new_operator(":", colon, [arg((str_t, int_t)),
                          arg((str_t, int_t),
                              expander = (colon_expander, None))],
             type = ["CLI"],
             pri = 700, infix = 1,
             short="unused operator",
             doc = 'Do not use')

#
# -------------------- pow --------------------
#

def pow_cmd(a, b):
    return a[1] ** b[1]

new_operator("pow", pow_cmd, [arg((int_t, float_t)),
                              arg((int_t, float_t))],
             type = ["CLI"],
             pri = 500, infix = 1, short="power of", doc="""
Return the <arg>arg1</arg> to the power of <arg>arg2</arg>.
""")

#
# -------------------- in-list --------------------
#

def in_list_cmd(a, b):
    return a in b

new_command("in-list", in_list_cmd,
            [arg(poly_t('needle', str_t, int_t, float_t, bool_t(), nil_t),
                 name = 'needle'),
             arg(list_t, name = 'haystack')],
            type = ["CLI"],
            short="check for occurrence in list",
            doc="""
Returns true if the argument <arg>needle</arg> can be found in
<arg>haystack</arg> and false if not. The first argument is an integer, string,
floating point or boolean value and the second is a list.
""")

#
# -------------------- in-string --------------------
#

def in_string_cmd(a, b):
    return a in b

new_command("in-string", in_string_cmd,
            [arg(str_t, name = 'needle'),
             arg(str_t, name = 'haystack')],
            type = ["CLI"],
            short="check for substring in string",
            doc="""
Returns true if the string argument <arg>needle</arg> can be found in
the <arg>haystack</arg> string and false if not.
""")

#
# -------------------- python --------------------
#

def python_return(val):
    if isinstance(val, simics.conf_object_t):
        # special handling of conf-object: use its name as return value
        text_repr = repr(val)
        val = val.name
    else:
        # convert to CLI value before presenting (may raise CliError)
        text_repr = cli_impl.value_to_token(val).string()
    return command_return(message = text_repr, value = val)

def python_cmd(text):
    try:
        (ret, _) = run_python_for_simics_script(text)
    except Exception as ex:
        raise CliError("Error in Python expression: %s" % ex)
    return python_return(ret)

new_command("python", python_cmd, [arg(str_t, "exp")],
            type = ["CLI", "Python"],
            short = "evaluate a Python expression",
            see_also = ['@', 'run-script', 'python-mode'],
            doc = """
Evaluates <arg>exp</arg> as a statement or expression in Python and returns the
result of any. For example:
<br/>
<cmd>$all_objects = (python "list(SIM_object_iterator(None))")</cmd>
<br/>
""")

new_command("`", cli_impl._DummyCommandHandler("`...`"),
            type  = ["CLI", "Python"],
            short = "evaluate a Python expression",
            doc_with = "python",
            synopsis = [ Markup.Keyword('`'),
                         Markup.Arg('exp'),
                         Markup.Keyword('`') ])

# Function runs 'text' as Python code assuming it is the code from a Simics
# script or Simics command line. All exceptions (including syntax errors)
# generated by the code are thrown as they are without any handling.
@cli.stop_traceback
def run_python_for_simics_script(text):
    def get_filename():
        # Returns a filename pointing to the location in a Simics script
        # in order to make Python stack traces more informative.
        script_pos = cli.get_script_pos()
        if script_pos is None:
            return "<string>"

        filename, line = script_pos
        if filename.startswith('<') and filename.endswith('>'):
            # Special case like '<cmdline>' (line is 0 and of no use):
            # use it as it is.
            return filename

        # NB: filenames starting with "<" and ending with ">" are treated
        # specially when Python interpreter formats a stacktrace:
        # the interpreter knows that such files don't exist and doesn't try
        # to find them on the disk in order to read code from them. We use
        # this fact to prevent unnecessary scanning of the disk.
        return f"<{filename}:{line}>"

    filename = get_filename()
    try:
        code = compile(text, filename, "eval")
    except (SyntaxError, TypeError):
        is_expression = False
    else:
        is_expression = True

    if not is_expression:
        # Don't run another compile directly in the except block of the first
        # compile as an error would output a traceback showing the error twice.
        code = compile(text, filename, "exec")

    ret = eval(code, __main__.__dict__)  # nosec: eval is intended here
    return (ret, is_expression)

@cli.stop_traceback
def one_line_python_cmd(text):
    try:
        (ret, is_expression) = run_python_for_simics_script(text)
    except SystemExit as ex:
        simics.SIM_quit(ex.code if isinstance(ex.code, int) else 0)
    except:
        (extype, value, tb) = sys.exc_info()
        msg = cli_impl.get_error_tb(extype, value, tb, True)
        if not cli_impl.stdout_output_mode.markup:
            msg = cli_impl.filter_out_simics_markup(msg)
        raise CliError(msg)

    if not is_expression:
        return  # no return value if the Python code is not an expression
    if interactive_command():
        sys.displayhook(ret)
    else:
        # While the @ command cannot be used in CLI expressions, a user may have
        # called it through run_command() to get a return value. Keep the
        # following code for backward compatibility until a future major
        # release.
        message = repr(ret)
        try:
            val = python_return(ret).get_value()
        except CliError:
            # Value cannot be converted to CLI, return string representation
            val = message
        return command_return(message = message, value = val)

new_command("@", one_line_python_cmd, [arg(str_t, "exp")],
            type  = ["CLI", "Python"],
            short = "evaluate a Python statement",
            see_also = ["python", "run-script", "python-mode"],
            synopsis = [ Markup.Keyword('@'), Markup.Arg('python-statement') ],
            doc = """
Evaluates the rest of the command line as a Python statement or expression.
Return values from expressions are printed as in Python and are not affected
by CLI output settings, such as output radix, unlike the <cmd>python</cmd>
command.""")

#
# -------------------- list-commands --------------------
#

def list_commands_cmd(obj, cls, iface, substr, plain, gonly):
    cmds  = set()
    if obj:
        cmds = set(cli.get_object_commands(obj))
    if cls:
        if not class_exists(cls):
            raise CliError(f"Class '{cls}' not registered by any"
                           " loadable module")
        else:
            cc = set(cli.get_class_commands(cls))
            if not cmds:
                cmds = cc
            else:
                cmds &= cc
    if iface:
        if iface not in all_known_interfaces():
            raise CliError(f"Interface '{iface}' not registered"
                           " by any loaded class")
        else:
            ic = set(cli.get_iface_commands(iface))
            if not cmds:
                cmds = ic
            else:
                cmds &= ic
    if not (obj or cls or iface):
        if gonly:
            cmds = [
                x for x in cli.global_cmds.get_all_accessible_global_commands()]
        else:
            cmds = cli.simics_commands()

    cmds = [c for c in cmds if substr in c.name and not ":" == c.name]
    cmds = sorted(cmds)

    if plain:
        data = [c.name for c in cmds]
        rows = [[d] for d in data]
        props = [(Table_Key_Columns, [[(Column_Key_Name, n)] for n in
                                      ["Command"]])]
    else:
        data = [[c.name, c.short] for c in cmds]
        rows = data
        props = [(Table_Key_Columns, [[(Column_Key_Name, n)] for n in
                                      ["Command", "Short Description"]])]
    tbl = table.Table(props, rows)
    msg = tbl.to_string(rows_printed=0, no_row_column=True) if data else ""
    return command_verbose_return(msg, data)

new_command("list-commands", list_commands_cmd,
            [arg(obj_t("object"), "object", "?", None),
             arg(str_t, "class", "?", None, expander = conf_class_expander()),
             arg(str_t, "iface", "?", None, expander = iface_expander),
             arg(str_t, "substr", "?", ""),
             arg(flag_t, "-plain"),
             arg(flag_t, "-global-only"),
            ],
            type = ["CLI", "Help"],
            short="list CLI commands",
            doc = """
Returns a list of CLI commands. If used in an expression it returns a list of
tuples which each contains the command name, and its short description.
Otherwise the list is printed.

If the <tt>-plain</tt> flag is specified, the return value or output
is instead only a list of command names.

Note that only those commands that have been registered with Simics at the
current time are listed. Hence, commands in modules or target systems that are
not yet loaded, will not be listed.

If the <tt>-global-only</tt> flag is specified, just global commands are
listed.

Without any arguments all commands will be listed. The <arg>object</arg>
argument will filter for commands registered on the specified object. The
<arg>class</arg> and <arg>iface</arg> arguments will filter on the given class
and/or interface names. And the <arg>substr</arg> argument will filter on
commands with matching names.
""")

def get_command_args_cmd(cmd):
    if not cmd in cli_impl.all_commands.cmds_dict:
        raise CliError(f"No such command: {cmd}")
    arg_names = [x.name for x in cli_impl.all_commands.cmds_dict[cmd].args]
    return command_return(value = arg_names)

def cmd_expander(comp):
    return get_completions(comp, cli_impl.all_commands.cmds_dict.keys())

new_command("get-command-args", get_command_args_cmd,
            args = [ arg(str_t, "command", expander = cmd_expander)],
            type = ["CLI", "Help"],
            short="get list of command arguments",
            doc = """Returns a list of argument names for a CLI
            <arg>command</arg>.""")

def api_help_cmd(str):
    import api_help
    import api_doc

    if api_doc.print_doc(str):
        return

    if api_help.api_help(str):
        print("Help on API keyword \"%s\":\n" % str)
        refmanual.print_api_help(str)
        return

    l = []
    for source in [api_doc.topics, api_help.topics]:
        for key in source():
            if key.find(str) >= 0:
                l.append(key)

    if not l:
        raise CliError(f'No API keyword matching "{str}" found.'
                       ' Try using the api-search command.')

    if len(l) == 1:
        return api_help_cmd(l[0])

    l.sort()
    print("The following API keywords contain the substring \"%s\":\n" % str)
    print_columns('l', l, has_title = 0, wrap_space = "  ")

def api_help_expander(comp):
    import api_help
    import api_doc

    return [key
            for source in [api_doc.topics, api_help.topics]
            for key in source()
            if key.lower().startswith(comp.lower())]

new_command("api-help", api_help_cmd,
            [ arg(str_t, "topic", expander = api_help_expander) ],
            short = "get API help",
            type = ["Help"],
            see_also = ["help", "api-search", "help-search"],
            doc = """
Shows API help on the given <arg>topic</arg>.

This command does the same thing as <cmd>help api:<arg>topic</arg></cmd>.""")

_api_help_description = {}
def get_api_help_description():
    global _api_help_description
    if _api_help_description:
        return _api_help_description

    import bz2
    import pickle
    path = SIM_lookup_file(
        '%simics%/' + conf.sim.host_type + '/doc/api-help-description.bz2')
    if path:
        # We trust data in the installation
        _api_help_description = pickle.load(bz2.BZ2File(path, 'rb')) # nosec
    return _api_help_description

def api_apropos_cmd(topic):
    import api_help
    from api_doc import apropos
    api_doc = get_api_help_description()

    def api_helps(topic):
        '''Generator that generates all strings used in the documentation of
        the API topic 'topic'.'''
        yield topic
        topic_help = api_help.api_help(topic)
        if len(topic_help) == 2:
            # Python API entries
            yield topic_help[1]
            return

        # C API entries
        for apis, help in topic_help[2]:
            if help is None:
                continue
            yield help

    l = []
    for key in api_help.topics():
        if any(s.find(topic) >= 0 for s in api_helps(key)):
            l.append(key)
        elif key in api_doc:
            if topic in api_doc[key]:
                l.append(key)

    l.extend(apropos(topic))

    if not l:
        raise CliError(
            f'The string "{topic}" cannot be found in any API documentation.')

    l.sort()
    if topic:
        print(('The string \"%s\" can be found in the following API'
               ' help entr%s:\n' % (topic, y_or_ies(len(l)))))
    else:
        print("The following API help entries exist:\n")
    print_columns('l', l, has_title = 0, wrap_space = "  ")

new_command("api-search", api_apropos_cmd,
            [ arg(str_t, "search-string") ],
            alias = "api-apropos",
            short = "search API help",
            type = ["Help"],
            see_also = ["api-help", "help", "help-search"],
            doc = """
Search the API documentation for the string <arg>search-string</arg>.
""")



#
# -------------------- hex --------------------
#

def int_fmt_cmd(value, radix, unformatted, no_prefix):
    if unformatted:
        return number_str(value, radix, 0, use_prefix = not no_prefix)
    else:
        return number_str(value, radix, use_prefix = not no_prefix)

def hex_cmd(value, unformatted, no_prefix):
    return int_fmt_cmd(value, 16, unformatted, no_prefix)

new_command("hex", hex_cmd,
            [arg(int_t, "value"), arg(flag_t, "-u"), arg(flag_t, "-p")],
            type = ["CLI"],
            short = "display integer in hexadecimal notation",
            see_also = ["print", "bin", "oct", "dec",
                        "digit-grouping", "atoi"],
            doc = """
Returns the parameter as a string in hexadecimal notation. This is similar to
<cmd>print</cmd> -x <arg>value</arg>. To ignore any default digit grouping, the
<tt>-u</tt> (unformatted) flag is used, while <tt>-p</tt> removes the
radix prefix <tt>0x</tt>.""")

def dec_cmd(value, unformatted):
    return int_fmt_cmd(value, 10, unformatted, False)

new_command("dec", dec_cmd,
            [arg(int_t, "value"), arg(flag_t, "-u")],
            type = ["CLI"],
            short = "display integer in decimal notation",
            see_also = ["print", "hex", "bin", "oct",
                        "digit-grouping", "atoi"],
            doc = """
Returns the parameter as a string in decimal notation. This is similar to
<cmd>print</cmd> -d <arg>value</arg>. To ignore any default digit grouping, the
<tt>-u</tt> (unformatted) flag is used.""")


def oct_cmd(value, unformatted, no_prefix):
    return int_fmt_cmd(value, 8, unformatted, no_prefix)

new_command("oct", oct_cmd,
            [arg(int_t, "value"), arg(flag_t, "-u"), arg(flag_t, "-p")],
            type = ["CLI"],
            short = "display integer in octal notation",
            see_also = ["print", "hex", "bin", "dec",
                        "digit-grouping", "atoi"],
            doc = """
Returns the parameter as a string in octal notation. This is similar to
<cmd>print</cmd> -o <arg>value</arg>. To ignore any default digit grouping, the
<tt>-u</tt> (unformatted) flag is used, while <tt>-p</tt> removes the
radix prefix <tt>0o</tt>.""")


def bin_cmd(value, unformatted, no_prefix):
    return int_fmt_cmd(value, 2, unformatted, no_prefix)

new_command("bin", bin_cmd,
            [arg(int_t, "value"), arg(flag_t, "-u"), arg(flag_t, "-p")],
            type = ["CLI"],
            short = "display integer in binary notation",
            see_also = ["print", "hex", "oct", "dec",
                        "digit-grouping", "atoi"],
            doc = """
Returns the parameter as a string in binary notation. This is similar to
<cmd>print</cmd> -b <arg>value</arg>. To ignore any default digit grouping, the
<tt>-u</tt> (unformatted) flag is used, while <tt>-p</tt> removes the
radix prefix <tt>0b</tt>.""")

import fp_to_string

def int_to_fp(value, mode):
    fp_val = fp_to_string.fp_to_fp(mode, value)
    return command_return(message = "%f" % fp_val, value = fp_val)

def int_to_single_cmd(value):
    return int_to_fp(value, "s")

def int_to_double_cmd(value):
    return int_to_fp(value, "d")

def int_to_edouble_cmd(value):
    return int_to_fp(value, "ed")

def int_to_quad_cmd(value):
    return int_to_fp(value, "q")

new_command("int-to-single-float", int_to_single_cmd,
            [arg(int_t, "value")],
            type = ["CLI"],
            short = "interpret integer as 32-bit floating point",
            doc = """
Returns the integer <arg>value</arg> interpreted as a IEEE 32-bit floating point
number.""")

new_command("int-to-double-float", int_to_double_cmd,
            [arg(int_t, "value")],
            type = ["CLI"],
            short = "interpret integer as 64-bit floating point",
            doc = """
Returns the integer <arg>value</arg> interpreted as a IEEE 64-bit floating point
number.""")

new_command("int-to-extended-double-float", int_to_edouble_cmd,
            [arg(int_t, "value")],
            type = ["CLI"],
            short = "interpret integer as 80-bit floating point",
            doc = """
Returns the integer <arg>value</arg> interpreted as a x87 80-bit floating point
number.""")

new_command("int-to-quad-float", int_to_quad_cmd,
            [arg(int_t, "value")],
            type = ["CLI"],
            short = "interpret integer as 128-bit floating point",
            doc = """
Returns the integer <arg>value</arg> interpreted as a IEEE 128-bit floating
point number.""")

#
# -------------------- output-radix --------------------
#
def output_radix_cmd(rad, digits):
    if rad == 0 and digits < 0:
        rad = cli.get_output_radix()
        digits = cli.get_output_grouping(rad)
        print("The current output-radix is %d." % rad)
        if digits:
            print("Output is grouped in units of %d digits." % digits)
        return

    try:
        if rad != 0:
            cli.set_output_radix(rad)
        if digits >= 0:
            cli.set_output_grouping(rad or cli.get_output_radix(), digits)
    except ValueError as ex:
        raise CliError("Failed changing output radix: %s" % ex)

new_command("output-radix", output_radix_cmd,
            [ arg(int_t, "base", "?", 0),
              arg(int_t, "group", "?", -1) ],
            type = ["CLI"],
            short = "change the default output radix",
            see_also = ["digit-grouping", "print", "hex", "dec", "oct", "bin"],
            doc = """
Change or display the default output radix for numbers. <arg>base</arg> can be
set to 2 for binary, 8 for octal, 10 for decimal, or 16 for hexadecimal
output.

If <arg>group</arg> is non-zero, numbers will be grouped in groups of
<arg>group</arg> digits, separated by underscores (<tt>_</tt>).

This affects the output of many CLI commands, such as
<cmd>print</cmd>, <cmd>hex</cmd>, <cmd>dec</cmd>, <cmd>oct</cmd>,
and <cmd>bin</cmd> commands, and how return values from commands are
displayed in CLI.

Without arguments, the current setting will be shown.

Run <cmd>save-preferences</cmd> to save any changes.
""")

#
# -------------------- digit-grouping --------------------
#
def digit_grouping_cmd(rad, digits):
    if rad > 0 and digits < 0:
        raise CliError("Both base and digits are required.")

    radixes = [2, 8, 10, 16]
    if rad < 0 or digits < 0:
        digits = [[rad, cli.get_output_grouping(rad)] for rad in radixes]
        props  = [(table.Table_Key_Columns,
                   [[(table.Column_Key_Name, n),
                     (Column_Key_Int_Radix, 10)] for n in ["Radix", "Digits"]])]
        result_table = table.Table(props, digits)
        print(result_table.to_string(no_row_column=True))
        return
    elif rad not in radixes:
        raise CliError("The radix must be either 2, 8, 10, or 16.")
    try:
        cli.set_output_grouping(rad, digits)
    except ValueError as ex:
        raise CliError(f"Failed changing digit grouping: {ex}")

new_command("digit-grouping", digit_grouping_cmd,
            [ arg(int_t, "base", "?", -1),
              arg(int_t, "digits", "?", -1) ],
            type = ["CLI"],
            short = "set or show output formatting for numbers",
            see_also = ["output-radix", "print", "hex", "dec", "oct", "bin"],
            doc = """
Change or display how numbers are formatted for the given <arg>base</arg>
(radix). If not both arguments are given the current preferences are printed.

This command will separate groups of <arg>digits</arg> digits by an
underscore when they are formatted for output. Separate grouping is maintained
for each radix. If <arg>digits</arg> is zero, no separators are printed for
that radix.

Run <cmd>save-preferences</cmd> to save any changes.""")

#
# -------------------- print --------------------
#
def print_single_int(f, value, size):
    base = None
    s = False
    assert isinstance(value, int)
    if f is not None:
        if f[2] == "-s":
            s = True
        else:
            base = {'-x': 16, '-d': 10, '-o': 8, '-b': 2}[f[2]]

    if size not in {8, 16, 32, 64, 128}:
        raise CliError("Size must be 8, 16, 32, 64, or 128")

    if value < 0:
        if value < -(1 << size):
            print(f'Truncated "{value}" to {size} bits.')
        value = ((1 << size) + value) & ((1 << size) - 1)
    elif value >= (1 << size):
        value = value & ((1 << size) - 1)
        print(f'Truncated "{value}" to {size} bits.')

    if s and value >= (1 << (size - 1)):
        value -= 1 << size

    return number_str(value, radix=base)

def print_single_cmd(f, value, size):
    return command_verbose_return(print_single_int(f, value, size))

def check_int_list(l):
    assert isinstance(l, list)
    for x in l:
        if isinstance(x, list):
            check_int_list(x)
        else:
            if not isinstance(x, int):
                raise CliError("Input list must have integer elements.")

def print_int_list(f, l, size):
    value = []
    for x in l:
        if isinstance(x, list):
            value.append(print_int_list(f, x, size))
        else:
            value.append(print_single_int(f, x, size))
    return value

def print_cmd(f, value, size):
    assert isinstance(value, (list, int))
    if isinstance(value, list):
        check_int_list(value)
        return command_verbose_return(print_int_list(f, value, size))
    else:
        return print_single_cmd(f, value, size)

new_command("print", print_cmd,
            [arg((flag_t, flag_t, flag_t, flag_t, flag_t),
                 ("-x", "-o", "-b", "-s", "-d"), "?"),
             arg(poly_t("value", int_t, list_t), "value"),
             arg(int_t, "size", "?", 64)],
            alias="p",
            repeat=print_cmd,
            type=["CLI"],
            short="display integer in various bases",
            see_also=["output-radix", "echo", "hex", "dec", "oct", "bin",
                      "digit-grouping", "atoi"],
            doc="""
Prints <arg>value</arg> in hexadecimal (<tt>-x</tt>), decimal (<tt>-d</tt>),
octal (<tt>-o</tt>), or binary (<tt>-b</tt>) notation. Default is to use the
notation specified by the <cmd>output-radix</cmd> command.

Use <tt>-s</tt> to convert the value to signed integers. <arg>size</arg> is the
bit width to use. E.g., <cmd>print -x 257 8</cmd> will print 0x1. Valid sizes
are 8, 16, 32, 64, and 128 bits. Default size is 64.
""")

#
# ---------------- split-string ---------------
#

def split_filename(split_str):
    filename = ''
    dirname = ''
    sep_found = False
    for i in reversed(list(range(len(split_str)))):
        if split_str[i] in ('/', '\\'):
            if not sep_found:
                dirname = split_str[:i + 1]
                sep_found = True
            continue
        if sep_found:
            if split_str[i] != ':':
                dirname = split_str[:i + 1]
            break
        else:
            filename = split_str[i] + filename
    if not dirname and len(filename) == 2 and filename[1] == ':':
        dirname = filename
        filename = ''
    return [dirname, filename]

def split_string_cmd(sep_type, str_type, split_str, string_return):
    if not sep_type:
        sep = None if len(str_type) == 0 else str_type
        return split_str.split(sep)

    if string_return:
        return_type = lambda x, y = 0 : x
    else:
        return_type = lambda x, y = 0 : int(x, y)
    if str_type == 'ethernet':
        val = split_str.split(':')
        try:
            if len(val) == 6 and all(int(x, 16) < 256 for x in val):
                return [return_type(x, 16) for x in val]
        except:
            pass
        raise CliError('String "%s" not in Ethernet address format' % split_str)
    elif str_type == 'ipv4':
        val = split_str.split('.')
        try:
            if len(val) == 4 and all(int(x) < 256 for x in val):
                return [return_type(x) for x in val]
        except:
            pass
        raise CliError('String "%s" not in IPv4 address format' % split_str)
    elif str_type == 'ipv6':
        val = split_str.split(':')
        if len(val) < 3:
            raise CliError('String "%s" not in IPv6 address format' % split_str)
        if val[0] == '' and val[1] == '':
            # remove duplicate spaces in list (happens on '::0')
            val.pop(0)
        elif val[0] == '':
            raise CliError('String "%s" not in IPv6 address format' % split_str)
        if val.count('') > 1:
            raise CliError('String "%s" not in IPv6 address format' % split_str)
        if '' in val:
            idx = val.index('') # replace :: with 0s
            val[idx:idx + 1] = ['0'] * (9 - len(val))
        if len(val) != 8 or any(int(x, 16) > 0xffff for x in val):
            raise CliError('String "%s" not in IPv6 address format' % split_str)
        return [return_type(x, 16) for x in val]
    elif str_type == 'filename':
        return split_filename(split_str)
    elif str_type == 'path':
        parts = []
        od = None
        d, f = split_filename(split_str)
        while d != od:
            if f:
                parts.insert(0, f)
            od = d
            d, f = split_filename(d)
        if f:
            parts.insert(0, f)
        elif d:
            parts.insert(0, d)
        return parts
    else:
        raise CliError('Unsupported string type "%s"' % str_type)

new_command("split-string", split_string_cmd,
            [arg(flag_t, "-type"),
             arg(str_t, "separator"), arg(str_t, "string"),
             arg(flag_t, "-str")],
            type = ["CLI"],
            short = "split string based on its type",
            doc = """
Splits the <arg>string</arg> argument using the given <arg>separator</arg> or
based on its type. A type is selected by adding the <tt>-type</tt> flag and
providing the name of type in the <arg>separator</arg> argument. The supported
types are <tt>ethernet</tt>, <tt>ipv4</tt>, <tt>ipv6</tt>, <tt>filename</tt>
or <tt>path</tt>.

If the empty string is used as separator, the command will split at any
whitespace.

The return value from the command is a list of strings or integers depending
on the type. If a user-supplied separator is used instead of a type, a list of
strings is returned. The <tt>-str</tt> can be used to always get a return
value of strings no matter the type.

Supported conversion types:
<dl>
<dt><tt>ethernet</tt></dt><dd>Split Ethernet MAC address into list of
six integers.</dd>
<dt><tt>ipv4</tt></dt><dd>Split IPv4 address in dot-decimal notation
into list of four integers.</dd>
<dt><tt>ipv6</tt></dt><dd>Split IPv6 address in hexadecimal,
colon-separated notation into list of eight integers.</dd>
<dt><tt>filename</tt></dt><dd>Split a filesystem path into a directory
part and a filename part.</dd>
<dt><tt>path</tt></dt><dd>Split a filesystem path into one part for
each directory level.</dd>
</dl>

The <tt>filename</tt> and <tt>path</tt> types work on both Linux and Windows
style filesystem paths independent of the host system.

Examples using pre-defined string types:

<tt>"ethernet" "ff:fe:01:55:88:11"</tt> &rarr; <tt>[255, 254, 1, 85, 136, 17]</tt><br/>
<tt>"ipv4" "255.0.0.1"</tt> &rarr; <tt>[255, 0, 0, 1]</tt><br/>
<tt>"ipv6" "2001:db8:85a3::7334"</tt> &rarr; <tt>[8193, 3512, 34211, 0, 0, 0, 0, 29492]</tt><br/>
<tt>"ipv6" "::1"</tt> &rarr; <tt>[0,0,0,0,0,0,0,1]</tt><br/>
<tt>"ipv6" -str "1:ffff::1"</tt> &rarr; <tt>["1","ffff","0","0","0","0","0","1"]</tt><br/>
<tt>"filename" "/"</tt> &rarr; <tt>["/", ""]</tt><br/>
<tt>"filename" "/home/user/x"</tt> &rarr; <tt>["/home/user", "x"]</tt><br/>
<tt>"filename" "\\\\home\\user\\x"</tt> &rarr; <tt>["\\\\home\\user", "x"]</tt><br/>
<tt>"filename" "c:\\x"</tt> &rarr; <tt>["c:\\", "x"]</tt><br/>
<tt>"path" "c:\\home\\user\\x"</tt> &rarr; <tt>["c:\\", "home", "user", "x"]</tt><br/>

""")


#
# -------------------- env --------------------
#

def env_cmd(check_exist, variable, substr):
    if check_exist:
        if variable is None:
            raise CliError("'variable' argument is missing")
        return variable in os.environ
    if variable is not None:
        if not variable in os.environ:
            raise CliError(f"No environment variable '{variable}'")
        return os.environ[variable]

    data = [[key, val] for (key, val) in os.environ.items() if substr in key]
    props = [(Table_Key_Columns,
              [[(Column_Key_Name, h)] for h in ["Variable", "Value"]])]
    tbl = table.Table(props, data)
    msg = tbl.to_string(rows_printed=0, no_row_column=True)
    return command_return(msg, data)

new_command(
    "env", env_cmd,
    [arg(flag_t, "-x"),
     arg(str_t, "variable", "?", None,
         expander = lambda prefix: get_completions(prefix, list(os.environ))),
     arg(str_t, "substr", "?", "")],
    type = ["CLI"],
    short = "return environment variable value",
    doc = """
Returns the value of an environment <arg>variable</arg>. The <tt>-x</tt> flag
can be used to test if a named variable exists.

If used without arguments this command will return all variables and their
values. In this use case the <arg>substr</arg> argument can be used to filter
for certain variable names (case sensitive).""")

#
# ---------------- object-exists ----------------
#

new_command("object-exists", cli.object_exists,
            [arg(str_t, "name")],
            type = ["CLI"],
            short = "check if object exists",
            doc = """
Returns true if an object exists with the given <arg>name</arg> and false if
not.""")

#
# -------------------- echo --------------------
#

def echo_single_item(val):
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    elif val is None:
        return "NIL"
    elif isinstance(val, int):
        return number_str(val)
    elif isinstance(val, str):
        return ensure_text(cli_impl.repr_cli_string(val))
    elif isinstance(val, list):
        return echo_list(val)
    else:
        return str(val)

def echo_list(val):
    return "[" + ", ".join(echo_single_item(v) for v in val) + "]"

def echo_cmd(poly, no_nl):
    if poly[0] == str_t:
        line = poly[1]
    else:
        line = echo_single_item(poly[1])
    sys.stdout.write(line  + ('' if no_nl else '\n'))

new_command("echo", echo_cmd,
            [arg((int_t, float_t, str_t, list_t, nil_t),
                 ("integer", "float", "string", "list", "nil"),
                 "?", (str_t, ""), doc = "arg"),
             arg(flag_t, "-n")],
            type = ["CLI"],
            short = "print a value",
            doc = """
Prints the value of <arg>arg</arg> on the command line. The <tt>-n</tt> flag
can be used to inhibit output of a trailing newline.""")

#
# -------------------- date --------------------
#

def date_cmd(t, format):
    if t and format != "":
        raise CliError("flag [-t] can not be used together with [format]")
    if t:
        return time.time()
    if format == "short":
        return datetime.datetime.now().strftime("%x, %I:%M %p")
    if format == "medium":
        return datetime.datetime.now().strftime("%b %d, %Y, %I:%M:%S %p")
    if format == "long":
        return datetime.datetime.now().strftime("%B %d, %Y at %I:%M:%S %p")
    if format == "full":
        return datetime.datetime.now().strftime("%A %B %d, %Y at %I:%M:%S.%f %p")
    if format == "iso":
        return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    if format == "shortDate":
        return datetime.datetime.now().strftime("%x")
    if format == "mediumDate":
        return datetime.datetime.now().strftime("%b %d, %Y")
    if format == "longDate":
        return datetime.datetime.now().strftime("%B %d, %Y")
    if format == "fullDate":
        return datetime.datetime.now().strftime("%A, %B %d, %y")
    if format == "shortTime":
        return datetime.datetime.now().strftime("%I:%M %p")
    if format == "mediumTime" or format == "longTime":
        return datetime.datetime.now().strftime("%I:%M:%S %p")
    if format == "fullTime":
        return datetime.datetime.now().strftime("%I:%M:%S.%f %p")
    if format == "date":
        return datetime.datetime.now().strftime("%Y-%m-%d")
    if format == "time":
        return datetime.datetime.now().strftime("%X")
    if format == "file":
        return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if format == "fileDate":
        return datetime.datetime.now().strftime("%Y%m%d")
    if format == "fileTime":
        return datetime.datetime.now().strftime("%H%M%S")
    if format:
        try:
            return datetime.datetime.now().strftime(format)
        except:
            raise CliError(f"Date format of string: {format} is not valid."
                           " Please use format codes derived from the C"
                           " standard")
    # Default
    return time.ctime(time.time())

def fmt_expander(value):
    return get_completions(value, ["short", "medium", "long", "full", "iso",
                                   "shortDate", "mediumDate", "longDate",
                                   "fullDate", "shortTime", "mediumTime",
                                   "longTime", "fullTime", "date", "time",
                                   "file", "fileDate", "fileTime"])

new_command("date", date_cmd,
            [arg(flag_t, "-t"),
             arg(str_t, "format", "?", "", expander = fmt_expander)],
            type = ["CLI"],
            short = "host time and date",
            doc = """
Return the current date and time on the host, in the form <tt>Fri Nov 7
12:00:36 2008</tt>. If the <tt>-t</tt> flag used, the time is instead
returned in seconds as a floating point value.

The <arg>format</arg> argument enables the user to pass custom formatting of
date and time based on formatting codes from the C standard. The file formats
are designed to be used to construct file names at CLI, such as $filename =
(date format=fileDate) + ".log".

<b>Pre-Defined format option:</b>
<i>(Results may vary slightly depending on host locale)</i>
<pre>
custom       Format codes from the C standard
full         Friday November 07, 2008 at 12:00:36.3467824 AM
fullDate     Friday November 07, 2008
fullTime     12:00:36.3467824 AM
iso          2008-11-07T12:00:36
long         November 07, 2008 at 12:00:36 AM
longDate     November 07, 2008
longTime     12:00:36 AM
medium       Nov 07, 2008, 12:00 AM
mediumDate   Nov 07, 2008
mediumTime   12:00:36 AM
short        11/07/08, 12:00 AM
shortDate    11/07/08
shortTime    12:00 AM
date         2008-11-07
time         12:00:36
file         20081107_120036
fileDate     20081107
fileTime     120036
</pre>
""")

#
# -------------------- timer-start --------------------
#

timer_start = 0
timer_stop = 0

def timer_start_cmd():
    global timer_start
    print("Timing of Simics started")
    timer_start = time.process_time()

new_unsupported_command("timer-start", "internals", timer_start_cmd,
                        [], # timer-start
                        short = "start user timing",
                        see_also = ['timer-stop', 'timer-query'],
                        doc = """
Start timing of Simics (user time).""")

#
# -------------------- timer-stop --------------------
#

def timer_stop_cmd():
    global timer_start, timer_stop
    timer_stop = (time.process_time() - timer_start)
    print("Timing of Simics stopped")

new_unsupported_command("timer-stop", "internals", timer_stop_cmd, [],
                        short = "end user timing",
                        see_also = ['timer-start', 'timer-query'],
                        doc = """
End timing of Simics (user time).""")

#
# -------------------- timer-query --------------------
#

def timer_query_cmd():
    global timer_stop
    print("User time (s): %.2f" % timer_stop)


new_unsupported_command("timer-query", "internals", timer_query_cmd, [],
                        short = "query user timing",
                        see_also = ['timer-start', 'timer-stop'],
                        doc = """
Query timing of Simics (user time).""")

#
# -------------------- ls --------------------
#

def ls_cmd(path):
    if path:
        try:
            l = os.listdir(str(path))
        except Exception as ex:
            raise CliError("Failed listing directory '%s': %s" %(path, ex))
    else:
        l = os.listdir(os.getcwd())
    print_columns('l', sorted(l), has_title = 0, wrap_space = "  ")

new_command("ls", ls_cmd,
            [arg(filename_t(dirs=1,exist=1), "path", "?", None)],
            type = ["CLI", "Files"],
            short = "list files",
            see_also = ["cd", "pwd"],
            doc = """
List files in the current working directory. Works like the <tt>ls</tt> command
in a Linux shell but with a single optional parameter <arg>path</arg>, the
directory to list files in.""")

#
# -------------------- cd --------------------
#

def cd_cmd(path):
    try:
        os.chdir(SIM_native_path(path))
    except OSError as ex:
        raise CliError("Failed changing directory: %s" % ex)

new_command("cd", cd_cmd,
            [arg(filename_t(dirs=1,exist=1), "path")],
            type = ["CLI", "Files"],
            short = "change working directory",
            see_also = ["ls", "pwd"],
            doc = """
Changes the working directory of Simics to <arg>path</arg>. Use with caution
since this is a global setting that may affect other parts of Simics. The
<arg>path</arg> is converted to host native form by the command (see
<cmd>native-path</cmd>).""")

#
# -------------------- change-namespace --------------------
#

def component_arg_deprecation(namespace, component, command):
    if component is not None:
        DEPRECATED(SIM_VERSION_6,
                   "The 'component' parameter of the '{0}' command have been"
                   " deprecated.".format(command),
                   "Use the 'namespace' parameter instead.")
    if namespace is not None and component is not None:
        raise CliError("Both 'namespace' and 'component' parameters"
                       " of the '{0}' command cannot be set. Please"
                       " use the 'namespace' parameter.".format(command))
    return namespace or component

# return parent name (e.g. "a.b:p" -> "a.b", "a.b" -> "a", "a" -> "")
def _namespace_parent(name):
    return name[0:max(name.rfind("."), name.rfind(":"), 0)]

def _change_namespace_cmd(s, cn):
    if s is None:  # default argument value
        s = ""
    if s == "":
        cn = ""
    elif s.startswith('.') and not s.startswith('..'):
        # handle absolute paths starting with a single '.'
        cn = ""
        s = s[1:]
    while s.startswith("../"):
        cn = _namespace_parent(cn)
        s = s[3:]
    if s.startswith(".."):
        cn = _namespace_parent(cn)
        s = s[2:]
    if cn and s and not s.startswith(":"):
        cn += "." + s
    else:
        cn += s
    try:
        obj = SIM_get_object(cn) if cn else None
    except simics.SimExc_General:
        return False
    if obj and obj.classname == 'index-map':
        return False
    cli.set_current_namespace(cn)
    return True

def change_namespace_cmd(namespace):
    namespace = component_arg_deprecation(
        namespace, None, "change-namespace")
    if _change_namespace_cmd(namespace, cli.current_namespace()):
        return
    # for backward compatibility, allow s to be an absolute path;
    # this is also a workaround for CLI replacing e.g. 'cn sub[0]'
    # with 'cn foo.sub[0]' when foo is the current namespace
    if not _change_namespace_cmd(namespace, ""):
        raise CliError("{} not a valid namespace".format(namespace))

def cn_expander(prefix):
    cn = cli.current_namespace()
    pre = ""
    ret = []
    if prefix == ".":
        ret = ["..", "../"]
    # handle absolute paths starting with a single "."
    if prefix.startswith(".") and not prefix.startswith(".."):
        cn = ""
        pre = "."
        prefix = prefix[1:]
    while prefix.startswith(".."):
        cn = _namespace_parent(cn)
        pre += "../"
        if not prefix.startswith("../"):
            prefix = prefix[2:]
            break
        else:
            prefix = prefix[3:]
    base = _namespace_parent(prefix)
    if cn and base and not base.startswith(":"):
        base = cn + "." + base
    else:
        base = cn + base
    try:
        obj = SIM_get_object(base) if base else None
    except simics.SimExc_General:
        return []
    subs = [(o, o.name[len(cn):].lstrip("."))
            for o in simics.CORE_shallow_object_iterator(obj, True)]
    def has_subs(o):
        return bool(next(simics.SIM_shallow_object_iterator(o), None))
    v = [(o, s) for (o, s) in subs if s.startswith(prefix)]
    # include objects with subobjects twice to avoid "final completion"
    w = [(o, s) for (o, s) in v if has_subs(o)]
    ret += [pre + s for (_, s) in v + w]
    if prefix and not prefix.endswith("."):
        # also include subobjects for completely specified objects
        ret += cn_expander(pre + prefix + ".")
        ret += cn_expander(pre + prefix + ":")
    return ret

new_command("change-namespace", change_namespace_cmd,
            [arg(str_t, "namespace", "?", None, expander = cn_expander)],
             type = ["CLI", "Components"],
             short = "change current namespace",
             alias = "cn",
             see_also = ["current-namespace", "list-objects"],
             doc = """
Change current namespace to <arg>namespace</arg>. Objects in
the current namespace can be specified using a relative
object name. The full object name can also be used even if
a current namespace has been set.

For example, if there is an object <i>system.cpu</i>, it is possible
to do:

<pre>  simics> cn system
  simics> cpu.log-level 2</pre>

Use

<pre>  simics> cn ..</pre>

to go "up" one level.

If no namespace is given, current namespace will be changed to the top level.

If a current namespace is set the <cmd>list-objects</cmd> command will
only list the objects in that namespace.  """)

def current_namespace_cmd():
    return "." + cli.current_namespace()
new_command("current-namespace", current_namespace_cmd, [],
            type = ["CLI", "Components"],
            short = "return current namespace",
            see_also = ["change-namespace"],
            doc = """
Return the current namespace. This can be passed to
<cmd>change-namespace</cmd> if you later want to return to the present
location.""")

#
# -------------- pushd/popd/dirs --------------
#

_dir_stack = [ ]

def _print_dir_stack():
    print(os.getcwd(), end=' ')
    for d in _dir_stack:
        print(d, end=' ')
    print()

def pushd_cmd(no_cd, path):
    global _dir_stack

    if not path and no_cd:
        return

    if not path:
        if len(_dir_stack) < 1:
            print("No other directory available on the directory stack.")
            return
        dir = _dir_stack[0]
        _dir_stack[0] = os.getcwd()

        try:
            os.chdir(SIM_native_path(dir))
        except OSError as ex:
            _dir_stack = _dir_stack[1:]
            raise CliError("Failed changing directory: %s" % ex)
        return

    old_dir = os.getcwd()

    if not no_cd:
        try:
            os.chdir(SIM_native_path(path))
        except OSError as ex:
            raise CliError("Failed changing directory: %s" % ex)
    _dir_stack =  [ old_dir ] + _dir_stack
    if not path:
        _print_dir_stack()

new_command("pushd", pushd_cmd,
            [arg(flag_t, "-n"),
             arg(filename_t(dirs = 1, exist = 1), "path", "?", 0)],
            type = ["CLI", "Files"],
            short = "push directory on directory stack",
            see_also = ["dirs", "popd"],
            doc = """
Pushes the directory <arg>path</arg> on top of the directory stack, or
exchanges the topmost two directories on the stack. If <tt>-n</tt> is
given, only change the contents of the stack, but do not change
current working directory.
""")

def popd_cmd(no_cd):
    global _dir_stack

    if len(_dir_stack) < 1:
        print("The directory stack is empty.")
        return

    dir = _dir_stack[0]
    if not no_cd:
        try:
            os.chdir(SIM_native_path(dir))
        except OSError as ex:
            raise CliError("Failed changing directory: %s" % ex)
    _dir_stack = _dir_stack[1:]
    if no_cd:
        _print_dir_stack()

new_command("popd", popd_cmd,
            [arg(flag_t, "-n")],
            type = ["CLI", "Files"],
            short = "pop directory from directory stack",
            see_also = ["dirs", "pushd"],
            doc = """
Pops a directory off the directory stack and, unless the <tt>-n</tt>
option is specified, change current working directory to that
directory.
""")

def dirs_cmd():
    _print_dir_stack()

new_command("dirs", dirs_cmd,
            [],
            type = ["CLI", "Files"],
            short = "display directory stack",
            see_also = ["pushd", "popd"],
            doc = """
Shows the contents of the directory stack.
""")


#
# -------------------- run-command-file --------------------
#

import scriptdecl

def sd_arg_completer(values, prefix):
    values = values if values else []
    return get_completions(prefix, values)

def arg_from_sd_type(decl_type):
    if isinstance(decl_type, scriptdecl.IntType):
        return (int_t, None)
    elif isinstance(decl_type, scriptdecl.FloatType):
        return (float_t, None)
    elif isinstance(decl_type, scriptdecl.StringType):
        return (str_t, None)
    elif isinstance(decl_type, scriptdecl.BoolType):
        return (bool_t(), None)
    elif isinstance(decl_type, scriptdecl.FileType):
        return (filename_t(exist = 1, simpath = 1), None)
    elif isinstance(decl_type, scriptdecl.OrNilType):
        return (poly_t('', nil_t, arg_from_sd_type(decl_type.type)[0]), None)
    elif isinstance(decl_type, scriptdecl.EnumType):
        arg_types = [arg_from_sd_value(v) for v in decl_type.values]
        values = [str(v.val) for v in decl_type.values]
        if all((isinstance(x, type(arg_types[0])) for x in arg_types)):
            return (arg_types[0], values)
        else:
            return (poly_t('', *arg_types), values)
    else:
        raise CliError("Unknown script-decl type:%s" % decl_type)

def arg_from_sd_value(decl_value):
    if isinstance(decl_value, scriptdecl.IntValue):
        return int_t
    elif isinstance(decl_value, scriptdecl.NilValue):
        return nil_t
    elif isinstance(decl_value, scriptdecl.BoolValue):
        return bool_t()
    elif isinstance(decl_value, scriptdecl.FloatValue):
        return float_t
    elif isinstance(decl_value, scriptdecl.StringValue):
        return str_t
    else:
        raise CliError("Unknown script-decl value:%s" % decl_value)

def create_sd_arg_expander(list_arg):
    return lambda x: sd_arg_completer(list_arg, x) if list_arg else None

def declspec_from_file(filename):
    (_, filename) = cli.expand_path_markers(filename)
    try:
        f = open(filename, encoding="utf-8")
    except (OSError, TypeError):
        return None

    from command_file import simics_paths
    try:
        r = scriptdecl.get_declspec(f, filename, simics_paths())
    except scriptdecl.DeclError as e:
        raise CliError("Failed reading script declaration from %s: %s"
                       % (filename, e))
    f.close()
    return r[0] if r else None

unspecified_arg = object()

# return list of CLI arguments matching decl {} parameters in a script
def cmd_args_from_script(filename, no_execute):
    args = []
    declspec = declspec_from_file(filename)
    if not declspec:
        return []
    for p in list(declspec.decl.params.values()):
        arg_type, values = arg_from_sd_type(p.type)
        args.append(arg(arg_type, p.name, "?",
                        expander = create_sd_arg_expander(values),
                        default = unspecified_arg))
    return args

def arg_name_from_script(filename):
    declspec = declspec_from_file(filename)
    return [p.name for p in list(declspec.decl.params.values())] if declspec else []

def report_script_error(ex, msg):
    if ex == simics.SimExc_Stop:
        raise CliQuietError(None)
    elif ex == simics.SimExc_Break:
        if interactive_command():
            if msg:
                print(msg)
            print("Interrupting script.")
        else:
            raise CliQuietError(msg)
    else: # IOError and General
        if interactive_command():
            print(msg)
            print("Error - interrupting script.")
        else:
            raise CliError(msg)

def param_val_to_str(val):
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    elif val is None:
        return "NIL"
    elif isinstance(val, str):
        return cli_impl.repr_cli_string(val)
    else:
        return str(val)

def run_command_file_cmd(filename, main_branch, local, *params):
    # argument priority order:
    # 1. parameter to run-command-file
    # 2. CLI variable in current scope
    # 3. default value in decl {} (handled automatically when script started)
    args = []
    for (i, s_arg) in enumerate(arg_name_from_script(filename)):
        if params[i] == unspecified_arg:
            # no parameter specified on command line, check CLI variables
            if not s_arg in cli.simenv:
                continue
            val = getattr(cli.simenv, s_arg)
        else:
            val = params[i]
        args.append([s_arg, param_val_to_str(val)])

    if not sb_in_main_branch():
        if main_branch:
            # run the new script file in the main branch
            sb_run_in_main_branch(
                'run-command-file',
                lambda : simics.CORE_run_target(filename, "", [], "", args, local))
            return
    else:
        if main_branch:
            raise CliError("The -main-branch flag can only be used in"
                           " a script-branch")
    try:
        simics.CORE_run_target(filename, "", [], "", args, local)
    except simics.SimExc_General as ex:
        report_script_error(sys.exc_info()[0], ex)

new_command("run-command-file", run_command_file_cmd,
            args = [arg(filename_t(exist = 1, simpath = 1,
                                   keep_simics_ref = 1), "file"),
                    arg(flag_t, "-main-branch"),
                    arg(flag_t, "-local")],
            dynamic_args=('file', cmd_args_from_script),
            short = "execute a simics script",
            see_also = ["run-script", "add-directory", "decl"],
            deprecated = "run-script",
            deprecated_version = SIM_VERSION_7,
            doc = """
Starts executing CLI commands from the Simics script <arg>file</arg>. Simics
scripts usually have the ".simics" filename extension but this is only
a convention.

Plain command scripts, i.e. scripts without any script declaration block,
execute in the same variable scope as the script calling
<cmd>run-command-file</cmd>. The only exception are variables in the called
script declared using the <tt>local</tt> keyword. Such variables are not
available to the calling script. If the <tt>-local</tt> flag is supplied to the
command, then the called script will run with its own copy of all global CLI
variables. When the script has finished executing, the original variable values
are restored.

CLI variable scoping is different for scripts starting with a script
declaration block. Only variables declared in the decl {} block are available
to such scripts and only return variables will be passed back to the calling
CLI environment.

If <cmd>run-command-file</cmd> is issued in a script-branch and the
<tt>-main-branch</tt> flag is specified, then the commands in the file will
execute in the main script branch the next time it is scheduled. This allows
the command file to define its own script branches for example. Note that
scripts without a script declaration block will run in the global CLI variable
environment and not within the script-branch scope. Scripts with a declaration
block on the other hand will get its parameter set from the script-branch CLI
environment at the time <cmd>run-command-file</cmd> is called.

If the script to run has declared parameters, then those parameters can be
specified as arguments to <cmd>run-command-file</cmd>. Tab completion can be
used to list the parameters available to a script.

<tt>
run-command-file script-with-parameters.simics name = "abc" cycle = 20
</tt>

This is identical to:

<tt>
$name = "abc"<br/>
$cycle = 20<br/>
run-command-file script-with-parameters.simics<br/>
unset name cycle
</tt>

It is not possible to pass parameters in this way to a plain script.

Python code can be included in a script by using the @ prefix. Multi-line
Python statements only need @ on the first line. For larger sections of Python
code, the use of <cmd>run-python-file</cmd> is encouraged instead.

Example Simics script:

<tt>
# This is a Simics script<br/>
<br/>
break 0xffc000 # set a breakpoint<br/>
run<br/>
echo "breakpoint reached"<br/>
run-command-file another-script.simics
</tt>

If a command fails, the user presses Ctrl-C or stops the simulation from a GUI,
the Simics script is interrupted.

<cmd>run-command-file</cmd> uses Simics's Search Path and path markers
(%simics%, %script%) to find the script to run. Refer to <cite>The Command
Line Interface</cite> chapter of the <cite>Simics User's Guide</cite>
manual for more information.""")

#
# -------------------- list-instrumentation-callbacks --------------------
#

def list_callbacks_cmd(obj):
    if obj:
        objs = [obj]
    else:
        objs = list(simics.SIM_object_iterator_for_interface(["callback_info"]))

    callbacks = {}
    val       = []
    for obj in objs:
        for (conn, desc, func, data) in obj.iface.callback_info.get_callbacks():
            callbacks[desc] = callbacks.get(desc, []) + [(obj, conn, func, data)]
            val += [[desc, obj, conn, func, data]]

    msg = ""
    for desc in sorted(callbacks.keys()):
        msg += f"{desc}:\n"
        for (obj, conn, func, data) in callbacks[desc]:
            msg += f"    user object: {conn.name if conn else 'N/A'}\n"
            msg += f"    provider:    {obj.name}\n"
            msg += f"    callback:    {func}\n"
            msg += f"    data:        {data}\n\n"
    return command_verbose_return(msg, val)

new_command("list-instrumentation-callbacks", list_callbacks_cmd,
            [arg(obj_t("obj", "callback_info"), "object", "?", None)],
            namespace_copy = ("callback_info", list_callbacks_cmd),
            type = ["Instrumentation"],
            short = "list instrumentation callbacks",
            doc  = """
Lists all instrumentation callbacks registered in the system.

If <arg>object</arg> is given only callbacks related to that object will be
included. Otherwise all instrumentation objects that supports instrumentation
are listed.
""")

#
# -------------------- list-haps --------------------
#

def skip_hap_expander(skip_list, prefix):
    return get_completions(prefix, [hap[0] for hap in conf.sim.hap_list
                                    if hap[0] not in skip_list])

def hap_expander(prefix):
    return skip_hap_expander([], prefix)

def hap_list_cmd(name, substr):
    haps = sorted([x for x in conf.sim.hap_list if substr in x[0]])
    if not haps:
        return command_verbose_return(
            f"No hap with name containing '{substr}' found", [])
    if not name:
        def help_pr():
            ofile = io.StringIO()
            print_columns('l', sorted([[x[0]] for x in haps]),
                          has_title=0, outfile=ofile)
            return ofile.getvalue()
        return command_verbose_return(help_pr, [x[0] for x in haps])

    for hap in haps:
        def pr_help2():
            argnames = [ "callback_data", "trigger_obj" ]
            if hap[2] != None:
                argnames = argnames + hap[2]
            cbtype = cli.hap_c_arguments("noc" + hap[1], argnames,
                                         cli.terminal_width() - 8)
            s = '<dl>\n'
            for dt, dd in (
                ('Name',               hap[0]),
                ('Callback Type',      '<pre>%s</pre>' % (cbtype,)),
                ('Index',              hap[3] or 'no index'),
                ('Installed Handlers', hap[5] or 'none'),
                ('Description',        hap[4]) ):
                s += '<dt><b>%s</b></dt><dd>%s</dd>\n' % (dt, dd)
            s += '</dl>'
            cli.format_print(s)
            return " "

        if hap[0] == name:
            return command_verbose_return(pr_help2, [hap[0]])

    print(f"No '{name}' hap found")

new_command("list-haps", hap_list_cmd,
            [arg(str_t, "hap", "?", "", expander = hap_expander),
             arg(str_t, "substr", "?", "")],
            alias="hl",
            type = ["Notifiers"],
            short="lists all haps",
            see_also = ["list-hap-callbacks"],
            doc  = """
Lists all haps. If a <arg>hap</arg> is specified, a detailed description of it
is printed. If <arg>substr</arg> is specified, just haps whose names
contain the given substring (case sensitive) are printed.""")

def hap_callback_list_cmd(name):
    hap_list = sorted([h[0] for h in conf.sim.hap_list])
    if name:
        if not name in hap_list:
            return command_verbose_return(f"No hap '{name}'", [])
        hap_list = [name]

    msg = io.StringIO()
    header = ["Hap", "Handle", "Function", "User data", "Object", "Range/Index"]
    properties = [(Table_Key_Columns,
                   [[(Column_Key_Name, h)] for h in header])]
    tbl_content = []
    for hap_name in sorted(hap_list):
        callbacks = conf.sim.hap_callbacks[hap_name]
        if not callbacks:
            continue
        print(hap_name, file=msg)
        for cb in callbacks:
            (handle, r, flags, obj, f, d) = cb
            m = re.match("<function (.*) at 0x.*>", f)
            if m:
                f = "(Python) '%s()'" % m.group(1)
            tbl_row = [ hap_name, handle, f, str(d),
                        obj.name if obj else 'No object',
                        r[0] if (r and r[0]==r[1])
                             else '%d..%d'%(r[0],r[1]) if r else "Not used"]
            tbl_content.append(tbl_row)
    tbl = table.Table(properties, tbl_content)
    return command_verbose_return(
        message = tbl.to_string(rows_printed=0, no_row_column=True),
        value = [header] + tbl_content)

new_command("list-hap-callbacks", hap_callback_list_cmd,
            [arg(str_t, "hap", "?", "", expander = hap_expander)],
            type = ["Notifiers"],
            short ="lists all hap callbacks",
            see_also = ["list-haps"],
            doc  = """
Lists all callbacks installed for <arg>hap</arg>, or for all haps if the
argument is omitted.""")

#
# -------------------- pwd --------------------
#

def pwd_cmd():
    cwd = os.getcwd()
    return command_verbose_return(message = "Current directory is %s" % cwd,
                                  value = cwd)

new_command("pwd", pwd_cmd,
            [],
            type = ["CLI", "Files"],
            short = "print working directory",
            see_also = ["cd", "ls"],
            doc = """
Return the working directory of Simics. Similar to the shell command 'pwd'
(print working directory).

When used as part of an expression, returns the current working directory as
a string.""")

#
# -------------------- quit --------------------
#

def quit_cmd(code, force, disconnect):
    if force and disconnect:
        raise CliError("The -f and -d flags cannot be used together")
    if disconnect:
        import command_line
        id = cli.get_current_cmdline()
        command_line.command_line_disconnect(id)
    elif cli.primary_cmdline() or force:
        simics.SIM_quit(code)
    else:
        raise CliError("Use -f to exit Simics from a secondary "
                       "command line or -d to disconnect")

new_command("quit", quit_cmd,
            [arg(sint32_t, "status", "?", 0),
             arg(flag_t, "-f"),
             arg(flag_t, "-d")],
            alias = ["q", "exit"],
            type = ["CLI"],
            short = "quit from Simics",
            doc = """
Exit Simics gracefully. The optional <arg>status</arg> argument is the exit
status of Simics. When issued in a secondary command-line, such as the
telnet-frontend, the <tt>-f</tt> force flag must be given to exit Simics
while the <tt>-d</tt> can be used to disconnect the command line only
keeping Simics running. Disconnecting the command line can also be done with
Ctrl-D""")

#
# -------------------- python-mode --------------------
#

def python_mode_cmd():
    import command_line
    id = cli.get_current_cmdline()
    if id < 0:
        raise CliError("Python mode is only available on command lines")
    command_line.command_line_python_mode(id, True)
    print("Entering Python mode. Use cli_mode() or Ctrl-D to return to CLI.")

new_command("python-mode", python_mode_cmd,
            [],
            type = ["CLI", "Python"],
            short = "switch command line to Python mode",
            see_also = ["@", "python", "run-script"],
            doc = """
Switch to Python mode in the current interactive command line. Other command
lines are not affected. In Python mode, indicated by an alternative prompt, all
input is interpreted as Python instead of CLI, i.e. there is no need to start
lines with the @ character. Use <fun>cli_mode()</fun> or Ctrl-D to return to
CLI mode.""")

#
# -------------------- expect --------------------
#

def expect_cmd(i1, i2, v):
    def fmt_val(value):
        if isinstance(value, int):
            return number_str(value)
        return str(value)

    if v:
        print("Value is", i1, "expecting", i2)
    if i1 != i2:
        print("*** Values differ in expect command:"
              f" {fmt_val(i1)} {fmt_val(i2)}")
        if not interactive_command():
            simics_print_stack()
        simics.SIM_quit(1)

new_command("expect", expect_cmd,
            [arg(poly_t('arg1', int_t, str_t, float_t, list_t, nil_t), 'arg1'),
             arg(poly_t('arg2', int_t, str_t, float_t, list_t, nil_t), 'arg2'),
             arg(flag_t, "-v")],
            type = ["CLI"],
            short = "fail if not equal",
            doc = """
If values <arg>arg1</arg> and <arg>arg2</arg> are not equal the simulator will
print them and exit with error <fun>exit(1)</fun>. <tt>-v</tt> prints the two
values before comparing them.

This can be useful when writing scripts that want to assert a state in
the simulator.""")

#
# -------------------- pid --------------------
#

def pid_cmd():
    pid = os.getpid()
    return command_verbose_return(message = "Simics's pid is %d" % pid,
                                  value = pid)

new_command("pid", pid_cmd,
            [],
            type = ["CLI"],
            short = "print pid of Simics process",
            doc = """
Return the process identity of the Simics process itself. Useful when attaching
a remote debugger for example.""")

#
# -------------------- license --------------------
#

def license_cmd(third_party, full):
    open_extra_args = {"encoding": "utf-8", "errors": "replace"}
    if not third_party:
        if full:
            licfile = simics.SIM_license_file('')
            try:
                with open(licfile, **open_extra_args) as f:
                    print(f.read())
            except IOError:
                raise CliError("Could not find license file %s" % licfile)
        else:
            simics.SIM_license()
            print()
            print('Use the "-third-party" flag to view third party licenses'
                  ' and copyrights.')
    else:
        print("Third-party software used by Simics")
        print()
        import glob
        licenses = []
        for (_, _, _, _, ppath) in simics_common.get_simics_packages():
            licenses.extend(glob.glob(os.path.join(
                ppath, "licenses", "simics", "LICENSE-*")))
        licenses = list(set(licenses))

        names = ['Package']
        for lic in sorted(licenses):
            fname = os.path.split(lic)[-1]
            pname = re.sub("(^LICENSE-)|(\\.txt$)", "", fname)
            if full:
                print(pname)
                print('=' * len(pname))
                with open(lic, **open_extra_args) as f:
                    for line in f:
                        print(line, end=' ')
                print()
            else:
                names.append(pname)
        if not full:
            print_columns("l", names)

new_command("license", license_cmd,
            [arg(flag_t, "-third-party"),
             arg(flag_t, "-full")],
            type = ["Help"],
            short = "print Simics license",
            doc = """
Prints information about the license that applies to this copy of Simics.
The <tt>-third-party</tt> flag prints a list of third party software that is
part of the application. The <tt>-full</tt> flag can be used to view the full
license text.""")

#
# -------------------- copyright --------------------
#

def copyright_cmd():
    lines = [simics.SIM_copyright(), "",
             "Use \"license -third-party\" to view third party licenses and copyrights."]
    print("\n".join(lines))

new_command("copyright", copyright_cmd,
            [],
            type = ["Help"],
            short = "print full Simics copyright information",
            see_also = ["license"],
            doc = """
Prints the copyright information that applies to this copy of Simics.""")

#
# -------------------- version --------------------
#

def package_expander(prefix):
    return get_completions(prefix, (x[1] for x in conf.sim.package_info))


def platform_version() -> str:
    hypervisor_info = simics.CORE_host_hypervisor_info()
    hypervisor_string = (f" in {hypervisor_info.vendor}"
                         if hypervisor_info.is_hv_detected else "")

    return (f"<b>Simics Base ({conf.sim.host_type})"
            f" running with Python {platform.python_version()}"
            f" on {platform.uname().system} ({simics_common.os_release()})"
            f"{hypervisor_string}</b>\n\n")

def print_version(verbose, package):
    head = ['Pkg', 'Name', 'Version', 'Build ID']
    if verbose:
        head += ['Path', 'Extra']
    if not package:
        cli.format_print(platform_version())
        cli.format_print("<b>Installed Packages:</b>\n")
        print()
    data = []
    have_prio = False
    for row in simics_common.all_packages():
        (_, name, nbr, ver, extra, build, host,
         _, _, path, _, namespace, *_) = row
        if namespace != "simics":
            buildid = f"{namespace}:{build}"
        else:
            buildid = build
        if package and package != name:
            continue
        # mark prioritized packages
        if name in conf.sim.prioritized_packages:
            name += '*'
            have_prio = True
        row = [nbr, name, ver, buildid]
        if verbose:
            row += [path, extra]
        data.append(row)
    if package and not data:
        raise CliError("No such package installed: %s" % package)
    props = [(Table_Key_Columns,
              [[(Column_Key_Name, h),
                (Column_Key_Int_Radix, 10),
                (Column_Key_Int_Grouping, False)] for h in head])]
    tbl = table.Table(props, data)
    print(tbl.to_string(rows_printed=0, no_row_column=True))
    if have_prio:
        print("* - prioritized package")
    if not package:
        print()
        print(cmd_vmp_version().get_message())
    return data

def version_cmd(verbose, package):
    (result, output) = cli.quiet_run_function(
        lambda: print_version(verbose, package), cli.output_modes.regular)
    return command_verbose_return(output, result)

new_command("version", version_cmd,
            [arg(flag_t, "-v"),
             arg(str_t, "package",  "?", None, expander = package_expander)],
            type = ["Help"],
            short = "display Simics version",
            doc = """
Prints information about Simics installation including a list of installed
packages with their versions. The version for a single package only is
printed if the <arg>package</arg> argument is supplied. The <tt>-v</tt> flag
turns on verbose output where the path to each installed package is included.

If used in an expression, the return value is a list of lists in the format
[[&lt;package&gt;, &lt;package-number&gt;, &lt;version&gt;, &lt;build-id&gt;,
and &lt;package-path&gt;]+], where package-path is only
included if <tt>-v</tt> is specified.
""")

def cmd_vmp_version():
    v = simics.SIM_vmxmon_version()
    if v is None:
        return cli.command_verbose_return(
            message = "VMP kernel module is not loaded")

    return cli.command_verbose_return(
        message = f"VMP kernel module: {v}",
        value = v)

cli.new_command("vmp-version", cmd_vmp_version,
                [],
                type = ["Performance"],
                short = "print VMP version information",
                doc = "Print the VMP kernel module version.")

#
# -------------------- quiet --------------------
#

quiet_mode = 0

def quiet_cmd(mode):
    global quiet_mode

    if mode not in [-1,0,1]:
        print("Illegal mode")
        return

    if mode == -1:
        quiet_mode = 1 - quiet_mode
    else:
        quiet_mode = mode

    simics.SIM_set_quiet(quiet_mode)
    if quiet_mode:
        print("[simics] Switching on quiet mode.")
    else:
        print("[simics] Switching off quiet mode.")

new_unsupported_command("quiet", "internals", quiet_cmd,
                        [arg(int_t, "mode", "?", -1)],
                        short = "toggle quiet mode", see_also = ["verbose"],
                        doc = """
Switch or toggle Simics quiet mode.

If <arg>mode</arg> is 1 it sets Simics to 'quiet' mode, while 0 turns off
quiet mode, and -1 will toggle the mode (default).""")

#
# -------------------- verbose --------------------
#

verbose_mode = 0

def verbose_cmd(mode):
    global verbose_mode

    if mode not in [-1,0,1]:
        print("Illegal mode")
        return

    if mode == -1:
        verbose_mode = 1 - verbose_mode
    else:
        verbose_mode = mode

    simics.SIM_set_verbose(verbose_mode)
    if verbose_mode:
        print("[simics] Switching on verbose mode.")
    else:
        print("[simics] Switching off verbose mode.")

new_unsupported_command("verbose", "internals", verbose_cmd,
                        [arg(int_t, "mode", "?", -1)],
                        short = "toggle verbose mode", see_also = ["quiet"],
                        doc = """
Configures the verbose mode in Simics. A <arg>mode</arg> value of 1 turns on
verbose mode while 0 disables it. Used without any argument, the current mode
is toggled.""")

#
# -------------------- = --------------------
#

def obj_write_reg_cmd(cpu, reg_name, value):
    if not hasattr(cpu.iface, "int_register"):
        raise CliError("%s does not implement the int_register interface." % cpu.name)
    value &= 0xffffffffffffffff
    id = cpu.iface.int_register.get_number(reg_name)
    if id < 0:
        raise CliError("No '%s' register in %s (%s)" % (reg_name, cpu.name,
                                                        cpu.classname))
    try:
        cpu.iface.int_register.write(id, value)
    except simics.SimExc_IllegalValue as ex:
        raise CliError("Failed writing '%s' register in %s: %s"
                        % (reg_name, cpu.name, ex))


def truncate64(x): return x & 0xffffffffffffffff

def assignment_command(name, value):
    if name[0] == '%':
        if not value[0] == int_t:
            raise CliError("Value is not an integer.")
        cpu = current_frontend_object()
        obj_write_reg_cmd(cpu, name[1:], truncate64(value[1]))
        return
    elif name.startswith('$$'):
        name = name[2:]
        local = 1
    elif name[0] == '$':
        name = name[1:]
        local = 0
    else:
        raise CliError("Cannot assign to '%s'" % name)
    if name.startswith('__'):
        raise CliError("CLI variable name may not start with __")
    cli.get_current_locals().set_variable_value(name, value[1], local)
    # do not return anything (avoid execution of string assignments)

def markup_assign(op):
    return [ [ Markup.Keyword('$'), Markup.Arg('var'), ' ',
               Markup.Keyword(op), ' ', Markup.Arg('value') ],
             [ Markup.Keyword('%'), Markup.Arg('reg'), ' ',
               Markup.Keyword(op), ' ', Markup.Arg('value') ] ]

new_operator("=", assignment_command,
             [arg(str_t, doc = "$var|%reg"),
              arg((int_t, str_t, float_t, list_t, nil_t), doc = "value")],
             type = ["CLI"],
             short = "set a CLI variable",
             synopses = markup_assign('='),
             pri = -100,
             infix = 1,
             doc = """
Sets a CLI variable to a value.

Can also be used to assign an integer value to a processor register.""")


#
# -------------------- [ --------------------
#
def index_list_by_list(lst, idx):
    for i in range(len(idx)):
        if not isinstance(lst, list):
            raise CliError("Indexing of non-list")
        if idx[i] >= len(lst):
            raise CliError("Index %d outside list of length %d"
                           % (idx[i], len(lst)))
        lst = lst[idx[i]]
    return lst

def index_list_by_list_w(lst, idx, rw, value):
    for i in range(len(idx) - 1):
        if not isinstance(lst, list):
            raise CliError("Indexing of non-list")
        if idx[i] >= len(lst):
            raise CliError("Index %d outside list of length %d"
                           % (idx[i], len(lst)))
        lst = lst[idx[i]]
    if len(lst) <= idx[-1]:
        lst += [0] * (1 + idx[-1] - len(lst))
    if rw == '-w':
        lst[idx[-1]] = value
    elif rw == '-i':
        lst[idx[-1]] = plus(value_to_poly(lst[idx[-1]]), value_to_poly(value))
    elif rw == '-d':
        lst[idx[-1]] = minus(value_to_poly(lst[idx[-1]]), value_to_poly(value))
    else:
        assert 0

def cli_variable_index_r(space, name, idx):
    try:
        lst = getattr(space, name)[idx[0]]
    except TypeError:
        raise CliError("The $%s variable is not a list" % name)
    except:
        raise CliError("Failed indexing $%s variable" % name)
    if len(idx) > 1:
        lst = index_list_by_list(lst, idx[1:])
    return lst

def cli_variable_index_w(space, name, local, idx, rw, value):
    if not name in space.get_all_variables():
        raise CliError('No CLI variable "%s"' % name)
    try:
        lst = getattr(space, name)
        if not isinstance(lst, list):
            raise CliError("Indexing of non-list value not allowed")
    except:
        raise CliError("Failed indexing $%s variable" % name)
    index_list_by_list_w(lst, idx, rw, value)
    space.set_variable_value(name, lst, local)

def namespace_indexing(name, idx):
    try:
        obj = cli.get_object(name)
    except simics.SimExc_General:
        raise CliError("Indexing of string not supported")
    for i in idx:
        if not obj.classname == "index-map":
            raise CliError("Indexing of non-list slot")
        try:
            obj = obj[i]
        except IndexError:
            raise CliError("Indexing outside slot")
    return obj

def array_command(poly, idx, rw, value):
    if poly[0] == list_t:
        return index_list_by_list(poly[1], idx)

    name = poly[1]
    if name.startswith('$$'):
        name = name[2:]
        local = True
    elif name.startswith('$'):
        name = name[1:]
        local = False
    else:
        return namespace_indexing(name, idx)
    if rw[2] == '-r':
        return cli_variable_index_r(cli.get_current_locals(), name, idx)
    else:
        cli_variable_index_w(cli.get_current_locals(), name, local, idx,
                             rw[2], value[1])

markup_indexed = [ Markup.Keyword('$'), Markup.Arg('var'),
                   Markup.Keyword('['), Markup.Arg('idx'),
                   Markup.Keyword(']') ]
new_operator("[", array_command,
             [arg((str_t, list_t), doc = "$var"),
              arg(list_t),
              arg((flag_t, flag_t, flag_t, flag_t),
                  ('-r', '-w', '-i', '-d'), doc = '] = '),
              arg((int_t, str_t, list_t, float_t, nil_t), doc = 'value')],
             type = ["CLI"],
             short = "",
             synopses = [ markup_indexed,
                          markup_indexed + [ ' ', Markup.Keyword('='), ' ',
                                             Markup.Arg('value') ] ],
             pri = 700,
             infix = 1,
             doc = """
Get or set the value for the indexed CLI variable <tt>$var</tt>.""")

#
# -------------------- unset --------------------
#

def unset_command(all_flag, names):
    for name in names:
        cli.check_variable_name(name, "unset")
    if all_flag:
        rlist = [x for x in cli.get_current_locals().get_all_variables()
                 if x not in names]
    else:
        rlist = names
    for n in rlist:
        try:
            cli.get_current_locals().remove_variable(n)
        except:
            print('Unset failed for $%s.' % n)

new_command("unset", unset_command,
            [arg(flag_t, "-a"),
             arg(str_t, "variables", "*")],
            type = ["CLI"],
            short = "remove a CLI variable",
            doc = """
Removes (unsets) a CLI variable. The <tt>-a</tt> flag causes
all variables to be removed, <em>except</em> the ones specified as
<arg>variables</arg>.
""")

#
# -------------------- += --------------------
#

def obj_read_reg_cmd(cpu, reg_name):
    if not hasattr(cpu.iface, "int_register"):
        raise CliError("%s does not implement the int_register interface."
                       % cpu.name)
    id = cpu.iface.int_register.get_number(reg_name)
    if id < 0:
        raise CliError("No '%s' register in %s (%s)" % (reg_name, cpu.name,
                                                        cpu.classname))
    return cpu.iface.int_register.read(id)

def value_to_poly(value):
    if isinstance(value, str):
        return (str_t, value)
    elif isinstance(value, int):
        return (int_t, value)
    elif isinstance(value, float):
        return (float_t, value)
    elif isinstance(value, list):
        return (list_t, value)
    else:
        raise CliError("Unsupported type")

def inc_environment_variable(name, value):
    if name[0] == '%':
        if not value[0] == int_t:
            raise CliError("Value is not an integer.")
        cpu = current_frontend_object()
        value = truncate64(obj_read_reg_cmd(cpu, name[1:]) + value[1])
        obj_write_reg_cmd(cpu, name[1:], value)
        return
    elif name[0] == '$':
        name = name[1:]
    else:
        raise CliError("Cannot assign to '%s'" % name)

    space = cli.get_current_locals()
    if name in space.get_all_variables():
        old = value_to_poly(getattr(space, name))
    else:
        raise CliError("Unknown variable $%s in +=" % name)
    setattr(space, name, plus(old, value))
    return getattr(space, name)

new_operator("+=", inc_environment_variable,
             [arg(str_t, doc = "$var|%reg"),
              arg((int_t, str_t, list_t, float_t), doc = "value")],
             type = ["CLI"],
             short = "add to a CLI variable",
             synopses = markup_assign('+='),
             pri = -100,
             infix = 1,
             doc = """
Add a string, integer or list to a CLI variable, or an integer
value to a register.""")

#
# -------------------- -= --------------------
#

def dec_environment_variable(name, value):
    if name[0] == '%':
        cpu = current_frontend_object()
        value = truncate64(obj_read_reg_cmd(cpu, name[1:]) - value[1])
        obj_write_reg_cmd(cpu, name[1:], value)
        return

    elif name[0] == '$':
        name = name[1:]
    else:
        raise CliError("Cannot assign to '%s'" % name)

    space = cli.get_current_locals()
    if name in space.get_all_variables():
        old = value_to_poly(getattr(space, name))
    else:
        raise CliError("Unknown variable $%s in -=" % name)
    setattr(space, name, minus(old, value))
    return getattr(space, name)

new_operator("-=", dec_environment_variable,
             [arg(str_t, doc = "$var|%reg"),
              arg((int_t, float_t), doc = "value")],
             type = ["CLI"],
             short = "subtract from a CLI variable",
             synopses = markup_assign('-='),
             pri = -100,
             infix = 1,
             doc = """
Subtract an integer from a CLI variable, or from a
register.""")

#
# -------------------- $ --------------------
#

def environment_var_expander(comp):
    return get_completions(
        comp,
        list(cli.get_current_locals().get_all_variables().keys()))

def get_environment_variable(name):
    cli.check_variable_name(name, "$")
    try:
        val = getattr(cli.get_current_locals(), name)
    except AttributeError as ex:
        raise CliError(str(ex))
    if isinstance(val, simics.conf_object_t):
        return val.name
    else:
        return val

new_operator("$", get_environment_variable,
             [arg(str_t, doc = "name", expander = environment_var_expander)],
             type = ["CLI"],
             short = "get the value of a CLI variable",
             synopsis = [ Markup.Keyword('$'), Markup.Arg('var') ],
             pri = 2000,
             see_also = ["defined", "read-variable"],
             check_args = False,
             doc = """
Gets the value of a CLI variable, like in <cmd>print $var</cmd>.""")

#
# -------------------- range --------------------
#

def range_command(start, end, step):
    if step == 0:
        raise CliError("A step of 0 is not allowed in the range command")
    if end == None and step == None:
        return list(range(0, start))
    elif end == None:
        return list(range(0, start, step))
    elif step == None:
        return list(range(start, end))
    else:
        return list(range(start, end, step))

new_command("range", range_command,
            [arg(int_t, "start"), arg(int_t, "end", "?", None),
             arg(int_t, "step", "?", None)],
            type = ["CLI"],
            short = "create and return a list of integers",
            doc = """
Returns a list of integers from <arg>start</arg> up to <arg>end</arg> - 1. A
single argument is interpreted as <arg>end</arg> with 0 as <arg>start</arg>.
The optional <arg>step</arg> specifies the increment and may be negative.
""")

#
# ----------------- list-length -----------------
#

def list_length_command(lst):
    return len(lst)

new_command("list-length", list_length_command,
            [arg(list_t, "list")],
            type = ["CLI"],
            short = "returns the length of a list",
            doc = """
Returns the length of a CLI <arg>list</arg>.""")

#
# ----------------- string-length -----------------
#

def string_length_command(str_arg):
    return len(str_arg)

new_command("string-length", string_length_command,
            [arg(str_t, "string")],
            type = ["CLI"],
            short = "returns the length of a string in bytes",
            doc = """
Return the length of a CLI <arg>string</arg> in bytes. For unicode strings,
the number of bytes may be larger than the number of characters.  """)

#
# ------------------ list-variables ------------------
#

def list_vars_cmd(substr):
    vars = cli.get_current_locals().get_all_variables()
    vars = {v:vars[v] for v in vars if not substr or substr in v}

    lst = [[n, cli.format_attribute(vars[n], True)] for n in sorted(vars)]

    props = [(Table_Key_Columns,
              [[(Column_Key_Name, h)] for h in ["Variable", "Value"]])]
    tbl = table.Table(props, lst)
    msg = tbl.to_string(rows_printed=0, no_row_column=True)
    return command_verbose_return(msg, [[n, vars[n]] for n in vars])

new_command("list-variables", list_vars_cmd,
            [arg(str_t, "substr", "?", None)],
            type = ["CLI"],
            short = "list CLI variables",
            alias = "list-vars",
            see_also = ["$", "read-variable", "defined"],
            doc = """
Lists all CLI variables and their current values.
Use <arg>substr</arg> to filter for matching variable names.
If the command is used in an expression, a list is returned instead.

CLI variables can be used to
store temporary values. To set a variable, write <cmd>$variable = value</cmd>
at the Simics prompt. The value can be of type integer, string, float, boolean
or a list or values. To access a variable, prefix the name with a dollar
sign (<tt>$</tt>); e.g., <cmd>$variable</cmd>. A variable can be used wherever
an expression can be used. For example:

<pre>simics> $tmp = %pc + 4
simics> $count = 10
simics> disassemble $tmp $count
</pre>

They can also be accessed from Python by using the namespace
<tt>simenv</tt> (<tt>simenv</tt> is imported into global namespace by default,
but if it is needed elsewhere, it can be imported from the <tt>cli</tt> module):

<pre>simics> $foo = 1 + 4 * 4
simics> @print(simenv.foo)
17
simics> @simenv.bar = "hello"
simics> echo $bar
hello
</pre>
""")

#
# -------------------- save-preferences --------------------
#

def save_preferences_cmd():
    try:
        simics.CORE_save_preferences()
        print("Preferences saved.")
    except Exception as ex:
        raise CliError("Failed saving preferences: %s" % ex)

new_command("save-preferences", save_preferences_cmd,
            [],
            type = ["Configuration"],
            short = "save preferences",
            see_also = ["list-preferences"],
            doc = """
Save the current user preference settings. The preferences will be loaded
automatically the next time Simics is started.
""")

#
# -------------------- list-preferences --------------------
#
class Preference:
    def __init__(self, name, desc, val = None):
        self.name = name
        self.desc = desc
        self.val = val

    def with_value(self):
        try:
            return Preference(self.name, self.desc,
                              simics.SIM_get_attribute(conf.prefs, self.name))
        except Exception as ex:
            raise CliError("Failed reading preference attribute %s: %s"
                           % (self.name, ex))

def get_preferences():
    ignore = ['class_desc']
    prefs = [Preference(name, doc)
             for (name, attr, doc, *_) in conf.prefs.attributes
             if not (attr & simics.Sim_Attr_Internal or name in ignore)]
    prefs = [p.with_value() for p in prefs]
    return prefs

def list_preferences_cmd(verbose):
    cols  = [[(Column_Key_Name, n)] for n in ["Preference", "Value"]]
    if verbose:
        cols.append([(Column_Key_Name, "Description")])
    props = [(Table_Key_Columns, cols)]
    data  = []
    for p in get_preferences():
        d = [p.name, echo_single_item(p.val)]
        if verbose:
            d.append(p.desc)
        data.append(d)
    data.sort()
    msg = table.Table(props, data).to_string(rows_printed=0, no_row_column=True)
    return command_verbose_return(
        msg,
        [[x.name, x.val] for x in get_preferences()])

new_command("list-preferences", list_preferences_cmd,
            [arg(flag_t, "-v")],
            type = ["Configuration"],
            short = "list preferences",
            see_also = ["save-preferences"],
            doc = """
Lists the current preference values. In interactive mode, the <tt>-v</tt> flag
will include a description of each preference entry.""")

#
# -------------------- run-python-file --------------------
#

def run_python_file(filename):
    # make the command line non-interactive while running from a script
    with cli.set_interactive_command_ctx(False):
        simics.SIM_source_python(filename)

def run_python_file_cmd(filename):
    try:
        run_python_file(filename)
    except Exception as ex:
        raise CliError("Failed running Python file %s: %s" % (filename, ex))

new_command("run-python-file",
            run_python_file_cmd,
            args  = [arg(filename_t(exist = 1, simpath = 1), "filename")],
            short = "execute Python file",
            see_also = ["python", "@", "run-script", "python-mode",
                        "add-directory"],
            deprecated = "run-script",
            deprecated_version = SIM_VERSION_7,
            doc = """
Read Python code from <arg>filename</arg>. Any definitions are entered into the
top level namespace in the Python environment. Uses the Simics search path to
locate <arg>filename</arg>. This command can be used to start Python scripts
inside Simics.

<cmd>run-python-file</cmd> uses Simics's Search Path and path markers
(%simics%, %script%) to find the script to run. Refer to <cite>The Command
Line Interface</cite> chapter of the <cite>Simics User's Guide</cite>
manual for more information.""")

def run_shell_cmd(bg, cmd):
    # Assume Popen() handles encoding from Unicode for us on Linux. On Windows
    # Popen() should have to use CreateProcessW() to handle unicode properly.
    # Since it doesn't, we only accept ASCII here for now. (One might think
    # that the CP1252 encoding should work, but for some reason it does not.)
    if simicsutils.host.is_windows():
        try:
            _ = cmd.encode('ascii')
        except (UnicodeDecodeError, UnicodeEncodeError):
            raise CliError("Only ASCII is allowed in the shell command on "
                           "Windows host")
    import subprocess
    p = subprocess.Popen(cmd, shell=True,  # nosec
                         stdin=subprocess.DEVNULL,
                         stdout=(None if bg else subprocess.PIPE),
                         stderr=subprocess.STDOUT,
                         close_fds = True)
    if bg:
        return (0, "")  # just report success with no output
    import locale
    (out, _) = p.communicate()
    out = str(out.strip(), locale.getpreferredencoding(), 'replace')
    exit_status = p.returncode
    if exit_status != 0:
        if not out:
            out = 'exit status %d' % exit_status
        if out.find('\n') >= 0:
            out = '\n' + out
    return (exit_status, out)

def shell_cmd(bg, cmd):
    (exit_status, output) = run_shell_cmd(bg, cmd)
    if exit_status != 0:
        raise CliError("Error return from shell command '%s': %s\n"
                       % (cmd, output))
    return command_return(message=output, value=output)

new_command("shell", shell_cmd, [arg(flag_t, "-bg"), arg(str_t, "exp")],
            type  = ["CLI"],
            short = "execute a shell command",
            see_also = ["!", "pipe", "script-branch"],
            doc = """
Executes the <arg>exp</arg> argument in the system command line interpreter.
For Linux this is the default shell and for Windows it is <file>cmd.exe</file>.

The <tt>-bg</tt> flag launches the job in the background without any way to
capture output or errors.

If the command returns a non-zero exit status and <tt>-bg</tt> is not used, a
command line error will be signalled. The actual exit status is not available.

The <cmd>wait-for-shell</cmd> command is similar to <cmd>shell</cmd>. It can
be used in a script branch, allowing other script branches to execute in
parallel while waiting for the command to finish.

When used in an expression (without the <tt>-bg</tt> flag), any messages printed
to standard output will be returned:<br/>
<cmd>$today = (shell "date +%F")</cmd> on Linux; or<br/>
<cmd>$today = (shell "date /t")</cmd> on Windows.""")

new_command("!", lambda x: shell_cmd(False, x), [arg(str_t, "exp")],
            type  = ["CLI"],
            short = "execute a shell command",
            see_also = ["shell"],
            synopsis = [ Markup.Keyword('!'), Markup.Arg('shell-command') ],
            doc = """
Executes the rest of the command line in the host command line interpreter.
Works like the <cmd>shell</cmd> command, except that the argument does not
need to be quoted.""")

class shell_command_thread(threading.Thread):
    def __init__(self, cmd, wait_id):
        threading.Thread.__init__(self)
        self.cmd = cmd
        self.wait_id = wait_id

    def run(self):
        (self.exit_status, self.output) = run_shell_cmd(False, self.cmd)
        simics.SIM_thread_safe_callback(
            lambda x: sb_signal_waiting(x), self.wait_id)

def wait_for_shell_cmd(cmd):
    wait_id = cli.sb_get_wait_id()
    thread = shell_command_thread(cmd, wait_id)
    thread.start()
    sb_wait('wait-for-shell', wait_id, wait_data = cmd)
    if thread.exit_status != 0:
        raise CliError("Error return from shell command '%s': %s\n"
                       % (cmd, thread.output))
    return command_return(message=thread.output, value=thread.output)

new_command("wait-for-shell", wait_for_shell_cmd,
            [arg(str_t, "exp")],
            type  = ["CLI"],
            short = "execute a shell command and wait for it to finish",
            doc_with = "shell")

def exec_cmd(cmd):
    try:
        return simics.SIM_run_command(cmd)
    except simics.SimExc_General as ex:
        raise CliError("Failed running '%s': %s" % (cmd, ex))

new_command("exec", exec_cmd, [arg(str_t, "cmd")],
            type  = ["CLI"],
            short = "execute a string as a CLI command",
            doc = """
Executes the <arg>cmd</arg> argument as a CLI command line and returns
the return value if any.
""")

new_command("#", cli_impl._DummyCommandHandler("#"),
            type  = ["CLI"],
            short = "treat the line as a comment",
            synopsis = [ Markup.Keyword('#'), ' ', Markup.Arg('comment') ],
            doc = """
Ignores the rest of the line, treating it as a comment.
""")

new_command("decl", cli_impl._DummyCommandHandler("decl"),
            type  = ["CLI", "Parameters"],
            synopsis = [Markup.Keyword('decl'), ' ', Markup.Keyword('{'),
                        Markup.Keyword(' '), Markup.Arg('declarations'),
                        Markup.Keyword(' '),
                        Markup.Keyword('}')],
            see_also = ["run-script"],
            short = "declare parameter",
            legacy=True,
            legacy_version=simics.SIM_VERSION_7,
            doc = """
A Simics script may have an optional script declaration block first in the
file. The block declares parameter that the user can specify on the command
line when launching Simics, or from the GUI, to alter the behavior of the
script.

Possible declarations are:
<ul>
<li>Script documentation</li>
<li>Parameter groups</li>
<li>Parameters</li>
<li>Imported parameters</li>
<li>Results</li>
</ul>

Scripts may be documented by adding one or more lines starting with <tt>!</tt>
first in the <cmd>decl</cmd> block.

A parameter declaration includes the name and the type of a script parameter
and an optional default value. It can also be followed by one or more lines
of documentation, each starting with <tt>!</tt>.
<br/>
<pre>
<b>param</b> <i>name</i> <b>:</b> <i>type</i> [ <b>=</b> <i>default-value</i>]
<b>!</b> <i>documentation line</i>
</pre>

Example:<br/>
<pre>
param ram_size : int = 8
! Size of RAM in MiB
</pre>

This means that the variable <tt>$ram_size</tt> will be set when the script is
executed, that it must be an integer, and that it will be 8 if not specified in
any other way. If there is no default value, then the parameter must be
specified when the script is started; otherwise it is optional.

A script with a declaration block will only see the variables that have been
declared as parameters. Other variables are hidden during the script&apos;s
execution and will re-appear when the script terminates.

Several parameter declarations may be collected together by declaring a group.
All parameters after a group declaration will belong to it, until a new group
is declared. Example:
<br/>
<pre>
group "Disks"
</pre>

Script parameters may be imported from another script, typically one included
in the command section using <cmd>run-command-file</cmd>. Example:<br/>
<pre>
params from &quot;qsp-system.include&quot;
 except mac_address, system
 default num_cpus = 8
</pre>

The <tt>except</tt> statement is used to skip the import of some named
parameters, while <tt>default</tt> provides a way to assign a default value to
a parameter in the imported script.

A script can return variables that it has set by declaring results in the
following way:<br/>
<pre>
<b>result</b> <i>param</i> : <i>type</i>
</pre>

Example:<br/>
<pre>
result mac_address : string
</pre>

It means that the script must set <tt>$mac_address</tt> before terminating,
that it must be a string value, and that this variable is available to the
caller. All other variables assigned to by the script are lost. The same name
can be used for both a parameter and a result.

The automatically generated script trampolines in project directories use a
single <b>substitute</b> line in the <cmd>decl</cmd> block to inherit all
parameters and return values from another script. This keyword is not supposed
to be used in user written scripts.

Whitespace (spaces, tabs, line breaks) are in general not significant in script
declaration blocks unless specifically noted. Comments are allowed, starting
with # and running to the end of the line.
""")

markup_code_block = [ Markup.Keyword('{'), ' ',
                      Markup.Arg('commands'), ' ',
                      Markup.Keyword('}') ]
markup_if         = [ Markup.Keyword('if'), ' ',
                      Markup.Arg('condition'), ' ' ]
new_command("if", cli_impl._DummyCommandHandler("if"),
            type  = ["CLI"],
            see_also = ["while"],
            synopses = [ markup_if + markup_code_block,
                         markup_if + markup_code_block
                         + [ ' ', Markup.Keyword('else'), ' ' ]
                         + markup_code_block,
                         markup_if + markup_code_block
                         + [ ' ', Markup.Keyword('else'), ' ' ]
                         + markup_if + markup_code_block ],
            short = "run a block conditionally",
            doc = """
Runs a block of commands conditionally.

The <cmd>if</cmd> command returns the value of the last executed command in
the block.
""")

new_command("else", cli_impl._DummyCommandHandler("else"),
            type  = ["CLI"],
            synopses = [],
            short = "run a block conditionally",
            doc_with = "if")

new_command("while", cli_impl._DummyCommandHandler("while"),
            type  = ["CLI"],
            see_also = ["if", "break-loop", "continue-loop", "foreach"],
            synopsis = [ Markup.Keyword('while'), ' ',
                         Markup.Arg('condition'), ' ' ] + markup_code_block,
            short = "run a block while true",
            doc = """
Runs a block of commands while <arg>condition</arg> is true.
""")

new_command("foreach", cli_impl._DummyCommandHandler("foreach"),
            type  = ["CLI"],
            synopsis = [ Markup.Keyword('foreach'), ' ',
                         Markup.Keyword('$'), Markup.Arg('iterator'), ' ',
                         Markup.Keyword('in'), ' ',
                         Markup.Arg('list'), ' ' ] + markup_code_block,
            see_also = ["if", "break-loop", "continue-loop", "while"],
            short = "run code with iterator",
            doc = """
Runs a block of commands with the variable <arg>$iterator</arg> set
to each of the entries in <arg>list</arg>. The <arg>$iterator</arg> variable is
only defined within the command block.
""")

new_command("script-branch", cli_impl._DummyCommandHandler("script-branch"),
            type  = ["CLI"],
            synopsis = [ Markup.Keyword('script-branch'),
                         ' [', Markup.Arg('"description"'), ']',
                         ' ' ] + markup_code_block,
            see_also = ["list-script-branches",
                        "break-script-branch",
                        "interrupt-script-branch",
                        "wait-for-script-barrier",
                        "wait-for-script-pipe",
                        "<breakpoint>.bp-wait-for-memory",
                        "<break_strings_v2>.bp-wait-for-console-string",
                        "<processor_internal>.bp-wait-for-control-register",
                        "<cycle>.bp-wait-for-cycle",
                        "<step>.bp-wait-for-step",
                        "<cycle>.bp-wait-for-time",
                        "<osa_component>.bp-wait-for"],
            short = "start a script branch",
            doc = """
Starts a block of commands as a separate branch. The <tt>wait-for-</tt>*
commands can be used to postpone the execution of a script branch until a
selection action occurs.

The optional <arg>description</arg> string may be used to identify the
script-branch. The text will be printed by <cmd>list-script-branches</cmd>.
""")

new_command("try", cli_impl._DummyCommandHandler("try"),
            type  = ["CLI"],
            short = "runs a block of commands and catches any error",
            synopsis = ([ Markup.Keyword('try'), ' ' ]
                        + markup_code_block +
                        [ ' ', Markup.Keyword('except'), ' ',
                          Markup.Keyword('{'), ' ',
                          Markup.Arg('on-error-commands'), ' ',
                          Markup.Keyword('}') ]),
            doc = """
Runs all <i>commands</i> from the <cmd>try</cmd> part until an error occurs.
If no error is encountered, <i>on-error-commands</i> are ignored, but if an
error does occur the <i>on-error-commands</i> are run. Information about the
error is available in the <cmd>except</cmd> part through the
<cmd>get-error-command</cmd>, <cmd>get-error-message</cmd>,
<cmd>get-error-file</cmd> and <cmd>get-error-line</cmd>
commands.
""")

def get_error_info(kind):
    return cli_impl.get_cli_error(kind)

new_command("get-error-command", lambda: get_error_info('command'),
            type  = ["CLI"],
            short = "return the name of command causing error",
            doc_with = "try")

new_command("get-error-message", lambda: get_error_info('message'),
            type  = ["CLI"],
            short = "return the message for an error",
            doc_with = "try")

new_command("get-error-file", lambda: get_error_info('file'),
            type  = ["CLI"],
            short = "return the file name of the CLI command error",
            doc_with = "try")

new_command("get-error-line", lambda: get_error_info('line'),
            type  = ["CLI"],
            short = "return the file line number of the CLI command error",
            doc_with = "try")

new_command("except", cli_impl._DummyCommandHandler("except"),
            type  = ["CLI"],
            synopses = [],
            short = "catch error from block of code",
            doc_with = "try")

new_command("local", cli_impl._DummyCommandHandler("local"),
            [arg(str_t, "variable assignment", "?")],
            type  = ["CLI"],
            short = "define a local variable",
            synopsis = [ Markup.Keyword('local'), ' ',
                         Markup.Keyword('$'), Markup.Arg('foo'), ' ',
                         Markup.Keyword('='), ' ',
                         Markup.Arg('value') ],
            see_also = ["=", "$"],
            doc = """
Makes a CLI variable local in a <arg>variable assignment</arg>.

Local variables only exist until the end of the current command block.
""")

def interrupt_cmd(msg = None, error = False):
    msg = msg if msg else "interrupt-script command"
    if error:
        raise CliError(msg)
    else:
        raise CliQuietError(msg)

new_command("interrupt-script", interrupt_cmd,
            [arg(str_t, "message", "?"),
             arg(flag_t, "-error")],
            type  = ["CLI"],
            short = "interrupt script execution",
            see_also = ["stop", "try"],
            doc = """
Interrupts the execution of a script and prints out
<arg>message</arg>. If <arg>message</arg> is not specified, a generic
message is printed.

The <tt>-error</tt> flag tells Simics to consider the interruption as
an error.""")

def break_loop_cmd():
    raise cli.CliBreakError()

new_command("break-loop", break_loop_cmd,
            [],
            type  = ["CLI"],
            short = "break the execution in a script loop",
            see_also = ["foreach", "while", "continue-loop"],
            doc = """
The <cmd>break-loop</cmd> commands ends the execution of the neareast
enclosing <cmd>foreach</cmd> or <cmd>while</cmd> loop. It is an error to use
it outside of a loop construct.
""")

def continue_loop_cmd():
    raise cli.CliContinueError()

new_command("continue-loop", continue_loop_cmd,
            [],
            type  = ["CLI"],
            short = "skip to next iteration in a script loop",
            see_also = ["foreach", "while", "break-loop"],
            doc = """
The <cmd>continue-loop</cmd> commands ends the execution of the current
iteration of the neareast enclosing <cmd>foreach</cmd> or <cmd>while</cmd>
loop. It is an error to use it outside of a loop construct.
""")

def command_file_stack_cmd():
    stack = cli_impl.get_script_stack()
    msg = "Current CLI command file stack:"
    for f, l in stack:
        msg += "\n  %s:%s" % (f, l)
    return command_verbose_return(message = msg, value = stack)

new_command("command-file-stack", command_file_stack_cmd,
            [],
            type  = ["CLI"],
            short = "list current CLI command file stack",
            see_also = ["run-script", "command-file-history"],
            doc = """
Displays the current CLI command file stack, useful for script debug purposes.
The stack is returned as a list if the command is used in an expression.""")

# Print a table (list of rows, each a list of strings).
# The alignments list specifies how each column should be aligned,
# each entry being "r" or "l". The string 'spacing' is put between columns.
def print_table(headers, data, alignment):
    props = [(Table_Key_Columns,
              [[(Column_Key_Name, n),
                (Column_Key_Alignment, a)]
               for (n, a) in zip(headers, alignment)])]
    tbl = table.Table(props, data)
    print(tbl.to_string(rows_printed=0, no_row_column=True))

def command_file_history_cmd(verbose):
    import command_file
    history = command_file.get_command_file_history()
    if not verbose:
        history = [[os.path.basename(f), a] for (f, a) in history]
    if interactive_command():
        print_table(["Command File", "Action"], history, ["left", "left"])
    return command_quiet_return(history)

new_command("command-file-history", command_file_history_cmd,
            [arg(flag_t, "-v")],
            type  = ["CLI"],
            short = "list current CLI script stack",
            see_also = ["run-script", "command-file-stack"],
            doc = """
Displays a list of all CLI command files that have run, useful for script debug
purposes. The list is returned instead if the command is used in an expression.
The <tt>-v</tt> flag tells the command to include the full file system paths to
the command files in the output.""")

def pipe_cmd(human_readable, cmd, prog):
    # quiet_run_command may raise CliError
    if human_readable:
        output_mode = cli.output_modes.formatted_text
    else:
        output_mode = cli.output_modes.unformatted_text
    (ret, text) = cli.quiet_run_command(cmd, output_mode)

    # We make the command suck input from a temporary file to dodge the Python
    # use of select() if more than one pipe is being used for the same process.
    import tempfile
    import locale
    inp = tempfile.TemporaryFile()
    encoding = locale.getpreferredencoding()
    text = codecs.encode(text, encoding, "replace")
    inp.write(text)
    inp.seek(0)

    import subprocess
    p = subprocess.Popen(prog, shell=True, stdin=inp,  # nosec
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         close_fds = True)
    inp.close()
    (out, _) = p.communicate()
    out = str(out.strip(), locale.getpreferredencoding())
    exit_status = p.returncode
    if exit_status != 0:
        if not out:
            out = 'exit status %d' % exit_status
        if out.find('\n') >= 0:
            out = '\n' + out
        raise CliError("Error return from shell command '%s': %s\n"
                       % (prog, out))
    return command_return(message=out, value=out)

new_command("pipe", pipe_cmd,
            [arg(flag_t, "-h"), arg(str_t, "command"), arg(str_t, "pipe")],
            type  = ["CLI"],
            see_also = ["shell"],
            short = "run commands through a pipe",
            doc = """
Runs the CLI command <arg>command</arg> in Simics and pipes the output
(stdout) through the external program <arg>pipe</arg>'s stdin.

By default, commands run this way will be formatted to be machine readable
rather than human readable. For example, this turns off multi-column output in
commands such as <cmd>list-classes</cmd>. By specifying the <tt>-h</tt> flag,
the output will be sent in human readable mode.

This command handles output and errors the same way as the <cmd>shell</cmd>
command does.""")


#
# -------------------- < --------------------
#

def less_than(a, b):
    return a[1] < b[1]

new_operator("<", less_than,
             [arg((int_t, float_t)),
              arg((int_t, float_t))],
             type = ["CLI"],
             pri = 50, infix = 1,
             short = "less than",
             doc = """
Returns true if <arg>arg1</arg> is less than  <arg>arg2</arg>, and false if not.
""")

#
# -------------------- <= --------------------
#

def less_or_equal(a, b):
    return a[1] <= b[1]

new_operator("<=", less_or_equal,
             [arg((int_t, float_t)),
              arg((int_t, float_t))],
             type = ["CLI"],
             pri = 50, infix = 1,
             short = "less or equal",
             doc = """
Returns true if <arg>arg1</arg> is less than or equal to <arg>arg2</arg>,
and false if not.
""")

#
# -------------------- > --------------------
#

def greater_than(a, b):
    return a[1] > b[1]

new_operator(">", greater_than,
             [arg((int_t, float_t)),
              arg((int_t, float_t))],
             type = ["CLI"],
             pri = 50, infix = 1,
             short = "greater than",
             doc = """
Returns true if <arg>arg1</arg> is greater than <arg>arg2</arg>, and false if
not.
""")

#
# -------------------- >= --------------------
#

def greater_or_equal(a, b):
    return a[1] >= b[1]

new_operator(">=", greater_or_equal,
             [arg((int_t, float_t)),
              arg((int_t, float_t))],
             type = ["CLI"],
             pri = 50, infix = 1,
             short = "greater or equal",
             doc = """
Returns true if <arg>arg1</arg> is greater than or equal to <arg>arg2</arg>,
and false if not.
""")

#
# -------------------- != --------------------
#

def not_equal(a, b):
    return a[1] != b[1]

new_operator("!=", not_equal,
             [arg((int_t, float_t, str_t, list_t, nil_t)),
              arg((int_t, float_t, str_t, list_t, nil_t))],
             type = ["CLI"],
             pri = 50, infix = 1,
             short = "not equal",
             doc = """
Returns true if <arg>arg1</arg> and <arg>arg2</arg> are not equal, and false if
equal.
""")

#
# -------------------- == --------------------
#

def equal(a, b):
    return a[1] == b[1]

new_operator("==", equal,
             [arg((int_t, float_t, str_t, list_t, nil_t)),
              arg((int_t, float_t, str_t, list_t, nil_t))],
             type = ["CLI"],
             pri = 50, infix = 1,
             short = "equal",
             doc = """
Returns true if <arg>arg1</arg> and <arg>arg2</arg> are equal, and false if
not.
""")

#
# -------------------- min --------------------
#

def min_cmd(a, b):
    return min(a[1], b[1])

new_command("min", min_cmd,
            [arg((int_t, float_t)),
             arg((int_t, float_t))],
            type = ["CLI"],
            short = "min",
            doc = """
Returns the smaller value of <arg>arg1</arg> and <arg>arg2</arg>.
""")

#
# -------------------- max --------------------
#

def max_cmd(a, b):
    return max(a[1], b[1])

new_command("max", max_cmd,
            [arg((int_t, float_t)),
             arg((int_t, float_t))],
            type = ["CLI"],
            short = "max",
            doc = """
Returns the larger value of <arg>arg1</arg> and <arg>arg2</arg>.
""")

#
# ------------------- and --------------------
#

def and_command(a, b):
    return a[1] and b[1]

new_operator("and", and_command,
             [arg((int_t, str_t, bool_t(), nil_t)),
              arg((int_t, str_t, bool_t(), nil_t))],
             type = ["CLI"],
             pri = 20, infix = 1,
             short = "logical and",
             doc = """
Evaluates <arg>arg1</arg> and returns its value if it is false. Otherwise
<arg>arg2</arg> is evaluated and its value is returned.
""")

#
# ------------------- or --------------------
#

def or_command(a, b):
    return a[1] or b[1]

new_operator("or", or_command,
             [arg((int_t, str_t, bool_t(), nil_t)),
              arg((int_t, str_t, bool_t(), nil_t))],
             type = ["CLI"],
             pri = 10, infix = 1,
             short = "logical or",
             doc = """
Evaluates <arg>arg1</arg> and returns its value if it is true. Otherwise
<arg>arg2</arg> is evaluated and its value is returned.
""")

#
# ------------------- not --------------------
#

def not_command(a):
    return not a[1]

new_operator("not", not_command,
             [arg((int_t, str_t, float_t, bool_t(), nil_t), doc = 'arg')],
             type = ["CLI"],
             pri = 30,
             short = "logical not",
             doc = """
Returns TRUE if <arg>arg</arg> is false, and FALSE if not.
""")

#
# ------------------- defined --------------------
#

def defined_command(v):
    cli.check_variable_name(v, "defined")
    return v in cli.get_current_locals().get_all_variables()

new_operator("defined", defined_command,
             [arg(str_t, doc = 'variable')],
             type = ["CLI"],
             short = "variable defined",
             see_also = ["read-variable", "$", "list-variables"],
             pri = 40, # higher than 'not' command
             doc = """
Returns TRUE if <arg>variable</arg> is a defined CLI variable, and FALSE if
not.

Note that <cmd>defined foo</cmd> tests whether the variable <tt>foo</tt> is
defined, whereas <cmd>defined $bar</cmd> tests whether the variable whose name
is stored in <tt>$bar</tt> is defined.""")

#
# ------------------- read-variable --------------------
#

def read_variable_command(name, alt):
    cli.check_variable_name(name, "read-variable")
    exists = name in cli.get_current_locals().get_all_variables()
    return getattr(cli.get_current_locals(), name) if exists else alt

new_command("read-variable", read_variable_command,
            [arg(str_t, name = 'variable'),
             arg(poly_t('alt', str_t, int_t, float_t, bool_t(), list_t),
                 spec = "?", name = 'alt', default = False)],
            type = ["CLI"],
            see_also = ["defined", "$"],
            short = "value of a named variable",
            doc = """
Returns the value of the CLI variable named <arg>variable</arg> if it is
defined. If the variable does not exist, then <arg>alt</arg> is returned or
FALSE if <arg>alt</arg> is not specified.

Note that <cmd>read-variable foo</cmd> returns the value of variable
<tt>$foo</tt>, whereas <cmd>read-variable $bar</cmd> returns the value of the
variable whose name is stored in <tt>$bar</tt>.""")


#
# ------------ list-notifiers ------------
#

def expand_notifiers(prefix):
    names = [entry[0] for entry in conf.sim.notifier_list]
    return cli.get_completions(prefix, names)

def list_notifiers_cmd(arg, notifier_name, show_all, show_unused, substr):

    def name_matches(name):
        return not notifier_name or name == notifier_name

    def format_description(description):
        return cli.get_format_string(description, mode='text').strip()

    show_global = arg[1] if (arg is not None and arg[0] is flag_t) else False
    obj = arg[1] if (arg is not None and arg[2] == 'object') else None
    cls_name = arg[1] if (arg is not None and arg[2] == 'class') else None
    # Eager evaluation
    notifiers = [x for x in simics.SIM_get_attribute(conf.sim, "notifier_list")
                 if substr in x[0]]
    if notifier_name:
        data = [x for x in notifiers if name_matches(x[0])]
        if data:
            show_global = data[0][2] is not None
        else:
            raise CliError(f"No such notifier: {notifier_name}")

    if show_global:
        tbl_data = [[notifier_id, name, format_description(description)]
                    for (name, notifier_id, description, _) in notifiers
                    if description is not None and name_matches(name)]
        header = ["ID", "Name", "Description"]
    else:
        if obj:
            cls_name = obj.classname
        if cls_name:
            # Verify that class exists
            try:
                simics.SIM_get_class(cls_name)
            except simics.SimExc_General as ex:
                raise CliError(ex)
            cls_names = [cls_name]
            data = {}
        else:
            # By default, do not display notifiers that exist on all classes
            if not show_all and not notifier_name:
                notifiers = [n for n in notifiers
                             if n[1] not in {simics.Sim_Notify_Queue_Change,
                                             simics.Sim_Notify_Cell_Change,
                                             simics.Sim_Notify_Object_Delete}]

            cls_names = SIM_get_all_classes()
            data = {notifier_id: []
                    for (name, notifier_id, global_desc, _) in notifiers
                    if global_desc is None and name_matches(name)}

        # Collect data about interesting classes
        class_data = {c:
                      [[notifier_id, name, desc,
                        list(simics.SIM_object_iterator_for_class(c))]
                       for (name, notifier_id, _, cls_list) in notifiers
                       for (c_name, desc) in cls_list
                       if c_name == c and name_matches(name)]
                      for c in cls_names}

        # Add registrations to notifier data
        for c in cls_names:
            for (notifier_id, name, desc, objs) in class_data[c]:
                if show_unused or objs:
                    data.setdefault(notifier_id, []).append(
                        [notifier_id, name, c, desc,
                         "\n".join([o.name for o in objs])])

        # Add lines for notifiers without registrations
        if show_unused:
            for (name, notifier_id, _, _) in notifiers:
                if notifier_id in data and not data[notifier_id]:
                    data[notifier_id] = [[notifier_id, name] + [""] * 3]

        tbl_data = sorted(item for l in data.values() for item in l)
        for record in tbl_data:
            record[3] = format_description(record[3])
        header = ["ID", "Notifier", "Class", "Description", "Objects"]

    properties = [(Table_Key_Columns, [[(Column_Key_Name, h)]
                                       for h in header])]
    tbl = table.Table(properties, tbl_data)
    return command_verbose_return(
        tbl.to_string(rows_printed=0, no_row_column=True),
        sorted(list({row[1] for row in tbl_data})))

new_command("list-notifiers", list_notifiers_cmd,
            [arg((flag_t, obj_t('notifier'), str_t),
                 ('-global', 'object', 'class'), '?',
                 expander=(None, object_expander(None),
                           conf_class_expander(True))),
             arg(str_t, 'name', '?', '', expander=expand_notifiers),
             arg(flag_t, "-a"),
             arg(flag_t, "-u"),
             arg(str_t, 'substr', '?', '')],
            type = ["Notifiers"],
            short = "list available notifiers",
            see_also = ['bp.notifier.wait-for', 'list-haps',
                        'list-notifier-subscribers'],
            doc = """
Print a list of available notifiers, with names that can be used
in commands such as <cmd>bp.notifier.wait-for</cmd>.

If <tt>-global</tt> is specified, the list contains the names of
available global notifiers.

Otherwise, the list contains registered notifiers on <arg>object</arg>
or <arg>class</arg>, or registered notifiers on all classes, if the
<arg>object</arg> and <arg>class</arg> parameters are omitted. Each
entry in the output contains the notifier name, notifier class,
notifier description and the list of objects of that class. By
default, if no class or object is specified, then notifiers that are
pre-defined on all classes are not shown; they can be displayed using
the <tt>-a</tt> flag. Also, by default only notifiers on classes with
at least one object are displayed, unless <tt>-u</tt> is specified.

If <arg>name</arg> is specified, display data about this notifier
only, ignoring <tt>-global</tt> and <tt>-a</tt>.

The <arg>substr</arg> argument can be used to print matching notifier
names only.
""")

def list_notifier_subscribers_cmd(arg):
    show_global = arg[1] if (arg is not None and arg[0] is flag_t) else False
    obj = arg[1] if (arg is not None
                     and isinstance(arg[0], obj_t)) else None

    if show_global:
        data = [[name, subscriber.name if subscriber else "", oneshot]
                 for (name, subscriber, oneshot)
                 in simics.CORE_get_global_notifier_subscribers()]
        header = ["Name", "Subscriber", "One-shot"]
    else:
        data = [[o,
                 name,
                 cli.get_format_string(desc, mode='text').strip(),
                 subscriber.name if subscriber else ""]
                for o in ([obj] if obj else SIM_object_iterator(None))
                for (name, desc, subscriber)
                in simics.CORE_get_notifier_subscribers(o)]
        header = ["Notifier", "Name", "Description", "Subscriber"]

    properties = [(Table_Key_Columns, [[(Column_Key_Name, h)]
                                       for h in header])]
    tbl = table.Table(properties, sorted(data))
    print(tbl.to_string(rows_printed=0, no_row_column=True))

new_command("list-notifier-subscribers", list_notifier_subscribers_cmd,
            [arg((flag_t, obj_t('notifier')), ('-global', 'object'), '?',
                 expander=(None, object_expander(None)))],
            type = ["Notifiers"],
            short = "list added notifier subscribers",
            see_also = ['list-notifiers', 'list-hap-callbacks'],
            doc = """
If the <tt>-global</tt> flag is specified, print a list of
added global notifier subscribers.

In this case each entry in the output contains: notifier name,
subscriber object (or <tt>NIL</tt> if no subscriber) and one-shot
status (<tt>TRUE</tt> if and only if the notifier was added with
<fun>SIM_add_global_notifier_once</fun>).

If the <tt>-global</tt> flag is not specified, print a list of added
notifier subscribers on <arg>object</arg>, or subscribers on all
objects, if the <arg>object</arg> parameter is omitted.

In this case each entry in the output contains: notifier object,
notifier name, notifier description, and the
subscriber object (or <tt>NIL</tt> if no subscriber).
""")

#
# ------------ create-script-barrier ------------
#

def create_script_barrier_command(num_branches):
    if num_branches < 1:
        raise CliError("A barrier must wait for at least one script branch.")
    return cli.create_script_barrier(num_branches)

new_command("create-script-barrier", create_script_barrier_command,
            [arg(int_t, 'num_branches')],
            type  = ["CLI"],
            short = "create a script barrier",
            see_also = ["script-branch",
                        "script-barrier-limit",
                        "wait-for-script-barrier"],
            doc = """
Creates a script barrier that can be used for synchronization of script
branches. The return value should only be used as argument to the
<cmd>wait-for-script-barrier</cmd> or <cmd>script-barrier-limit</cmd>
commands.

A script branch enters a barrier by calling <cmd>wait-for-script-barrier</cmd>.
It will then be suspended until <arg>num_branches</arg> script branches have
entered the barrier. Once all script branches have reached the barrier, they
are released and will continue executing. At the same time the barrier is reset
and can be used again.
""")

#
# ------------ script-barrier-limit ------------
#

def script_barrier_limit_command(barrier, add_or_sub, num_branches):
    cli.check_valid_script_barrier(barrier)
    limit = cli.script_barrier_limit(barrier)
    if num_branches is not None:
        if add_or_sub[2] == "-add":
            limit += num_branches
        elif add_or_sub[2] == "-sub":
            limit -= num_branches
        else:
            limit = num_branches
        cli.update_script_barrier_limit(barrier, limit)
    ret = ("Current wait limit: %d\n"
           "Waiting branches: %d"
           % (limit, cli.script_barrier_count(barrier)))
    # Always print when used with no argument (except in an expression)
    if num_branches is None:
        return command_verbose_return(message = ret, value = limit)
    else:
        return command_return(message = ret, value = limit)

new_command("script-barrier-limit", script_barrier_limit_command,
            [arg(int_t, 'barrier'),
             arg((flag_t, flag_t), ("-add", "-sub"), "?", (flag_t, 0, None)),
             arg(uint_t, 'num_branches', "?", None)],
            type  = ["CLI"],
            short = "manipulate the script barrier limit",
            see_also = ["script-branch",
                        "create-script-barrier",
                        "wait-for-script-barrier"],
            doc = """
Changes the number of script branches that an existing script branch
<arg>barrier</arg> waits for. The <tt>-add</tt> and <tt>-sub</tt> flags tell
the command to add or subtract <arg>num_branches</arg> to or from the current
wait limit. Without any flag, the new limit is set to <arg>num_branches</arg>.
Lowering the limit below the number of currently waiting script branches for a
barrier is not allowed. The command can be called without any argument to get
the current limit. When used in an expression, the command returns the current
wait limit.""")

#
# ------------ wait-for-script-barrier ------------
#

def wait_for_script_barrier_command(barrier):
    # allow in recording script-branch
    check_script_branch_command("wait-for-script-barrier")
    cli.check_valid_script_barrier(barrier)
    cli.add_script_barrier_branch(barrier)
    if cli.script_barrier_ready(barrier):
        cli.reset_script_barrier(barrier)
    else:
        sb_wait('wait-for-script-barrier', barrier, wait_data = "%d" % barrier)

new_command("wait-for-script-barrier", wait_for_script_barrier_command,
            [arg(int_t, 'barrier')],
            type  = ["CLI"],
            short = "wait until enough branches have reached a barrier",
            see_also = ["script-branch",
                        "create-script-barrier"],
            doc = """
Suspends execution of a script branch until enough script branches have
entered the script barrier <arg>barrier</arg>.""")

#
# ------------ create-script-pipe ------------
#

def create_script_pipe_command():
    return cli.create_script_pipe()

new_command("create-script-pipe", create_script_pipe_command,
            [],
            short = "create a script pipe",
            type  = ["CLI"],
            see_also = ["script-branch",
                        "script-pipe-has-data",
                        "wait-for-script-pipe",
                        "add-data-to-script-pipe"],
            doc = """
Creates a script pipe that can be used to send data from one script branch, or
the main branch, to another script branch. The return value should only be used
as argument to the <cmd>wait-for-script-pipe</cmd> and
<cmd>add-data-to-script-pipe</cmd> commands.""")

#
# ------------ wait-for-script-pipe ------------
#

def wait_for_pipe_command(pipe):
    # allow in recording script-branch
    check_script_branch_command("wait-for-script-pipe")
    cli.check_valid_script_pipe(pipe)
    while not cli.script_pipe_has_data(pipe):
        sb_wait('wait-for-script-pipe', pipe, wait_data = "%d" % pipe)
    return cli.script_pipe_get_data(pipe)

new_command("wait-for-script-pipe", wait_for_pipe_command,
            [arg(int_t, 'pipe')],
            type  = ["CLI"],
            short = "wait until there is data on a script pipe",
            see_also = ["script-branch",
                        "create-script-pipe",
                        "script-pipe-has-data",
                        "add-data-to-script-pipe"],
            doc = """
Suspends execution of a script branch until there is some data to read from the
script pipe <arg>pipe</arg>. If there already is data available, the command
will return immediately. The return value is the data send by the
<cmd>add-data-to-script-pipe</cmd> commands.""")

#
# ------------ add-data-to-script-pipe ------------
#

def add_data_to_pipe_command(pipe, data):
    cli.check_valid_script_pipe(pipe)
    cli.script_pipe_add_data(pipe, data)

new_command("add-data-to-script-pipe", add_data_to_pipe_command,
            [arg(int_t, 'pipe'),
             arg(poly_t('data', int_t, str_t, list_t, float_t, nil_t), "data")],
            type  = ["CLI"],
            short = "send data to a script pipe",
            see_also = ["script-branch",
                        "create-script-pipe",
                        "script-pipe-has-data",
                        "wait-for-script-pipe"],
            doc = """
Sends <arg>data</arg> to a script branch using the <arg>pipe</arg> script pipe.
The data will be queued until the receiving script branch reads it with
<cmd>wait-for-script-pipe</cmd>. The data can be an integer, string, floating
point value, nil or a list.""")

#
# ------------ script-pipe-has-data ------------
#

def script_pipe_has_data_command(pipe):
    cli.check_valid_script_pipe(pipe)
    return cli.script_pipe_has_data(pipe)

new_command("script-pipe-has-data", script_pipe_has_data_command,
            [arg(int_t, 'pipe')],
            type  = ["CLI"],
            short = "check if script pipe contains data",
            see_also = ["script-branch",
                        "create-script-pipe",
                        "wait-for-script-pipe",
                        "add-data-to-script-pipe"],
            doc = """
Returns true if the script pipe has data that can be read and false if it is
empty. The <arg>pipe</arg> argument is the return value from
<cmd>create-script-pipe</cmd>.
""")

#
# ------------ list-script-branches ------------
#

def list_script_branch_command(bids_to_show, verbose):
    filename_filter = (lambda f: f) if verbose else os.path.basename
    def create_table_line(branch_info):
        (bid, desc, command, _, ccaller, cfile, cline,
         wcaller, wfile, wline, wdata) = branch_info
        if command is None:
            command = ""
        if '.' in command:
            obj, cmd = command.rsplit(".", 1)
        else:
            obj = ""
            cmd = command
        return [bid, cmd, obj, ('"%s"' % desc) if desc else "",
                (ccaller + " " if ccaller else "") +
                "%s:%d" % (filename_filter(cfile), cline) if cfile else "",
                (wcaller + " " if wcaller else "") +
                "%s:%d" % (filename_filter(wfile), wline) if wfile else "",
                wdata if wdata else ""]
    data = [create_table_line(branch_info)
            for branch_info in conf.sim.script_branches
            if len(bids_to_show) == 0 or branch_info[0] in bids_to_show]
    header = [("ID", "right"), ("Wait Condition", "left"), ("Object", "left"),
              ("Description", "left"), ("Created", "left"), ("Waiting", "left"),
              ("Wait data", "left")]
    properties = [(table.Table_Key_Columns,
                   [[(table.Column_Key_Name, n),
                     (table.Column_Key_Alignment, a)]
                    for (n, a) in header])]
    result_table = table.Table(properties, data)
    msgstring = result_table.to_string(rows_printed=0, no_row_column=True)
    return cli.command_verbose_return(message = msgstring,
                                      value = data)

new_command("list-script-branches", list_script_branch_command,
            [arg(uint_t, 'id', '*'),
             arg(flag_t, '-verbose')],
            type  = ["CLI"],
            short = "list all script branches",
            see_also = ["script-branch", "interrupt-script-branch"],
            doc = """
Lists all currently active script branches. With the <tt>-verbose</tt> flag
the full paths to the scripts are shown, otherwise just scripts' filenames.

The <arg>id</arg> parameter can be used to list only script branches with
the given IDs.

Here are a few examples of the command usage:

Listing all script branches:<br/>
<tt>list-script-branches</tt><br/>
Listing script branches with full paths to the scripts:<br/>
<tt>list-script-branches -verbose</tt><br/>
Listing only the script branch with ID 1:<br/>
<tt>list-script-branches id = 1</tt><br/>
Listing script branches with IDs 1 and 2:<br/>
<tt>list-script-branches id = 1 2</tt><br/>
or<br/>
<tt>list-script-branches id = [1, 2]</tt>
""")

#
# ------------ interrupt-script-branch ------------
#

def interrupt_script_branch_command(id):
    try:
        cli.sb_interrupt_branch(id)
        print("Script branch %d interrupted." % id)
    except Exception as ex:
        raise CliError("Failed interrupting script branch: %s" % ex)

new_command("interrupt-script-branch", interrupt_script_branch_command,
            [arg(int_t, 'id')],
            short = "interrupt the execution of a script branch",
            type  = ["CLI"],
            see_also = ["script-branch",
                        "break-script-branch",
                        "list-script-branches"],
            doc = """
Send an interrupt exception to a script branch with the given <arg>id</arg>.

The ID was returned from the <cmd>script-branch</cmd> command and is also
listed by the <cmd>list-script-branches</cmd> command. The branch will
immediately wake up from any pending waits and exit when it receives the
exception.""")

#
# ------------ break-script-branch ------------
#

def break_script_branch_command():
    if sb_in_main_branch():
        raise CliError("The break-script-branch command can only be used"
                       " in a script-branch")
    raise CliQuietError(None, is_script_branch_interrupt=True)

new_command("break-script-branch", break_script_branch_command,
            [],
            short = "break the execution of a script branch",
            type  = ["CLI"],
            see_also = ["script-branch",
                        "interrupt-script-branch",
                        "list-script-branches"],
            doc = """
The <cmd>break-script-branch</cmd> commands ends the execution of the current
script branch. It is an error to use it outside of a script-branch.
""")

#
# ------------------- match-string ------------------
#

def match_string_cmd(pattern, match_str, error):
    try:
        m = re.search(pattern, match_str)
    except Exception as ex:
        raise CliError("String match failed: %s" % ex)
    if not m:
        if error:
            raise CliError("The string '%s' does not match pattern '%s'"
                           % (match_str, pattern))
        return False
    elif not m.groups():
        return True
    else:
        return list(m.groups())

new_command("match-string", match_string_cmd,
            [arg(str_t, "pattern"), arg(str_t, "string"),
             arg(flag_t, "-error")],
            type = ["CLI"],
            short = "compare string with a pattern and return matches",
            see_also = ['split-string'],
            doc = """
Match <arg>pattern</arg> with <arg>string</arg> returning TRUE if the pattern
matches and FALSE if not. The command will signal an error if the
<tt>-error</tt> flag is used and the string does not match the
pattern. The format of <arg>pattern</arg> is the same as used by the Python
<tt>re.search()</tt> method. If the pattern contains groups, the return value
on a match is a list of matching strings. Example:

<tt>match-string "abd" "abcdef"</tt> &rarr; <tt>FALSE</tt><br/>
<tt>match-string "abc" "abcdef"</tt> &rarr; <tt>TRUE</tt><br/>
<tt>match-string "(a*)([0-9]*)x" "aaa04x")</tt> &rarr; <tt>["aaa", "04"]</tt>
<br/>
""")

def start_command_line_capture_cmd(filename, overwrite, append, timestamp):
    try:
        filename = os.path.abspath(filename)
    except:
        # Let tee_add() handle invalid paths.
        pass
    cli_impl.tee_add(filename, overwrite, append, timestamp)
    return command_return("Output captured to '%s'" % filename, filename)

new_command("start-command-line-capture", start_command_line_capture_cmd,
            [arg(filename_t(), "filename"),
             arg(flag_t, "-overwrite"),
             arg(flag_t, "-append"),
             arg(flag_t, "-timestamp")],
            type = ["Files"],
            short = "send output to file",
            see_also = ['stop-command-line-capture'],
            doc = """
Start directing Simics output to the file <arg>filename</arg>. The file will
not be overwritten unless the <tt>-overwrite</tt> flag is specified. The
<tt>-append</tt> flag allows the output to be appended to the specified file.
An optional time stamp showing wall-clock time can be added at the start of
each line, enabled with the <tt>-timestamp</tt> flag.

The file will contain regular Simics output and CLI error messages, as well
as typed CLI commands, prefixed by the Simics prompt.""")

def stop_command_line_capture_cmd(filename):
    if filename:
        try:
            filename = os.path.abspath(filename)
        except:
            # Let tee_remove() handle invalid paths.
            pass
    cli_impl.tee_remove(filename)

new_command("stop-command-line-capture", stop_command_line_capture_cmd,
            [arg(filename_t(), "filename", "?", None,
                 expander = cli_impl.tee_expander)],
            type = ["Files"],
            short = "stop sending output to file",
            see_also = ['start-command-line-capture'],
            doc = """
Stop sending output to the file <arg>filename</arg>. If no argument is given,
then the command will disable all file output.""")

def signed_cmd(size, value):
    return (value & ((1 << size) - 1)) - ((value << 1) & (1 << size))

new_command("signed", lambda x : signed_cmd(64, x),
            [arg(int_t, "int")],
            type = ["CLI"],
            short = "interpret unsigned integer as signed",
            see_also = ["atoi", "unsigned"],
            doc = """
Interpret an integer, <arg>int</arg>, as a signed value of a specific bit
width. For example <cmd>signed16 0xffff</cmd> will return -1. The
<cmd>signed</cmd> command assumes a 64 bit width.
""")

def _signed_cmd(s):
    return lambda x : signed_cmd(s, x)

for i in (8, 16, 32, 64):
    new_command("signed%d" % i, _signed_cmd(i),
                [arg(int_t, "int")],
                type = ["CLI"],
                short = "interpret unsigned integer as signed",
                doc_with = "signed")

def unsigned_cmd(size, v):
    num_bytes = size // 8
    bytes_v = int.to_bytes(
        v & ((1 << size) - 1), num_bytes, 'little', signed=False)
    new_v = int.from_bytes(bytes_v, 'little', signed=False)
    return command_return(message=f'0x{new_v:0{num_bytes * 2}x}', value=new_v)

new_command("unsigned", lambda x : unsigned_cmd(64, x),
            [arg(int_t, "int")],
            type = ["CLI"],
            short = "interpret an integer as unsigned 64-bit",
            see_also = ["atoi", "signed"],
            doc = """
Interpret an integer, <arg>int</arg>, as an unsigned value of a specific bit
width. For example <cmd>unsigned16 -1</cmd> will return 0xffff. The
<cmd>unsigned</cmd> command assumes a 64 bit width.
""")

def _unsigned_cmd(s):
    return lambda x : unsigned_cmd(s, x)

for i in (8, 16, 32, 64):
    new_command("unsigned%d" % i, _unsigned_cmd(i),
                [arg(int_t, "int")],
                type = ["CLI"],
                short = f"interpret an integer as unsigned {i}-bit",
                doc_with = "unsigned")

def atoi_cmd(string, base):
    try:
        return int(string, base)
    except ValueError as ex:
        raise CliError(str(ex).replace('int()', 'atoi'))

new_command("atoi", atoi_cmd,
            [arg(str_t, "string"),
             arg(int_t, "base", "?", 0)],
            type = ["CLI"],
            short = "convert string to integer",
            see_also = ["signed", "print", "hex", "dec", "oct", "bin"],
            doc = """
Convert the <arg>string</arg> argument to an integer. The string will be
interpreted according to the given <arg>base</arg>. If the <arg>base</arg>
argument is left out, the command will try to guess the base based on the
string. A string prefix of 0x is interpreted as base 16, 0o or 0 is interpreted
as base 8, and 0b as base 2. The <arg>base</arg> argument must be between 2 and
36 inclusive.
""")


#
# -------------------- info --------------------
#

class JitStatus(Enum):
    NOT_AVAILABLE = "Not Available"
    DISABLED = "Disabled"
    ENABLED = "Enabled"

def get_jit_status(obj):
    has_jit = hasattr(obj, "turbo_execution_mode")
    if not has_jit:
        return JitStatus.NOT_AVAILABLE
    elif not obj.turbo_execution_mode:
        return JitStatus.DISABLED
    else:
        return JitStatus.ENABLED

def vmp_loaded():
    return simics.SIM_vmxmon_version() is not None

def common_processor_get_info(obj):
    jit_status = get_jit_status(obj)
    if obj.freq_mhz == int(obj.freq_mhz):
        clock_freq = "%d" % obj.freq_mhz
    else:
        clock_freq = "%f" % obj.freq_mhz
    try:
        phys_mem = obj.iface.processor_info.get_physical_memory().name
    except Exception:
        phys_mem = None
    r = obj.iface.step_cycle_ratio.get_ratio()
    cpi = r.cycles / r.steps  # NB: "/" operator always returns float (Python 3)
    ret = [("VMP status", "Not Loaded" if not vmp_loaded() else "Not Available"),
           ("JIT compilation", jit_status.value),
           ("Clock frequency", "%s MHz" % clock_freq),
           ("Cycles per instruction (CPI)", f"{cpi:.2f}"),
           ("Instructions per cycle (IPC; equals '1 / CPI')", f"{1 / cpi:.2f}"),
           ("Physical memory", phys_mem)]
    if hasattr(obj, "cell"):
        ret += [("Cell" , obj.cell)]
    if getattr(obj, "physical_io", None) is not None:
        ret += [("Physical I/O", obj.physical_io.name)]
    return ret

def default_processor_get_info(obj):
    return [ (None,
              common_processor_get_info(obj)) ]

def common_processor_get_status(obj):
    next_action = obj.iface.processor_cli.get_pending_exception_string()
    if next_action == None:
        next_action = "Executing (fetch/execute from program counter)"
    ret = [("Clock frequency", "%f MHz" % obj.freq_mhz),
           ("Activity", next_action)]
    return ret

def default_processor_get_status(obj):
    return [ (None,
              common_processor_get_status(obj)) ]

#
# -------------------- diff, diff-gen --------------------
#

def diff_gen(cmd, file):
    old_out = sys.stdout
    try:
        fd = open(file, "w")
    except:
        pr("Error while opening file %s for writing\n" % file)
        return

    sys.stdout = fd

    try:
        cli.run_command(cmd)
        sys.stdout = old_out
        fd.close()
    except:
        fd.close()
        sys.stdout = old_out
        raise


new_unsupported_command("diff-gen", "internals", diff_gen,
                        [arg(str_t, "cmd"), arg(filename_t(), "file", "?",
                                                "last-command-output.txt")],
                        short = "diff command output",
                        doc = """
Writes the output of the command <arg>cmd</arg> to the
<arg>file</arg>. Default file name is <file>last-command-output.txt</file>.""")

def diff(cmd, filename):
    import subprocess
    filename_cmp = filename + ".cmp"
    diff_gen(cmd, filename_cmp)
    subprocess.run(["diff", filename, filename_cmp])

new_unsupported_command("diff", "internals", diff,
                        [arg(str_t, "cmd"),
                         arg(filename_t(exist = 1),
                             "file",  "?", "last-command-output.txt")],
                        short = "diff command output",
                        doc = """
Uses system diff to compare the output in the <arg>file</arg> with the output
of the command <arg>cmd</arg>. Default file name is
<file>last-command-output.txt</file>.
""")

#
# ----------------------- devs -----------------------
#

def is_port_mapping(map_line):
    return isinstance(map_line[1], list)

def mapping_dev_name(map_line):
    if is_port_mapping(map_line):
        return map_line[1][0].name
    else:
        return map_line[1].name

def mapping_dev_port_or_func(map_line):
    if is_port_mapping(map_line):
        return map_line[1][1]
    else:
        return map_line[2]

def devs_cmd(device, device_name):
    if device_name:
        print("The 'object-name' argument has been deprecated."
              + " Use the 'object' argument instead.")
        device = device_name
    if device:
        objects = [ device ]
    else:
        objects = SIM_object_iterator(None)
    objects = [ x for x in objects if hasattr(x, 'access_count') ]

    data = []
    header = ['Count', 'Device', 'Space', 'Range', None]

    max_range = 0
    if objects:
        any_port = False
        any_fn   = False
        onames  = dict((x.name, x) for x in objects)
        objects = dict((x, []) for x in objects)
        for mobj in sorted(o for o in SIM_object_iterator(None)
                           if (hasattr(o, 'map')
                               and hasattr(o.iface, 'map_demap'))):
            seen_targets = set()
            for line in mobj.map:
                mtarget = onames.get(mapping_dev_name(line))
                if mtarget is None:
                    continue
                rlo = line[0]
                rhi = line[0] + line[4] - 1
                max_range = max(max_range, rlo, rhi)
                lines = objects[mtarget]
                if lines:
                    count = target_name = ''
                else:
                    count       = mtarget.access_count
                    target_name = mtarget.name
                if mtarget in seen_targets:
                    mname = ''
                else:
                    seen_targets.add(mtarget)
                    mname = mobj.name
                any_port = any_port or is_port_mapping(line)
                any_fn   = any_fn or not is_port_mapping(line)
                lines.append([
                        count,
                        target_name,
                        mname,
                        [rlo, rhi],
                        mapping_dev_port_or_func(line) ])

        i = (1 if any_fn else 0) | (2 if any_port else 0)
        fnprt = ( 'Fn', 'Fn', 'Port', 'Fn/Port' )[i]
        assert header[4] is None
        header[4] = fnprt

        for obj in sorted(objects):
            data.extend(objects[obj])

    if not data:
        print("No mappings found")
        return

    precision = len('%x' % max_range)
    for d in data:
        if isinstance(d[3], str):
            continue
        d[3] = '%s - %s' % (
            number_str(d[3][0], radix = 16, precision = precision),
            number_str(d[3][1], radix = 16, precision = precision))

    props = [(Table_Key_Columns,
              [[(Column_Key_Name, h),
                (Column_Key_Int_Radix, 10)] for h in header])]
    tbl = table.Table(props, data)
    msg = tbl.to_string(rows_printed=0, no_row_column=True)
    return command_verbose_return(msg, data)

new_command("devs", devs_cmd,
            args  = [arg(obj_t("device"), "object", "?", None),
                     arg(obj_t("device"), "object-name", "?", None)],
            type  = ["Configuration", "Inspection"],
            short = "list all mapped devices in Simics",
            doc = """
Print a list of all mapped devices in Simics, with information about how many
times each device has been accessed, and where they are mapped. The
<arg>object</arg> argument can be used to show information for a single
device only.

The <arg>object-name</arg> argument has been deprecated in favor of
<arg>object</arg>.

The mappings are presented as start and end offsets within a named
memory space.

The function number or port name associated with each different
mapping for a device is also printed.
""")


#
# ----------------------- print-device-access-stats -----------------------
#
class IO_stat_cmds:
    def __init__(self):
        # Cache how many steps the processors have executed
        # and old access_count for the devices.
        # Populated by the io-stats-clear command.
        self.init_cpu_steps = {}
        self.init_cpu_esteps = {}
        self.init_dev_accesses = {}
        self.register_commands()

    def cpu_steps(self, cpu):
        '''Steps a processor has executed'''
        if hasattr(cpu.iface, "step"):
            return cpu.iface.step.get_step_count()
        else:
            return 0

    def cpu_esteps(self, cpu):
        '''Steps a processor has executed, discarding halt and ffwd steps'''
        steps = self.cpu_steps(cpu)
        if hasattr(cpu.iface, "step_info"):
            return (steps - cpu.iface.step_info.get_ffwd_steps() -
                    cpu.iface.step_info.get_halt_steps())
        else:
            return steps

    def current_cpu_steps(self, cpu):
        return self.cpu_steps(cpu) - self.init_cpu_steps.get(cpu, 0)

    def current_cpu_esteps(self, cpu):
        return self.cpu_esteps(cpu) - self.init_cpu_esteps.get(cpu, 0)

    def current_dev_io(self, dev):
        return dev.access_count - self.init_dev_accesses.get(dev, 0)

    def io_stats_cmd(self, cutoff, cell_arg):

        def get_stats(devs, cpus):
            '''Return tuple: (total io operation, total steps, total estep).'''
            return (
                sum([self.current_dev_io(x) for x in devs]),
                sum([self.current_cpu_steps(p) for p in cpus]),
                sum([self.current_cpu_esteps(p) for p in cpus]),
                )

        def print_stats(title, devs, cpus):
            (io_sum, step_sum, estep_sum) = get_stats(devs, cpus)

            print("%s: %s" % (title +  " io-accesses   ",
                              number_str(io_sum, radix=10)))
            if not io_sum:
                return

            print("%s: %s (in average an io access each %s)" % (
                title + " steps         ", number_str(step_sum, radix=10),
                number_str(step_sum // io_sum, radix=10)))
            print("%s: %s (in average an io access each %s)" % (
                title + " non-idle steps", number_str(estep_sum, radix=10),
                number_str(estep_sum // io_sum, radix=10)))

            print()
            print("Most frequently accessed device classes (%s):" % (title,))
            print()
            c = {}
            for x in devs:
                cls = x.classname
                c.setdefault(cls, 0)
                c[cls] += self.current_dev_io(x)
            l = [(c[x], x) for x in c]
            l.sort(reverse=True)
            print_table(["Accesses", "Class", "Percent"],
                        [[number_str(acc_cnt, radix=10), cls_name,
                          "%4.1f%%" % (acc_cnt * 100.0 / io_sum)]
                         for (acc_cnt, cls_name) in l if (
                                 acc_cnt > 0 and
                                 acc_cnt * 100.0 / io_sum >= cutoff)],
                        ["right", "left", "right"])
            print()
            print("Most frequently accessed device objects (%s):" % (title,))
            print()
            l = [(self.current_dev_io(x), x) for x in devs]
            l.sort(reverse=True)
            print_table(["Accesses", "Object", "Class", "Percent"],
                        [[number_str(acc_cnt, radix=10), dev.name,
                          dev.classname, "%4.1f%%" % (acc_cnt *
                                                      100.0 / io_sum)]
                         for (acc_cnt, dev) in l if (
                                 acc_cnt > 0 and
                                 acc_cnt * 100.0 / io_sum >= cutoff)],
                        ["right", "left", "left", "right"])

        def filter_on_cell(cell, objects):
            return [obj for obj in objects
                    if simics.VT_object_cell(obj) == cell]

        devs = [ x for x in SIM_object_iterator(None)
                 if hasattr(x, 'access_count') ]
        cpus = simics.SIM_get_all_processors()

        if not cell_arg:
            print_stats("Total", devs, cpus)

            machine_list = list(simics.SIM_object_iterator_for_class("cell"))
            if len(machine_list) > 1:
                cell_stats = []
                for cell in machine_list:
                    cell_devs = filter_on_cell(cell, devs)
                    cell_cpus = filter_on_cell(cell, cpus)
                    cell_stats.append((cell, get_stats(cell_devs, cell_cpus)))

                def cell_stat_sort_key(data):
                    (cell, (io_sum, step_sum, estep_sum)) = data
                    return estep_sum/io_sum if io_sum != 0 else float("inf")
                cell_stats.sort(key=cell_stat_sort_key)

                print()
                print(("Data for cells (ascending sort by non-idle steps per"
                       + " io access):"))
                print()

                print_table(
                    ["Cell", "Non-idle steps per io", "Total io operations",
                     "Total steps", "Total non-idle steps"],
                    [[cell.name, number_str(estep_sum // io_sum, radix=10)
                      if io_sum != 0 else "inf",
                      number_str(io_sum, radix=10),
                      number_str(step_sum, radix=10),
                      number_str(estep_sum, radix=10)]
                      for (cell, (io_sum, step_sum, estep_sum)) in cell_stats],
                    ["left", "right", "right", "right", "right"])

        else:
            print_stats(
                "Cell '%s'" % (cell_arg.name,),
                filter_on_cell(cell_arg, devs),
                filter_on_cell(cell_arg, cpus))

    def clear_io_stats_cmd(self, cell_arg):
        devs = [o for o in SIM_object_iterator(None)
                if hasattr(o, 'access_count')]
        cpus = simics.SIM_get_all_processors()
        if cell_arg:
            devs = [dev for dev in devs
                    if simics.VT_object_cell(dev) == cell_arg]
            cpus = [cpu for cpu in cpus
                    if simics.VT_object_cell(cpu) == cell_arg]
        for dev in devs:
            self.init_dev_accesses[dev] = dev.access_count
        for cpu in cpus:
            self.init_cpu_steps[cpu] = self.cpu_steps(cpu)
            self.init_cpu_esteps[cpu] = self.cpu_esteps(cpu)

    def register_commands(self):
        new_command("print-device-access-stats", self.io_stats_cmd,
                    alias = "io-stats",
                    args = [arg(float_t, "cutoff", "?", 1.0),
                            arg(obj_t('cell object', 'cell'), "cell", "?")],
                    type = ["Performance"],
                    see_also = ["devs", "clear-io-stats"],
                    short = "list most frequently accessed devices",
                    doc = """
        Gives an overview of how many device accesses have happened
        during the simulation and provides top lists for the most
        frequently accessed device classes and objects. The <arg>cell</arg>
        argument can be used to analyze only the devices belonging to the
        particular cell. The <arg>cutoff</arg> argument's default
        is 1.0%, which means that classes or objects with lower than
        1.0% of the total number of I/O accesses will be discarded.""")

        new_command("clear-io-stats", self.clear_io_stats_cmd,
                    args = [arg(obj_t('cell object', 'cell'), "cell", "?"),],
                    type = ["Performance"],
                    alias = "clear-device-access-stats",
                    see_also = ["print-device-access-stats"],
                    short = "clear the device access stats",
                    doc = """
        Reset all counts reported by <cmd>print-device-access-stats</cmd>. The
        <arg>cell</arg> argument can be used to restrict flushing only to the
        devices belonging to the particular cell.""")


def format_log_line(initiator, address, read, value, size, be):
    if be == None:
        value_str = "<unknown>"
    else:
        value_str = "%s (%s)" % (number_str(value, 16), "BE" if be else "LE")

    return "%s from %s: PA %s SZ %d %s" % ("Read" if read else "Write",
                                           initiator and initiator.name,
                                           number_str(address, 16),
                                           size, value_str)

IO_stat_cmds()

def get_size_with_bi_prefix(size):
    """Returns a tuple with a value (float) and a unit-prefix. The value is 'size'
    divided by 1024 down to a suitable unit-prefix. """
    prefixes = ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi', 'Yi']
    order = 0
    while size >= 1024 << (order * 10) and order < len(prefixes):
        order += 1
    return (size / (1 << (order * 10)), prefixes[order])

def abbrev_size(size):
    """Returns a human-readable string describing 'size' in bytes with the most
    fitting prefix and at most two decimals."""
    size, prefix = get_size_with_bi_prefix(size)
    # always allow up to two decimals
    if size:
        extra_digits = int(math.log(size, 10))
    else:
        extra_digits = 0
    fmt = "%%.%dg" % (3 + extra_digits)
    return fmt % size + " %sB" % prefix

def get_value_with_dec_prefix(val):
    """Returns a tuple with a value (float) and a unit-prefix. The value is 'size'
    adjusted by 1000 to a suitable unit-prefix. """
    if abs(val) < 1.0:
        e = 1000.0
        for p in ["m", "µ", "n", "p", "f", "a", "z", "y"]:
            if abs(val) >= 1.0/e:
                return (val * e, p)
            e *= 1000.0
    else:
        e = 1.0
        for p in ["", "k", "M", "G", "T", "P", "E", "Z", "Y"]:
            if abs(val) < e*1000:
                return (val / e, p)
            e *= 1000
    return (val, "")

def abbrev_value(value, unit):
    """Returns a human-readable string describing 'value' in 'unit' with the most
    fitting prefix and at most two decimals."""
    val, prefix = get_value_with_dec_prefix(value)
    # always allow up to two decimals
    if val:
        extra_digits = int(math.log(val, 10))
    else:
        extra_digits = 0
    fmt = "%%.%dg" % (3 + extra_digits)
    return fmt % val + " %s%s" % (prefix, unit)

class _test_abbrev(unittest.TestCase):
    def test_abbrev_size(self):
        self.assertEqual(abbrev_size(7 * 1024 * 1024), '7 MiB')
        self.assertEqual(abbrev_size(3.3333333 * 10**6), '3.18 MiB')
        self.assertEqual(abbrev_size(0), "0 B")
    def test_abbrev_value(self):
        self.assertEqual(abbrev_value(2 * 10**6, "Hz"), '2 MHz')
        self.assertEqual(abbrev_value(3.3333333 * 10**6, "Hz"), '3.33 MHz')

#
# -------------------- print-image-memory-stats -------------
#

def img_memory_stats_cmd(imgs, show_all, human_readable):
    if not isinstance(imgs, list):
        imgs = [imgs]

    def stat_sort_key(data):
        (name, _) = data
        return name

    def make_human_readable(value):
        if value == 0:
            return 0
        if human_readable:
            val, prefix = get_size_with_bi_prefix(value * 0x2000)
            return "{0:.2f} {1}B".format(val, prefix)
        else:
            return value

    # Object-specific command should always display something
    if len(imgs) == 1:
        show_all = True

    # Extract statistics data
    stats = sorted(([im, im.stats] for im in imgs
                    if (show_all or im.stats[0])), key=stat_sort_key)
    if not stats:
        return command_return(" ", [])
    if len(stats) > 1:
        statcols = zip(*([s for (_, s) in stats] + [[0] * 5]))
        stats.append(['total', [sum(col) for col in statcols]])

    # Create table
    header = ['Image', 'Pages', 'In memory', 'Swap slot', 'Dirty', 'Uaread']
    properties = [(Table_Key_Columns,
                   [[(Column_Key_Name, h),
                     (Column_Key_Int_Radix, 10),
                     (Column_Key_Alignment, "right")]
                    for i, h in enumerate(header)])]
    properties[0][1][0].pop()  ##  remove alignment for Image column
    tbl_data = [[name] + [make_human_readable(x) for x in s]
                for (name, s) in stats]
    tbl = table.Table(properties, tbl_data)
    (nswaps, swap_time, swap_bytes) = conf.classes.image.swap_stats

    # Construct message
    output = [tbl.to_string(no_row_column=True, rows_printed=0),
              f"Number of swapouts: {nswaps}"]
    if nswaps:
        output += [("Time spent swapping:"
                    f" {swap_time * 1e-3:10.3f} s"
                    f" ({swap_time / nswaps:.1f} ms each time)"),
                   (f"Bytes written: {abbrev_size(swap_bytes)}"
                    f" ({abbrev_size(swap_bytes // nswaps)} each time)")]
    ret = [[name] + list(s) for (name, s) in stats]
    return command_verbose_return(message="\n".join(output), value=ret)

def global_img_memory_stats_cmd(obj, show_all, human_readable):
    if not obj:
        objs = list(simics.SIM_object_iterator_for_class('image'))
    else:
        objs = [obj]
    return img_memory_stats_cmd(objs, show_all, human_readable)

new_command("print-image-memory-stats", global_img_memory_stats_cmd,
            args = [arg(obj_t("object", "image"), "image", "?", None),
                    arg(flag_t, "-all"),
                    arg(flag_t, "-h")],
            short = "image memory usage statistics",
            type = ["Memory"],
            see_also = ["system-info", "<image>.print-image-memory-stats"],
            doc = """
Print statistics for memory usage of image objects, or for a single
image, in the case of <cmd
class="image">print-image-memory-stats</cmd>, or by using
<arg>image</arg>. Images without resident pages are omitted, unless
<tt>-all</tt> is specified, or if there is a single image only.

By default, the unit is 8 KiB storage pages. By specifying the
<tt>-h</tt> flag you get output in human readable units.

The <i>Pages</i> column shows the number of allocated pages, that can
be either in memory or swapped out. The <i>In memory</i> column shows
the number of pages that are resident in memory. The <i>Swap slot</i>
column shows how many pages have, at some point, been swapped out. The
number of swapped out pages can be derived from this info as
<i>Pages</i> - <i>In memory</i>. <i>Dirty</i> is the number of pages
that are modified in relation to the on-disk persistent (non-swap)
image data.

<i>Uaread</i> is the number of read operations from a page that is
not already cached in memory.

Additional statistics about swapping is also printed.

If the command is used in an expression, the statistics table is
returned as a list of lists.
""")

new_command("print-image-memory-stats", img_memory_stats_cmd,
            args = [arg(flag_t, "-all"),
                    arg(flag_t, "-h")],
            short = "image memory usage statistics",
            type = ["Memory"],
            see_also = ["print-image-memory-stats"],
            iface = 'image',
            doc_with = 'print-image-memory-stats')

#
# ram commands
#

def get_ram_info(obj):
    # We should use the ram.size method for this, but the rom interface
    # isn't Python wrapped yet (should it be?)
    size = obj.mapped_size
    return [ (None,
              [ ("Image", obj.image),
                ("Image size", abbrev_size(size))])]

new_info_command('ram', get_ram_info)
new_info_command('rom', get_ram_info)
new_info_command('persistent-ram', get_ram_info)
new_status_command('ram', lambda obj: None)
new_status_command('rom', lambda obj: None)
new_status_command('persistent-ram', lambda obj: None)

#
# image commands
#

def get_image_info(obj):
    return [
        (None,
         [("Image size", abbrev_size(obj.size)),
          ("Is data persistent",
           "Yes" if obj.iface.checkpoint.has_persistent_data() else "No"),
          ("Files", [f"{x[0]} ({'read-only' if x[1] == 'ro' else 'read-write'})"
                     for x in obj.files])
         ])
    ]
new_info_command('image', get_image_info, doc = (
    "Print information about the image object. This information includes:"
    " logical size of the image in bytes;"
    " information whether the image contains persistent data (i.e. if"
    " the image data is saved by the <cmd>save-persistent-state</cmd> command);"
    " information about the files that represent image contents and whether"
    " these files are opened in the read-only or read-write mode."))

def get_image_status(obj):
    return [ (None,
              [ ("Dirty pages", "Yes" if obj.dirty else "No")])]
new_status_command('image', get_image_status)

#
# sim commands
#

def binary_amount(n):
    suffixes = "Byte kB MB GB TB".split()
    if n <= 0:
        index = 0
    else:
        index = min(int(math.log(n, 1024)), len(suffixes) - 1)
    return "%.4g %s" % (n / float(1 << (index * 10)), suffixes[index])

def get_memory_limit_data():
    lim = conf.classes.image.memory_limit
    if lim:
        lim_str = "limited to " + binary_amount(lim)
    else:
        lim_str = "not limited"
    (nswaps, swap_time, swap_bytes) = conf.classes.image.swap_stats
    hits_str = "%d time%s" % (nswaps, "s" if nswaps != 1 else "")
    return (lim_str, conf.prefs.swap_dir, hits_str)

def get_sim_info(obj):
    (system, node, _, version, machine, _) = platform.uname()
    hv_info = simics.CORE_host_hypervisor_info()
    return [("Host",
             [ ("Hostname", node),
               ("IPv4 address", obj.host_ipv4),
               ("IPv6 address", obj.host_ipv6),
               ("Number of CPUs", obj.host_num_cpus),
               ("OS", system),
               ("OS architecture", machine),
               ("OS release", simics_common.os_release()),
               ("OS version", version),
               ("Hypervisor",
                "no" if not hv_info.is_hv_detected else
                (hv_info.vendor or "an unknown hypervisor detected")),
               ("Physical memory", abbrev_size(obj.host_phys_mem)),
               ("Simics OS", obj.host_os),
               ("Simics architecture", obj.host_arch),
             ]),
            ("Environment",
             [ ("Python", platform.python_version()),
               ("Executable", sys.executable),
               ("Simics Build ID", obj.version),
               ("Simics Base", obj.simics_base),
               ("Simics Home", obj.simics_home),
               ("Simics Path", obj.simics_path),
               ("Fail on warnings", obj.stop_on_error),
               ("Module searchpath", obj.module_searchpath),
               ("Project", obj.project)])]

def cap_first(s):
    return s[:1].capitalize() + s[1:]

def get_sim_status(obj):
    enabled = ["Disabled", "Enabled"]
    (lim, swapdir, hits) = get_memory_limit_data()

    def get_num_sim_threads_used():
        num = conf.sim.attr.num_threads_used
        if num == 0:
            return "N/A until the simulation was started for the first time"
        return num

    def realtime_mode_status():
        is_running_realtime = any(
            rt.enabled
            for rt in simics.SIM_object_iterator_for_class('realtime'))
        return 'Enabled' if is_running_realtime else 'Disabled'

    def simulation_time_str():
        stime_s = VT_get_simulation_time() / 1000

        seconds = stime_s
        hrs = int(seconds // 3600)
        mins = int((seconds - (hrs * 3600)) // 60)
        seconds -= hrs * 3600 + mins * 60
        hstr = f"{hrs} h " if hrs else ""
        mstr = f"{mins} min " if mins else ""
        rv = "%s%s%.3f s" % (hstr, mstr, seconds)

        if hrs or mins:
            rv += f" (= {stime_s:.3f} s)"

        return rv

    return [
        ("Environment",
         [ ("Hide Console Windows",
            ["No", "Yes"][obj.hide_console_windows]) ] ),
        ("Multithreading",
         [ ("Multithreading enabled", enabled[obj.multithreading]),
           ("User thread number limit (see set-thread-limit command)",
            conf.sim.max_threads if conf.sim.max_threads else "Unlimited"),
           ("Worker threads limit", conf.sim.actual_worker_threads),
           ("Number of simulation threads used", get_num_sim_threads_used()),
           ("Maximum number of simulation threads for the simulated system",
            simics.CORE_num_execution_threads()),
         ]),
        ("Simulation Engine",
         [ ("Global VMP status",
            "Enabled" if vmp_loaded() else "Not Loaded"),
           ("Global JIT default", enabled[obj.enable_jit]),
           ("Page Sharing", enabled[obj.page_sharing]),
           ("Image memory usage", cap_first(lim)),
           ("Image memory limit hit", hits),
           ("Swap directory", swapdir),
           ("Realtime mode", realtime_mode_status()),
           ("Total wall-clock time when the simulation was running",
            simulation_time_str()),
          ]),
        ("Internal",
         [ ("D-STC", enabled[obj.data_stc_enabled]),
           ("I-STC", enabled[obj.instruction_stc_enabled]) ] )
        ]


new_info_command('sim', get_sim_info)
new_status_command('sim', get_sim_status)

def restart_simics_cmd(filename, fast, stall, extra_args = []):
    try:
        ws = importlib.import_module("simmod.mini_winsome.check_wx")
    except ImportError:
        pass
    else:
        ws.prepare_for_shutdown()
    argv = ['--no-copyright']
    # extra_args is used from win_utils.py
    argv += extra_args
    if conf.sim.project:
        argv += ['--project', conf.sim.project]
    if conf.sim.package_list:
        argv += ['--package-list', conf.sim.package_list]
    if conf.sim.stop_on_error:
        argv += ['--werror']
    if conf.sim.batch_mode:
        argv += ['--batch-mode']
    if simics.SIM_get_quiet():
        argv.append('--quiet')
    if simics.SIM_get_verbose():
        argv.append('--verbose')
    if conf.sim.hide_console_windows:
        argv.append('--no-win')
    if fast:
        DEPRECATED(6000, "The -fast flag is no longer available", "")
    if stall:
        DEPRECATED(6000, "The -stall flag is no longer available", "")
    if filename:
        argv.append(filename)
    simics.CORE_restart_simics(argv)

new_command("restart-simics", restart_simics_cmd,
            [arg(filename_t(dirs=True),"file", "?", ""),
             arg(flag_t, "-fast"),
             arg(flag_t, "-stall")],
            type = ["CLI"],
            short = "restart the current simics session",
            legacy=True,
            legacy_version=simics.SIM_VERSION_7,
            doc = """
Exits the current Simics session and starts a new empty one. The optional
<arg>file</arg> argument can be the name of a Simics script or checkpoint file
to open after restarting.
The <tt>-fast</tt> and <tt>-stall</tt> flags are deprecated.
""")

def object_lock_stats_cmd(flag):
    if not simics.CORE_object_lock_stats_enabled():
        print("Object lock statistics not collected"
              " (use 'enable-object-lock-stats' command to enable)")
        return

    # Set limit to one of (None, "-u", "-f", "-s")
    limit = None if not flag else flag[2]
    class Entry:
        def __init__(self, location, func, kind):
            self.func = func
            self.location = location
            self.kind = kind
            self.count = 0
            self.tot = 0
    d = {}
    for o in SIM_object_iterator(None):
        olist = simics.CORE_get_object_lock_stats(o) or []
        for (func, s, kind, count1, tot1, count10, tot10, count, tot) in olist:
            el = d.setdefault(s, Entry(s, func, kind))
            if limit == "-s":
                el.count += count
                el.tot += tot
            elif limit == "-f":
                el.count += count10
                el.tot += tot10
            elif limit == "-u":
                el.count += count1
                el.tot += tot1
            else:
                el.count += count10 + count
                el.tot += tot10 + tot

    def location(loc):
        if loc.count("/") > 3:
            loc = "/".join(loc.rsplit("/", 3)[1:])
        return loc

    entries = sorted(d.values(), key = lambda x:x.tot, reverse = True)
    data = [[el.count, el.tot/el.count, el.kind, el.func,
             location(el.location)] for el in entries if el.count]
    if data:
        header = ["Count", "Avg(us)", "", "Function", "File"]
        props  = [(Table_Key_Columns,
                   [[(Column_Key_Name, h),
                     (Column_Key_Int_Radix, 10),
                     (Column_Key_Int_Grouping, False)] for h in header])]
        tbl = table.Table(props, data)
        out = tbl.to_string(rows_printed=0, no_row_column=True)
    else:
        out = ""
    return command_verbose_return(message=out, value=data)

new_command('print-object-lock-stats', object_lock_stats_cmd,
            args = [arg((flag_t, flag_t, flag_t), ("-u", "-f", '-s'), "?")],
            type = ["Execution", "Performance"],
            short = "print object lock statistics",
            see_also = ["enable-object-lock-stats",
                        "disable-object-lock-stats", "clear-object-lock-stats"],
            doc = """
Print a report based on collected object lock statistics. The report
contains information about the number of times a lock has been
taken and the average wait time for the lock to become available.
The third column displays what kind of lock was taken where 'C' means cell,
'S' means serial domain, otherwise it means an object lock.

Uncontended locks are excluded from the statistics unless
the <tt>-u</tt> flag is used, in which case the report is based solely
on uncontended lock acquisition.

The <tt>-f</tt> and <tt>-s</tt> flags can be used to only include
statistics from "fast" or "slow" locks, respectively. A lock acquiry is
considered "fast" if the wait time is less than 10 us.
""")

def clear_object_lock_stats_cmd():
    simics.CORE_clear_object_lock_stats()

new_command('clear-object-lock-stats', clear_object_lock_stats_cmd,
            args = [], type = ["Execution", "Performance"],
            short = "clear object lock statistics",
            see_also = ["enable-object-lock-stats",
                        "disable-object-lock-stats", "print-object-lock-stats"],
            doc = """
Clear collected object lock statistics.
""")

class ObjectLockStats:
    def what(self):
        return "Object lock statistics"
    def is_enabled(self):
        return simics.CORE_object_lock_stats_enabled()
    def set_enabled(self, enabled):
        if enabled:
            simics.CORE_enable_object_lock_stats()
        else:
            simics.CORE_disable_object_lock_stats()

new_command('enable-object-lock-stats', cli.enable_cmd(ObjectLockStats),
            args = [],
            type = ["Execution", "Performance"],
            short = "enable object lock statistics collection",
            see_also = ["clear-object-lock-stats",
                        "disable-object-lock-stats", "print-object-lock-stats"],
            doc = """
Enable object lock statistics collection.
""")
new_command('disable-object-lock-stats', cli.disable_cmd(ObjectLockStats),
            args = [],
            type = ["Execution", "Performance"],
            short = "disable object lock statistics collection",
            see_also = ["enable-object-lock-stats",
                        "clear-object-lock-stats", "print-object-lock-stats"],
            doc = """
Disable object lock statistics collection.
""")

def print_header(label, level):
    if level > 1:
        print()
    else:
        print("*"*79)
    print("*"*79)
    label_len = len(label)
    print("*", end=' ')
    leading_space_len = (77 - label_len) // 2
    trailing_space_len = 77 - label_len - leading_space_len
    print(" "*(leading_space_len - 2), end=' ')
    print(label, end=' ')
    print(" "*(trailing_space_len - 2), end=' ')
    print("*")
    print("*"*79)
    if level == 1:
        print("*"*79)

def system_info_cmd_helper():
    print_header("Simics system information", level=1)

    print_header("Version and Build information", level=2)
    # Get version info
    cli.run_command("version -v")

    print_header("Sim object information", level=2)
    # Get basic information about the system
    cli.run_command("sim.info")

    # Get more detailed information about the system
    # Platform specific
    if conf.sim.host_os == "linux":
        print_header("CPU Information from /proc/cpuinfo", level=2)
        try:
            cpuinfo = open('/proc/cpuinfo', 'r')
            for line in cpuinfo:
                sys.stdout.write('    ')
                sys.stdout.write(line)
            cpuinfo.close()
        except IOError as ex:
            print('    I/O error: %s' % ex)
    elif conf.sim.host_os == "windows":
        print_header("CPU Information from WMI", level=2)
        try:
            import subprocess
            p = subprocess.Popen(
                ["powershell.exe", "-NoProfile",
                 "Get-WMIObject Win32_Processor"],
                creationflags=0x08000000, stdout=subprocess.PIPE)
            resp, _ = p.communicate()
            sys.stdout.write(resp.decode("utf-8").strip())
        except Exception as ex:
            print("    Error finding CPU information: %s" % ex)

    print_header("Module information", level=2)
    # Build IDs for all modules
    cli.run_command("list-modules")

    print_header("Failed module information", level=2)
    cli.run_command("list-failed-modules")

    print_header("Simulator settings", level=2)
    # High level settings
    cli.run_command("sim.status")
    print()

    print_header("Sync domain settings", level=2)
    # Sync domain hierarchy and latency settings
    for o in SIM_object_iterator(None):
        if o.classname == "sync_domain":
            cli.run_command("%s.info" % o.name)

    print_header("Cell information", level=2)
    # Cells, their processors, and time quanta
    for o in SIM_object_iterator(None):
        if o.classname == "cell":
            cli.run_command("%s.info" % o.name)

    print_header("Link information", level=2)
    # "New" links
    for o in SIM_object_iterator(None):
        if hasattr(o.iface, "link"):
            if cli.get_obj_func(o, 'get_info'):
                cli.run_command("%s.info" % o.name)
            if cli.get_obj_func(o, 'get_status'):
                cli.run_command("%s.status" % o.name)

    print_header("Processors and related objects", level=2)
    # Print info about certain objects
    cpu_list = []
    space_list = []
    for o in SIM_object_iterator(None):
        is_exec = hasattr(o.iface, "execute")
        is_cycle = hasattr(o.iface, "cycle")
        is_step_cycle_ratio = hasattr(o.iface, "step_cycle_ratio")
        is_processor_info = hasattr(o.iface, "processor_info")
        if is_exec or is_cycle or is_step_cycle_ratio or is_processor_info:
            if is_cycle:
                freq = "%.1f MHz" % (o.iface.cycle.get_frequency() / 1e6)
            else:
                freq = "n/a"
            if is_step_cycle_ratio:
                ratio = o.iface.step_cycle_ratio.get_ratio()
                cpi = "%.2f" % (ratio.cycles / ratio.steps)
            else:
                cpi = "n/a"
            if is_processor_info:
                if o.iface.processor_info.architecture:
                    arch = o.iface.processor_info.architecture()
                else:
                    arch = "n/a"
                va_bits = str(o.iface.processor_info
                              .get_logical_address_width())
                pa_bits = str(o.iface.processor_info
                              .get_physical_address_width())
            else:
                arch = "n/a"
                va_bits = "n/a"
                pa_bits = "n/a"
            special = ""
            if hasattr(o, "compat_magic") and o.compat_magic:
                special += "compat_magic"
            cpu_list.append([o.name, o.classname, freq, cpi, arch,
                             va_bits, pa_bits, special])

        if o.classname == "memory-space":
            def name_or_none(obj_or_none):
                if obj_or_none:
                    return obj_or_none.name
                else:
                    return "None"
            snoop_str = name_or_none(o.snoop_device)
            timing_str = name_or_none(o.timing_model)

            map = o.map
            align = None

            def alignment(addr):
                if addr == 0:
                    return 1 << 64
                mask = 1
                align = 1
                while (addr & mask) == 0:
                    mask = (mask << 1) | 1
                    align *= 2
                return align

            for (base, obj_or_obj_port, func, offset, length, target, prio,
                 align_size, byte_swap) in map:
                if isinstance(obj_or_obj_port, simics.conf_object_t):
                    if (hasattr(obj_or_obj_port.iface, "ram")
                        or hasattr(obj_or_obj_port.iface, "rom")):
                        start_align = alignment(base)
                        stop_align = alignment(base + length)
                        if not align or start_align < align:
                            align = start_align
                        if stop_align < align:
                            align = stop_align

            if align:
                align_str = binary_amount(align)
            else:
                align_str = "None"
            space_list.append([o.name, align_str, snoop_str, timing_str])

    print_table(["Object", "Class", "Frequency", "CPI", "Arch", "VA bits",
                 "PA bits", ""], cpu_list,
                ["left", "left", "left", "left",
                 "left", "left", "left", "left"])

    print_header("Memory space information", level=2)
    print_table(["Object", "Min memory alignment", "Snoop device",
                 "Timing model"], space_list,
                ["left", "left", "left", "left"])

def wrap_system_info_cmd_helper():
    try:
        system_info_cmd_helper()
    except Exception as ex:
        raise CliError(f"Failed getting system-info: {ex}")

def system_info_cmd(name):
    if name:
        try:
            outfile = open(name, "w", encoding="utf-8")
        except IOError as ex:
            raise CliError(f'Failed to open {name}: {ex}')
        with outfile:
            with cli_impl.push_stdout(
                    outfile, output_mode=cli.output_modes.unformatted_text):
                wrap_system_info_cmd_helper()
    else:
        wrap_system_info_cmd_helper()

new_command('system-info', system_info_cmd,
            args = [arg(filename_t(), "file", "?", None)],
            short = "system info",
            type = ["Help"],
            see_also = ["print-image-memory-stats"],
            doc = """
Show information about both the host system and the target
system. Includes information useful when analyzing correctness and
performance problems. Use <arg>file</arg> to write the information
to file.
""")

def command_history_cmd(max_lines, substr):
    import command_line
    try:
        id = cli.get_current_cmdline()
        lines = command_line.get_command_history(id, max_lines, substr)
        return command_return(value=lines, message='\n'.join(lines))
    except Exception as ex:
        raise CliError("Failed getting command-line history: %s" % ex)

new_command('command-history', command_history_cmd,
            args = [arg(int_t, "max-lines", "?", 100),
                    arg(str_t, "substr", "?", None)],
            short = "show CLI command history",
            type = ["CLI"],
            alias = 'history',
            doc = """
Prints the recent CLI command-line history. Up to <arg>max-lines</arg> lines
are displayed, default is 100.
Use <arg>substr</arg> to filter for matching commands.
""")

def leader_info_cmd(obj):
    return [(None,
             [("Port", obj.port),
              ("Agent", obj.agent),
              ("Clock", obj.clock),
              ])]

def leader_status_cmd(obj):
    return [(None,
             [("Connected", obj.connected)])]

new_info_command('leader', leader_info_cmd)
new_status_command('leader', leader_status_cmd)

def simulation_running_cmd():
    return simics.SIM_simics_is_running()

new_command("simulation-running", simulation_running_cmd,
            [],
            type  = ["CLI"],
            short = "check if simulation is running",
            see_also = ["run", "stop"],
            doc = """
Returns true if the simulation is currently running and false if it is stopped.
""")

def prefs_info_cmd(obj):
    return []

def prefs_status_cmd(obj):
    global_prefs = [("Global Preferences", [(p.name, str(p.val))
                                            for p in get_preferences()])]

    mod_prefs = list(("Module: " + mod, list((k,v) for k, v in list(prefs.items())))
                     for mod, prefs in list(obj.module_preferences.items()))

    return global_prefs + mod_prefs

new_info_command('preferences', prefs_info_cmd)
new_status_command('preferences', prefs_status_cmd)

def tech_previews_enabled():
    '''returns list of technology previews that are enabled'''
    return [f for (f, en, _) in cli_impl.tech_preview_info() if en]

def tech_previews_disabled():
    '''returns list of technology previews that are enabled'''
    return [f for (f, en, _) in cli_impl.tech_preview_info() if not en]

class TechPreview:
    def __init__(self, arg, verbose = False):
        if isinstance(arg, str):
            self.preview = arg
        else:
            self.preview = arg[1] if arg[0] == str_t else None
        if self.preview and not cli.tech_preview_exists(self.preview):
            raise CliError("No such Technology Preview: %s" % self.preview)
        self.verbose = verbose
    def what(self):
        return ("All Technology Previews" if self.preview is None
                else "Technology Preview '%s'" % self.preview)
    def is_enabled(self):
        if not self.preview:
            return bool(tech_previews_enabled())
        else:
            return cli.tech_preview_enabled(self.preview)
    def set_enabled(self, enable):
        if enable:
            cli.enable_tech_preview(self.preview, self.verbose)
            self.extra_msg = (
                "\nNote: Technology Previews are subject to change at any time"
                " and may not be included in future versions of Simics.")
        else:
            if self.preview:
                previews = [self.preview]
            else:
                previews = tech_previews_enabled()
            for preview in previews:
                cli.disable_tech_preview(preview)

def tech_preview_disabled_expander(prefix):
    return get_completions(prefix, tech_previews_disabled())

new_command("enable-tech-preview", enable_cmd(TechPreview),
            [arg(str_t, "preview", expander = tech_preview_disabled_expander),
             arg(flag_t, "-v")],
            type = ["CLI"],
            see_also = ["disable-tech-preview", "enable-unsupported-feature"],
            short = "enable tech preview for feature",
            doc = """
Enable the Technology Preview feature specified by <arg>preview</arg> and
exposes any related CLI commands. The name of the feature should have been
provided by the Simics team together with separate instructions for how to use
it. List all enabled commands using the <tt>-v</tt> flag.""")

def tech_preview_enabled_expander(prefix):
    return get_completions(prefix, tech_previews_enabled())

new_command("disable-tech-preview", disable_cmd(TechPreview),
            [arg((flag_t,str_t), ("-all", "preview"),
                 expander = (None, tech_preview_enabled_expander))],
            type = ["CLI"],
            see_also = ["enable-tech-preview", "enable-unsupported-feature"],
            short = "disable tech preview for feature",
            doc = """
Disable the Technology Preview feature specified by <arg>preview</arg> and
hide all related CLI commands. Or disable all with the <tt>-all</tt> flag.
""")


def list_tech_previews_cmd():
    cmd_list = []
    for (preview, enabled, cmd_set) in cli_impl.tech_preview_info():
        for cmd in cmd_set:
            cmd_list.append([preview, ["disabled", "enabled"][enabled], cmd])
    print_columns('lll', [['Preview', 'Enabled', 'Command']] + cmd_list)

new_unsupported_command("list-tech-previews", "internals",
                        list_tech_previews_cmd, [],
                        short = "list tech preview commands",
                        see_also = ["list-unsupported-features"],
                        doc = """List all tech preview commands.""")


def unsupported_features_enabled():
    '''returns list of unsupported features that are enabled'''
    return [f for (f, en, _) in cli_impl.unsupported_info() if en]

def unsupported_features_disabled():
    '''returns list of unsupported features that are disabled'''
    return [f for (f, en, _) in cli_impl.unsupported_info() if not en]

class Unsupported:
    def __init__(self, arg, verbose = False):
        if isinstance(arg, str):
            self.feature = arg
        else:
            self.feature = arg[1] if arg[0] == str_t else None
        if self.feature and not cli.unsupported_exists(self.feature):
            raise CliError("No such unsupported feature: %s" % self.feature)
        self.verbose = verbose
    def what(self):
        return ("All unsupported features" if self.feature is None
                else "Unsupported feature '%s'" % self.feature)
    def is_enabled(self):
        if not self.feature:
            return bool(unsupported_features_enabled())
        else:
            return cli.unsupported_enabled(self.feature)
    def set_enabled(self, enable):
        if enable:
            cli.enable_unsupported(self.feature, self.verbose)
            self.extra_msg = (
                "\nNote: Unsupported features are subject to change at any"
                " time and may not be included in future versions of"
                " Simics.")
        else:
            if self.feature:
                features = [self.feature]
            else:
                features = unsupported_features_enabled()
            for feature in features:
                cli.disable_unsupported(feature)

def unsupported_disabled_expander(prefix):
    return get_completions(prefix, unsupported_features_disabled())

new_command("enable-unsupported-feature", enable_cmd(Unsupported),
            [arg(str_t, "feature", expander = unsupported_disabled_expander),
             arg(flag_t, "-v")],
            type = ["CLI"],
            see_also = ["disable-unsupported-feature",
                        "enable-tech-preview"],
            short = "enable unsupported feature",
            doc = """
Enable the specified unsupported <arg>feature</arg> and exposes any related
CLI commands. The name of the feature should have been provided by the Simics
team together with separate instructions for how to use it.

List all enabled commands using the <tt>-v</tt> flag.
""")

def unsupported_enabled_expander(prefix):
    return get_completions(prefix, unsupported_features_enabled())

new_command("disable-unsupported-feature", disable_cmd(Unsupported),
            [arg((flag_t,str_t), ("-all", "feature"),
                 expander = (None, unsupported_enabled_expander))],
            type = ["CLI"],
            see_also = ["enable-unsupported-feature", "enable-tech-preview"],
            short = "disable unsupported feature",
            doc = """
Disable the specified unsupported <arg>feature</arg> and hide all related CLI
commands. Or disable all with the <tt>-all</tt> flag.
""")

def list_unsupported_features_cmd():
    cmd_list = []
    for (feature, enabled, cmd_set) in cli_impl.unsupported_info():
        for cmd in cmd_set:
            cmd_list.append([feature, ["disabled", "enabled"][enabled], cmd])
    print_columns('lll', [['Feature', 'Enabled', 'Command']] + cmd_list)

new_unsupported_command("list-unsupported-features", "internals",
                        list_unsupported_features_cmd, [],
                        short = "list unsupported commands",
                        see_also = ["list-tech-previews"],
                        doc = """List all unsupported commands.""")

#
# -------------------- release-notes --------------------
#

def previous_installed_build_id(pkg_number):
    return simics_common.previous_installed_build_id(pkg_number)

def print_pkg_header(pkg_name, pkg_version):
    version_string = pkg_name +" - " + pkg_version
    print()
    print(version_string)
    print("-" * len(version_string))

def print_releasenotes(pkg_name, pkg_ver, filename, oldest_build_id):
    import pickle
    try:
        with open(filename, 'rb') as f:
            data = pickle.load(f)  # nosec: we process here trusted data
        if len(data) == 3:
            # old 6 packages provide a redundant indirection dict,
            # that maps category-id to category-name.
            (notes, pkg_versions, categories) = data
            # in rndata from old packages, &amp; will be resolved to
            # &, and we need well-formed XML. Make sure & is escaped.
            for cats in notes.values():
                for texts in cats.values():
                    for i in range(len(texts)):
                        texts[i] = texts[i].replace('&', '&amp;')
            def category_name(cat): return categories.get(cat, cat)
        else:
            (notes, pkg_versions) = data
            def category_name(cat): return cat
    except EOFError:
        notes = {}
    if not notes:
        print_pkg_header(pkg_name, pkg_ver)
        print("No release-notes available.")
        return
    prev_version = ""
    for x in sorted(list(notes.keys()),
                    # Consider "next" to a high build ID
                    key = lambda x: 10000000 if not isinstance(x, int) else x):
        # x can be a string, e.g. "next"
        if isinstance(x, int) and x < oldest_build_id:
            continue
        version = pkg_versions[x]
        # Groups releases notes from different build-ids together if released
        # in the same package version
        if version != prev_version:
            print_pkg_header(pkg_name, version)
            prev_version = version
        for cat in notes[x]:
            for note in notes[x][cat]:
                cli.format_print("* [" + category_name(cat) + "] " + note,
                                 indent = 2, first_indent = 0)
                print("\n")


def print_releasenotes_json(pkg_name, pkg_ver, filename, oldest_build_id):
    import json
    import structured_text
    try:
        with open(filename, 'rb') as f:
            data = json.load(f)
    except EOFError:
        data = {}
    text = []
    if not data:
        text.append({"tag": "h2", "children": [f"{pkg_name} - {pkg_ver}"]})
        text.append("No release-notes available.")
    prev_version = ""
    for x in data:
        # x can be a string, e.g. "next"
        build_id = x['build_id']
        if isinstance(build_id, int) and build_id < oldest_build_id:
            continue
        version = x['version']
        # Groups releases notes from different build-ids together if released
        # in the same package version
        if version != prev_version:
            text.append({"tag": "h2", "children": [f"{pkg_name} - {version}"]})
            prev_version = version
        for (cat, notes) in x['notes'].items():
            text.append({"tag": "h3", "children": [cat]})
            for note in notes:
                text.extend(note)
    structured_text.StructuredCLI(sys.stdout).format(text)


def find_rn_printer(pkg_path, pkg_id):
    host = conf.sim.host_type
    rn_json_file = os.path.join(pkg_path, host, 'doc', f'{pkg_id}.rn.json')
    if os.path.exists(rn_json_file):
        return lambda name, ver, oldest: print_releasenotes_json(
            name, ver, rn_json_file, oldest)
    pkg_id = pkg_id.lower()
    rn_file = os.path.join(pkg_path, host, 'doc', f'{pkg_id}.rndata')
    # old (<= 2020) location. Can safely be removed in simics 7.
    if not os.path.exists(rn_file):
        rn_file = os.path.join(pkg_path, 'packageinfo', f'{pkg_id}.rndata')
    if os.path.exists(rn_file):
        return lambda name, ver, oldest: print_releasenotes(
            name, ver, rn_file, oldest)


def release_notes_cmd(package, show_all, verbose):
    if package:
        pkgs = [x for x in conf.sim.package_info if x[1] == package]
        if not pkgs:
            raise CliError("No package %s installed" % package)
        single_package = True
    else:
        pkgs = conf.sim.package_info
        single_package = False
    no_output = True
    for (pkg_name, pkg_id, pkg_nbr, pkg_ver,
         _, _, _, _, _, pkg_path, *_) in pkgs:
        print_rn = find_rn_printer(pkg_path, pkg_id)
        if print_rn == None:
            if verbose or single_package:
                print_pkg_header(pkg_name, pkg_ver)
                no_output = False
                print("No release-notes available.")
            continue
        if show_all:
            oldest_build_id = 0
        else:
            oldest_build_id = previous_installed_build_id(pkg_nbr) + 1
            if oldest_build_id == 0:
                if verbose or single_package:
                    print_pkg_header(pkg_name, pkg_ver)
                    no_output = False
                    print("Initial install - not an update."
                               " Use -all flag to display all"
                               " the release notes.")
                continue
        no_output = False
        print_rn(pkg_name, pkg_ver, oldest_build_id)
    if no_output:
        print("No updated packages."
                   " Use -all flag to display all the release notes.")

new_command("release-notes", release_notes_cmd,
            [arg(str_t, "package",  "?", None, expander = package_expander),
             arg(flag_t, "-all"), arg(flag_t, "-v")],
            type = ["Help"],
            short = "display product release notes",
            see_also = ["version"],
            doc = """
List release notes for all product packages, or a single package selected with
the <arg>package</arg> argument, since the previous versions installed.
Nothing is displayed for packages without release note files or for packages
installed for the first time. The <tt>-all</tt> flag adds older release notes
to the output. The <tt>-v</tt> flag turns on verbose output where information
on packages without release note files is included.
""")


def transaction_type(t):
    types = ['read' if t.read else '',
             'write' if t.write else '',
             'fetch' if t.fetch else '',
             'inquiry' if t.inquiry else '']
    return '/'.join([_f for _f in types if _f])

def list_deferred_transactions_cmd(chains, show_only_waited):
    info_records = simics.CORE_get_deferred_transactions_info()

    if not info_records:
        return command_verbose_return(
            message="There are no deferred transactions in the system.",
            value=[])

    transaction_to_info = {r.t: r for r in info_records}

    def get_transaction_chain(r):
        '''Return list with records corresponding to r.t, r.t.prev,
           r.t.prev.prev etc.
           r is expected to be 'last', i.e. r.is_last is True.'''

        assert r.is_last, "Internal error"
        chain = [r]
        t = r.t.prev
        while t is not None:
            chain.append(transaction_to_info[t])
            t = t.prev
        return chain

    def add_legend(msg, notes):
        # Add (only if needed) a legend for the "Notes" column
        def is_symbol_present_in_notes(symbol):
            return any(symbol in note for note in notes)
        descriptions = {
            '*': 'Transaction is waited for with SIM_transaction_wait',
        }
        for (symbol, descr) in descriptions.items():
            if is_symbol_present_in_notes(symbol):
                msg += f"\n'{symbol}' - {descr}"
        return msg

    if show_only_waited:
        # Keep only transactions waited for with SIM_transaction_wait.
        # To do that it is enough to update info_records accordingly.
        info_records_filtered = []
        for r in info_records:
            if r.is_last:
                chain = get_transaction_chain(r)
                is_wait = any(r.is_wait for r in chain)
                if is_wait:
                    info_records_filtered.extend(chain)
        info_records = info_records_filtered

    if chains:
        chains_list = [reversed(get_transaction_chain(r))
                       for r in info_records if r.is_last]

        table_data = []
        for chain in chains_list:
            table_data.extend([
                [r.id,
                 getattr(r.t, "owner", None),
                 transaction_to_info[r.t.prev].id if r.t.prev else None,
                 r.state,
                 "*" if r.is_wait else ""]
                for r in chain])

        properties = [(Table_Key_Columns,
                       [
                           [(Column_Key_Name, "ID")],
                           [(Column_Key_Name, "Owner")],
                           [(Column_Key_Name, "Prev")],
                           [(Column_Key_Name, "State")],
                           [(Column_Key_Name, "Notes"),
                            (Column_Key_Hide_Homogeneous, "")],
                       ])
                      ]

        tbl = table.Table(properties, table_data)
        msg = tbl.to_string(rows_printed=0, no_row_column=True)
        msg = add_legend(msg, [row[4] for row in table_data])

        return command_verbose_return(
            message=msg,
            value=[e[:4] for e in table_data]  # we exclude Notes
        )
    else:
        def generate_notes(r):
            is_wait = any(r.is_wait for r in get_transaction_chain(r))
            return "*" if is_wait else ""

        # We pick last transactions from "transaction chains" here. Most likely
        # the atoms that we report below are the same for all transactions in a
        # transaction chain but picking the last transaction allows to show what
        # the endpoint sees. NB: Simics doesn't prohibit overriding of, for
        # example, the "initiator" atom.
        records_to_report = [r for r in info_records if r.is_last]

        table_data = []
        for r in records_to_report:
            t = r.t
            table_data.append([t.size, t.initiator if t.initiator else None,
                               t.flags, transaction_type(t), generate_notes(r)])

        properties = [(Table_Key_Columns,
                       [
                           [(Column_Key_Name, "Size")],
                           [(Column_Key_Name, "Initiator")],
                           [(Column_Key_Name, "Flags")],
                           [(Column_Key_Name, "Type")],
                           [(Column_Key_Name, "Notes"),
                            (Column_Key_Hide_Homogeneous, "")],
                       ])
                      ]
        tbl = table.Table(properties, table_data)
        msg = tbl.to_string(rows_printed=0, no_row_column=True)
        msg = add_legend(msg, [row[4] for row in table_data])

        return command_verbose_return(
            message=msg,
            value=[e[:4] for e in table_data]  # we exclude Notes
        )

new_command("list-transactions", list_deferred_transactions_cmd,
            [arg(flag_t, "-chains"), arg(flag_t, "-show-only-waited")],
            type = ["CLI"],
            short = "list deferred transactions",
            see_also = [],
            doc = """
Lists deferred transactions that are present in the simulated system. Deferred
transactions are described in Moder Builder User's Guide, section Transactions,
chapter Asynchronous Completion.

When the command is invoked without any flags, for each deferred transaction the
information about its size, initiator object, and flags as well as a
human-readable type of the transaction - such as "read" or "write" - are
reported.

When the command is invoked with the <tt>-chains</tt> flag, more detailed
information about deferred transactions is shown. The Transaction Chaining
section in Model Builder User's Guide explains that in order to append atoms to
an existing transaction two or more transactions can be chained together into a
linked list with the help of the <tt>prev</tt> field in the
<type>transaction_t</type> type. Passing the <tt>-chains</tt> flag makes the
command show information about all transactions that are linked to each deferred
transaction.

When the <tt>-show-only-waited</tt> flag is passed, the command
reports information only about deferred transactions whose completion
is waited for via the call to the <fun>SIM_transaction_wait</fun>
function.

Without any flags given, the return value is a list of lists of transaction
data, where each data list contains the transaction size, initiator (or NIL if
no initiator), the value of the transaction's flags and a human-readable type
string describing the type of the transaction.

If the <tt>-chains</tt> flag is given, the return value is a list of lists of
data for each transaction chain record, where each data list contains the ID,
the owner, ID of the previous record in the chain, and the state.
""")

def cmd_bits(action, value, first, last, is_size):
    if is_size:
        low = first
        num_bits = last
        if not num_bits:
            raise CliError("Number of bits must be greater than zero"
                           " when the -size flag is used.")
    else:
        low = min(first, last)
        # Allow specifying first/last in any order
        num_bits = abs(last - first) + 1

    assert num_bits > 0

    if action == "remove":
        low_mask = (1 << low) - 1
        high = low + num_bits
        high_mask = (1 << high) - 1
        return (value & low_mask) | ((value & ~high_mask) >> num_bits)
    else:
        mask = ((1 << num_bits) - 1) << low
        if action == "extract":
            return (value & mask) >> low
        elif action == "clear":
            return value & ~mask
        elif action == "set":
            return value | mask
        else:
            assert action == "keep"
            return value & mask

new_command("bits", cmd_bits,
            args=[arg(string_set_t(("extract", "clear",
                                    "set", "keep", "remove")),
                      "action", "?", "extract"),
                  arg(uint_t, "value"),
                  arg(uint_t, "first"),
                  arg(uint_t, "last"),
                  arg(flag_t, "-size")],
            type = ["CLI"],
            short="bit manipulation",
            doc="""
Perform bit manipulation on <arg>value</arg> and return the result.

The manipulation done depends on <arg>action</arg>. In all cases, a
bit range is specified using 0-based (little endian) bit numbers
<arg>first</arg> and <arg>last</arg>. If the <tt>-size</tt> flag is
given, <arg>last</arg> is instead interpreted as the number of bits in
the range.

<ul>
<li><em>extract</em> (default) - mask out and shift down the range.</li>

<li><em>keep</em> - mask out the range (like <em>extract</em> bit without shift).</li>

<li><em>clear</em> - set the range to 0.</li>

<li><em>set</em> - set the range to 1.</li>

<li><em>remove</em> - remove the range (and shift down the bits above it).</li>
</ul>

Some examples:
<ul>
<li>Extract bits 1 to 2<br/>
<tt>bits 0b11101 1 2</tt><br/>
The bit numbers can in fact be given in opposite order as well:<br/>
<tt>bits 0b11101 2 1</tt>
</li>

<li>Mask out bits 1 to 2<br/>
<tt>bits "keep" 0b11101 1 2</tt></li>

<li>Remove 2 bits from bit 2<br/>
<tt>bits "remove" 0b10111 2 2 -size</tt></li>

</ul>
""")

#
# -------------------- print-target-info --------------------
#

def print_target_info_cmd(only_print):
    messages = []
    value = []
    indent = "   "
    for info in target_info.TargetInfoExtractor().target_info():
        value.append(info[:2] + [[[x[0].lower(), x[1], x[2]] for x in info[2]]])
        msg = f"{info[0]}\n"
        tbl = table.Table([], [x[:2] for x in info[2]])
        msg += indent + tbl.to_string(
            rows_printed=0, no_row_column=True).replace("\n", "\n" + indent)
        messages.append(msg)
    message = "\n".join(messages)
    if only_print and message:
        print(message)
        return
    return command_verbose_return(message=message, value=value)

new_command(
    "print-target-info", lambda: print_target_info_cmd(True),
    short = "prints target information",
    type = ["Help"],
    see_also = ["list-target-info"],
    doc = """
    Prints a summary of the target machines of the configuration, similar to
    what is presented in the GUI.""")

new_command(
    "list-target-info", lambda: print_target_info_cmd(False),
    short = "lists target information",
    type = ["Help"],
    see_also = ["print-target-info"],
    doc = """
    Lists a summary of the target machines of the configuration, similar to
    what is presented in the GUI.""")

#
# -------------------- table-border-style -------------
#

def table_border_style(style):
    if not style:
        current_value = conf.prefs.cli_table_border_style
        return command_verbose_return(
            message=f"'{current_value}'",
            value=current_value)
    else:
        conf.prefs.cli_table_border_style = style

def add_table_border_style_cmd(name):
    args = [
        arg(string_set_t(table.border.border_styles), "style", "?")]
    styles = ", ".join(sorted(table.border.border_styles))
    new_command(
        name, table_border_style, args,
        short="set table border style",
        type = ["CLI"],
        alias = "table-border-style",
        doc = f"""Set or report the border style of tables.
        Without argument the current value is reported. Values for
        <arg>style</arg> can be any of {styles}.
        Run <cmd>save-preferences</cmd> to save any changes for the
        future.""")

add_table_border_style_cmd('set-table-border-style')

#
# -------------------- set-current-serial-console -------------
#

cli.add_tech_preview("console-switch")

def set_console_switch_cmd(arg):
    assert arg is None or (isinstance(arg, tuple) and len(arg) == 3
                           and arg[2] in {'console', '-clear'})

    def activate_msg(obj):
        return f'Press Control-g to switch to "{obj.name}".'

    curr_con = get_cur_con()
    if arg is not None and arg[1] is not None:
        if arg[2] == '-clear':
            set_cur_con(None)
            msg = "Unsetting console used for switch."
            ret = None
        else:
            obj = arg[1]
            assert obj is not None
            if obj == curr_con:
                msg = f"Console is unchanged '{curr_con.name}'."
                ret = obj
            else:
                ret = set_cur_con(obj)
                if ret is None:
                    raise CliError(
                        f'Object "{obj.name}" is not a serial console with'
                        ' enabled host-serial connection.')
                msg = (f'Console is now "{obj.name}".\n'
                       f'{activate_msg(obj)}')
                ret = get_cur_con()
    else:
        if curr_con is None:
            msg = "No console is set."
        else:
            msg = (f'Selected console is "{curr_con.name}".\n'
                   f'{activate_msg(curr_con)}')
        ret = curr_con
    return cli.command_return(message=msg, value=ret)

def serial_console_expander(name):
    return [o.name for o in simics.SIM_object_iterator_for_class("textcon")
            if o.name.startswith(name) and o.pty]

if not simicsutils.host.is_windows():
    new_command(
        "set-console-switch", set_console_switch_cmd,
        [arg((poly_t("serial console or NIL",
                     obj_t("serial console", cls="textcon"), nil_t), flag_t),
             ("console", "-clear"), "?", None,
             expander=(serial_console_expander, None))],
        short="set serial console to switch to",
        type=["CLI"],
        see_also=["<textcon>.host-serial-setup"],
        preview=con_preview_name,
        doc="""
        Set the serial console, that will be switched to using Ctrl+g, to the
        object <arg>console</arg>. By using <tt>-clear</tt>, the currently set
        serial console will be cleared, and console switching will be disabled.
        Without arguments, the currently selected console will be returned.""")
