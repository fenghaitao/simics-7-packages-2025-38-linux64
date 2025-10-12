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

from simics import (
    SIM_class_has_attribute,
    SIM_create_object,
    SIM_disassemble_address,
    SIM_get_all_classes,
    SIM_object_iterator,
    SIM_get_all_processors,
    SIM_get_class,
    SIM_get_class_attribute,
    SIM_get_object,
    SIM_set_class_attribute,
    SIM_step_count,
    SIM_time,
    SimExc_General,
    VT_get_current_processor,
)
import cli
import conf
import table

import sys
import re
import os
from functools import cmp_to_key

def get_host():
    return conf.sim.host_arch

if get_host() == "x86":
    processor_regexp = re.compile(r"((0x[0-9a-fA-F]+)|([0-9]+))\[esi\]")
    register_regexp = re.compile(r"((0x[0-9a-fA-F]+)|([0-9]+))\[edi\]")
    global_var_regexp = re.compile(r"\[(0x[0-9a-fA-F]+)\]")
    call_regexp = re.compile(r"((call)|(jmp)) (0x[0-9a-fA-F]+)")
    call_regexp_addr = 4
    spill_regexp = re.compile(r"\[esp\]")
    copy_lambda = lambda str: ("mov" in str) and not ("[" in str)
elif get_host() == "x86_64":
    processor_regexp = re.compile(r"\[rbp\+((0x[0-9a-fA-F]+)|([0-9]+))\]")
    register_regexp = re.compile(r"\[r14\+((0x[0-9a-fA-F]+)|([0-9]+))\]")
    global_var_regexp = re.compile(r"\[rip\+((0x[0-9a-fA-F]+))\]")
    call_regexp = re.compile(r"((call)|(jmp)) (0x[0-9a-fA-F]+)")
    call_regexp_addr = 4
    copy_lambda = lambda str: ("mov" in str) and not ("[" in str)
else:
    raise Exception("Unknown host")

def int32(i):
    if i & (1 << 31):
        return -((i ^ 0xffffffff) + 1)
    else:
        return i

def unsignify(a):
    return (int(a >> 4) << 4) | int(a & 0xf)

class turbo_class_info:
    def __init__(self, classname):
        self.processor_name = {}
        self.register_name = {}
        self.call_name = {}
        self.global_name = {}
        self.class_ref = SIM_get_class(classname)
        self.add_offsets()
        self.add_globals()

    def add_offsets(self):
        try:
            for pair in self.class_ref.turbo_processor_offsets:
                self.processor_name[pair[1]] = pair[0]
            for pair in self.class_ref.turbo_register_offsets:
                self.register_name[pair[1]] = pair[0]
            for pair in self.class_ref.turbo_link_targets:
                self.call_name[pair[1]] = pair[0]
        except AttributeError:
            print("Could not get offsets from processor, disassembly will not be nice.")

    def add_globals(self):
        try:
            for pair in self.class_ref.turbo_global_vars:
                self.global_name[pair[1]] = pair[0]
        except AttributeError:
            print("Could not get global var locations, disassembly will suffer.")

class turbo_object_info:
    def __init__(self, obj):
        self.info_virtual_time = 0
        self.info_steps = 0
        self.info_base_turbo_stat = {}

class_info = {}
object_info = {}

def add_class_info(classname):
    global class_info
    if not classname in class_info:
        class_info[classname] = turbo_class_info(classname)

def add_object_info(obj):
    global object_info
    if not obj in object_info:
        object_info[obj] = turbo_object_info(obj)

def turbo_attr(cl, name):
    return SIM_get_class_attribute(cl, name)

def all_turbo_classes():
    seen_turbo_chain = []
    ret = []
    for cl in SIM_get_all_classes():
        if SIM_class_has_attribute(cl, "turbo_execution_mode"):
            link_targets =  turbo_attr(cl, "turbo_link_targets")
            for (name, addr) in link_targets:
                if name == "turbo_chain":
                    if not addr in seen_turbo_chain:
                        seen_turbo_chain.append(addr)
                        ret.append(cl)
    return ret

def add_code_areas():
    # already done in selfprof
    pass

def get_turbo_blocks(classname):
    tmp = SIM_get_class_attribute(classname, "turbo_blocks")
    for i in range(len(tmp)):
        for j in range(len(tmp[i])):
            if j < 7:
                tmp[i][j] = unsignify(tmp[i][j])
    return tmp

def block_sort_ticks(a, b):
    if a[1][6] > b[1][6]:
        return -1
    elif a[1][6] < b[1][6]:
        return 1
    else:
        return 0

def block_sort_target_address(a, b):
    if a[1][2] > b[1][2]:
        return 1
    elif a[1][2] < b[1][2]:
        return -1
    else:
        return 0

def block_sort_host_address(a, b):
    if a[1][0] > b[1][0]:
        return 1
    elif a[1][0] < b[1][0]:
        return -1
    else:
        return 0

def block_profile(n, filename, sort_target_address, target_disassemble, show_host_address, sort_host_address, show_all):
    all_blocks = []
    for cl in all_turbo_classes():
        all_blocks += [[cl, x] for x in SIM_get_class_attribute(cl, "turbo_blocks")]
    if sort_target_address:
        all_blocks.sort(key = cmp_to_key(block_sort_target_address))
    elif sort_host_address:
        all_blocks.sort(key = cmp_to_key(block_sort_host_address))
    else:
        all_blocks.sort(key = cmp_to_key(block_sort_ticks))
    if n >= 0:
        all_blocks = all_blocks[:n]
    if not show_all:
        all_blocks = [x for x in all_blocks if x[1][6] > 0]
    descs = []
    if filename == None and target_disassemble:
        for (classname, block) in all_blocks:
            print("Class: %s Ticks: %d" % (classname, block[6]))
            (num_instr, block_str) = turbo_block_string(block[7], block, False, context=True)
            print(block_str)
    elif filename == None:
        for (classname, block) in all_blocks:
            if show_host_address:
                descs.append([classname, block[7].name, "0x%x" % block[0], "0x%x" % block[1], "0x%x" % block[2], "0x%x" % block[4], block[6]])
            else:
                descs.append([classname, block[7].name, "0x%x" % block[2], "0x%x" % block[4], block[6]])
        if show_host_address:
            cli.print_columns([cli.Just_Left, cli.Just_Left, cli.Just_Left, cli.Just_Left, cli.Just_Left, cli.Just_Left, cli.Just_Left],
                              [ [ "Class", "CPU", "Host address", "Host length", "Virtual address", "Length", "Ticks" ] ] + descs)
        else:
            cli.print_columns([cli.Just_Left, cli.Just_Left, cli.Just_Left, cli.Just_Left, cli.Just_Left],
                              [ [ "Class", "CPU", "Virtual address", "Length", "Ticks" ] ] + descs)
    else:
        get_dis()
        try:
            f = open(filename, "w")
        except IOError as err:
            raise cli.CliError("Failed opening file %s: %s"
                               % (filename, err[1]))
        f.write("<html>\n")
        f.write("<head>\n")
        f.write("<title>Hottest %d turbo blocks</title>\n" % len(all_blocks))
        f.write("</head>\n")
        f.write("<table>\n")
        f.write("<tr> <td><b>Class</b></td> <td><b>CPU</b></td> <td><b>Virtual address</b></td> <td><b>Ticks</b></td> <td><b>Instructions</b></td> <td><b>Bytes</b></td> </tr>\n")
        i = 0
        for (classname, block) in all_blocks:
            has_rregs = classname.startswith("sparc-")
            block_filename = filename + ("_block_%d.html" % i)
            block_f = open(block_filename, "w")
            block_f.write("<html><body>")
            i += 1
            stdout_backup = sys.stdout
            sys.stdout = block_f
            block_info = {}
            try:
                block_info = disassemble_block_block(block, True, False, bold, True, has_rregs)
            finally:
                sys.stdout = stdout_backup
            block_f.write("</body></html>")
            block_f.close()
            if "host instructions" in block_info:
                host_instructions = block_info["host instructions"]
            else:
                host_instructions = 0
            if "host bytes" in block_info:
                host_bytes = block_info["host bytes"]
            else:
                host_bytes = 0
            f.write("<tr> <td>%s</td> <td>%s</td> <td><a href=\"%s\">0x%x</a></td> <td>%d</td> <td>%d</td> <td>%d</td> </tr>\n" % (classname, block[7].name, os.path.basename(block_filename), block[2], block[6], host_instructions, host_bytes))
        f.write("</table>\n")
        f.write("</html>\n")
        f.close()
        print("Profile written (html) to %s." % filename)

cli.new_command("turbo-show-block-profile", block_profile, [cli.arg(cli.int_t, "num", "?", -1),
                                                            cli.arg(cli.filename_t(), "filename", "?", None),
                                                            cli.arg(cli.flag_t, "-sort-target-address"),
                                                            cli.arg(cli.flag_t, "-target-disassemble"),
                                                            cli.arg(cli.flag_t, "-show-host-address"),
                                                            cli.arg(cli.flag_t, "-sort-host-address"),
                                                            cli.arg(cli.flag_t, "-show-all")],
                doc = "List the <arg>num</arg> hottest turbo blocks. The default when <arg>num</arg> is not given is to print all blocks that have been hit by a sample. With <arg>-show-all</arg>, even blocks without ticks are shown.",
                doc_items = [('SEE ALSO', 'turbo-enable-block-profile')])

def enable_block_profile():
    for cl in all_turbo_classes():
        SIM_set_class_attribute(cl, "turbo_enable_block_profile", True)

def disable_block_profile():
    for cl in all_turbo_classes():
        SIM_set_class_attribute(cl, "turbo_enable_block_profile", False)

cli.new_command("turbo-enable-block-profile", enable_block_profile, [],
                doc = "Enable or disable turbo self profiling.",
                doc_items = [('SEE ALSO', 'turbo-show-block-profile')])

cli.new_command("turbo-disable-block-profile", disable_block_profile, [],
                doc_with = "turbo-enable-block-profile")

def turbo_block_string(cpu, b, html, context):
    a = b[3]
    v = b[2]
    num_instr = 0
    str = ""
    instr_after = 0
    if context:
        instr_after = 1
        for i in range(1, 17):
            try:
                int_str = SIM_disassemble_address(cpu, a - i, 0, 0)
                str += "Before "
                str += "v:0x%016lx p:0x%016lx %s\n" % (v - i, a - i, int_str[1])
                if html:
                    str += "<br/>\n"
                break
            except Exception:
                pass
    try:
        while a < b[3]+b[4]+instr_after:
            int_str = SIM_disassemble_address(cpu, a, 0, 0)
            if context:
                context_str = "       "
            else:
                context_str = ""
            if a >= b[3]+b[4]:
                context_str = "After  "
                num_instr -= 1
            str += context_str
            str += "v:0x%016lx p:0x%016lx %s\n" % (v, a, int_str[1])
            if html:
                str += "<br/>\n"
            if int_str[0]:
                a += int_str[0]
                v += int_str[0]
                num_instr += 1
            else:
                str += "Got zero length from SIM_disassemble_address()\n"
                break
    except Exception:
        str += "Got exception on read\n"
    return (num_instr, str)

def get_dis():
    try:
        SIM_get_object("dis")
    except SimExc_General:
        try:
            if get_host() == "x86":
                SIM_create_object("disassemble_x86", "dis")
            elif get_host() == "x86_64":
                SIM_create_object("disassemble_x86", "dis")
            else:
                raise Exception("Unknown host")
        except LookupError:
            raise cli.CliError("Disassembly module not available.")
    if get_host() == "x86":
        cli.conf.dis.lm64_mode=0
        cli.conf.dis.cs_d=1
        cli.conf.dis.ss_b=1
    elif get_host() == "x86_64":
        cli.conf.dis.lm64_mode=1
        cli.conf.dis.cs_d=1
        cli.conf.dis.ss_b=1
    return SIM_get_object("dis")

def bold(s):
    return cli.format_print("<b>" + s + "</b>")

spill_regexp = 0

def chained_jump_location(cpu, addr):
    for tblock in cpu.turbo_blocks:
        if tblock[0] == addr:
            return (True, tblock[3]) # block physical address
    return (False, None)


def process_disasm_str(cpu, str, next_pc, has_rregs, block):
    chained = False
    match_obj = processor_regexp.search(str)
    if match_obj != None:
        index = int(match_obj.group(1), 0)
        try:
            name = class_info[cpu.classname].processor_name[index]
        except KeyError:
            try:
                name = "hi32(%s)" % class_info[cpu.classname].processor_name[index - 4]
            except KeyError:
                name = index
        str = str[:match_obj.start()] + ("[cpu + %s]" % name) + str[match_obj.end():]
    if register_regexp and has_rregs:
        match_obj = register_regexp.search(str)
    else:
        match_obj = None
    if match_obj != None:
        index = int(match_obj.group(1), 0)
        try:
            name = class_info[cpu.classname].register_name[index]
        except KeyError:
            try:
                name = "hi32(%s)" % class_info[cpu.classname].register_name[index - 4]
            except KeyError:
                name = index
        str = str[:match_obj.start()] + ("[regfile + %s]" % name) + str[match_obj.end():]
    if global_var_regexp:
        match_obj = global_var_regexp.search(str)
    else:
        match_obj = None
    if match_obj != None:
        var_addr = int32(int(match_obj.group(1), 0))
        add_str = ""
        if get_host() == "x86_64":
            add_str = "[rip]"
            var_addr = var_addr + int(next_pc)
        try:
            name = class_info[cpu.classname].global_name[var_addr]
        except KeyError:
            name = "%s (unknown global)" % var_addr
        str = str[:match_obj.start()] + add_str + "[" + name + "]" + str[match_obj.end():]
    if call_regexp:
        match_obj = call_regexp.search(str)
    else:
        match_obj = None
    if match_obj != None:
        addr = int(match_obj.group(call_regexp_addr), 0)

        try:
            name = class_info[cpu.classname].call_name[addr]
        except KeyError:
            (found, dest_pa) = chained_jump_location(cpu, addr)
            if found:
                name = "0x%x (chained jump to p:0x%x)" % (addr, dest_pa)
                chained = True
            else:
                block_start = block[0]
                block_end = block_start + block[1] - 1
                if addr >= block_start and addr <= block_end:
                    name = "0x%x" % (addr,) # Block internal jmp
                else:
                    name = "0x%x (unknown call target)" % (addr,)
        str = str[:match_obj.start()] + match_obj.group(1) + " " + name + str[match_obj.end():]
    if spill_regexp:
        match_obj = spill_regexp.search(str)
    else:
        match_obj = None
    return (str, match_obj != None, copy_lambda(str), chained)

def disassemble_block_block(block, html, text, bold_text, print_block, has_rregs):
    add_class_info(block[7].classname)
    ret = {}
    ret["compile step"] = block[5]
    ret["target bytes"] = block[4]
    if print_block:
        print("Block 0x%x .. 0x%x matched. Compiled at %d." % (block[2], block[2] + block[4] - 1, block[5]))
    if html:
        print("<br/>")
    elif not print_block:
        print("\n")
    if print_block:
        (num_instr, block_str) = turbo_block_string(block[7], block, html, context=False)
    start_addr = block[0]
    indx = 0
    strs = []
    total_instr = 0
    spill_instr = 0
    copy_instr = 0
    while indx < block[1]:
        disasm = cli.conf.dis.disassemble[start_addr + indx]
        (processed_disasm_str, is_spill, is_copy, chained_jmp) = process_disasm_str(
            block[7], disasm[1], start_addr + indx + disasm[0], has_rregs, block)
        dis_str = "0x%x %s" % (start_addr + indx, processed_disasm_str)
        strs.append(dis_str.split())
        indx = indx + disasm[0]
        total_instr += 1
        spill_instr += is_spill
        copy_instr += is_copy
        # print the page offset of the instruction after the chaining
        if "call turbo_chain" in processed_disasm_str or chained_jmp:
            dis_str = "0x%x .data 0x%02x%02x ; page offset for chaining" % (
                start_addr + indx,
                cli.conf.dis.host_byte[start_addr + indx + 1],
                cli.conf.dis.host_byte[start_addr + indx + 0])
            strs.append(dis_str.split())
            indx += 2

    ret["host instructions"] = total_instr
    ret["target instructions"] = num_instr
    if print_block:
        print("%d host instructions / %d target instructions (= %.1f)." % (total_instr, num_instr, total_instr * 1.0 / num_instr))
        if (SIM_class_has_attribute(block[7].classname, "turbo_enable_block_profile") and
            block[7].turbo_enable_block_profile):
            if html:
                print("<br/>")
            (total_ticks, class_turbo_ticks, removed_block_ticks) = block[7].turbo_profile_summary
            if class_turbo_ticks == 0:
                of_class_ticks = 0
            else:
                of_class_ticks = block[6] * 100.0 / class_turbo_ticks
            if total_ticks == 0:
                of_total_ticks = 0
            else:
                of_total_ticks = block[6] * 100.0 / total_ticks
            print("%d profile ticks, %.2f%% of class turbo ticks, %.2f%% of all ticks." % (block[6], of_class_ticks, of_total_ticks))
            ret["ticks"] = block[6]
        if html:
            print("<br/>")
        else:
            print()
        if html:
            print("<tt>")
        print(block_str)
    for str in strs:
        is_label = 0
        for s in strs:
            for w in s[1:]:
                if str[0] == w:
                    is_label = 1
        if is_label:
            if html:
                cli.pr("<b>%s</b>" % str[0])
            elif not text:
                bold_text(str[0])
            else:
                cli.pr(str[0])
        else:
            cli.pr(str[0])
        cli.pr("  ")
        for d in str[1:]:
            is_addr = 0
            for s in strs:
                if s[0] == d:
                    is_addr = 1
            if is_addr:
                if html:
                    cli.pr("<b>%s</b> " % d)
                elif not text:
                    bold_text("%s " % d)
                else:
                    cli.pr("%s " % d)
            else:
                cli.pr("%s " % d)
        cli.pr("\n")
        if html:
            print("<br/>")
    if html:
        print("</tt>")
    if total_instr:
        spill_perc = spill_instr * 100.0 / total_instr
        copy_perc = copy_instr * 100.0 / total_instr
    else:
        spill_perc = 0
        copy_perc = 0
    print("%d instructions, %d bytes, %d spill instructions %.2f%%, %d copy instructions %.2f%%" % (total_instr, block[1], spill_instr, spill_perc, copy_instr, copy_perc))
    ret["host bytes"] = block[1]
    ret["spill instructions"] = spill_instr
    ret["copy instructions"] = copy_instr
    return ret

def dump_profile_information(profiler, filename):
    view = 0
    f = open(filename, "w")
    addr_bits = profiler.iface.address_profiler.address_bits(view)
    last_addr = (1 << addr_bits) - 1
    for (count, addr) in profiler.iface.address_profiler.iter(view, 0, last_addr):
        if count != 0:
            f.write("0x%x %d\n" % (addr, count))
    f.close()
    print("Profile information written to '%s'" % filename)

def instruction_status(cpu, target_pc, pc_is_virtual):
    blocks = get_turbo_blocks(cpu.classname)
    entry_point = False
    jitted = False
    if pc_is_virtual:
        addr_index = 2
    else:
        addr_index = 3
    for block in blocks:
        if target_pc == block[addr_index]:
            entry_point = True
        if target_pc >= block[addr_index] and target_pc < block[addr_index] + block[4]:
            jitted = True
    return (entry_point, jitted)

def dump_profile_status(profile_filename, status_filename):
    cpu = VT_get_current_processor()
    f = open(profile_filename, "r")
    fo = open(status_filename, "w")
    for l in f:
        s = l.split()
        addr = int(s[0], 16)
        count = int(s[1])
        if (addr & 3) == 0:
            (size, disasm) = SIM_disassemble_address(cpu, addr, 0, 0)
            (entry_point, jitted) = instruction_status(cpu, addr, False)
            if size > 0:
                fo.write("0x%x %d %s %s %s\n" % (addr, count, (".", "E")[entry_point], (".", "T")[jitted], disasm))
    f.close()
    fo.close()

def disassemble_block(cpu, target_pc, host_pc, html, text, filename, no_bold,
                      all, start_time):
    get_dis()
    if html:
        if filename == None:
            filename = "block.html"
        try:
            f = open(filename, "w")
        except IOError as ex:
            raise cli.CliError("Failed opening file: %s" % ex)
        stdout_backup = sys.stdout
        sys.stdout = f
    elif text:
        if filename == None:
            filename = "block.txt"
        try:
            f = open(filename, "w")
        except IOError as ex:
            raise cli.CliError("Failed opening file: %s" % ex)
        stdout_backup = sys.stdout
        sys.stdout = f
    if no_bold:
        bold_text = cli.pr
    else:
        bold_text = bold
    blocks = get_turbo_blocks(cpu.classname)
    if html:
        print("<html><body>")
    has_rregs = cpu.classname.startswith("sparc-")
    for block in blocks:
        if (start_time == None or block[5] >= start_time) and (all or (host_pc == -1 and target_pc >= block[2] and target_pc < block[2] + block[4]) or (host_pc != -1 and host_pc >= block[0] and host_pc < block[0] + block[1])):
            disassemble_block_block(block, html, text, bold_text, 1, has_rregs)
    if html:
        print("</body></html>")
    if html or text:
        sys.stdout = stdout_backup
        f.close()

def turbo_disassemble_block(cpu, pc, host_addr, filename, start_time, all,
                            html, text, no_bold):
    add_class_info(cpu.classname)
    if pc != -1 and host_addr != -1:
        raise cli.CliError("Both logical and host address specified.")
    if pc == -1 and host_addr == -1:
        pc = cpu.iface.processor_info.get_program_counter()
    disassemble_block(cpu, pc, host_addr, html, text, filename, no_bold, all,
                      start_time)

cli.new_command("disassemble-block", turbo_disassemble_block, [
    cli.arg(cli.int_t, "addr", "?", -1),
    cli.arg(cli.int_t, "host_addr", "?", -1),
    cli.arg(cli.filename_t(), "filename", "?", None),
    cli.arg(cli.int_t, "start_time", "?", None),
    cli.arg(cli.flag_t, "-a"),
    cli.arg(cli.flag_t, "-h"),
    cli.arg(cli.flag_t, "-t"),
    cli.arg(cli.flag_t, "-r")],
                iface = "processor_info",
                doc = "Disassemble blocks with given address. With the <arg>-a</arg> flag all blocks compiled no earlier than <arg>start_time</arg> are disassembled. The <arg>-h</arg> flag disassembles the block to <arg>filename</arg> (or block.html in the current directory if no filename is given). Similarly, <arg>-t</arg> disassembles in text format to a file (default block.txt). If neither <arg>-h</arg> nor <arg>-t</arg> is given, the disassembly will be directly in the Simics window.")

# Check if the stored turbo entry points are valid (can be found in
# turbo_blocks) for all the entries in TEC.
def check_tec_against_turbo_block(tecs, turbo_blocks):
    alive_turbo_blocks = [entry[0] for entry in turbo_blocks]
    invalid_entry_points = []
    for tec in tecs:
        t = [(x[0], x[1]) for x in tec]
        for (vaddr, jit_entry_point) in t:
            if jit_entry_point not in alive_turbo_blocks:
                invalid_entry_points.append((vaddr, jit_entry_point))

    if len(invalid_entry_points) == 0:
        print ("All TEC entries have been successfully validated"
               " against turbo_blocks.")
        return True

    print ("The following TEC entries contains JIT entry points"
           " not found in turbo_blocks:")

    for (vaddr, entry_point) in invalid_entry_points:
        print("(0x%x, 0x%x)" % (vaddr, entry_point))
    return False

# Check if the stored turbo entry points are valid (can be found in PISTC)
# for all the entries in TEC.
def check_tec_against_pistc(tecs, pistcs, icode_page_size_log2):

    def get_page_addr(vaddr):
        return (vaddr >> icode_page_size_log2) << icode_page_size_log2

    # Returns all pistc mappings matching address
    def get_pistc_mappings(t_indx, address):
        return [x for x in pistcs[t_indx] if x[0] == address]

    invalid_entry_points = []
    for (i, tec) in enumerate(tecs):
        for entry in tec:
            (vaddr, jit_entry_point) = (entry[0], entry[1])
            paddr = get_page_addr(vaddr)
            m = get_pistc_mappings(i, paddr)

            if len(m) == 0:
                # TEC address not found in PISTC (page address)
                invalid_entry_points.append((i, vaddr, jit_entry_point))
            else:
                if len(m) > 1:
                    # Multiple mappings in PISTC (pistc error, not TEC error)
                    print("multiple mappings in PISTC for address %x: %d:" % (
                        paddr, len(m)), m)
                if len(entry) == 3:    # only for x86 PISTC
                    # Make sure the icode_block_t * is the same in PISTC and TEC
                    icb = entry[2]
                    first_pistc_map = m[0]
                    if first_pistc_map[1] != icb:
                        invalid_entry_points.append((i, vaddr, jit_entry_point))

    if len(invalid_entry_points) == 0:
        print ("All TEC entries have been successfully validated"
               " against PISTC.")
        return True

    print ("The following TEC entries contain JIT entry points"
           " not found in PISTC:")

    for (idx, vaddr, entry_point) in invalid_entry_points:
        print("(%d: 0x%x, 0x%x)" % (idx, vaddr, entry_point))

    return False



def check_pistc(cpu):
    if not hasattr(cpu, "pistc"):
        print("%s: No PISTC" % (cpu.name,))
        return

    pistc = cpu.pistc
    passed = True
    for (t, pistc_table) in enumerate(pistc):
        va_set = set()   # virtual address set
        for (va, _) in pistc_table:
            if va in va_set:
                print("Table %d: already had 0x%x mapped" % (t, va))
                passed = False
            else:
                va_set.add(va)

    if not passed:
        raise cli.CliError("PISTC check failed.")

def check_pistc_all():
    fail = False
    for cpu in SIM_get_all_processors():
        print("Check PISTC for cpu %s" % cpu.name)
        try:
            check_pistc(cpu)
        except cli.CliError:
            fail = True
    if fail:
        raise cli.CliError("PISTC check failed.")


def check_tec(cpu):
    if not hasattr(cpu, "tec"):
        print("%s: No Turbo Entry Cache (TEC)" % (cpu.name,))
        return

    tecs = cpu.tec
    turbo_pass = check_tec_against_turbo_block(tecs, cpu.turbo_blocks)
    pistc_pass = check_tec_against_pistc(tecs, cpu.pistc,
                                         cpu.icode_page_size_log2)
    if (not turbo_pass) or (not pistc_pass):
        raise cli.CliError("TEC check failed.")

def check_tec_all():
    fail = False
    for cpu in SIM_get_all_processors():
        print("Check TEC for cpu %s" % cpu.name)
        try:
            check_tec(cpu)
        except cli.CliError:
            fail = True
    if fail:
        raise cli.CliError("TEC check failed.")

def tec_stats(cpu):
    if not hasattr(cpu, "tec"):
        print("%s: No Turbo Entry Cache (TEC)" % (cpu.name,))
        return
    tec = cpu.tec
    valid_entries = []

    for tec_table in tec:
        valid_entries.append(len(tec_table))
    print("%s: %r" % (cpu.name, valid_entries))

def tec_stats_all():
    for cpu in SIM_get_all_processors():
        tec_stats(cpu)


cli.new_command("pistc-check", check_pistc,
                [],
                iface = "processor_info",
                doc = ("Check that there are no duplicate addresses"
                       " in the PISTC")
                )

cli.new_command("pistc-check", check_pistc_all,
                [],
                doc = ("Check that there are no duplicate addresses"
                       " in the PISTC for all cpus.")
                )

cli.new_command("tec-check", check_tec,
                [],
                iface = "processor_info",
                doc = ("Check if the turbo entry cache entries are consistent"
                       " with PISTC and turbo_blocks.")
                )

cli.new_command("tec-check", check_tec_all,
                [],
                doc = ("Check if the turbo entry cache entries are consistent"
                       " with PISTC and turbo_blocks for all cpus.")
                )

cli.new_command("tec-stats", tec_stats,
                [],
                iface = "processor_info",
                doc = ("Display the current population count of the"
                       " turbo entry caches (for each table)."))

cli.new_command("tec-stats", tec_stats_all,
                [],
                doc = ("Display the current population count of the"
                       " turbo entry caches (for each table)"
                       " for all cpus."))

def prefix_table_append(tbl, prefixes, name, val, count_vsecond = None, count_percent = None):
    do_append = 0
    if prefixes == None:
        do_append = 1
    else:
        for prefix in prefixes:
            if name.startswith(prefix):
                do_append = 1
    if do_append:
        if count_vsecond != None:
            tbl.append([name, val, count_vsecond, count_percent])
        else:
            tbl.append([name, val])

def get_turbo_block_info(classname):
    blocks = get_turbo_blocks(classname)
    num_blocks = len(blocks)
    code_size = 0
    for block in blocks:
        code_size += block[1]
    return (num_blocks, code_size)

def turbo_info_class(classname, prefixes=None):
    add_class_info(classname)
    cl = class_info[classname].class_ref

    if SIM_class_has_attribute(cl, "turbo_block_info") and prefixes == None:
        block_info = SIM_get_class_attribute(cl, "turbo_block_info")
        tbl = [["Length", "Traces", "Static blocks", "Dynamic blocks"]]
        for i in range(len(block_info)):
            tbl.append([i, block_info[i][0], block_info[i][1], block_info[i][2]])
        cli.print_columns([cli.Just_Left, cli.Just_Left, cli.Just_Left, cli.Just_Left], tbl)

    (num_blocks, code_size) = get_turbo_block_info(classname)
    tbl = [["Metric", "Count"]]
    prefix_table_append(tbl, prefixes, "JIT blocks", "%d" % num_blocks)
    prefix_table_append(tbl, prefixes, "JIT code size", "%d" % code_size)
    cli.print_columns([cli.Just_Left, cli.Just_Left], tbl)

def turbo_info_object(obj, prefixes=None):
    turbo_info_with_stats(obj, prefixes,
                          obj.turbo_stat if hasattr(obj, 'turbo_stat') else [])

def turbo_info_with_stats(obj, prefixes, obj_turbo_stat):
    add_object_info(obj)
    add_class_info(obj.classname)
    turbo_info_virtual_time_diff = SIM_time(obj) - object_info[obj].info_virtual_time
    turbo_info_steps_diff = SIM_step_count(obj) - object_info[obj].info_steps

    if obj_turbo_stat:
        turbo_stats = {}

        stat = obj_turbo_stat
        for (name, val) in stat:
            if name in turbo_stats:
                turbo_stats[name] += val
            else:
                turbo_stats[name] = val - object_info[obj].info_base_turbo_stat.setdefault(name, 0)

        tbl = [["Metric", "Count", "Count/vsecond", '"%"']]
        keys = sorted(turbo_stats.keys())
        for name in keys:
            val = turbo_stats[name]
            try:
                count_vsecond = "%.2f" % (float(val) / turbo_info_virtual_time_diff)
            except ZeroDivisionError:
                count_vsecond = 0
            try:
                count_percent = "%.4f" % (100.0 * float(val) / turbo_info_steps_diff)
            except ZeroDivisionError:
                count_percent = 0
            prefix_table_append(tbl, prefixes, name, val, count_vsecond, count_percent)
        if ("generated_instructions" in turbo_stats
            and "translated_instructions" in turbo_stats):
            try:
                prefix_table_append(tbl, prefixes, "generated / translated", "%.2f" % (float(turbo_stats["generated_instructions"]) / float(turbo_stats["translated_instructions"])), "", "")
            except ZeroDivisionError:
                pass
        if ("dynamic_instructions" in turbo_stats
            and "trampolines" in turbo_stats):
            try:
                prefix_table_append(tbl, prefixes, "average sequence", "%.2f" % (float(turbo_stats["dynamic_instructions"]) / float(turbo_stats["trampolines"])), "", "")
            except ZeroDivisionError:
                pass
        halt_steps = 0
        if hasattr(obj.iface, "step_info"):
            halt_steps += obj.iface.step_info.get_halt_steps()
        try:
            count_vsecond = "%.2f" % (float(halt_steps) / turbo_info_virtual_time_diff)
        except ZeroDivisionError:
            count_vsecond = 0
        try:
            count_percent = "%.4f" % (100.0 * float(halt_steps) / turbo_info_steps_diff)
        except ZeroDivisionError:
            count_percent = 0
        prefix_table_append(tbl, prefixes, "halt_steps", halt_steps, count_vsecond, count_percent)
        if len(tbl) > 1:
            print("Turbo stats for object: %s" % obj.name)
            cli.print_columns([cli.Just_Left, cli.Just_Left, cli.Just_Left, cli.Just_Left], tbl)

def turbo_info_all(prefixes=None):
    handled = []
    for o in SIM_object_iterator(None):
        if o.classname not in handled:
            handled.append(o.classname)
            if SIM_class_has_attribute(o.classname, "turbo_execution_mode"):
                print("Turbo stats for class: %s" % o.classname)
                turbo_info_class(o.classname, prefixes)
    for o in SIM_object_iterator(None):
        if SIM_class_has_attribute(o.classname, "turbo_execution_mode"):
            turbo_info_object(o, prefixes)

def turbo_info_clear_object(obj):
    add_object_info(obj)
    object_info[obj].info_virtual_time = SIM_time(obj)
    object_info[obj].info_steps = SIM_step_count(obj)
    stat = obj.turbo_stat
    for (name, val) in stat:
        object_info[obj].info_base_turbo_stat[name] = val
    if hasattr(obj.iface, "step_info"):
        obj.iface.step_info.set_halt_steps(0)

def turbo_info_clear_class(classname):
    add_class_info(classname)
    cl = class_info[classname].class_ref
    if SIM_class_has_attribute(cl, "turbo_block_info"):
        SIM_set_class_attribute(cl, "turbo_block_info", 0)

def turbo_info_clear_all():
    for cl in SIM_get_all_classes():
        if SIM_class_has_attribute(cl, "turbo_execution_mode"):
            turbo_info_clear_class(cl)
    for o in SIM_object_iterator(None):
        if SIM_class_has_attribute(o.classname, "turbo_execution_mode"):
            turbo_info_clear_object(o)

cli.new_command("turbo-info", turbo_info_object, [],
                iface = "processor_info_v2",
                doc = "Print turbo statistics for a CPU.")

cli.new_command("turbo-info", turbo_info_all, [],
                doc = "Print turbo statistics for all classes and CPUs.")

cli.new_command("turbo-info-clean", turbo_info_clear_object, [],
                iface = "processor_info_v2",
                doc = "Reset turbo statistics. Acts on all objects belonging to the same class as the object given to the command. Also resets exec-info stats.")

cli.new_command("turbo-info-clean", turbo_info_clear_all, [],
                doc = "Reset turbo statistics. Also resets exec-info stats.")

def exec_info(cpu):
    turbo_info_object(cpu, prefixes=("vmp_", "dynamic_instr", "halt_steps"))

def exec_info_all():
    turbo_info_all(prefixes=("vmp_", "dynamic_instr", "halt_steps"))

def exec_info_clear(cpu):
    turbo_info_clear_object(cpu)

def exec_info_clear_all():
    turbo_info_clear_all()

cli.new_command("exec-info", exec_info, [],
                iface = "processor_info_v2",
                doc = "Print CPU engine execution statistics. Prints the shared stats for all objects that are of the same class as the object that the command in invoked on.")

cli.new_command("exec-info", exec_info_all, [],
                doc = "Print CPU engine execution statistics.")

cli.new_command("exec-info-clean", exec_info_clear, [],
                iface = "processor_info_v2",
                doc = "Reset CPU engine execution statistics. Acts on all objects belonging to the same class as the object given to the command. Also resets turbo stats.")

cli.new_command("exec-info-clean", exec_info_clear_all, [],
                doc = "Reset CPU engine execution statistics. Also resets turbo stats.")

# Corresponds to the turbo_blocks attribute element
class JitBlock:
    __slots__ = ('host_address', 'host_length',
                 'virtual_address', 'phys_address',
                 'target_length', 'compile_step',
                 'ticks', 'trigger_cpu',
                 'length_ratio')
    def __init__(self, turbo_block):
        self.host_address = unsignify(turbo_block[0])
        self.host_length = unsignify(turbo_block[1])
        self.virtual_address = unsignify(turbo_block[2])
        self.phys_address = unsignify(turbo_block[3])
        self.target_length = unsignify(turbo_block[4])
        self.compile_step = unsignify(turbo_block[5])
        self.ticks = unsignify(turbo_block[6])
        self.trigger_cpu = turbo_block[7]
        # Extra calculated data
        self.length_ratio = self.host_length / self.target_length

def list_turbo_blocks_cmd(obj, *table_args):
    blocks = SIM_get_class_attribute(obj.classname, "turbo_blocks")
    jit_blocks = [JitBlock(b) for b in blocks]

    column_props = [
        [(table.Column_Key_Name, "Host addr"),
         (table.Column_Key_Int_Radix, 16),
         (table.Column_Key_Int_Pad_Width, 32)],
        [(table.Column_Key_Name, "Host length")],
        [(table.Column_Key_Name, "Target VA"),
         (table.Column_Key_Int_Radix, 16),
         (table.Column_Key_Int_Pad_Width, 32)],
        [(table.Column_Key_Name, "Target PA"),
         (table.Column_Key_Int_Radix, 16),
         (table.Column_Key_Int_Pad_Width, 32)],
        [(table.Column_Key_Name, "Target length")],
        [(table.Column_Key_Name, "Compile step")],
        [(table.Column_Key_Name, "Prof ticks")],
        [(table.Column_Key_Name, "Trigger CPU")],
        [(table.Column_Key_Name, "Length ratio")],
    ]
    table_props = [
        (table.Table_Key_Default_Sort_Column, "Host addr"),
        (table.Table_Key_Columns, column_props)
    ]
    table_data = [
        [b.host_address,
         b.host_length,
         b.virtual_address,
         b.phys_address,
         b.target_length,
         b.compile_step,
         b.ticks,
         b.trigger_cpu,
         b.length_ratio]
        for b in jit_blocks
    ]
    table.show(table_props, table_data, *table_args)

table.new_table_command(
    "list-turbo-blocks", list_turbo_blocks_cmd,
    args = [],
    iface = "processor_info",
    short = "list all JIT blocks",
    doc = """List all JIT blocks""",
    sortable_columns = ["Host addr", "Host length",
                        "Target VA", "Target PA",
                        "Target length", "Compile step",
                        "Trigger CPU", "Length ratio"]
)
