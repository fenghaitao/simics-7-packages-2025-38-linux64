# © 2014 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Commands related to memory and register maps.


from dataclasses import dataclass
from collections import namedtuple, defaultdict

import cli
import simics
from sim_commands import (
    all_known_interfaces,
    conf_class_expander,
    Column_Key_Alignment,
    Column_Key_Int_Radix,
    Column_Key_Name,
    Table_Key_Columns,
)
import device_info
import table
from mem_commands import translate_to_physical
from conf_commands import obj_cls_name_match

from cli import (
    arg,
    int_t,
    obj_t,
    str_t,
    uint16_t,
    sint16_t,
    uint64_t,
    new_command,
    number_str,
    get_completions,
)

uint64_max = (1 << 64) - 1
uint32_max = (1 << 32) - 1


def iface_expander(prefix):
    return cli.get_completions(prefix, list(all_known_interfaces()))


def hits_to_table(addr_spec, paddr, route):
    tgt = route[-1]
    is64 = any(h.address > uint32_max for h in route)
    digits = 16 if is64 else 8

    def mti_is_mem_space(mti):
        if not mti:
            return False
        return mti.object.classname == "memory-space"

    def mti_has_iface(mti, iface):
        """True if mti implements iface and is not a memory-space"""
        if not mti:
            return False
        gpi = simics.SIM_c_get_port_interface
        return (gpi(mti.object, iface, mti.port)
                and mti.object.classname != "memory-space")

    def mti_name(mti):
        if not mti:
            return "None"
        name = mti.object.name
        suffix = mti.port or (mti.function or '')
        return f"{name}{f':{suffix}' if suffix else ''}"

    def num_str(v):
        """Force radix 16 but honor grouping configured by user"""
        return cli.number_str(v, radix=16, precision=digits)

    def atoms_str(i, route):
        """Show all atoms that are added or changed in the next step"""
        cur = route[i].atoms
        nxt = {} if (i+1) == len(route) else route[i+1].atoms

        items = []
        for k, v in sorted(nxt.items()):
            if k not in cur or cur[k] != v:
                items.append((k, v))

        s = ""
        for k, v in items:
            if k == "completion":
                s += f"{k}\n"
            else:
                if isinstance(v, simics.conf_object_t):
                    s += f"{k}={v.name}\n"
                else:
                    s += f"{k}=" + str(v) + "\n"

        return s

    def accessed_atoms(i, route):
        if (i+1) == len(route):
            return ""
        nxt_access = route[i+1].atom_accesses
        s = ""
        for name, hit in nxt_access.items():
            if hit:
                s += f"{name}\n"
        return s

    def missed_atoms(i, route):
        if (i+1) == len(route):
            return ""
        nxt_access = route[i+1].atom_accesses
        s = ""
        for name, hit in nxt_access.items():
            if not hit:
                s += f"{name}\n"
        return s

    def hit_notes(h):
        mti = h.map_target_info
        return (("*" if mti_has_iface(mti, "translator") else "")
                + ("~" if mti_has_iface(mti, "transaction_translator") else "")
                + ("+" if mti_has_iface(mti, "translate") else "")
                + ("?" if h.flags & simics.Sim_Translation_Ambiguous else "")
                + ("@" if h.loop else "")
                + ("&" if h == tgt and not h.loop and mti_is_mem_space(mti) else "")
                + ("miss" if h.map_target_info is None else ""))

    def hit_str(h):
        if h.map_target_info is None:
            return "No matching mapping in the last map target\n"

        mapinfo = mti_name(h.map_target_info)
        msg = f"Destination: {mapinfo} offset 0x{h.address:x}"

        nfo = device_info.get_device_info(h.map_target_info.object)
        bank_list = nfo.banks if nfo and nfo.banks else []
        if h.map_target_info.port:
            banks = [b for b in bank_list
                     if b.name == h.map_target_info.port]
        else:
            banks = [b for b in bank_list
                     if b.function == h.map_target_info.function]

        if not banks:
            if mti_has_iface(h.map_target_info, 'io_memory'):
                return msg + " - no register information available"
            return msg

        hits = list(banks[0].regs_overlapping(h.address))
        if hits:
            [reg] = hits
            return msg + ("\nRegister:    %s @ 0x%x (%d bytes) + %d\n"
                          % (reg.name, reg.offset, reg.size,
                             h.address - reg.offset))
        else:
            return msg + (
                f" - no matching register in {banks[0].name or 'bank'}")

    def data_row(i, h, route):
        row = [mti_name(h.map_target_info),
               num_str(h.address) if h.map_target_info else 'N/A',
               hit_notes(h), atoms_str(i, route),
               accessed_atoms(i, route),
               missed_atoms(i, route)]
        return row

    data = [data_row(i, h, route) for (i, h) in enumerate(route)]
    column_names = ["Target", "Offset", "Notes", "Added Atoms",
                    "Inspected Atoms", "Missed Atoms"]
    props = [(table.Table_Key_Columns, [
        [(table.Column_Key_Name, n), (table.Column_Key_Hide_Homogeneous, "")] for n in column_names]),
    ]
    tbl = table.Table(props, data)

    msg = ""
    (addr_kind, addr) = addr_spec
    if addr_kind != 'p':
        # virtual to physical
        msg = ("Translating virtual address to physical:"
               f" {addr:#x} -> p:{paddr:#x}\n")

    msg += tbl.to_string(rows_printed=0, no_row_column=True) + "\n"

    # Add a legend for the "Notes" column:
    notes = [row[2] for row in data]
    def is_symbol_present_in_notes(symbol):
        return any(symbol in note for note in notes)
    descriptions = {
        '*' : "Translator implementing 'translator' interface",
        '~' : "Translator implementing 'transaction_translator' interface",
        '+' : "Translator implementing 'translate' interface",
        '?' : "More than one mapping matched",
        '@' : "Loop in memory space mappings detected",
        '&' : ("Memory space handles access (see documentation for"
               " memory-space->unmapped_read_value"
               " and memory-space->ignore_unmapped_writes)"),
    }
    for (symbol, descr) in descriptions.items():
        if is_symbol_present_in_notes(symbol):
            msg += f"'{symbol}' - {descr}\n"

    msg += hit_str(tgt)
    return (msg, tgt.map_target_info.object if tgt.map_target_info else None)


def probe_address(mt, paddr, access=simics.Sim_Access_Read,
                  depth=None, inquiry=False, atoms={}):
    def map_target_info(mt):
        if mt is None:
            return None
        return MapTargetInfo(
            mt.object, mt.port, mt.function, map_target_info(mt.target))

    def find_loop(prev, mti, address, flags):
        found = [p for p in prev if
                 p.map_target_info == mti and
                 p.address == address and
                 p.flags == flags]

        if not found:
            return False

        if ((mti.object.classname == "memory-space"
             and (mti.object.attr.unmapped_read_value is not None
                  or mti.object.attr.ignore_unmapped_writes))
            and len(found) == 1):
            # It is likely a special case when memory space handles
            # the access itself. And even if it is not, then len(found) becomes
            # larger than 1 later so we will catch the loop in any case.
            return False

        for f in found:
            f.loop = True
        return True

    MapTargetInfo = namedtuple(
        "map_target_info", "object, port, function, target")

    @dataclass
    class ProbeHit:
        # Holds info for each callback from SIM_inspect_address_routing
        # address is the address within map_target_info
        # loop indicates if this hit is part of a loop
        # all other fields correspond to the translation that lead to this hit
        map_target_info: MapTargetInfo
        address: int
        base: int
        start: int
        size: int
        access: int
        flags: int
        loop: bool
        atoms: dict
        atom_accesses: dict

    class atom_id_to_atom_name_helper(dict):
        def __missing__(self, atom_id):
            # New atom ids can be registered during execution,
            # here we allow for that.
            for name in simics.VT_list_registered_atoms():
                if simics.VT_lookup_atom_class_id(name) == atom_id:
                    self[atom_id] = name
                    return name
            assert False, f"No name for {atom_id} was found"

    atom_access = {}
    atom_name = atom_id_to_atom_name_helper(
         { simics.VT_lookup_atom_class_id(name) : name
           for name in simics.VT_list_registered_atoms() })

    def atom_tracing_callback(t, atom_id, cb_data):
        name = atom_name[atom_id]
        atom_access[name] = hasattr(t, name)

    def callback(mt, t, address, base, start, size, access, flags, hits):
        mti = map_target_info(mt)
        loop = find_loop(hits, mti, address, flags)
        ra = simics.VT_list_registered_atoms()

        # Disable tracing while we inspect atoms:
        simics.CORE_set_atom_tracing(False)
        atom_values = { k: getattr(t, k) for k in dir(t)
                        if k in ra and k != "trace_atom_access" }
        simics.CORE_set_atom_tracing(True)

        h = ProbeHit(
            mti, address, base, start, size, access, flags, loop,
            atom_values, atom_access.copy())
        atom_access.clear()
        hits.append(h)
        if loop:
            # Add a dummy None-translation, and terminate the trace
            hits.append(ProbeHit(
                None, address, base, start, size, access, flags, loop,
                atom_values, {}))
            return False
        return depth is None or len(hits) <= depth


    if access == simics.Sim_Access_Read:
        flags = 0
    elif access == simics.Sim_Access_Write:
        flags = simics.Sim_Transaction_Write
    elif access == simics.Sim_Access_Execute:
        flags = simics.Sim_Transaction_Fetch
    else:
        raise cli.CliError(
            f"Invalid access '{access}', must be one of 'r', 'w' or 'x'")

    hits = []
    trace_atom = simics.transaction_trace_atom_access_t(
            callback=atom_tracing_callback,
            cb_data=None)
    t = simics.transaction_t(flags=flags, inquiry=inquiry,
                             trace_atom_access=trace_atom)
    for k, v in atoms.items():
        setattr(t, k, v)

    pv = simics.CORE_set_atom_tracing(True)
    try:
        simics.SIM_inspect_address_routing(mt, t, paddr, callback, hits)
    finally:
        simics.CORE_set_atom_tracing(pv)

    return hits


def simple_atom_list():
    atoms = []
    r_atoms = simics.VT_list_registered_atoms()
    t = simics.transaction_t()
    for a in r_atoms:
        try:
            setattr(t, a, 1)
            atoms.append(a)
        except TypeError:  # Cannot be expressed as an integer
            pass
        except AttributeError:  # Atom is not Python wrapped
            pass
    return atoms


def atom_args(add_atoms: bool, execute: bool):
    if add_atoms:
        atoms = simple_atom_list()
        return [cli.arg(cli.int_t, f"ATOM_{a}", "?", default=None) for a in atoms]
    else:
        return []

def probe_address_cmd(addr_spec, obj, inquiry, port, add_atoms, *simple_atoms):
    (addr_kind, addr) = addr_spec

    obj = obj if obj else cli.current_cpu_obj()
    if simics.SIM_object_is_processor(obj):
        if port:
            space = getattr(obj, "port_space", None)
        else:
            space = obj.iface.processor_info.get_physical_memory()
        if not space:
            raise cli.CliError("The processor '%s' has no physical %s"
                               " space configured."
                               % (obj.name, "port" if port else "memory"))
        if addr_kind == 'p':
            paddr = addr
        else:
            try:
                paddr = translate_to_physical(obj, addr_spec)
            except simics.SimExc_Memory as e:
                raise cli.CliError(e)
    else:
        if port:
            raise cli.CliError("-port can only be used with a processor")
        if addr_kind not in ('p', ''):
            raise cli.CliError("Logical or virtual addresses can only be"
                               " used with a processor")
        paddr = addr
        space = obj

    try:
        mt = simics.SIM_new_map_target(space, None, None)
    except simics.SimExc_Lookup as e:
        raise cli.CliError(e)

    atoms = {}
    if simple_atoms:
        names = simple_atom_list()
        atoms = { names[i] : v for (i, v) in enumerate(simple_atoms)
                  if v is not None }
    hits = probe_address(mt, paddr, inquiry=inquiry, atoms=atoms)
    simics.SIM_free_map_target(mt)
    (msg, val) = hits_to_table(addr_spec, paddr, hits)
    return cli.command_return(msg.rstrip(), val)

include_atoms_doc = """
Transaction <tt>atoms</tt> can be used for routing rules
and access rights in a platform.
The <tt>-add-atoms</tt> flag opens up the capability to set transaction <tt>atoms</tt>
on the command line: once the flag is set the command accepts additional
arguments that have names starting with <tt>ATOM_</tt> prefix.
Tab complete after setting the <tt>-add-atoms</tt> flag
to see the available <tt>atoms</tt>.
These arguments are used by the command to pass in atom
values to the translators it passes through during
the transaction probing.

Please note that the <tt>ATOM_...</tt> arguments can be used only to specify values for
transaction atoms that have integer values and provide Python wrappings.
Complex atoms such as pointers and structures are not available from CLI.
"""

cli.new_command("probe-address", probe_address_cmd,
                args=[cli.arg(cli.addr_t, "address"),
                      cli.arg(cli.obj_t('processor, memory-space or translator',
                                   (simics.PROCESSOR_INFO_INTERFACE,
                                    simics.PORT_SPACE_INTERFACE,
                                    simics.TRANSLATOR_INTERFACE,
                                    simics.TRANSACTION_TRANSLATOR_INTERFACE)),
                         "obj", "?"),
                     cli.arg(cli.boolean_t, "inquiry", "?", default=True),
                     cli.arg(cli.flag_t, "-port"),
                     cli.arg(cli.flag_t, "-add-atoms")],
                dynamic_args=("-add-atoms", atom_args),
                type=["Memory", "Inspection"],
                short="find destination for an address",
                see_also=["memory-map", "devs", "<memory-space>.map",
                          "<port-space>.map",
                          "print-device-regs", "print-device-reg-info"],
                doc=f"""
Probes a memory <arg>address</arg> for a processor, memory space or custom translator objects, and
reports the destination object. If the destination is a device that provides
register information, the addressed register within the device will be shown.
If used in an expression the destination object will be returned.

If no address prefix is used (<tt>p:</tt>, <tt>l:</tt> or <tt>v:</tt>), the
address is interpreted as virtual when used with a processor or else as a
physical address.

The currently selected frontend processor is used unless the <arg>obj</arg>
argument selects a specific processor or map target object in the system.

The <arg>inquiry</arg> argument, which defaults to <tt>TRUE</tt>, sets
the inquiry flag of the transaction that is used when probing. Transactions
in inquiry mode must have no side-effects and may bypass certain access
restrictions.

The <tt>-port</tt> flag only applies to processor and selects the port space
instead of the memory address space if it exists.

{include_atoms_doc}

All memory spaces that the access will traverse are listed, with the
local address in each. The command warns for overlapping mappings with
the same priority.

The <tt>Notes</tt> column indicates what type of operation took place
on the transaction:
<table>
<tr><td><iface>translator</iface>: *</td></tr>
<tr><td><iface>transaction_translator</iface>: ~</td></tr>
<tr><td><iface>translate</iface>: +</td></tr>
<tr><td>Unknown: ?</td></tr>
<tr><td>Loop: @</td></tr>
<tr><td>Miss: miss</td></tr>
</table>
<br></br>
<br></br>
The <tt>Added Atoms</tt> column displays transaction atoms
that were added by the translator.
The <tt>Inspected Atoms</tt> column displays transaction atoms
that were inspected by the translator and possibly edited if the
atom is a pointer.
The <tt>Missed Atoms</tt> column displays transaction atoms
that the translator tried to lookup but were absent in the transaction.
""")


def memory_map(mt, cls=None, iface=None,
               fallback_access=simics.Sim_Access_Read,
               depth=None, max_regions=256, exclude_classes=[],
               exclude_objects=[], start=0, end=1 << 64, substr="", atoms={}):
    def map_target_info(mt):
        if mt is None:
            return None
        return MapTargetInfo(
            mt.object, mt.port, mt.function, map_target_info(mt.target))

    MapTargetInfo = namedtuple(
        "map_target_info", "object, port, function, target")
    Region = namedtuple('Region', 'base, top, device, offset, access')

    if fallback_access == simics.Sim_Access_Read:
        flags = 0
    elif fallback_access == simics.Sim_Access_Write:
        flags = simics.Sim_Transaction_Write
    else:
        flags = simics.Sim_Transaction_Fetch

    memory_map = []
    base = start
    i = 0
    while base < end and i < max_regions:
        # We use probe_address to find the target of the address we're
        # currently looking at, which is the base of the region.
        #
        # The size of this region is the minimum size 'above' the
        # address within all the regions we hit while probing.
        #
        # The offset of the region is the address within the final
        # region we hit.
        #
        # The access of the region is 'rwx' only if -all- hits were
        # 'rwx', otherwise the fallback access-mode was used at least
        # once so we use that for the region.
        t = simics.transaction_t(flags=flags, inquiry=True)
        for k, v in atoms.items():
            setattr(t, k, v)
        max_depth = 0 if depth is None else depth
        tgt_info = simics.CORE_inspect_transaction_terminus(mt, t, base,
                                                            max_depth)
        device = map_target_info(tgt_info.terminus)
        # CORE_inspect_transaction_terminus increments refcount of terminus
        # caller has to decrement refcount and does it by calling
        # SIM_free_map_target()
        simics.SIM_free_map_target(tgt_info.terminus)
        offset = tgt_info.offset
        size = 1 << 64 if tgt_info.size == 0 else tgt_info.size
        access = tgt_info.access
        port_space = device and tgt_info.in_port_space
        top = base + size - 1
        region = Region(base, top, device, offset, access)

        if port_space:
            base += 1  # port-spaces have strange behavior
        else:
            base += size

        i += 1
        if region.device is None:
            continue
        if region.device.object.classname in exclude_classes:
            continue
        if region.device.object in exclude_objects:
            continue
        if substr and not obj_cls_name_match(substr, region.device.object.name):
            continue
        if tgt_info.loop:
            continue
        if cls and not region.device.object.classname == cls:
            continue
        if iface:
            try:
                simics.SIM_get_port_interface(
                    region.device.object, iface, region.device.port)
            except simics.SimExc_Lookup:
                continue  # not found
            except simics.SimExc_PythonTranslation:
                pass  # found, but no python-wrapping
        memory_map.append(region)

    return (memory_map, i >= max_regions, base - 1)


def memory_map_cmd(obj, cls, iface, access_flags, recurse_flags,
                   max_regions, exclude_arg, start, end, is_global, substr, *simple_atoms):
    def region_to_table_entry(region):
        def mti_str(mti):
            if mti is None:
                return ""
            res = f"{mti.object.name}"
            if mti.port:
                res += f":{mti.port}"
            return res

        base = region.base
        top = region.top
        device = mti_str(region.device)
        function = region.device.function or ""
        offset = region.offset or ""
        target = mti_str(region.device.target) if region.device else None
        if region.access == simics.Sim_Access_Read:
            access = 'read'
        elif region.access == simics.Sim_Access_Write:
            access = 'write'
        elif region.access == simics.Sim_Access_Execute:
            access = 'exec'
        else:
            access = ''
        return [base, top, device, offset, access, function, target]

    def region_to_map_entry(region):
        def mti_me(mti):
            if mti is None:
                return None
            if mti.port:
                return [mti.object, mti.port]
            else:
                return mti.object

        return [region.base, region.top, mti_me(region.device),
                region.offset, region.access]

    if max_regions <= 0:
        raise cli.CliError("The max-regions argument must be a positive integer")
    obj = obj or cli.current_cpu_obj()
    if simics.SIM_object_is_processor(obj):
        space = obj.iface.processor_info.get_physical_memory()
        if not space:
            raise cli.CliError(f"The processor {obj.name} has no physical"
                               " memory space configured.")
        obj = space

    if recurse_flags is None:
        depth = None if is_global else 1
    else:
        depth = None if recurse_flags[-1] == '-recurse' else 1

    if access_flags is None:
        access = simics.Sim_Access_Read
    else:
        access = {'-r': simics.Sim_Access_Read,
                  '-w': simics.Sim_Access_Write,
                  '-x': simics.Sim_Access_Execute}[access_flags[-1]]

    if cls and cls not in simics.SIM_get_all_classes():
        raise cli.CliError(f"'{cls}' is not a loaded class")
    if iface and iface not in all_known_interfaces():
        raise cli.CliError(f"'{iface}' is not a known interface")

    exclude_objects = []
    exclude_classes = []
    for exclude in exclude_arg:
        if isinstance(exclude, simics.conf_object_t):
            exclude_objects.append(exclude)
        else:
            try:
                ex_cls = simics.SIM_get_class(exclude)
            except simics.SimExc_General:
                ex_cls = None
            if ex_cls is None:
                # be polite and warn a user that it is not a class
                raise cli.CliError(
                    f"'{exclude}' specified in the ‘exclude’ parameter"
                    " is neither an object nor a class")
            exclude_classes.append(exclude)
    try:
        mt = simics.SIM_new_map_target(obj, None, None)
    except simics.SimExc_Lookup as e:
        raise cli.CliError(e)

    atoms = {}
    if simple_atoms:
        names = simple_atom_list()
        atoms = { names[i] : v for (i, v) in enumerate(simple_atoms)
                  if v is not None }
    (regions, incomplete, end) = memory_map(mt, cls, iface, access, depth,
                                            max_regions, exclude_classes,
                                            exclude_objects, start, end,
                                            substr, atoms)
    simics.SIM_free_map_target(mt)

    table_list = [region_to_table_entry(r) for r in regions]
    map_list = [region_to_map_entry(r) for r in regions]

    def max_hex_width(map_list, i):
        if not map_list:
            return 0
        return max(len(hex(entry[i])) - 2 for entry in map_list)

    pad_width = {k: max_hex_width(map_list, i)
                 for (k, i) in (("Start", 0), ("End", 1), ("Offset", 3))}

    columns = [
        [(table.Column_Key_Name, "Start"),
         (table.Column_Key_Int_Radix, 16),
         (table.Column_Key_Int_Pad_Width, pad_width["Start"]),
         (table.Column_Key_Alignment, "right")],
        [(table.Column_Key_Name, "End"),
         (table.Column_Key_Int_Radix, 16),
         (table.Column_Key_Int_Pad_Width, pad_width["End"]),
         (table.Column_Key_Alignment, "right")],
        [(table.Column_Key_Name, "Object"),
         (table.Column_Key_Alignment, "left")],
        [(table.Column_Key_Name, "Offset"),
         (table.Column_Key_Hide_Homogeneous, ""),
         (table.Column_Key_Int_Radix, 16),
         (table.Column_Key_Int_Pad_Width, pad_width["Offset"]),
         (table.Column_Key_Alignment, "right")],
        [(table.Column_Key_Name, "Access"),
         (table.Column_Key_Hide_Homogeneous, ""),
         (table.Column_Key_Alignment, "left")],
        [(table.Column_Key_Name, "Fn"),
         (table.Column_Key_Hide_Homogeneous, ""),
         (table.Column_Key_Alignment, "right")],
        [(table.Column_Key_Name, "Target"),
         (table.Column_Key_Hide_Homogeneous, ""),
         (table.Column_Key_Alignment, "left")],
    ]

    headers = [(table.Extra_Header_Key_Row,
                [[(table.Extra_Header_Key_Name, obj.name)]])]

    props = [(table.Table_Key_Extra_Headers, headers),
             (table.Table_Key_Columns, columns)]
    tbl = table.Table(props, table_list)
    output = tbl.to_string(rows_printed=0, no_row_column=True)
    if incomplete:
        output += (f"\nMaximum number of regions probed ({max_regions}),"
                   f" output only covers the [0x0:{end:#x}] address range")
    return cli.command_verbose_return(output, map_list)

memory_map_ns_args = [
    cli.arg(cli.str_t, "class", "?", None,
          expander=conf_class_expander(True)),
    cli.arg(cli.str_t, "interface", "?", None,
            expander=iface_expander),
    cli.arg((cli.flag_t, cli.flag_t, cli.flag_t),
            ('-r', '-w', '-x'), "?", None),
    cli.arg((cli.flag_t, cli.flag_t),
            ("-recurse", "-local"), "?", None),
    cli.arg(cli.uint_t, "max-regions", "?", 256),
    cli.arg(cli.poly_t('exclude', cli.obj_t('object'), cli.str_t),
            "exclude", "*"
            # we provide no expander - it is hard to provide a reasonable one
           ),
    cli.arg(cli.range_t(0, (1 << 64) - 1, "Value in range 0, 2^64 - 1"), "start", "?", 0x0),
    cli.arg(cli.range_t(0, 1 << 64, "Value in range 0, 2^64"), "end", "?", 1 << 64),
    cli.arg(cli.str_t, "substr", "?", ""),
    cli.arg(cli.flag_t, "-add-atoms")
]
memory_map_global_args = [
    cli.arg(cli.obj_t('processor or translator',
                      (simics.PROCESSOR_INFO_INTERFACE,
                       simics.PORT_SPACE_INTERFACE,
                       simics.TRANSLATOR_INTERFACE,
                       simics.TRANSACTION_TRANSLATOR_INTERFACE)),
            "object", "?")] + memory_map_ns_args

memory_map_common_args = {
    "type": ["Memory", "Inspection"],
    "short": "print physical memory map",
    "see_also": ["probe-address"],
    "doc": f"""
Displays the physical memory map for a processor or a translator
(e.g. a memory-space). The map of the currently selected frontend
processor is shown, unless the <arg>object</arg> argument selects another
processor or a specific translator in the system.

The <arg>interface</arg>, <arg>class</arg> and <arg>exclude</arg> arguments
can be used to filter the output, only including objects of a certain class, or
implementing a certain interface. The <arg>exclude</arg> argument is a list holding
objects and/or classes to filter out.

Example excluding RAM objects, memory spaces and object <tt>board.foo</tt>:<br/>
<tt>memory-map object = board.phys_mem exclude = ram memory-space board.foo</tt><br/>
or with the list syntax:<br/>
<tt>memory-map object = board.phys_mem exclude = ["ram", "memory-space", board.foo]</tt>

If the optional <arg>substr</arg> argument is specified, only objects with a
name matching this sub-string will be printed. The current namespace part of
the object name will not be included in the name matched against.

If possible, the memory map will be probed using 'rwx' access mode.
Otherwise, the mode specified by either of the <tt>-r</tt>,
<tt>-w</tt> or <tt>-x</tt> flags is used, default is <tt>-r</tt>.

The command can probe the memory map recursively, or it can show the
local map only. This can be controlled using the flags
<tt>-recurse</tt> and <tt>-local</tt>. The default behavior of the
non-namespaced version of this command is to probe recursively, while
the default behaviour of the namespaced version is to probe the local
memory map only.

{include_atoms_doc}

The output table minimally shows these columns:<br/>
- <tt>Start</tt> and <tt>End</tt> are the start and the end of the mapping<br/>
- <tt>Device</tt> is the destination device<br/>

Optional columns, which are shown when required, are:<br/>
- <tt>Offset</tt> is the offset in the destination device<br/>
- <tt>Access</tt> is the access type for which the entry is valid<br/>
- <tt>Fn</tt> is the (deprecated) function number for the entry<br/>
- <tt>Target</tt> is the default target of the entry, which is used
when <tt>device</tt> is a <tt>translator</tt>. This can only occur if
<tt>-local</tt> was used or the command ended prematurely

Argument <arg>max-regions</arg> can be used to increase the number of
rows presented. Default is a maximum of 256 rows.

Arguments <arg>start</arg> and <arg>end</arg> can be used to view a subrange
of the memory map. The subrange spans [start, end).

When the command is used in an expression, a list is returned with
entries describing individual mappings. Each entry describing an
individual mapping is a list in the form [start, end, device, offset,
access].

The list items are:<br/>
- <tt>start</tt> and <tt>end</tt> are the start and the end of the mapping<br/>
- <tt>device</tt> is the destination device<br/>
- <tt>offset</tt> is the offset in the destination device<br/>
- <tt>access</tt> is the bitmap of the <tt>access_t</tt> values showing for
which access types the entry is valid.

Please note that the list describing an individual mapping may grow
in future Simics versions, but the currently defined fields will not change.

Please note that the command can in some cases take a long time to execute.
Long execution times happen when there is a high occurrence of small map segments
in a platform. The <cmd>memory-map</cmd> command has to iterate over all
these segments.
"""}

def memory_map_cmd_local(obj, cls, iface, access_flags, recurse_flags,
                         max_regions, exclude_arg, start, end,
                         substr, add_atoms, *simple_atoms):
    return memory_map_cmd(obj, cls, iface, access_flags, recurse_flags,
                          max_regions, exclude_arg, start, end, False, substr, *simple_atoms)

def memory_map_cmd_global(obj, cls, iface, access_flags, recurse_flags,
                          max_regions, exclude_arg, start, end,
                          substr, add_atoms, *simple_atoms):
    return memory_map_cmd(obj, cls, iface, access_flags, recurse_flags,
                          max_regions, exclude_arg, start, end, True, substr, *simple_atoms)

cli.new_command('memory-map',
                memory_map_cmd_global,
                args=memory_map_global_args,
                dynamic_args=("-add-atoms", atom_args),
                **memory_map_common_args)


for ifc in [simics.TRANSLATOR_INTERFACE,
            simics.TRANSACTION_TRANSLATOR_INTERFACE]:
    cli.new_command('memory-map',
                    memory_map_cmd_local,
                    args=memory_map_ns_args, iface=ifc,
                    dynamic_args=("-add-atoms", atom_args),
                    **memory_map_common_args)


# Legacy method, used by Eclipse, TCF and UEFI tracker
# Returns a list of devices mapped into obj, which is assumed to be a
# memory space, sorted by base address, and a boolean indicating
# whether or not the map may be incomplete due to use of the
# 'translate' interface. Each entry in the map is a list of the form:
# [ start, end, object, port, function, warn_translator, warn_no_map,
# offset ].
def get_mapped_devices(obj=None):
    if obj:
        map_list = cli.global_cmds.memory_map(object=obj)
    else:
        try:
            map_list = cli.global_cmds.memory_map()
        except cli.CliError:
            map_list = []

    # convert to legacy format
    devs = []
    for (base, top, device, offset, access) in map_list:
        (obj, port) = device if isinstance(device, list) else (device, None)
        devs.append([base, top, obj, port, 0, False, False, offset])

    return [devs, False]


#
# -------------------- map --------------------
#

def objname(obj):
    if not isinstance(obj, simics.conf_object_t):
        (obj, port) = obj
        if port:
            return obj.name + ":" + port
    return obj.name

def map_cmd(space):
    def map_key(m):
        # NB: the function is called for both {memory/port}-space map entries.
        # Priority is ignored since we anyway don't analyze entries overlaps.
        return (m[0], m[4])  # base and length
    def b_swap(bs):
        if bs == simics.Sim_Swap_Bus:
            return "bus"
        elif bs == simics.Sim_Swap_Trans:
            return "trans"
        elif bs == simics.Sim_Swap_Bus_Trans:
            return "bus-trans"
        else:
            return ""
    def tgtname(tgt):
        return objname(tgt) if tgt else ""
    def val_empty(val):
        return val if val else ""

    props  = [(Table_Key_Columns,
               [[(Column_Key_Name, "Base"), (Column_Key_Int_Radix, 16),
                 (Column_Key_Alignment, "right")],
                [(Column_Key_Name, "Object"), (Column_Key_Alignment, "left")],
                [(Column_Key_Name, "Fn"), (Column_Key_Alignment, "right")],
                [(Column_Key_Name, "Offset"), (Column_Key_Int_Radix, 16),
                 (Column_Key_Alignment, "right")],
                [(Column_Key_Name, "Length"), (Column_Key_Int_Radix, 16),
                 (Column_Key_Alignment, "right")],
                [(Column_Key_Name, "Target"), (Column_Key_Alignment, "left")],
                [(Column_Key_Name, "Prio"), (Column_Key_Int_Radix, 10)],
                [(Column_Key_Name, "Align"), (Column_Key_Int_Radix, 10)],
                [(Column_Key_Name, "Swap"), (Column_Key_Alignment, "left")]
               ])]
    data   = []
    spacemap = sorted(space.map, key = map_key)
    for line in spacemap:
        (base, obj, fn, offs, length) = line[:5]
        if len(line) > 5:
            (target, prio, alsize, bswap) = line[5:]
        else:
            target = prio = alsize = bswap = 0
        data.append([int(base), objname(obj), val_empty(fn), int(offs),
                     int(length), tgtname(target), int(prio),
                     val_empty(alsize), b_swap(bswap)])

    try:
        deftarg = space.default_target
        if deftarg:
            obj, fn, offs, tgt = deftarg[:4]
            data.append(["-default-", objname(obj), val_empty(fn),
                         int(offs), "", tgtname(tgt), "", "", ""])
    except AttributeError:
        pass

    tbl = table.Table(props, data)
    output = tbl.to_string(rows_printed=0, no_row_column=True)
    return cli.command_verbose_return(message=output, value=spacemap)

new_command("map", map_cmd,
            [],
            cls = "memory-space",
            type = ["Memory", "Configuration", "Inspection"],
            short = "print memory map",
            see_also = ['<memory-space>.add-map', '<memory-space>.del-map',
                        'memory-map'],
            doc = """
Prints the memory map of the memory space object.

One line per entry in the map attribute of the memory space is printed.
The <em>base</em> column is the starting address of the map.
The <em>object</em> column contains the object mapped at that address.
The <em>fn</em> is the function number (deprecated - should be zero in all new
devices).
The <em>offset</em> is the offset for the object and the <em>length</em>
is the number of bytes mapped.
If the line is a translator, space-to-space, or bridge mapping,
the <em>target</em> is the destination object of the mapping.
The <em>prio</em> is the optional value of precedence.
The <em>align</em> is the optional align-size value.
The <em>swap</em> is the optional byte-swap value which can be "bus",
"bus-trans" or "trans". "Bus" swaps data based on the align-size setting,
while "trans" swaps data based on access size, and "bus-trans" is a
combination of the two. See <cite>Model Builder User's Guide</cite> for more
information.

If a <em>default target</em> has been set it is displayed at the final line.
""")

new_command("map", map_cmd,
            [],
            cls = "port-space",
            short = "print port map",
            type = ["Memory", "Configuration", "Inspection"],
            see_also = ['<port-space>.add-map', '<port-space>.del-map',
                        'memory-map'],
            doc = """
Prints the memory map of the memory space object.

One line per entry in the map attribute of the memory space is printed.
The <em>base</em> column is the starting address of the map.
The <em>object</em> column contains the object mapped at that address.
The <em>fn</em> is the function number (deprecated - should be zero in all new
devices).
The <em>offset</em> is the offset for the object and the <em>length</em>
is the number of bytes mapped.
""")

def check_overlaps_cmd(mem):

    # output data
    out_data = []

    # memory-space: base, object / port, function, offset, len, target, priority, align, byte-swap
    memspace_index = namedtuple('memspace_index', ['adr',
                                                   'obj',
                                                   'func',
                                                   'offs',
                                                   'len',
                                                   'targ',
                                                   'prio',
                                                   'align',
                                                   'swap'])

    grouped = defaultdict(list)

    for raw in mem.map:
        i = memspace_index(*raw)
        # group by priority, we only want to check for the same priority
        grouped[i.prio].append(i)

    # sort each priority group by address
    for x in grouped:
        grouped[x] = sorted(grouped[x], key=lambda y: y[0])

    # for every priotiry group
    for (x, group) in grouped.items():
        # check every memory-space in group, for gaps or overlaps
        for i in range(len(group) - 1):
            if (group[i].adr + group[i].len) > group[i + 1].adr:
                # format output data
                out_data.append(["OVERLAPPING",
                                 objname(group[i].obj),
                                 hex(group[i].adr),
                                 hex(group[i].len),
                                 objname(group[i + 1].obj),
                                 hex(group[i + 1].adr),
                                 hex(group[i + 1].len),
                                 group[i].prio])

    if not out_data:
        msgstring = "No issues with the selected filter."
        return cli.command_return(message=msgstring, value=[])

    # setup readable table output
    header = [("Issue", "left"),
              ("Name #1", "left"),
              ("Offset #1", "right"),
              ("Length #1", "right"),
              ("Name #2", "left"),
              ("Offset #2", "right"),
              ("Length #2", "right"),
              ("Prio", "right")]

    properties = [(table.Table_Key_Columns,
                [[(table.Column_Key_Name, n),
                    (table.Column_Key_Alignment, a)]
                    for (n, a) in header])]

    result_table = table.Table(properties, out_data)
    msgstring = result_table.to_string(rows_printed=0, no_row_column=True)

    return cli.command_return(message=msgstring, value=out_data)

new_command("check-overlaps", check_overlaps_cmd,
            [],
            short = 'check memory space overlaps',
            type = ["Memory"],
            cls = "memory-space",
            see_also = ['probe-address'],
            doc = ('The command will go through the memory-space and check for overlaps '
                  'given addresses and lengths for the same priority levels.'))

#
# add-map / del-map in memory-space
#

swap_names = {
    'none': simics.Sim_Swap_None,
    'bus': simics.Sim_Swap_Bus,
    'bus-trans': simics.Sim_Swap_Bus_Trans,
    'trans': simics.Sim_Swap_Trans,
}

def add_map_cmd(space, obj, base, length, fn, offset, target,
                pri, align_size, swap):
    o, port = obj
    objectname = "%s:%s" % (o.name, port) if port else o.name

    if port and fn != 0:
        raise cli.CliError("The function number must be 0 if a port is given")
    if base + offset >= 2**64:
        raise cli.CliError("Sum of 'base' and 'offset' is 2^64 or larger")

    if swap not in swap_names:
        raise cli.CliError("Unknown byte swapping requested: '%s'" % (swap,))

    try:
        space.map.append([base, obj, fn, offset, length, target, pri,
                          align_size, swap_names[swap]])
    except simics.SimExc_General as ex:
        raise cli.CliError("Failed mapping '%s' in '%s': %s" % (
                objectname, space.name, ex))
    return cli.command_return("Mapped '%s' in '%s' at address 0x%x." % (
            objectname, space.name, base))

def swap_expander(comp):
    return cli.get_completions(comp, swap_names)

new_command("add-map", add_map_cmd,
            [arg(obj_t('object', want_port = True), 'device'),
             arg(uint64_t, 'base'),
             arg(uint64_t, 'length'),
             arg(int_t, 'function', '?', 0),
             arg(uint64_t, 'offset', '?', 0),
             arg(obj_t('object'), 'target', '?', None),
             arg(sint16_t, 'priority', '?', 0),
             arg(uint64_t, 'align-size', '?', 0),
             arg(str_t, 'swap', '?', 'none', expander = swap_expander)],
            cls = "memory-space",
            type = ["Memory", "Configuration"],
            see_also = ['<memory-space>.map', '<memory-space>.del-map'],
            short = "map device in a memory-space",
            doc = """
Map <arg>device</arg> into a memory-space at address <arg>base</arg> and with
length <arg>length</arg>.

The <arg>device</arg> parameter specifies the object
to map. It can be a device object, a port object of a device (for a DML device,
it is usually a bank object having the <obj>object.bank.&lt;bank_name&gt;</obj>
name), or another memory space. The <arg>device</arg> argument in the legacy
form <i>device</i>:<i>port</i> can be used to map named ports.
Providing <arg>function</arg> maps a legacy device-specific
function in the <arg>device</arg>; <arg>function</arg> should
never be specified for port objects or named ports.

For translator and bridge mappings, a <arg>target</arg> device should be given.

The mapping may specify an offset into the device's memory space, using the
<arg>offset</arg> argument.

If several mappings overlap, the <arg>priority</arg> is used to select
the mapping that will receive the memory accesses. The priority is an
integer between -32768 and 32767; lower numbers have higher priority.

For objects that do not support large accesses, the <arg>align-size</arg>
argument governs how accesses are split before the device is accessed. The
default value is 4 bytes for port-space devices and 8 bytes for other devices,
but it is not used for memories and memory-space objects (unless set explicitly).

A device mapping
may swap the bytes of an access based on the <arg>swap</arg> argument, that
should be one of <tt>none</tt>, <tt>bus</tt>, <tt>bus-trans</tt> and
<tt>trans</tt>. For a description of these, see the documentation of the
<attr>map</attr> attribute in the <class>memory-space</class> class.
""")

def map_match(o, port, fn, base, mapentry):
    "Return if obj and mapentry describe the same object/port combination"
    mapbase, mapobj, mapfn = mapentry[0:3]
    if isinstance(mapobj, simics.conf_object_t):
        mapport = None
    else:
        (mapobj, mapport) = mapobj
    return ((o, port) == (mapobj, mapport)
            and (fn == -1 or fn == mapfn)
            and (base == -1 or base == mapbase))

def memory_space_del_map_cmd(space, obj, fn, base):
    o, port = obj
    objectname = "%s:%s" % (o.name, port) if port else o.name

    base = -1 if base is None else base
    oldmap = space.map
    newmap = [x for x in oldmap if not map_match(o, port, fn, base, x)]

    nmatches = len(oldmap) - len(newmap)
    if nmatches == 0:
        return cli.command_return("No matching mappings in %s." % (space.name,),
                              nmatches)

    try:
        space.map = newmap
    except Exception as ex:
        raise cli.CliError("Failed removing mappings for '%s' from '%s': %s" % (
                objectname, space.name, ex))

    func_str = "" if fn == -1 else "%d " % fn
    addr_str = "" if base == -1 else "at %s " % number_str(base, radix = 16)

    if nmatches == 1:
        count_str = "the mapping"
    elif fn == -1 and base == -1:
        count_str = "all %d mappings" % nmatches
    else:
        count_str = "%d mappings" % nmatches

    return cli.command_return("Removed %s %sof '%s' %sfrom '%s'." % (
            count_str, func_str, objectname, addr_str, space.name),
                          nmatches)

def non_namespace_objname(obj):
    if not cli.get_component_path():
        return objname(obj)
    if not isinstance(obj, simics.conf_object_t):
        (obj, port) = obj
    else:
        port = None
    if port:
        return (obj.name.partition(cli.current_namespace() + ".")[2]
                + ":" + port)
    else:
        return obj.name.partition(cli.current_namespace() + ".")[2]

def ms_mapped_objs_expander(comp, space):
    objs = {objname(x[1]) for x in space.map}
    objs |= {non_namespace_objname(x[1]) for x in space.map}
    return get_completions(comp, objs)

new_command("del-map", memory_space_del_map_cmd,
            [arg(obj_t('object', want_port = True), 'device',
                 expander = ms_mapped_objs_expander),
             arg(int_t, 'function', '?', -1),
             arg(uint64_t, 'base', '?')],
            cls = "memory-space",
            type = ["Memory", "Configuration"],
            see_also = ['<memory-space>.map', '<memory-space>.add-map'],
            short = "remove device map from a memory-space",
            doc = """
Remove the mapping of <arg>device</arg> from a memory-space.

The <arg>device</arg> argument is the same as in
the <cmd class="memory-space">add-map</cmd> command. Please find
the argument's description in the documentation of the latter command.

If a function number is given by the <arg>function</arg> argument,
then only mappings with a matching number are removed.

If a <arg>base</arg> address is specified, only mappings with the matching
address are removed.

If both <arg>function</arg> and <arg>base</arg> address are specified, only
mappings with a matching function number, at the specified address,
are removed.

When used in an expression, the command returns the number of removed mappings.""")

#
# add-map / del-map for port-space
#

def add_portmap_cmd(space, object, base, length, fn, offset):
    o, port = object
    if port:
        objectname = "%s:%s" % (o.name, port)
    else:
        objectname = o.name

    if base + offset >= 2**64:
        raise cli.CliError("Sum of 'base' and 'offset' is 2^64 or larger")
    if length > 4:
        raise cli.CliError("Failed mapping '%s' in '%s': "
                       % (objectname, space.name)
                       + "Length of mapping (0x%x) larger than 4" % length)

    if port and fn != 0:
        raise cli.CliError("The function number must be 0 if a port is given")

    try:
        space.map += [[base, object, fn, offset, length]]
    except Exception as ex:
        raise cli.CliError("Failed mapping '%s' in '%s': %s" % (objectname,
                                                            space.name, ex))
    else:
        simics.SIM_log_info(
            1, space, 0, "Mapped '%s' in '%s' at address 0x%x." %
            (objectname, space.name, base))

new_command("add-map", add_portmap_cmd,
            [arg(obj_t('object', want_port = True), 'device'),
             arg(uint16_t, 'base'),
             arg(uint16_t, 'length'),
             arg(int_t, 'function', '?', 0),
             arg(uint64_t, 'offset', '?', 0)],
            cls = "port-space",
            type = ["Memory", "Configuration"],
            see_also = ['<port-space>.map', '<port-space>.del-map'],
            short = "map device in a port-space",
            doc = """
Map <arg>device</arg> into a port-space at address <arg>base</arg> and with
length <arg>length</arg>. Different mappings of the same device may be
identified by a device specific <arg>function</arg> number. The mapping may
specify an offset into the device's memory space, using the <arg>offset</arg>
argument.
""")

def port_space_del_map_cmd(space, object, fn, base):
    o, port = object
    if port:
        objectname = "%s:%s" % (o.name, port)
    else:
        objectname = o.name

    map = [x for x in space.map if not map_match(o, port, fn, base, x)]
    if len(map) == len(space.map):
        print("No matching mappings in %s." % (space.name))
        return
    space.map = map
    try:
        space.map = map
        if fn == -1:
            print("Removing all mappings of '%s' from '%s'." % (objectname,
                                                                space.name))
        else:
            print("Removing mapping %d of '%s' from '%s'." % (fn, objectname,
                                                              space.name))
    except Exception as ex:
        print("Failed removing mappings for '%s' from '%s': %s" % (objectname,
                                                                   space.name,
                                                                   ex))

def ps_mapped_objs_expander(comp, space):
    objs = [x[1][0].name if isinstance(x[1], list) else x[1].name
            for x in space.map]
    return cli.get_completions(comp, objs)

new_command("del-map", port_space_del_map_cmd,
            [arg(obj_t('object', want_port = True), 'device',
                 expander = ps_mapped_objs_expander),
             arg(int_t, 'function', '?', -1),
             arg(uint16_t, 'base', '?', -1)],
            cls = "port-space",
            type = ["Memory", "Configuration"],
            see_also = ['<port-space>.map', '<port-space>.add-map'],
            short = "remove device map from a port-space",
            doc = """
Remove the mapping of <arg>device</arg> from a port-space. If a function number
is given by the <arg>function</arg> argument, then only mappings with a
matching number is removed.

If a <arg>base</arg> address is specified, only mappings with the matching
address are removed.
""")
