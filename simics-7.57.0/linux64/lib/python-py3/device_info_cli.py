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

import glob
import DML
import cli
import device_info
import fnmatch
import re
import simics
from operator import itemgetter
from functools import reduce
import table

from io import StringIO

from simics import (
    Column_Key_Name,
    Table_Key_Columns,
)


def dev_banks(dev):
    return [b for b in dev.banks if b.nregs]

def split_device_bank_reg(dev_spec):
    # input is device, device.bank, device.function or device.bank.register
    # return (device-obj, bank.register) or None for unspecified parts
    items = dev_spec.split('.')
    for i in range(len(items), 0, -1):
        name = ".".join(items[:i])
        try:
            dev = cli.get_object(name)
        except simics.SimExc_General:
            continue
        if dev.classname != 'namespace':
            return (dev, '.'.join(items[i:]) or None)
    return (None, None)

def swap_endian(val, size):
    return int.from_bytes(val.to_bytes(length=size, byteorder='big'),
                          byteorder='little')

def generate_reg_info(obj, bank, reg, val, mapping_result):
    def regname_str(bank, reg):
        return (f'{bank.name}.' if bank.name else '') + reg.name

    def bitfields_info(fields, rval, nbits, be_bitorder, info):
        for f in fields:
            msb, lsb = f.msb, f.lsb
            bits = msb - lsb + 1
            if rval is None:
                val_str = '-' * bits
            else:
                val_str = cli.number_str((rval >> lsb) & ((1 << bits) - 1),
                                         2, precision=bits,
                                         use_prefix=False)
            if be_bitorder:
                msb = nbits - msb - 1
                lsb = nbits - lsb - 1
            desc = f'"{f.desc}"' if f.desc else ""
            info.append((f'{f.name} @ [{msb}:{lsb}]', ":",  val_str, desc))


    oft = reg.offset
    oftstr = 'N/A' if oft is None else oft
    valstr = 'N/A' if val is None else val

    data = [('Bits', ":", reg.size * 8, ""),
            ('Offset', ":", oftstr, ""),
            ('Value', ":", valstr, "")]

    (mappings, limit_reached) = mapping_result
    phys_addr = []
    if mappings or limit_reached:
        for i, mapping in enumerate(mappings):
            name = 'Physical Address' if i == 0 else ''
            addr, space, is_port = mapping
            phys_addr.append([addr, space])
            mappingstr = ""
            if is_port:
                mappingstr += '(I/O port)'
            if space:
                mappingstr += f"{' ' if mappingstr else ''}({space.name})"
            data.append([name, ":", cli.number_str(addr, 16), mappingstr])
        if limit_reached:
            data.append(('' if mappings else 'Physical Address', ':', '--', ''))
    ret_value = [oft or 0, reg.size * 8, val or 0, phys_addr]

    if reg.fields:
        data.append(["----------", "", "", ""])
        data.append(['Bit Fields', "", "", ""])
        bitfields_info(reg.fields, val, reg.size * 8, bank.be_bitorder, data)

    title = (f'\n{reg.desc or ""}{" " if reg.desc else ""}'
             + f'[{obj.name}.{regname_str(bank, reg)}]')

    props = [(table.Table_Key_Columns,
              [[(table.Column_Key_Name, n),
                (table.Column_Key_Alignment, a)] for n, a in
               (("", "right"), ("", "center"), ("", "left"), ("", "left"))])]
    tbl = table.Table(props, data)
    output = tbl.to_string(no_row_column=True, rows_printed=0, border_style="borderless")

    return cli.command_verbose_return(f"{title}\n\n{output}", ret_value)

def _get_io_iface_from_bank(obj, bank):
    # Intentionally propagate lookup error, gets caught later
    if bank.name:
        bobj = simics.SIM_object_descendant(obj, f'bank.{bank.name}')
        if bobj is not None:
            return (bobj, simics.SIM_get_interface(bobj, "io_memory"))
        else:
            return (obj, simics.SIM_get_port_interface(
                obj, "io_memory", bank.name))
    else:
        return (obj, simics.SIM_get_interface(obj, "io_memory"))

# Try reading from device using transaction interface and return the value.
# Raises SimExc_Memory if the access failed and SimExc_Lookup if the io_memory
# interface is missing.
def _read_io_memory(obj, bank, offset, size, be_byte_order, inquiry):
    (iface_obj, iface) = _get_io_iface_from_bank(obj, bank)
    # Perform the access via the io_memory interface
    mop = simics.generic_transaction_t()
    simics.SIM_set_mem_op_type(mop, simics.Sim_Trans_Load)
    simics.SIM_set_mem_op_inquiry(mop, inquiry)
    mapinfo = simics.map_info_t()
    if bank.function is not None:
        mapinfo.function = bank.function
    zeros = b'\0' * size

    simics.SIM_set_mem_op_physical_address(mop, offset)
    # Let caller handle possible SimExc_Memory
    return int.from_bytes(
        simics.VT_io_memory_operation(iface_obj, iface, mop, zeros, mapinfo),
        'big' if be_byte_order else 'little')

# Try writing to device using io-memory.
# Raises SimExc_Lookup if no port interface exist and SimExc_Memory if the
# access failed
def _write_io_memory(obj, bank, offset, data, size, be_byte_order, inquiry):
    (iface_obj, iface) = _get_io_iface_from_bank(obj, bank)
    # Perform the access via the io_memory interface
    mop = simics.generic_transaction_t()
    simics.SIM_set_mem_op_type(mop, simics.Sim_Trans_Store)
    simics.SIM_set_mem_op_physical_address(mop, offset)
    simics.SIM_set_mem_op_inquiry(mop, inquiry)
    mapinfo = simics.map_info_t()
    if bank.function is not None:
        mapinfo.function = bank.function

    # TODO: report error on overflow, SIMICS-22702
    data = data % (1 << (size * 8))
    val = data.to_bytes(size, 'big' if be_byte_order else 'little')

    # Let caller handle possible SimExc_Memory
    return simics.VT_io_memory_operation(iface_obj, iface, mop, val, mapinfo)

def _get_transaction_iface_from_bank(obj, bank):
    # Intentionally propagate lookup error, gets caught later
    if bank.name:
        bobj = simics.SIM_object_descendant(obj, f'bank.{bank.name}')
        if bobj is not None:
            return simics.SIM_get_interface(bobj, "transaction")
        else:
            return simics.SIM_get_port_interface(obj, "transaction", bank.name)
    else:
        return simics.SIM_get_interface(obj, "transaction")

# Try reading from device using transaction interface and return the value.
# Raises SimExc_Memory if the access failed and SimExc_Lookup if the interface
# is missing.
def _read_transaction(obj, bank, offset, size, be_byte_order, inquiry):
    iface = _get_transaction_iface_from_bank(obj, bank)

    # Perform the access via the transaction interface
    t = simics.transaction_t(inquiry = inquiry, read = True, size = size)
    ex = iface.issue(t, offset)
    if ex != simics.Sim_PE_No_Exception:
        raise simics.SimExc_Memory(simics.SIM_describe_pseudo_exception(ex))
    # use bank default if user hasn't requested explicit endian interpretation
    if be_byte_order:
        return t.value_be
    else:
        return t.value_le

# Try writing to device using transaction interface.
# Raises SimExc_Memory if the access failed and SimExc_Lookup if the interface
# is missing.
def _write_transaction(obj, bank, offset, data, size, be_byte_order, inquiry):
    iface = _get_transaction_iface_from_bank(obj, bank)

    # TODO: report error on overflow, SIMICS-22702
    data = data % (1 << (size * 8))
    val = data.to_bytes(size, 'big' if be_byte_order else 'little')

    # Perform the access via the transaction interface
    t = simics.transaction_t(write = True, size = size, inquiry = inquiry,
                             data = val)
    ex = iface.issue(t, offset)
    if ex != simics.Sim_PE_No_Exception:
        raise simics.SimExc_Memory(simics.SIM_describe_pseudo_exception(ex))
    # use bank default if user hasn't requested explicit endian interpretation
    if be_byte_order:
        return t.value_be
    else:
        return t.value_le

def _get_sc_register_access_iface_from_bank(obj, bank):
    # Intentionally propagate lookup error, gets caught later
    if bank.name:
        return simics.SIM_get_port_interface(obj, "sc_register_access",
                                             bank.name)
    else:
        return simics.SIM_get_interface(obj, "sc_register_access")

def _read_sc_register_access(obj, bank, offset, size, be_byte_order):
    iface = _get_sc_register_access_iface_from_bank(obj, bank)
    data_read = simics.buffer_t(size)
    ex = iface.read(offset, data_read)
    if ex != simics.Sim_PE_No_Exception:
        raise simics.SimExc_Memory(simics.SIM_describe_pseudo_exception(ex))

    return int.from_bytes(data_read, 'big' if be_byte_order else 'little')

def _write_sc_register_access(obj, bank, offset, data, size, be_byte_order):
    iface = _get_sc_register_access_iface_from_bank(obj, bank)

    # TODO: report error on overflow, SIMICS-22702
    data = data % (1 << (size * 8))
    val = data.to_bytes(size, 'big' if be_byte_order else 'little')

    ex = iface.write(offset, val)
    if ex != simics.Sim_PE_No_Exception:
        raise simics.SimExc_Memory(simics.SIM_describe_pseudo_exception(ex))

# Try reading from device using io-memory or transaction interface. Returns
# value on success or None if no usable interface was found.
# Raises SimExc_Memory if the access failed.
def read_memory(obj, bank, offset, size, be_byte_order, inquiry):
    try:
        return _read_transaction(obj, bank,
                                 offset, size, be_byte_order, inquiry)
    except simics.SimExc_Lookup:
        try:
            return _read_io_memory(obj, bank, offset, size, be_byte_order, inquiry)
        except simics.SimExc_Lookup:
            return _read_sc_register_access(obj, bank, offset, size, be_byte_order)

def write_memory(obj, bank, offset, data, size, be_byte_order, inquiry):
    try:
        _write_transaction(obj, bank, offset, data, size, be_byte_order, inquiry)
    except simics.SimExc_Lookup:
        try:
            _write_io_memory(obj, bank, offset, data, size, be_byte_order, inquiry)
        except simics.SimExc_Lookup:
            _write_sc_register_access(obj, bank, offset, data, size, be_byte_order)


# Read the current value of the register
def read_reg_val(obj, bank, reg, inquiry=True):
    if bank.rviface and inquiry:
        return bank.rviface.get_register_value(reg.view_id)

    try:
        return read_memory(obj, bank, reg.offset,
                           reg.size, reg.be_byte_order, inquiry)
    except simics.SimExc_Memory as ex:
        raise cli.CliError("Failed accessing register %s in %s: %s"
                           % (reg.name, obj.name, ex))
    except simics.SimExc_Lookup:
        # The bank does not implement the io_memory interface.
        # Read the attribute directly.
        raise cli.CliError(f"Cannot read register value in {obj.name}: "
                           " bank does not implement required interface")

# Write the given value to the register
def write_reg_val(obj, bank, reg, data, inquiry = True):
    if bank.rviface and inquiry:
        bank.rviface.set_register_value(reg.view_id, data)
        return
    try:
        # Try the io-memory interface
        write_memory(obj, bank, reg.offset, data, reg.size,
                     reg.be_byte_order, inquiry)
    except simics.SimExc_Memory as ex:
        raise cli.CliError("Failed accessing register %s in %s: %s"
                           % (reg.name, obj.name, ex))
    except simics.SimExc_Lookup:
        raise cli.CliError(("Register %s in %s: bank does not implement"
                            + " required interface")
                           % (reg.name, obj.name))

def find_mappings(dml_obj, dev_info, bank, reg):
    def obj_references(obj):
        def obj_refs(val):
            if isinstance(val, simics.conf_object_t):
                yield val
                return
            elif isinstance(val, list):
                it = iter(val)
            elif isinstance(val, dict):
                it = iter(list(val.values()))
            else:
                return
            for i in it:
                for v in obj_refs(i):
                    yield v

        refs = set()
        for attr in simics.VT_get_attributes(obj.classname):
            a_type = simics.VT_get_attribute_type(obj.classname, attr)
            if a_type is not None and 'o' not in a_type and 'a' not in a_type:
                # Skip attributes which may not contain objects:
                # this saves cycles and avoids touching attribute
                # getters which may have errors and in rare cases crash Simics.
                continue
            if (simics.SIM_get_attribute_attributes(obj.classname, attr)
                & simics.Sim_Attr_Internal):
                # skip internal attributes
                continue
            try:
                val = getattr(obj, attr)
            except simics.SimExc_Attribute:
                continue
            if isinstance(val, simics.conf_attribute_t):
                try:
                    val = val.copy()
                except simics.SimExc_Attribute:
                    continue
            for o in obj_refs(val):
                refs.add(o)
        return refs


    def make_graph(cpu, dml_obj):
        def parse_obj_spec(obj):
            if isinstance(obj, simics.conf_attribute_t):
                obj = obj.copy()
            if isinstance(obj, list):
                return obj[0], obj[1]
            return obj, None

        def add_edge(node, edges, obj, func, base,
                     map_start, map_len, target_obj,
                     default_mapping=False):
            obj, port = parse_obj_spec(obj)
            target_obj, target_port = parse_obj_spec(target_obj)
            if obj.classname in ('memory-space', 'port-space'):
                # Don't know how to handle translate objects in general,
                # so skip them all but memory/port spaces.
                if (target_obj and obj != target_obj
                    and target_obj.classname in ('memory-space', 'port-space')):
                    edges.append((target_obj,
                                  (node, obj, None, func, base,
                                   map_start, map_len)))
                else:
                    edges.append((obj,
                                  (node, None, None, None, base,
                                   map_start, map_len)))
            elif obj is dml_obj and not default_mapping:
                edges.append((obj, (node, None, port, func, base,
                                    map_start, map_len)))

        graph = {}

        # All instances of classes 'memory-space' and/or 'port-space'
        for obj in simics.SIM_object_iterator(None):
            if hasattr(obj, 'map'):
                edges = []
                if obj.classname == 'memory-space':
                    for m in obj.map:
                        add_edge(obj, edges, m[1], m[2], m[0], m[3], m[4], m[5])
                elif obj.classname == 'port-space':
                    for m in obj.map:
                        add_edge(obj, edges, m[1], m[2], m[0], m[3], m[4], None)
                else:
                    continue
                t = getattr(obj, 'default_target', None)
                if t:
                    add_edge(obj, edges, t[0], t[1], 0, t[2], 0, t[3], True)
                graph[obj] = edges

        # Look for memory space references in the cpu object
        refs = set()
        for o in obj_references(cpu):
            if o.classname in ('memory-space', 'port-space'):
                refs.add(o)
        graph[cpu] = [(o, None) for o in refs]

        graph[dml_obj] = []
        return graph

    def find_all_paths(graph, start, target_obj, max_depth):
        all_paths = []
        limit_reached = [False]
        def dfs(node, path, depth):
            if node is target_obj:
                all_paths.append(path)
            elif depth < max_depth:
                for e in graph[node]:
                    if not e in path:
                        dfs(e[0], path + [e], depth + 1)
            else:
                limit_reached[0] = True
        dfs(start, [], 0)
        return (all_paths, limit_reached[0])

    try:
        cpu = getattr(dml_obj, 'queue')
    except simics.SimExc_Attribute:
        return ((), False)

    if not cpu:
        return ((), False)

    graph = make_graph(cpu, dml_obj)

    bank_name = bank.name
    bank_func = bank.function

    # TODO: this would exclude the case when multiple banks are
    # defined together with a default bank.
    default_bank = len(dev_info.banks) == 1

    # use a fixed maximum depth, unlikely to hit that limit
    (all_paths, limit_reached) = find_all_paths(graph, cpu, dml_obj, 256)

    res = set()
    for path in all_paths:
        obj, (_, _, port, func, map_base, map_start, map_len) = path[-1]
        assert(obj is dml_obj)
        # check if bank/port matches
        if port and port != bank_name:
            continue
        elif bank_func is None and default_bank:
            pass
        elif bank_func != func:
            # function mapping
            continue

        # calculate the physical address by accumulating over
        # the formula map_base - map_start along the path
        phys_addr = reg.offset + sum(p[1][4] - p[1][5] for p in path[1:])

        # check if each mapping is in the range
        port_space = False
        addr = phys_addr
        for p in path[1:]:
            _, (spc, _, _, _, map_base, map_start, map_len) = p
            port_space = port_space or spc.classname == 'port-space'
            addr -= map_base
            if (0 <= addr < map_len) or (map_len == 0):
                addr += map_start
            else:
                break
        else:
            res.add((phys_addr, path[0][0], port_space))

    return (sorted(tuple(res)), limit_reached)


def lookup_register(obj, arg):
    def find_bank(dev, name):
        for b in dev_banks(dev):
            if b.name == name:
                return b

    dev = device_info.get_device_info(obj)
    if dev is None:
        raise cli.CliError("No register information available for %s"
                           % obj.name)

    def tokenize_indexed_name(name):
        names = []
        for indexed in name.split('.'):
            match = re.match(r'([\w]+)((?:\[\d+\])*)$', indexed)
            if not match:
                raise cli.CliError(
                    f"Invalid register argument ({indexed!r} in {name!r})")
            indices = re.findall(r'\[(\d+)\]', match.group(2))
            names += ((match.group(1),
                       [int(m) for m in indices]),)
        return names

    def bank_or_anon(device, bank_name):
        bank = find_bank(device, bank_name)
        if bank:
            return (False, bank)
        return (True, find_bank(device, ''))

    reg_names_and_indices = tokenize_indexed_name(arg)

    (bname, bidxs) = reg_names_and_indices[0]  # bank or register in anon bank
    if bidxs:
        bname = "%s%s" % (bname, "".join("[%s]" % i for i in bidxs))
    (is_anon, bank) = bank_or_anon(dev, bname)
    if not is_anon:
        reg_names_and_indices.pop(0)

    if bank is None:
        # We could perform some additional lookups here based on bidx
        # to guide users towards the proper bank
        raise cli.CliError("Unknown bank '%s'" % bname)

    rname = '.'.join(['%s%s' %
                      (name, ''.join('[%d]' % idx for idx in idxs))
                      for (name, idxs) in reg_names_and_indices])
    reg = bank.reg_from_name(rname)
    if reg is None:
        raise cli.CliError(
            ("Unknown register '%s' in bank '%s'" % (rname, bank.name))
            if bank.name
            else ("Unknown register '%s'" % rname))

    return (dev, bank, reg)

def dev_reg_info(obj, arg):
    dev, bank, reg = lookup_register(obj, arg)
    val = read_reg_val(obj, bank, reg)
    mappings = find_mappings(obj, dev, bank, reg)
    return generate_reg_info(obj, bank, reg, val, mappings)

def cmd_print_device_reg_info(reg_spec):
    (dev, reg) = split_device_bank_reg(reg_spec)
    if not dev or not reg:
        raise cli.CliError("Not a valid register definition: %s" % reg_spec)
    return dev_reg_info(dev, reg)

def expander_device_or_bank_object(comp):
    # Expand to "device" or "device.bank.bank_name". To "force" users to use
    # bank objects this expander doesn't provide device.bank_name completions.
    return cli.get_completions(
        comp,
        [k for (k, o) in cli.visible_objects(recursive = True).items()
         if (device_info.is_iomem_device(o)
             and device_info.has_device_info(o))])

def expander_register(comp):
    # Expand up to "device.bank.bank_name.reg_name". To "force" users to use
    # bank objects the "device.bank_name.reg_name" completions are not produced.
    # Anonymous banks (DML 1.4 don't have them) are not supported either.

    comp_devs = []
    for (n, o) in cli.visible_objects(recursive = True).items():
        rv_iface = getattr(o.iface, simics.REGISTER_VIEW_INTERFACE, None)
        if rv_iface and rv_iface.number_of_registers() > 0:
            comp_devs.append(n + '.')

        if hasattr(o.iface, 'sc_object'):
            for port_name in set(o.ports):
                port = getattr(o.ports, port_name)
                if hasattr(port, simics.REGISTER_VIEW_INTERFACE):
                    rv_iface = simics.SIM_get_port_interface(o,
                        simics.REGISTER_VIEW_INTERFACE, port_name)
                    if rv_iface.number_of_registers() > 0:
                        comp_devs.append(n + '.' + port_name)

    comp_devs = cli.get_completions(comp, comp_devs)
    if len(comp_devs) > 1:
        return comp_devs

    if len(comp_devs) == 1:
        # Simics immediately asks for the next argument if only one completion
        # is returned. So we try to get more completions from the device.
        comp = comp_devs.pop()

    comps = []
    (dev, remainder) = split_device_bank_reg(comp)
    bank = remainder.split('.') if remainder else None
    if bank:
        bank = bank[0]

    if dev:
        rv_iface = getattr(dev.iface, simics.REGISTER_VIEW_INTERFACE, None)
        if not rv_iface and bank and bank in set(dev.ports):
            port = getattr(dev.ports, bank)
            if hasattr(port, simics.REGISTER_VIEW_INTERFACE):
                rv_iface = simics.SIM_get_port_interface(dev,
                    simics.REGISTER_VIEW_INTERFACE, bank)
        else:
            bank = None

        if rv_iface:
            for i in range(rv_iface.number_of_registers()):
                reg = dev.name + '.'
                if bank:
                    reg += bank + '.'

                reg += rv_iface.register_info(i)[0]
                comps.append(reg)

    return cli.get_completions(comp, comps)

def expander_register_field(comp, _, args):
    reg_spec = args[0]
    if reg_spec is None:
        return []

    (dev, reg) = split_device_bank_reg(reg_spec)
    if not dev or not reg:
        return []
    try:
        (_, bank, r) = lookup_register(dev, reg)
    except cli.CliError:
        return []

    return cli.get_completions(comp, [f.name for f in r.fields])

def expander_io_device(comp):
    # Expand to "device" or "device.bank.bank_name". To "force" users to use
    # bank objects this expander doesn't provide device.bank_name completions.
    return cli.get_completions(
        comp,
        [k for (k, o) in cli.visible_objects(recursive = True).items()
         if (hasattr(o.iface, simics.TRANSACTION_INTERFACE)
             or hasattr(o.iface, simics.IO_MEMORY_INTERFACE))])

cli.new_command('print-device-reg-info', cmd_print_device_reg_info,
                [cli.arg(cli.str_t, "register", expander = expander_register)],
                type = ["Registers", "Inspection"],
                short = "print detailed information of device registers",
                alias = [],
                see_also = ['print-device-regs',
                            'get-device-reg', 'get-device-offset'],
                doc = """
Print detailed information about a device register. The <arg>register</arg>
argument is of the form <tt>device.bank.register</tt>. The information includes
the register width in bits, byte offset within the register bank, its current
value and all bit fields. If the device bank is mapped into memory, the command
will try to resolve which physical address or addresses the register is mapped
at.

When used in an expression, the return value is a list with register
offset within the bank, the register width in bits, the current value,
and the physical addresses where the register is mapped, together with
the corresponding memory spaces. If the register is not mapped or does
not hold any value, the return value will still report them as 0.
""")

def check_device(obj):
    dev = device_info.get_device_info(obj)
    if dev is None:
        raise cli.CliError("No register information available for %s"
                           % obj.name)
    if not dev_banks(dev):
        raise cli.CliError("The %s device does not have any bank with "
                           "mapped registers" % obj.name)
    return dev

def lookup_bank(dev, arg):
    if arg is None:  # default argument
        return dev_banks(dev)

    arg = re.match(r'([a-zA-Z_]\w*)((:?\[\s*\d+\s*\])*)\.?\Z', arg)
    if not arg:
        raise cli.CliError("Invalid bank argument")
    name = re.sub(r'\s', '', arg.group(0))
    for b in dev_banks(dev):
        if b.name == name:
            return (b,)
    raise cli.CliError("Unknown bank '%s'" % (name or '<anonymous>'))

def cmd_dev_reg_list_common(obj, bspec, pattern, substr, byname, show_description):
    dev = check_device(obj)
    banks = lookup_bank(dev, bspec)
    line_separator = ""
    output = ""
    regs = []
    msg = ""
    warn = ""

    if show_description:
        props = [(Table_Key_Columns, [
            [(Column_Key_Name, "Offset")
             if not byname else (Column_Key_Name, "Name")],
            [(Column_Key_Name, "Name")
             if not byname else (Column_Key_Name, "Offset")],
            [(Column_Key_Name, "Size")],
            [(Column_Key_Name, "Value")],
            [(Column_Key_Name, "Description")]])]
    else:
        props = [(Table_Key_Columns, [
            [(Column_Key_Name, "Offset")
             if not byname else (Column_Key_Name, "Name")],
            [(Column_Key_Name, "Name")
             if not byname else (Column_Key_Name, "Offset")],
            [(Column_Key_Name, "Size")],
            [(Column_Key_Name, "Value")]])]

    if pattern != "*" and substr:
        warn = "Note: pattern and substr both set. Ignoring substr.\n"
        substr = None
    if substr:
        pattern = f"*{glob.escape(substr)}*"

    for bank in banks:
        b_regs = print_reg_list(
            obj, bank, pattern, byname, show_description)
        if pattern and not b_regs:
            continue

        if not bspec and bank.name:
            # only include bank name if none specified on the command line
            output += line_separator + ' Bank: ' + bank.name

        regs += b_regs
        regview = simics.SIM_c_get_interface(obj,
                                            simics.REGISTER_VIEW_INTERFACE)
        if regview is not None:
            if regview.description():
                output += "\nDescription\n\t"
                output += regview.description()

        if len(regs):
            tbl = table.Table(props, regs)
            if byname:
                regs.sort(key = lambda row: row[0])
            msg += warn + output + "\n"
            msg += tbl.to_string(rows_printed=0, no_row_column=True)
        output = ""
        line_separator = "\n\n"

    return cli.command_verbose_return(message=msg, value=regs)

def cmd_print_device_regs(bank_spec, pattern, substr, byname, show_description):
    (dev, bank_name) = split_device_bank_reg(bank_spec)
    if not dev:
        raise cli.CliError("Not a valid bank definition: %s" % bank_spec)
    return cmd_dev_reg_list_common(dev, bank_name, pattern, substr, byname,
                                   show_description)

def print_reg_list(obj, bank, pattern, byname, show_description):
    regs = []
    for rname in bank.reg_names():
        if pattern and not fnmatch.fnmatchcase(rname, pattern):
            continue
        r = bank.reg_from_name(rname)
        assert r, rname

        if byname:
            data = [r.name, r.offset, r.size, read_reg_val(
                obj, bank, r)]
        else:
            data = [r.offset, r.name, r.size, read_reg_val(
                obj, bank, r)]

        if show_description:
            description = ''
            if bank.rviface:
                description = bank.rviface.register_info(r.view_id)[1]
            data.append(description)
        regs.append(data)
    if not regs:
        return []

    return sorted([x[:6] for x in regs])

cli.new_command('print-device-regs', cmd_print_device_regs,
                [cli.arg(cli.str_t, "bank",
                         expander = expander_device_or_bank_object),
                 cli.arg(cli.str_t, "pattern", "?", "*"),
                 cli.arg(cli.str_t, "substr",  "?", None),
                 cli.arg(cli.flag_t, '-s'),
                 cli.arg(cli.flag_t, '-description')],
                type = ["Registers", "Inspection"],
                short = "list registers in a bank",
                alias = [],
                see_also = ['print-device-reg-info',
                            'get-device-reg', 'get-device-offset'],
                doc = """
Print information about the registers in <arg>bank</arg>.
The <arg>bank</arg> argument can either be a <tt>device</tt> or a bank object,
i.e. <tt>device.bank.&lt;bank-name&gt;</tt>. For a device object, all banks of
the device will be listed. The old way to specify register banks
(<tt>device.&lt;bank-name&gt;</tt>) is supported but deprecated.

The optional argument <arg>pattern</arg> is a glob pattern that will be used
to match against register names. By default, all registers in the bank will be
matched.

The optional argument <arg>substr</arg> is a convenience for using the
pattern argument. For example, <tt>substr=foo</tt> is equivalent to using
<tt>pattern="*foo*"</tt>.

<tt>-s</tt>, if provided, will sort the output by the name of the registers
instead of their offsets, which is the default.

<tt>-description</tt>, if provided, the register description will be output
for each register that has description.

If used in an expression, the return value is a list of lists in the format
[[&lt;offset&gt;, &lt;bank&gt;, &lt;name&gt;, &lt;size&gt;, &lt;value&gt;]*].
The returned list is always sorted by offsets and not affected by the
<tt>-s</tt> flag.
""")

#
# ----------------- set-device-reg/write-device-reg --------------------
#

def cmd_dev_reg_set(reg_spec, register_field, data,
                    l_or_b_flag, inquiry = True):
    (dev, reg) = split_device_bank_reg(reg_spec)
    if not dev or not reg:
        raise cli.CliError("Not a valid register definition: %s" % reg_spec)
    (_, bank, r) = lookup_register(dev, reg)

    if l_or_b_flag is None:
        be_byte_order = r.be_byte_order
    else:
        be_byte_order = l_or_b_flag[2] == "-b"

    if register_field is not None:
        matching_fields = [f for f in r.fields if f.name == register_field]
        if not matching_fields:
            raise cli.CliError(
                f"No field '{register_field}' in register '{dev.name}.{reg}'")
        if len(matching_fields) > 1:
            raise cli.CliError(
                f"There are {len(matching_fields)} fields named"
                f" '{register_field}' in register '{dev.name}.{reg}'")
        f = matching_fields[0]
        f_num_bits = f.msb + 1 - f.lsb
        if data.bit_length() > f_num_bits:
            raise cli.CliError(
                f"Value '{data:#x}' is too large for"
                f" {f_num_bits}-bit field {register_field}")
        if be_byte_order != r.be_byte_order:
            if f.msb % 8 != 7 or f.lsb % 8 != 0:
                raise cli.CliError(
                    f"Cannot swap endianness of field {register_field}: bitrange {f.msb}:{f.lsb}"
                    " is not aligned to byte boundaries")
            data = swap_endian(data, f_num_bits//8)

        if r.size*8 > f_num_bits:
            # The field doesn't cover the whole register. We need to
            # read out a missing part before writing the register.
            val = read_reg_val(dev, bank, r, inquiry=True)
            mask = (1 << (f.msb + 1)) - (1 << f.lsb)
            data = (val & ~mask) | (data << f.lsb)

        write_reg_val(dev, bank, r, data, inquiry=inquiry)
    else:
        if be_byte_order != r.be_byte_order:
            data = swap_endian(data, r.size)
        write_reg_val(dev, bank, r, data, inquiry)

def cmd_dev_reg_write(reg_spec, register_field, data, l_or_b_flag):
    cmd_dev_reg_set(reg_spec, register_field, data, l_or_b_flag, False)

args_set_device_reg = [
    cli.arg(cli.str_t, "register", expander = expander_register),
    cli.arg(cli.str_t, "field", "?", expander = expander_register_field),
    cli.arg(cli.uint64_t, "data"),
    cli.arg((cli.flag_t, cli.flag_t), ("-l", "-b"), "?", None),
]
cli.new_command("set-device-reg", cmd_dev_reg_set, args_set_device_reg,
                type = ["Registers", "Inspection"],
                short = "write to a register in a device bank",
                see_also = ["read-device-reg", "set-device-offset",
                            "print-device-reg-info", "print-device-regs"],
                doc = """
Write <arg>data</arg> to a device register. The <arg>register</arg>
argument is of the form <tt>device.bank.register</tt>.

If the destination register bank implements the
<iface>register_view</iface> interface, then this is used by
the <cmd>set-device-reg</cmd> command to write
register. Otherwise the <cmd>set-device-reg</cmd> command performs an
inquiry write, typically not overwriting read-only data in the device.
The <cmd>write-device-reg</cmd> command always does a standard write access.
Note that not all device models support inquiry accesses.

The <arg>field</arg> parameter can be specified to update
a register field. One can use the <cmd>print-device-reg-info</cmd> command
to see which fields a register has.

The <tt>-l</tt> or <tt>-b</tt> flags are used to specify in what byte
order <arg>data</arg> should be interpreted. The default is to interpret
data as little-endian, except if a bank has explicitly declared big-endian
as its preferred byte order (which can happen for devices written in DML).""")

cli.new_command("write-device-reg", cmd_dev_reg_write, args_set_device_reg,
                short = "write to a register in a device bank",
                doc_with = "set-device-reg")

#
# ----------------- get-device-reg/read-device-reg --------------------
#

def cmd_dev_reg_get(reg_spec, register_field, l_or_b_flag, inquiry = True):
    (dev, reg) = split_device_bank_reg(reg_spec)
    if not dev or not reg:
        raise cli.CliError("Not a valid register definition: %s" % reg_spec)
    (_, bank, r) = lookup_register(dev, reg)
    if l_or_b_flag is None:
        be_byte_order = r.be_byte_order
    else:
        be_byte_order = l_or_b_flag[2] == "-b"

    if register_field is None:
        val = read_reg_val(dev, bank, r, inquiry)
        if be_byte_order != r.be_byte_order:
            val = swap_endian(val, r.size)
    else:
        # -l/-b affect only register field, not how we interpret register value
        val = read_reg_val(dev, bank, r, inquiry=inquiry)
        matching_fields = [f for f in r.fields if f.name == register_field]
        if not matching_fields:
            raise cli.CliError(
                f"No field '{register_field}' in register '{dev.name}.{reg}'")
        if len(matching_fields) > 1:
            raise cli.CliError(
                f"There are {len(matching_fields)} fields named"
                f" '{register_field}' in register '{dev.name}.{reg}'")
        f = matching_fields[0]
        f_num_bits = f.msb - f.lsb + 1  # f.msb >= f.lsb even if bitorder == be
        val = (val >> f.lsb) & ((1 << f_num_bits) - 1)

        if be_byte_order != r.be_byte_order:
            if f.msb % 8 != 7 or f.lsb % 8 != 0:
                raise cli.CliError(
                    f"Cannot swap endianness of field {register_field}:"
                    f" bitrange {f.msb}:{f.lsb} is not aligned"
                    " to byte boundaries")
            val = swap_endian(val, f_num_bits//8)

    return cli.command_return(cli.number_str(val), val)

def cmd_dev_reg_read(reg_spec, register_field, l_or_b_flag):
    return cmd_dev_reg_get(reg_spec, register_field, l_or_b_flag, False)

args_get_device_reg = [
    cli.arg(cli.str_t, "register", expander = expander_register),
    cli.arg(cli.str_t, "field", "?", expander = expander_register_field),
    cli.arg((cli.flag_t, cli.flag_t), ("-l", "-b"), "?", None),
]
cli.new_command("get-device-reg", cmd_dev_reg_get, args_get_device_reg,
                type = ["Registers", "Inspection"],
                short = "read from a register in a device bank",
                see_also = ["read-device-offset",
                            "set-device-reg",
                            "print-device-reg-info", "print-device-regs"],
                doc = """
Read from a device register and return the value. The <arg>register</arg>
argument is of the form <tt>device.bank.register</tt>.

The <cmd>get-device-reg</cmd> command performs an inquiry read, typically used
for non-intrusive inspection, while <cmd>read-device-reg</cmd> does a standard
access that may trigger side-effects in the device. Note that not all device
models support inquiry accesses.

The <arg>field</arg> parameter can be specified to get the value of
a register field. One can use the <cmd>print-device-reg-info</cmd> command
to see which fields a register has.

The <tt>-l</tt> or <tt>-b</tt> flags are used to specify in what byte
order the read data (that is a whole register or a register field) should
be interpreted. The default is to interpret data as little-endian, except
when a whole register is read out (i.e. no <arg>field</arg> argument is
passed) from the bank that declares big-endian as its
as its preferred byte order (which can happen for devices written in DML).""")

cli.new_command("read-device-reg", cmd_dev_reg_read, args_get_device_reg,
                short = "read from a register in a device bank",
                doc_with = "get-device-reg")

def lookup_destination(bank_spec, size):
    if size < 1 or size > 8:
        raise cli.CliError("Size must be between 1 and 8")
    (dev, bank_name) = split_device_bank_reg(bank_spec)
    if not dev:
        raise cli.CliError("Not a valid bank definition: %s" % bank_spec)

    try:
        function = int(bank_name)
    except (ValueError, TypeError):
        pass
    else:
        # bank_name is a function number, don't bother with device info
        bank = DML.Bank('', None, function, False, None, None)
        return (dev, bank)

    try:
        device = check_device(dev)
    except cli.CliError:
        # no bank information
        bank = DML.Bank(bank_name or '', None, 0, False, None, None)
    else:
        banks = lookup_bank(device, bank_name)
        if len(banks) > 1:
            raise cli.CliError(
                "Need to specify which bank in %s to access" % dev.name)
        # Banks is guaranteed nonempty by check_device
        bank = banks[0]

    return (dev, bank)


#
# --------------- set-device-offset/write-device-offset ---------------
#

def cmd_dev_offset_set(bank_spec, offset, data, size,
                       l_or_b_flag, inquiry = True):
    (dev, bank) = lookup_destination(bank_spec, size)
    if l_or_b_flag is None:
        be_byte_order = False
    else:
        be_byte_order = l_or_b_flag[2] == "-b"

    try:
        write_memory(dev, bank, offset, data, size, be_byte_order, inquiry)
    except simics.SimExc_Lookup:
        raise cli.CliError("Device %s does not have any interface for bank"
                       " accesses" % dev.name)
    except simics.SimExc_Memory as ex:
        raise cli.CliError("Failed accessing offset 0x%x in the %s device: %s"
                           % (offset, dev.name, ex))

def cmd_dev_offset_write(bank_spec, offset, data, size, l_or_b_flag):
    cmd_dev_offset_set(bank_spec, offset, data, size, l_or_b_flag, False)

args_set_device_offset = [
    cli.arg(cli.str_t, "bank", expander = expander_io_device),
    cli.arg(cli.uint_t, "offset"),
    cli.arg(cli.uint64_t, "data"),
    cli.arg(cli.uint_t, "size"),
    cli.arg((cli.flag_t, cli.flag_t), ("-l", "-b"), "?", None),
]
cli.new_command("set-device-offset", cmd_dev_offset_set, args_set_device_offset,
                type = ["Registers", "Inspection"],
                short = "write at an offset in a device bank",
                see_also = ["get-device-reg", "get-device-offset",
                            "set-device-reg",
                            "print-device-reg-info", "print-device-regs"],
                doc = """
Write <arg>data</arg> of <arg>size</arg> to the bank object <arg>bank</arg>,
i.e. <tt>device.bank.&lt;bank-name&gt;</tt>, or to other object implementing
the <iface>transaction</iface> or <iface>io_memory</iface> interface.
The old way to specify register banks (<tt>device.&lt;bank-name&gt;</tt>)
is supported but deprecated. The <arg>offset</arg> is the byte offset
from the start of the bank/object. For devices that still use function numbers
to identify memory mappings, the <arg>bank</arg> argument can be in the form
<tt>device.&lt;function_number&gt;</tt>.

The <cmd>set-device-offset</cmd> command performs an inquiry write,
typically not overwriting read-only data in the device, while
<cmd>write-device-offset</cmd> does a standard write access. Note that
not all device models support inquiry accesses.

Some devices, such as ones written in DML, provide a preferred byte
endianness that data should be converted to. The command will convert
to this endianness unless the <tt>-l</tt> or <tt>-b</tt> flags are
used to select an alternate one.

Not all devices support accesses that span several registers or that accesses
a register partially. (For DML 1.2 devices, such support must be enabled in
the device when it is compiled. This limitation is planned to be removed in
the next version of the language.)""")

cli.new_command("write-device-offset", cmd_dev_offset_write,
                args_set_device_offset,
                short = "write at an offset in a device bank",
                doc_with = "set-device-offset")

#
# --------------- get-device-offset/read-device-offset ---------------
#

def cmd_dev_offset_get(bank_spec, offset, size, l_or_b_flag, inquiry = True):
    (dev, bank) = lookup_destination(bank_spec, size)
    if l_or_b_flag is None:
        be_byte_order = False
    else:
        be_byte_order = l_or_b_flag[2] == "-b"
    try:
        val = read_memory(dev, bank, offset, size, be_byte_order, inquiry)
        return cli.command_return(cli.number_str(val), val)
    except simics.SimExc_Lookup:
        raise cli.CliError("Device %s does not have any interface for bank"
                       " accesses" % dev.name)
    except simics.SimExc_Memory as ex:
        raise cli.CliError("Failed accessing offset 0x%x in the %s device: %s"
                           % (offset, dev.name, ex))

def cmd_dev_offset_read(bank_spec, offset, size, l_or_b_flag):
    return cmd_dev_offset_get(bank_spec, offset, size, l_or_b_flag, False)

args_get_device_offset = [
    cli.arg(cli.str_t, "bank", expander = expander_io_device),
    cli.arg(cli.uint_t, "offset"),
    cli.arg(cli.uint_t, "size"),
    cli.arg((cli.flag_t, cli.flag_t), ("-l", "-b"), "?", None),
]
cli.new_command("get-device-offset", cmd_dev_offset_get, args_get_device_offset,
                type = ["Registers", "Inspection"],
                short = "read from an offset in a device bank",
                see_also = ["get-device-reg", "read-device-offset",
                            "set-device-offset", "set-device-reg",
                            "print-device-reg-info", "print-device-regs"],
                doc = """
Read and return the value from the bank object <arg>bank</arg>,
i.e. <tt>device.bank.&lt;bank-name&gt;</tt>, or from other object implementing
the <iface>transaction</iface> or <iface>io_memory</iface> interface.
The old way to specify register banks (<tt>device.&lt;bank-name&gt;</tt>)
is supported but deprecated. The <arg>offset</arg> is the byte offset
from the start of the bank/object and <arg>size</arg> is the number of bytes
to read, from 1 to 8. For devices that still use function numbers
to identify memory mappings, the <arg>bank</arg> argument can be in the form
<tt>device.&lt;function_number&gt;</tt>.

The <cmd>get-device-offset</cmd> command performs an inquiry read, typically
used for non-intrusive inspection, while <cmd>read-device-offset</cmd> does a
standard access that may trigger side-effects in the device. Note that not all
device models support inquiry accesses.

Some devices, such as ones written in DML, provide a preferred byte endianness
that data should be interpreted in. The command will use this endianness unless
the <tt>-l</tt> or <tt>-b</tt> flags are used to select an alternate one.

Not all devices support accesses that span several registers or that accesses
a register partially. (For DML 1.2 devices, such support must be enabled in
the device when it is compiled. This limitation is planned to be removed in
the next version of the language.)""")

cli.new_command("read-device-offset", cmd_dev_offset_read,
                args_get_device_offset,
                short = "read from an offset in a device bank",
                doc_with = "get-device-offset")

def cmd_list_device_regs(search_root, pattern):
    if not pattern or "".join(set(pattern)) == "*":
        raise cli.CliError("Cowardly refusing to print the unfiltered list"
                           " of all registers as this might take very long.")
    stage1 = [o for o in cli.visible_objects(recursive=True,
                                             component=search_root,
                                             include_root=True).values()
                            if (device_info.is_iomem_device(o)
                                and device_info.has_device_info(o)
                                and hasattr(o.iface, simics.REGISTER_VIEW_INTERFACE))]
    rv = [f'{o.name}.{name}'
          for o in stage1
          for bank in dev_banks(device_info.get_device_info(o))
          for name in bank.reg_names()
          if fnmatch.fnmatchcase(name, pattern)]
    return cli.command_return('\n'.join(rv), rv)

cli.new_command("list-device-regs", cmd_list_device_regs,
                [
                    cli.arg(cli.obj_t('root_of_search'), "root_of_search", "?", None),
                    cli.arg(cli.str_t, "pattern")
                ],
                type = ["Registers", "Inspection"],
                short = "find registers by name",
                see_also = ["get-device-reg", "read-device-offset",
                            "set-device-offset", "set-device-reg",
                            "print-device-reg-info", "print-device-regs"],
                doc = """
List all registers whose name matches <arg>pattern</arg>.

The <arg>pattern</arg> argument supports Unix shell-style wildcards. For more
information, see <url >https://docs.python.org/3.10/library/fnmatch.html</url>.

If the optional argument <arg>root_of_search</arg> is set, the search is limited
to this object and all its child objects. When not set, all objects in the
simulation will be searched.""")
