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

import bisect, os, socket, subprocess
import conf, simics
from cli import (
    CliError,
    Just_Left,
    Just_Right,
    arg,
    filename_t,
    flag_t,
    float_t,
    get_completions,
    int_t,
    new_info_command,
    new_status_command,
    new_unsupported_command,
    obj_t,
    print_columns,
    str_t,
    )
import mmap
import struct
from sim_commands import print_table
from simicsutils.host import host_type
from functools import cmp_to_key
from simicsutils.internal import ensure_text

in_testing = False

# Retrieve the name of a symbol. Data is the mapped file data, name is
# the name field of the symbol, and str_table_start is start index of
# the string table in the data.
def retrieve_symbol_name(data, name, str_table_start):
    (flag, offset) = struct.unpack("<II", name)
    if flag == 0:
        # If the lowest 4 bytes of the name field are 0, then the
        # higher 4-bytes value is the offset to the string
        # table. Otherwise the 8 bytes is UTF-8 encoded symbol name
        # for the symbol (Microsoft Portable Executable and Common
        # Object File Format spec page 59).
        end = data.find(b"\0", str_table_start + offset)
        return data[str_table_start + offset : end]
    else:
        return name.split(b"\0", 1)[0]

# Return a list of (virtual_offset, characteristic) for all sections.
def parse_section_header(data, sec_num, section_header_start):
    sections = []
    for i in range(sec_num):
        # Each section entry is 40 bytes.
        ofs = section_header_start + i * 40
        (_, _, vma, _, _, _, _, _, _, cha) = struct.unpack(
            "<QIIIIIIHHI", data[ofs : ofs + 40])
        sections.append((vma, cha))
    return sections

# Return a list of (v, n) pairs, where v is the symbol value and n is
# the function symbol name.
def parse_symbol_table(data, sections, num_syms,
                       sym_table_start, str_table_start):
    sym_table = []
    num_of_sec = len(sections)
    for i in range(num_syms):
        # Each entry in the symbol table is 18 bytes.
        ofs = sym_table_start + i * 18
        name = data[ofs : ofs + 8]
        (value, sec_num,
         sym_type, storage_class,
         num_aux) = struct.unpack("<IHHBB", data[ofs + 8 : ofs + 18])
        # The sec_num is one-based index (PE spec, chapter of COFF
        # symbol table).
        if sec_num >= 1 and sec_num <= num_of_sec:
            (vma, characteristic) = sections[sec_num - 1]
            # We check if this symbol lies in an executable
            # section. (PE format spec section 3.1 Section Flags).
            if characteristic & 0x20000020:
                sym_name = retrieve_symbol_name(data, name, str_table_start)
                if not sym_name.startswith(b"."):
                    sym_table.append((value + vma, sym_name))
    return sym_table

# Parse the symbol table for the given DLL file, and return a list of
# (v, n) pairs for function symbols, where n is the name of a
# function, and v is the offset address of the function symbol
# relative to its DLL's base address.
def pe_nm(dll_f_name):
    with open(dll_f_name, "rb") as f:
        data = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        signature_offset = data[0x3c]
        coff_header_offset = signature_offset + 4
        coff_header = data[coff_header_offset : coff_header_offset + 20]
        (_, sec_num, _,
         sym_table_start, num_syms,
         optional_header_size, _) = struct.unpack("<HHIIIHH", coff_header)
        section_header_start = coff_header_offset + 20 + optional_header_size
        sym_table_size = num_syms * 18
        str_table_start = sym_table_start + sym_table_size

        sections = parse_section_header(data, sec_num,
                                        section_header_start)
        sym_table = parse_symbol_table(data, sections, num_syms,
                                       sym_table_start, str_table_start)
        data.close()
    return sym_table

# Read the program header and obtain the base load address of the
# executable section. The base load address is non-zero for prelinked
# libraries. This function raises a CliError exception if it fails to
# find the base load address.
def library_load_base(filename):
    program_header = run_without_stderr(["objdump", "-p", filename])

    lines = program_header.stdout.readlines()

    for (i, line) in enumerate(lines):
        if line.strip().startswith(b"LOAD"):
            # This entry is loadable. Now check the next line to see
            # if this entry is executable.
            try:
                (_, _, _, _, _, mode) = lines[i + 1].split()
                if mode == b"r-x":
                    (_, _, _, _, addr, _, _, _, _) = line.split()
                    return int(addr, 0)
            except (ValueError, IndexError):
                break
    raise CliError("Failed to find the load base address for %s" % filename)

# Parse the symbol table for the given .so file, and returns a list of
# tuples (v, n) for function symbols, where n is the name of a
# function, and v is the offset address of the function symbol
# relative to its .so file's base address.
def elf_nm(filename):
    # For vdso libraries e.g., linux-vdso.so.1 we treat it as it only
    # define one function named vdso.
    if "vdso" in filename:
        return [(0, b"vdso")]

    syms = []
    load_base = library_load_base(filename)
    nm = run_without_stderr(["nm", '--format=sysv', filename])
    for line in nm.stdout:
        cols = line.split(b'|')
        if len(cols) > 3:
            cls = cols[2].strip()
            if cls.upper() == b'T':
                name = cols[0].strip()
                val = int(cols[1], 16)
                # For prelinked libraries, the symbol value is no
                # longer the offset to the base load address. To get
                # the offset, we need to subtract the prelinked load
                # base address of this library from the symbol
                # value. For non-prelinked library the load base is 0.
                syms.append((val - load_base, name))
    return syms

def memoize(f):
    memory = {}
    def memoized(*args):
        if args in memory:
            return memory[args]
        result = f(*args)
        memory[args] = result
        return result
    return memoized

def run_without_stderr(args):
    return subprocess.Popen(args, bufsize = 16384,
                            stdout = subprocess.PIPE,
                            stderr = subprocess.DEVNULL)

@memoize
def read_object_symbols(filename):
    if 'win' in host_type():
        syms = pe_nm(filename)
    else:
        syms = elf_nm(filename)
    return sorted(syms)

def lookup_symbol(filename, ofs):
    syms = read_object_symbols(filename)
    if syms:
        index = bisect.bisect_left(syms, (ofs, b''))
        if index > 0:
            (offset, name) = syms[index - 1]
            return (offset, name)
    return (0, None)

added_symbols = {}
added_index = []

def add_symbol(name, file, start, length):
    if not start in added_symbols:
        bisect.insort(added_index, start)
        added_symbols[start] = (length, name, file)

def lookup_added_symbol(address):
    # check the user added symbols as well if not in a known module
    index = bisect.bisect_left(added_index, address)
    if index > 0:
        start = added_index[index - 1]
        (length, name, file) = added_symbols[start]
        if start <= address and address < start + length:
            return (start, name, file)
    return (0, b'', b'')

# Where modules are located in memory:
# module_file_name -> (base, length) where length is None if unknown.
module_mapping = {}

def find_symbol(address):
    '''return address and name of a function at a given address'''
    if in_testing:
        return test_symbols[address]
    (astart, aname, afile) = lookup_added_symbol(address)
    if astart and aname:
        return (astart, aname, afile)
    # The address is not in the turbo area, continue to lookup in
    # the symbol table of the belonging library.
    try:
        (base, file) = selfprof.lookup[address]
    except simics.SimExc_Attribute:
        return (0, None, None)
    # On linux, the filename name returned by dladdr is ""
    # sometime. So it is kept in the unknown bucket.
    if file.strip() == b"":
        assert 'win' not in conf.sim.host_os
        return (base, None, None)
    if file not in module_mapping:
        # We skip obtaining the code length for non-turbo-area
        # module.
        module_mapping[file] = (base, None)
    (offset, name) = lookup_symbol(file, address - base)
    return (base + offset, name, file)


dummy_addresses = {}
dummy_address = 0

def get_dummy_address(name):
    global dummy_address
    if name in dummy_addresses:
        return dummy_addresses[name]
    dummy_address += 1
    dummy_addresses[name] = dummy_address
    return dummy_address

class arc_sample:
    def __init__(self, dst):
        self.dst = dst
        self.ticks = 0

    def add_tick(self):
        self.ticks += 1

class func_sample:
    def __init__(self, address, name, file):
        self.address = address
        self.name = name
        self.file = file
        self.arcs = {}
        self.ticks = 0
        self.parent_ticks = 0
        self.head = True
        self.parents = 0

    def add_tick(self):
        self.ticks += 1

    def add_parent_tick(self):
        self.parent_ticks += 1

    def adjust_duplicate(self):
        self.parent_ticks -= 1

    def add_arc(self, dst):
        if dst.address in self.arcs:
            arc = self.arcs[dst.address]
        else:
            arc = arc_sample(dst)
            self.arcs[dst.address] = arc
            dst.parents += 1
        arc.add_tick()
        return arc

    def dot_id(self):
        id = "%s_%x" % (self.name, self.address)
        return id.replace('<', '_').replace('>', '_')

class prog:
    def __init__(self):
        self.funcs = {}

    def add_func(self, parent, address, name, file, leaf, node_dup, arc_dup):
        if address in self.funcs:
            func = self.funcs[address]
        else:
            func = func_sample(address, name, file)
            self.funcs[address] = func
        if parent:
            func.head = False
            if not arc_dup:
                parent.add_arc(func)
            parent.add_parent_tick()
        if node_dup:
            func.adjust_duplicate()
        if leaf:
            func.add_tick()
        return func

    def sorted(self, order):
        if order == "ticks":
            key = lambda x: x.ticks
        elif order == "parent_ticks":
            key = lambda x: x.parent_ticks + x.ticks
        else:
            raise ValueError('unknown sort order "%s"' % order)
        return sorted(list(self.funcs.values()), key = key, reverse = True)

prog_info = None

def check_dup_arc(stack, src_start, src, dst):
    for i in range(src_start):
        if stack[i][0] == src and stack[i + 1][0] == dst:
            return True
    return False

def collect_statistics(samples, total):
    global prog_info
    prog_info = prog()
    for raw_stack in samples:
        # keep track of duplicates in the stack-trace since functions should
        # only be counted once
        prev_address = None
        stack = []
        for sample_addr in reversed(raw_stack):
            (addr, name, file) = find_symbol(sample_addr)
            if not addr or not name:
                name = os.path.basename(file) if file else "unknown"
                addr = get_dummy_address(name)
                file = file if file else "unknown"
            if addr == prev_address:
                # remove directly recursive function calls
                continue
            prev_address = addr
            stack.append((addr, name, file))
        dups = set()
        prev = None
        for i, (addr, name, file) in enumerate(stack):
            arc_dup = prev and check_dup_arc(stack, i - 1, prev.address, addr)
            prev = prog_info.add_func(prev, addr, name, file,
                                      leaf = i == len(stack) - 1,
                                      node_dup = (addr in dups),
                                      arc_dup = arc_dup)
            dups.add(addr)
    heads = [f for f in list(prog_info.funcs.values()) if f.head]
    if len(heads) > 1:
        # add a dummy head of there are several top-level ones
        head = prog_info.add_func(None, get_dummy_address("_head_"), "_head_",
                                  "", False, False, False)
        head.parent_ticks = total
        head.head = True
        for h in heads:
            arc = head.add_arc(h)
            arc.ticks = h.parent_ticks + h.ticks
            h.head = False

def function_list(accumulated, total_ticks):
    if accumulated:
        funcs = prog_info.sorted(order = 'parent_ticks')
    else:
        funcs = prog_info.sorted(order = 'ticks')
    ret = []
    total = 0
    for f in funcs:
        value = (f.ticks + f.parent_ticks) if accumulated else f.ticks
        total += value
        if accumulated:
            ret.append([f.name, f.file, value, 100 * value / total_ticks, 0])
        else:
            ret.append([f.name, f.file, value, 100 * value / total_ticks,
                        100 * total / total_ticks])
    if not accumulated and selfprof:
        if total != total_ticks:
            simics.SIM_log_error(selfprof, 0,
                                 "Function ticks != total ticks (%d != %d)"
                                 % (total, total_ticks))
    return ret

printed_nodes = {}
nodes_total = 0

def get_func_info(func, scale, arc_ticks, level, total):
    global nodes_total
    nodes_total += scale * func.ticks
    if scale * (func.parent_ticks + func.ticks) * 100 / total < 0.005:
        return []
    else:
        return [scale * (func.parent_ticks + func.ticks) * 100 / total,
                scale * func.ticks * 100 / total,
                func.name, []]

def get_func_tree(func, scale, arc_ticks, level, total):
    node_ticks = func.parent_ticks + func.ticks
    scale = scale * (arc_ticks / node_ticks)
    if func.address in printed_nodes:
        if printed_nodes[func.address] >= node_ticks:
            # skip recursive once all ticks collected
            return []
    else:
        printed_nodes[func.address] = 0
    printed_nodes[func.address] += scale * node_ticks
    ret = get_func_info(func, scale, arc_ticks, level, total)
    if not ret:
        return []
    arcs = sorted(list(func.arcs.values()), key = lambda x: x.ticks, reverse = True)
    for arc in arcs:
        child = get_func_tree(arc.dst, scale, arc.ticks, level + 1, total)
        if child:
            ret[3].append(child)
    return ret

def get_prog_tree(cutoff, total):
    global printed_nodes, nodes_total
    printed_nodes = {}
    nodes_total = 0
    heads = [f for f in list(prog_info.funcs.values()) if f.head]
    # TODO: It would be better to understand why this happens and
    # print something sensible. See bug 13681.
    if not heads:
        raise CliError("No head found in the call graph")
    elif len(heads) > 1:
        print("WARNING: multiple head nodes found, using the first one only")
    func = heads[0]
    ret = get_func_tree(func, 1, func.parent_ticks, 0, total)
    # make sure all functions have been iterated over
    for f in list(prog_info.funcs.values()):
        if f.address not in printed_nodes:
            print("WARNING %s (%s) not printed" % (f.name, f.file))
    if nodes_total > total:
        print(("WARNING: Collected ticks (%d) > real total (%d)"
               % (nodes_total, total)))
    return ret

handled_nodes = set()

def print_dot_node(dotfile, cutoff, func, merged, total):

    def dot_name(s):
        return s.replace("-", "_").replace(".", "_")

    if func.address in handled_nodes:
        return
    handled_nodes.add(func.address)
    merge_limit = max(cutoff, 0.01)
    if len(func.arcs) == 1 and 100 * func.ticks / total < merge_limit:
        dst = list(func.arcs.values())[0].dst
        if dst.parents == 1 and 100 * dst.ticks / total < merge_limit:
            # merge with next one if single path and low use
            print_dot_node(dotfile, cutoff, dst, merged + [func], total)
            return
    all = 100 * (sum([x.ticks for x in merged])
                 + func.parent_ticks + func.ticks) / total
    local = 100 * (sum([x.ticks for x in merged]) + func.ticks) / total
    label = "\\n".join([x.name for x in merged] + [func.name])
    if merged:
        shape = "shape=box,"
        node_id = merged[0].dot_id()
    else:
        node_id = func.dot_id()
        shape = ""
    dotfile.write('"%s" [%slabel="%s\\n%.2f%% (%.2f%%)",style=bold];\n'
                  % (dot_name(node_id), shape, label, all, local))
    for arc in list(func.arcs.values()):
        arc_weight = 100 * arc.ticks / total
        if arc_weight >= cutoff:
            dotfile.write('"%s" -> "%s" [label="%.2f%%"];\n'
                          % (dot_name(node_id),
                             dot_name(arc.dst.dot_id()),
                             arc_weight))
            print_dot_node(dotfile, cutoff, arc.dst, [], total)

page_sizes = {'A1'      : (23.375, 33.0),
              'A2'      : (16.5,   23.375),
              'A3'      : (11.75,  16.5),
              'A4'      : ( 8.25,  11.75),
              'letter'  : ( 8.5,   11.0),
              'tabloid' : (11.0,   17.0),
              'ANSI-C'  : (17.0,   22.0),
              'ANSI-D'  : (22.0,   34.0)}

page_types = list(page_sizes.keys())

def write_dot_file(filename, cutoff, page_type, landscape, total):
    global handled_nodes
    handled_nodes = set()
    try:
        dotfile = open(filename, "w")
    except Exception as ex:
        raise CliError("Failed opening %s: %s" % (filename, ex))
    x = page_sizes[page_type][int(landscape)]
    y = page_sizes[page_type][1 - int(landscape)]
    dotfile.write('digraph prof {\n'
                  'ranksep=0.3;\n'
                  'size="%.3f,%.3f";\n'
                  'ratio=fill;\n'
                  'fontsize=10;\n'
                  'label="Simics version: %d\\n'
                  'Host: %s (%s-%s)\\n'
                  'Run time: %.2fs"\n'
                  % (x - 1, y - 1, # .5 * 2 margins
                     conf.sim.version,
                     socket.gethostname(),
                     conf.sim.host_arch, conf.sim.host_os,
                     selfprof.total_time))
    heads = [f for f in list(prog_info.funcs.values()) if f.head]
    if len(heads) == 0:
        raise CliError("No selfprof samples found")
    assert len(heads) == 1
    print_dot_node(dotfile, cutoff, heads[0], [], total)
    dotfile.write('}\n')

def attr_get_function_list(data, obj, idx):
    if obj.run:
        simics.SIM_attribute_error("No access allowed when selfprof running")
        return None
    plain = function_list(False, obj.num_samples)
    accum = function_list(True, obj.num_samples)
    ret = []
    for i in range(len(plain)):
        ret.append([plain[i][0], plain[i][1], plain[i][2], accum[i][2]])
    return ret

selfprof = None

def get_object():
    global selfprof
    if not selfprof:
        simics.SIM_register_typed_attribute(
            "selfprof", "function_list",
            attr_get_function_list, None,
            None, None,
            simics.Sim_Attr_Pseudo | simics.Sim_Attr_Internal,
            "[[ssii]*]", None,
            "Internal selfprof attribute")
        selfprof = simics.SIM_create_object("selfprof", "selfprof", [])
    return selfprof

def add_turbo_areas():
    for cl in [simics.SIM_get_class(x) for x in simics.SIM_get_all_classes()
               if hasattr(simics.SIM_get_class(x), 'turbo_code_area')]:
        name = cl.classname.replace("-", "_") + '_turbo_area'
        (base, length) = cl.turbo_code_area
        add_symbol(name, '', base, length)
        if name not in module_mapping:
            module_mapping[name] = (base, length)

#################### Commands

def stop_selfprof_cmd(obj):
    try:
        obj.run = False
        print("Self profiling stopped.")
        print("Profiled CPU time %.2fs. Total %.2fs." % (
            obj.last_time, obj.total_time))
        if obj.buffer_overflow:
            print ("\nWARNING: Sample buffer overflow. The self-profiling "
                   "results will not be accurate. Please rerun the session "
                   "again with a larger sample buffer size.")
        if obj.unknown_cell:
            print ("\nWARNING: Samples received from more cells that selfprof "
                   "was configured for. Make sure that the self-profiling is "
                   "not started until all cells have been created.")
    except Exception as ex:
        raise CliError("Failed stopping self profiling: %s" % ex)
    add_turbo_areas()
    collect_statistics(obj.stack_samples, obj.num_samples)

new_unsupported_command("stop", "selfprof", stop_selfprof_cmd, [],
                        cls = "selfprof",
                        see_also = ['start-selfprof', '<selfprof>.clear',
                                    '<selfprof>.list', '<selfprof>.print-tree',
                                    '<selfprof>.save-graph'],
                        short = "stop self-profiling",
                        doc = """
Stop self-profiling. The profiling run can be resumed again with
<cmd>start-selfprof</cmd>.""")

def clear_selfprof_cmd(obj):
    try:
        obj.init = 0
    except Exception as ex:
        raise CliError("Failed clearing self profiling statistics: %s" % ex)

new_unsupported_command("clear", "selfprof", clear_selfprof_cmd, [],
                        cls = "selfprof",
                        see_also = ['start-selfprof', '<selfprof>.stop',
                                    '<selfprof>.list', '<selfprof>.print-tree',
                                    '<selfprof>.save-graph',
                                    '<selfprof>.save-samples'],
                        short = "clear self-profiling statistics",
                        doc = """
Clear all collected self-profiling statistics.""")

def list_selfprof_cmd(obj, acc, n, func, file, binary_func_file):
    total_ticks = obj.num_samples
    print(("Function                         File                   Ticks"), end=' ')
    if not acc:
        print("        Accum", end=' ')
    print ("\n================================================================"
           "==============")
    func_list = function_list(acc, total_ticks)[0:n]
    if binary_func_file != None:
        binary_output = open(binary_func_file, "w")

    for (name, filename, ticks, part, total) in func_list:
        filename = os.path.basename(filename)
        name = ensure_text(name)
        if ((func and not name.startswith(func))
            or (file and not filename.startswith(file))
            or ticks == 0):
            continue
        if acc:
            print("%-32s %-22s (%5ld = %5.1f%%)" % (
                name, filename, ticks, part))
        else:
            print("%-32s %-22s (%5ld = %4.1f%%) %5.1f%%" % (
                name, filename, ticks, part,  total))
        if binary_func_file != None:
            binary_output.write(repr([name, filename, ticks, part]) + "\n")

    if binary_func_file != None:
        binary_output.close()

new_unsupported_command("list", "selfprof", list_selfprof_cmd,
                        [arg(flag_t, "-a"),
                         arg(int_t, "n", "?", 10),
                         arg(str_t, "func", "?", ""),
                         arg(filename_t(exist = True), "file", "?", ""),
                         arg(filename_t(), "binary-func-file", "?", None),],
                        cls = "selfprof",
                        see_also = ['start-selfprof', '<selfprof>.stop',
                                    '<selfprof>.clear', '<selfprof>.print-tree',
                                    '<selfprof>.save-graph',
                                    '<selfprof>.save-samples'],
                        short = "print self-profiling profile",
                        doc = """
List the <arg>n</arg> most executed functions during the self profiling run,
defaulting to 10. If <tt>-a</tt> is given, list functions in order of
accumulated times (including time spent in callees). If <arg>func</arg> is
given, only list functions whose name start with that string. If
<arg>file</arg> is given, only functions in that file are listed.
If <arg>binary-func-file</arg> is given, output is written to that file.""")

def cell_filter_cmd(obj, cell, all_flag, only_outside_flag, skip_outside_flag):

    args = sum([cell != None, all_flag, only_outside_flag, skip_outside_flag])

    if args > 1:
        raise CliError('Only one flag or cell can be specified')

    if args == 0:               # No args, print current settings
        print("Current cell filtering: ", end=' ')
        if obj.filter_cell:
            print("cell: %s" % (obj.filter_cell.name))
        elif obj.filter_only_outside_cells:
            print("only outside cell samples")
        elif obj.filter_skip_outside_cells:
            print("all cell, without samples outside cells")
        else:
            print("none, all samples shown")
        return

    # Clear all filters
    obj.filter_cell = None
    obj.filter_only_outside_cells = False
    obj.filter_skip_outside_cells = False

    # Set filters according to user args
    if all_flag:
        pass
    elif skip_outside_flag:
        obj.filter_skip_outside_cells = True
    elif only_outside_flag:
        obj.filter_only_outside_cells = True
    elif cell:
        obj.filter_cell = cell

    # Get new samples with filters applied
    collect_statistics(obj.stack_samples, obj.num_samples)

new_unsupported_command("cell-filter", "selfprof", cell_filter_cmd,
                        [arg(obj_t('cell', 'cell'), 'cell', '?'),
                         arg(flag_t, "-all"),
                         arg(flag_t, "-only-outside-cell"),
                         arg(flag_t, "-skip-outside-cell")],
                        cls = "selfprof",
                        see_also = ['start-selfprof', '<selfprof>.stop',
                                    '<selfprof>.list', '<selfprof>.print-tree',
                                    '<selfprof>.save-graph',
                                    '<selfprof>.save-samples'],
                        short = "select only a samples from certain cell",
                        doc = """ Selects the scope of the selfprof data being
 presented. By default, all (<tt>-all</tt>) profile data is used. The
<arg>cell</arg> can be used to restrict the selfprof to only show the
execution identified associated to a particular cell. Profile data
that falls outside of any cell execution can be discarded with the
<tt>-skip-outside-cell</tt> switch. To only look at the profile
outside cells, the <tt>-only-outside-cell</tt> switch can be
used. It is only possible to select one filter at a time. To see
currently active filter, run the command without any arguments.""")

def cell_stat_cmd(obj):
    def compare(x, y):
        if x[1] > y[1]: return -1
        if x[1] < y[1]: return 1
        return 0

    # Get a list from selfprof on which cells and how many samples each have
    l = obj.cell_stat[:]
    tot_samples = sum(s for _,s in l)
    l.sort(key = cmp_to_key(compare))

    print_table(["Cell", "Samples", "%"],
                [[name,
                  "%d" % (samples),
                  "%4.1f%%" % (samples * 100.0 / tot_samples)]
                 for name, samples in l],
                ["left", "right", "right"])

new_unsupported_command("cell-stat", "selfprof", cell_stat_cmd, [],
                        cls = "selfprof",
                        see_also = ['start-selfprof', '<selfprof>.stop',
                                    '<selfprof>.list', '<selfprof>.print-tree',
                                    '<selfprof>.save-graph',
                                    '<selfprof>.save-samples'],
                        short = "Show samples distribution over cells",
                        doc = """
Displays a list of how the samples have been distributed over the cells.
This can be used to identify cells which takes longer than
others to simulate. Execution that falls outside of cell execution is
displayed under the '&lt;outside cells&gt;' name.""")

def save_samples_cmd(obj, filename):
    with open(filename, "w") as f:
        f.write(repr((obj.stack_samples, module_mapping)))

new_unsupported_command("save-samples", "selfprof", save_samples_cmd,
                        [arg(filename_t(), "file")],
                        cls = "selfprof",
                        see_also = ['start-selfprof', '<selfprof>.stop',
                                    '<selfprof>.clear', '<selfprof>.print-tree',
                                    '<selfprof>.save-graph'],
                        short = "save sampled data to a file",
                        doc = """
Save sampled program counters and the locations of loaded modules to
the given <arg>file</arg>.
""")

from symbol_aggregation import name_to_module

def strip_end(s, e):
    if s.endswith(e):
        return s[:len(s) - len(e)]
    else:
        return s

def list_selfprof_aggregate_cmd(obj, print_unknown, binary_module_file):
    total_ticks = obj.num_samples
    func_list = function_list(False, total_ticks)
    module_info = {}
    module_acc = False
    for (name, filename, ticks, part, total) in func_list:
        name = ensure_text(name)
        filename = os.path.basename(filename)
        filename = strip_end(filename, ".so")
        if name.endswith("_turbo_area"):
            module = strip_end(name, "_turbo_area")
            module_area = "JIT code"
        else:
            (module, module_area, match) = name_to_module(name, filename)
            if print_unknown and not match:
                print("Unclassified function %s (%d ticks)" % (name, ticks))
        if not module in module_info:
            module_info[module] = {}
        module_info[module][module_area] = module_info[module].get(module_area, 0) + ticks

    def module_ticks(m):
        t = 0
        for (area, ticks) in module_info[m].items():
            t += ticks
        return t

    def sort_modules_by_ticks(a, b):
        a_ticks = module_ticks(a)
        b_ticks = module_ticks(b)
        if a_ticks < b_ticks:
            return 1
        elif a_ticks > b_ticks:
            return -1
        else:
            return 0
    all_modules = list(module_info.keys())
    all_modules.sort(key = cmp_to_key(sort_modules_by_ticks))
    print_list = []
    acc_module_ticks = 0
    for module in all_modules:
        def sort_areas_by_ticks(a, b):
            if module_info[module][a] < module_info[module][b]:
                return 1
            elif module_info[module][a] > module_info[module][b]:
                return -1
            else:
                return 0
        areas = list(module_info[module].keys())
        areas.sort(key = cmp_to_key(sort_areas_by_ticks))
        mticks = module_ticks(module)
        acc_module_ticks += mticks
        ls = [module, "", "", "", mticks, "%.2f%%" % (mticks * 100.0 / total_ticks)]
        if module_acc:
            ls.append("%.2f%%" % (acc_module_ticks * 100.0 / total_ticks))
        print_list.append(ls)
        if len(areas) > 1 or areas[0] != None:
            for area in areas:
                if area == None:
                    area_name = "other"
                else:
                    area_name = area
                ls = [module, area_name, module_info[module][area], "%.2f%%" % (module_info[module][area] * 100.0 / total_ticks), "", ""]
                if module_acc:
                    ls.append("")
                print_list.append(ls)

    cols = [Just_Left, Just_Left, Just_Left, Just_Right, Just_Left, Just_Right]
    if module_acc:
        cols.append(Just_Right)
    headings = [ "Module", "Part", "Part ticks", "Part %", "Module ticks", "Module %"]
    if module_acc:
        headings.append("Module acc-%")
    print_columns(cols, [headings] + print_list)

    if binary_module_file != None:
        new_print_list = []
        # Remove the empty string in the list
        for entry_list in print_list:
            new_print_list.append([item for item in entry_list if item != ''])

        open(binary_module_file, "w").write(repr(new_print_list))

new_unsupported_command("list-aggregate", "selfprof",
                        list_selfprof_aggregate_cmd,
                        [arg(flag_t, "-u"),
                         arg(filename_t(), "binary-module-file", "?", None),],
                        cls = "selfprof",
                        see_also = ['start-selfprof', '<selfprof>.stop',
                                    '<selfprof>.clear', '<selfprof>.print-tree',
                                    '<selfprof>.save-graph'],
                        short = "print aggregate self-profiling profile",
                        doc = """
            Print aggregate self-profiling profile. If
            <arg>binary-module-file</arg> is given, output is written to this
            file. With <tt>-u</tt> also un-classified functions are
            written.""")

def print_tree_node(level, cutoff, func, do_print,
                    node_total, node_internal, name, nodes):
    if node_total < cutoff:
        return
    if do_print:
        s = "    " * level
        print(s + "%6.2f%%   %6.2f%% %s" % (node_total, node_internal, name))
    for node in nodes:
        print_tree_node(level + int(do_print), cutoff, func,
                        do_print or node[2] == func, *node)

def print_selfprof_tree_cmd(obj, func, cutoff):
    do_print = not bool(func)
    node = get_prog_tree(cutoff, obj.num_samples)
    print_tree_node(0, cutoff, func, do_print or node[2] == func, *node)

new_unsupported_command("print-tree", "selfprof", print_selfprof_tree_cmd,
                        [arg(str_t, "function", "?", None),
                         arg(float_t, "cutoff", "?", 0.0)],
                        cls = "selfprof",
                        see_also = ['start-selfprof', '<selfprof>.stop',
                                    '<selfprof>.clear', '<selfprof>.list',
                                    '<selfprof>.save-graph'],
                        short = "print self-profiling call tree",
                        doc = """
Prints the call tree for <arg>function</arg> and the accumulated time spent in
each function called from this path. <arg>cutoff</arg>, if nonzero, limits the
display to paths where at least <arg>cutoff</arg>% of the time is spent. If
<arg>function</arg> is not given, the complete program tree is printed.
""")

def save_selfprof_graph_cmd(obj, file, cutoff, page_type, fmt):
    if not fmt in ("ps", "pdf"):
        raise CliError('Only "ps" and "pdf" supported as page formats, '
                       'not "%s"' % fmt)
    if page_type[-1] == 'L':
        page_type = page_type[:-1]
        landscape = True
    else:
        landscape = False
    if page_type not in page_types:
        raise CliError("Unknown page type %s, use one of %s"
                       % (page_type,' '.join(page_types)))
    write_dot_file(file +'.dot', cutoff, page_type, landscape, obj.num_samples)
    cp = subprocess.run(
        ['dot', '-T%s' % fmt, '-o', '%s.%s' % (file, fmt), '%s.dot' % file])
    if cp.returncode == 0:
        print("Converted to %s. File: %s.%s" % (fmt.upper(), file, fmt))
    else:
        print("Conversion to %s failed." % fmt.upper())

def ps_expander(comp):
    return get_completions(comp, page_types + [x + 'L' for x in page_types])

def fmt_expander(comp):
    return get_completions(comp, ['pdf', 'ps'])

new_unsupported_command("save-graph", "selfprof", save_selfprof_graph_cmd,
                        [arg(filename_t(), "file"),
                         arg(float_t, "cutoff", "?", 0.0),
                         arg(str_t, "page-size", "?", "A4",
                             expander = ps_expander),
                         arg(str_t, "format", "?", "pdf",
                             expander = fmt_expander)],
                        cls = "selfprof",
                        see_also = ['start-selfprof', '<selfprof>.stop',
                                    '<selfprof>.clear', '<selfprof>.list',
                                    '<selfprof>.print-tree',
                                    '<selfprof>.save-samples'],
                        short = "save self-profiling call graph to file",
                        doc = """
Generates a complete call graph based on the self-profiling information for
Simics and saves it to <arg>file</arg>.dot in the &quot;dot&quot; graph
language file format (<url>http://www.graphviz.org/</url>).

The <arg>page-size</arg> argument specifies the size of the generated
graph and should be one of A4, A3, A2, A1, letter, tabloid, ANSI-C and
ANSI-D. A capital L following the page size indicates landscape,
e.g. A4L.

If the <tt>dot</tt> command line utility is installed on the host, the
graph will also be saved to a PDF or PS file depending on the
<arg>format</arg> argument that can be one of <tt>pdf</tt> and
<tt>ps</tt>.

If <arg>cutoff</arg> is not zero it limits the display to paths where at least
cutoff% of the time is spent.
""")

def time_string(total_seconds):
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return ((('%d min' % minutes) if minutes else '')
            + (' ' if minutes and seconds else '')
            + (('%.2f sec' % seconds) if seconds or not minutes else ''))

def get_info(obj):
    return [('Buffers',
             [('PC Buffers', '%d (%s)' % (
                        obj.sample_buffers,
                        time_string(obj.sample_buffers / 100))),
              ('Stack Buffers', obj.stack_buffers)])]

def get_status(obj):
    if obj.run:
        return [(None, [('Running', 'Yes')])]
    else:
        return [(None,
                 [('Running', 'No'),
                  ('Profiled CPU Time', time_string(obj.total_time))]),
                ('Buffers',
                 [('PC Buffers Used', obj.num_samples),
                  ('Stack Buffers Used', obj.num_stacks),
                  ('Stack Duplicates', obj.stack_duplicates)])]

new_info_command('selfprof', get_info)
new_status_command('selfprof', get_status)

#################### Tests

A = 0x100
B = 0x200
C = 0x300
D = 0x400
E = 0x500
F = 0x600
G = 0x700

test_symbols = {A : (A, 'A', 'test.so'),
                B : (B, 'B', 'test.so'),
                C : (C, 'C', 'test.so'),
                D : (D, 'D', 'test.so'),
                E : (E, 'E', 'test.so'),
                F : (F, 'F', 'test.so'),
                G : (G, 'G', 'test.so')}

test_samples1 = [
    [E, D, B, A],
    [E, D, B, A],
    [E, D, B, A],
    [E, D, C, A],
    [E, D, C, A],
    [E, D, C, A],
    [F, D, B, A],
    [F, D, B, A],
    [F, D, B, A],
    [F, D, B, A],
    [F, D, B, A],
    [F, D, B, A],
    [F, D, C, A],
    [F, D, C, A],
    [F, D, C, A],
    [F, D, C, A],
    [F, D, C, A],
    [F, D, C, A],
       [G, C, A],
       [G, C, A],
       [G, C, A],
       [G, C, A],
       [G, C, A],
       [G, C, A]]

# expected list
test_list1 = [
    ['F', 'test.so', 12, 50.0,  50.0],
    ['E', 'test.so',  6, 25.0,  75.0],
    ['G', 'test.so',  6, 25.0, 100.0],
    ['A', 'test.so',  0,  0.0, 100.0],
    ['B', 'test.so',  0,  0.0, 100.0],
    ['D', 'test.so',  0,  0.0, 100.0],
    ['C', 'test.so',  0,  0.0, 100.0]]

# expected accumulated list
test_list1_acc = [
    ['A', 'test.so', 24, 100.0, 0],
    ['D', 'test.so', 18,  75.0, 0],
    ['C', 'test.so', 15,  62.5, 0],
    ['F', 'test.so', 12,  50.0, 0],
    ['B', 'test.so',  9,  37.5, 0],
    ['E', 'test.so',  6,  25.0, 0],
    ['G', 'test.so',  6,  25.0, 0]]

test_tree1 = [100.0, 0.0, 'A',
              [[62.5, 0.0, 'C',
                [[37.5, 0.0, 'D',
                  [[25.0, 25.0, 'F', []],
                   [12.5, 12.5, 'E', []]]],
                 [25.0, 25.0, 'G', []]]],
               [37.5, 0.0, 'B',
                [[37.5, 0.0, 'D',
                  [[25.0, 25.0, 'F', []],
                   [12.5, 12.5, 'E', []]]]]]]]

# recursive function calls
test_samples2 = [
    [E, C, B, D, C, B, A],
    [E, C, B, D, C, B, A],
    [E, C, B, D, C, B, A],
             [E, C, B, A],
             [E, C, B, A]]

# expected list
test_list2 = [
    ['E', 'test.so', 5, 100.0, 100.0],
    ['A', 'test.so', 0,   0.0, 100.0],
    ['B', 'test.so', 0,   0.0, 100.0],
    ['C', 'test.so', 0,   0.0, 100.0],
    ['D', 'test.so', 0,   0.0, 100.0]]

# expected accumulated list
test_list2_acc = [
    ['A', 'test.so', 5, 100.0, 0],
    ['B', 'test.so', 5, 100.0, 0],
    ['C', 'test.so', 5, 100.0, 0],
    ['E', 'test.so', 5, 100.0, 0],
    ['D', 'test.so', 3,  60.0, 0]]

test_tree2 = [100.0, 0.0, 'A',
              [[100.0, 0.0, 'B',
                [[100.0, 0.0, 'C',
                  [[100.0, 100.0, 'E', []],
                   [60.0,   0.0, 'D', []]]]]]]]

def list_test(acc, total_ticks, expect_list):
    func_list = function_list(acc, total_ticks)
    if func_list != expect_list:
        print("*** Unexpected function list")
        print("Expected:")
        print(expect_list)
        print("Actual:")
        print(func_list)

def tree_test(total_ticks, expect_tree):
    ret = get_prog_tree(0, total_ticks)
    if ret != expect_tree:
        print("*** Unexpected function tree")
        print("Expected:")
        print(expect_tree)
        print("Actual:")
        print(ret)

def run_test(samples, test_list, test_list_acc, test_tree):
    collect_statistics(samples, len(samples))
    list_test(False, len(samples), test_list)
    list_test(True, len(samples), test_list_acc)
    tree_test(len(samples), test_tree)

def do_test():
    global in_testing
    in_testing = True
    try:
        run_test(test_samples1, test_list1, test_list1_acc, test_tree1)
        run_test(test_samples2, test_list2, test_list2_acc, test_tree2)
    finally:
        in_testing = False

do_test()
