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
    arg,
    flag_t,
    new_unsupported_command,
    number_str,
    str_t,
)
from simics import *

def add_symbol(table_name, name, start, end, sym_list):
    length = end - start
    GLOBAL = 0x01
    CODE   = 0x10
    #print "%s 0x%x - 0x%x (0x%x)" % (name, start, end, length)
    sym_list.append([name, CODE | GLOBAL, start, length])

def simics_module_symbols(name):
    memory_usage = SIM_get_class_attribute("perfanalyze-client", "memory_usage")
    syms = []
    for mapping in memory_usage:
        (file, is_text, start, end) = mapping
        if is_text:
            type_desc = "text"
        else:
            type_desc = "data"
        tr_file = file.replace(".", "_").replace("-", "_")
        add_symbol(name, "%s_%s" % (tr_file, type_desc), start, end, syms)
    internal_symbols = SIM_get_object(name)
    internal_symbols.symbol_list["<unknown>"] = syms

def memory_usage_cmd(verbose):
    memory_usage = SIM_get_class_attribute("perfanalyze-client", "memory_usage")

    module_text = 0
    module_data = 0
    anonymous_text = 0
    anonymous_data = 0

    print("=== Memory map ===")
    if verbose:
        print("")

    for mapping in memory_usage:
        (file, is_text, start, end) = mapping
        if file == "anonymous":
            if is_text:
                anonymous_text += end - start
            else:
                anonymous_data += end - start
        else:
            if is_text:
                module_text += end - start
            else:
                module_data += end - start
        if verbose:
            if is_text:
                type_desc = "text"
            else:
                type_desc = "data"
            print("%s %s %s" % (number_str(end - start), file, type_desc))

    print("")
    print("Total module text: %s" % number_str(module_text))
    print("Total module data: %s" % number_str(module_data))
    print("Total anonymous exec: %s" % number_str(anonymous_text))
    print("Total anonymous data: %s" % number_str(anonymous_data))
    print("Total all: %s" % number_str(module_text + module_data
                                       + anonymous_text + anonymous_data))

    print("")
    print("=== Dynamic memory ===")
    if verbose:
        print("")

    sites = DBG_mm_get_sites()[:64]

    for site in reversed(sorted(sites)):
        (bytes, allocs, totallocs, typename, file, line) = site
        src_file = file
        try:
            src_file = file[file.rindex("/") + 1:]
        except ValueError:
            pass
        if verbose:
            print("%s %s %s %s:%d" % (number_str(bytes), number_str(allocs),
                                      typename, src_file, line))

new_unsupported_command("memory-usage", "malloc-debug", memory_usage_cmd,
                        args = [arg(flag_t, "-verbose")],
                        short = "memory usage",
                        doc = """
Print the memory map and usage info for this session.

With the <tt>-verbose</tt> flag, individual mappings and the top dynamic
allocation sites will also be shown.""")

new_unsupported_command("simics-module-symbols", "internals",
                        simics_module_symbols,
                        [arg(str_t, "name", "?", "internal-symbols")],
                        short = "load module symbols from Simics",
                        doc = """
Populate symbol table with symbols corresponding to the memory
mappings. <arg>name</arg> may take a table name, default is
"internal-symbols". """)
