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

from cli import (
    CliError,
    arg,
    get_completions,
    new_command,
    new_info_command,
    new_status_command,
    new_unsupported_command,
    obj_t,
    uint64_t,
    )
from simics import *

def pm_get_info(obj):
    ap = []
    for c in pattern_match_classes():
        info = VT_get_class_info(c)
        desc = info[0]
        ap.append((c, desc))

    up = []
    for c in obj.patterns:
        up.append((c.classname, c.name))
    return [ (None,
              [("Description", "Hypersimulation Pattern matcher")]),
             ("Patterns used",
              up),
             ("Available patterns (loaded)",
              ap)]

def pm_get_status(obj):
    mem = obj.memory_space.name
    (ffwd_is, ffwd_s) = obj.total_ffwd_steps
    overall = [["Physical memory",     mem],
               ["Ffwd idle steps",     ffwd_is],
               ["Ffwd steps",          ffwd_s],
               ["Next sample interval",  "%d - %d" % (obj.search_interval[0], obj.search_interval[1])]]

    p_info = []

    # p_ = pattern, r_ = range, c_ = cpu
    active_str = [" (inactive)", ""]
    for (p_obj, p_name, p_r_list,
         bad_examine, good_trigger, bad_trigger) in obj.pattern_info:

        if p_r_list:
            p_info.append(("%s API statistics" % p_name, [
                        ("successful examine calls", len(p_r_list)),
                        ("failed examine calls", bad_examine),
                        ("successful trigger calls", good_trigger),
                        ("failed trigger calls", bad_trigger)]))

        for (r_addr, r_active, r_c_list) in p_r_list:
            p_attr = []

            for (c_obj, c_idle, c_steps) in r_c_list:
                p_attr.append((c_obj.name, "ffwd idle steps %d, ffwd steps %d" % (c_idle, c_steps)))

            p_attr = [( "%s @ p:0x%x%s" % (p_name, r_addr, active_str[r_active]), p_attr)]
            p_info += p_attr

    res = [('General', overall)] + p_info
    return res

new_info_command("hypersim-pattern-matcher", pm_get_info)
new_status_command("hypersim-pattern-matcher", pm_get_status)

def has_class_pattern_interface(cls_name):
    try:
        SIM_get_class_interface(SIM_get_class(cls_name), "hypersim_pattern")
    except SimExc_Lookup:
        # Interface not found
        return False
    except SimExc_PythonTranslation:
        # The interface is not wrapped in python, this is okay
        return True
    else:
        return True

def pattern_match_classes():
    l = []
    for cls_name in SIM_get_all_classes():
        if has_class_pattern_interface(cls_name):
            l.append(cls_name)
    return l

def pattern_matcher_class_expander(string, obj):
    return get_completions(string, pattern_match_classes())

def pattern_object_expander(string, obj):
    n = []
    for o in obj.patterns:
        n.append(o.name)
    return get_completions(string, n)

def delete_pattern_cmd(obj, pattern_obj):
    p = obj.patterns
    if pattern_obj in p:
        SIM_delete_object(pattern_obj)
    else:
        raise CliError("Object %s is not used by %s" % (pattern_obj.name,
                                                        obj.name))

new_command("delete-pattern", delete_pattern_cmd,
            [arg(obj_t('pattern'), 'pattern',
                 expander = pattern_object_expander)],
            type  = ["Performance"],
            short = "remove a pattern from the matcher",
            cls = "hypersim-pattern-matcher",
            doc = """
Remove a pattern from the pattern-matcher. The <arg>pattern</arg> object
name is used to identify the pattern to remove.""")


def gen_pattern_cmd(obj, addr, length):
    cpu = obj.queue
    tagged_addr = cpu.iface.processor_info.logical_to_physical(addr,
                                                            Sim_Access_Execute)
    if not tagged_addr.valid:
        raise CliError("address not mapped")
    paddr = tagged_addr.address
    print("static const char * const pattern[] = {")
    descs = []
    comments = []
    phys_mem = cpu.physical_memory
    for i in range(length):
        chunk = phys_mem.memory[paddr:paddr+20]
        (l, dis) = cpu.iface.processor_info.disassemble(addr, chunk, 1)
        words = [ SIM_read_phys_memory(cpu, paddr+j, 1) for j in range(l) ]
        if cpu.iface.processor_info.architecture() == "ppc32" and l == 4:
            desc = "0x"+"".join([ "%02x"%word for word in words ])
        else:
            desc = " ".join([ "0x%02x"%word for word in words ])
        comment = "%d: 0x%08x %s" % (i, addr, dis)
        descs.append("%s\"%s\","% (" " * 8, desc))
        comments.append("// %s" % (comment,))
        paddr += l
        addr += l
    descs_len = max(list(map(len, descs)))
    for i in range(length):
        print(descs[i].ljust(descs_len), comments[i])

    print("%sNULL" % (" " * 8))
    print("};")

new_unsupported_command(
    "generate_pattern_template", "internals", gen_pattern_cmd,
    [arg(uint64_t, "address"), arg(uint64_t, "length")],
    short = "dump a C template for a pattern matcher",
    cls = "hypersim-pattern-matcher",
    doc = """
internal, dump a C struct for <arg>length</arg> number of instructions at a
given <arg>address</arg> with suitable to use in a hypersim pattern.""")
