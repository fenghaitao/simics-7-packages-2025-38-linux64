# © 2015 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import cli
import re
import simics
from . import memory_comp

memory_comp.simple_memory_module.register()
memory_comp.ddr_memory_module_comp.register()
memory_comp.ddr2_memory_module_comp.register()
memory_comp.ddr3_memory_module_comp.register()
memory_comp.sdram_memory_module_comp.register()

def create_and_connect_ddr(system, memory_megs, organization, slot_name,
                           ranks_per_module, min_module_size, max_module_size,
                           ecc, ddr_type, module_type, hierarchical,
                           columns, rows):
    def is_po2(val):
        return 1 if val and not(val & (val - 1)) else 0

    def organization_ok(dl):
        for idx_a in range(len(organization)):
            if organization[idx_a] == '-':
                if dl[idx_a] != 0:
                    return 0
                continue
            l = []
            for idx_b in range(len(organization)):
                if organization[idx_a] == organization[idx_b]:
                    l.append(idx_b)
            val = -1
            for idx_c in l:
                if (organization[idx_a].islower()
                    and dl[idx_c] > 0) or (organization[idx_a].isupper()):
                    if val == -1:
                        val = dl[idx_c]
                    elif val != dl[idx_c]:
                        return 0
        return 1

    def loop(dl, pos):
        if pos == len(organization):
            return (0, dl)
        for i in dimm_sizes:
            dl[pos] = i
            (res, dl) = loop(dl, pos + 1)
            if res == 0:
                if sum(dl) == memory_megs and organization_ok(dl):
                    return (1, dl)
            else:
                return (1, dl)
        return (0, dl)

    if not is_po2(ranks_per_module):
        raise cli.CliError("Error, ranks_per_module must be power of 2.")

    if not is_po2(min_module_size):
        raise cli.CliError("Error, min_module_size must be power of 2.")

    if not is_po2(max_module_size):
        raise cli.CliError("Error, max_module_size must be power of 2.")

    if max_module_size < min_module_size:
        raise cli.CliError("Error, min_module_size can not be less than "
                           "max_module_size.")

    try:
        system_obj = simics.SIM_get_object(system)
    except simics.SimExc_General:
        raise cli.CliError("No system component '%s' found" % system)

    r = re.compile(r'[a-dA-D\-]*\Z')
    if not re.match(r, organization):
        raise cli.CliError("Error, organization string %s not valid." % organization)
    if len(organization) > 8:
        raise cli.CliError("Error, organization with 8 DIMMs is the maximum.")

    dimm_sizes = [(2**x) for x in range(
        max_module_size.bit_length() - 1,
        min_module_size.bit_length() - 2, -1)] + [0]
    (res, dimms) = loop([0 for x in range(len(organization))], 0)

    if res == 0:
        raise cli.CliError("Error, could not find any combination of memory "
                           "modules to get total %d MB memory" % memory_megs)

    for i in range(len(dimms)):
        cli.run_command("$dimms = []") # FIXME: This may clobber existing variable
        if dimms[i] != 0:
            if ddr_type == 'DDR':
                t = ''
            else:
                t = ddr_type[3]
            name = "name = %s.memory%d" % (system, i) if hierarchical else ""
            create_str = "$dimms[%d] = (create-ddr%s-memory-module-comp %s " % (i, t, name)
            create_str += "ranks = %d " % ranks_per_module
            create_str += "rank_density = %d " % (dimms[i] // ranks_per_module)
            create_str += "module_type = %s " % (module_type)
            if ecc:
                create_str += "module_data_width = 72 "
                create_str += "ecc_width = 8 "
            if columns != -1:
                create_str += "columns = %d " % columns
            if rows != -1:
                create_str += "rows = %d " % rows
            create_str += ")"
            cli.run_command(create_str)

            if slot_name == None and hasattr(system_obj, 'static_slots'):
                # Auto-detect DIMM slots.
                mem_slots = sorted([slot for (slot, o)
                             in list(system_obj.object_list.items())
                             if (hasattr(o, 'classname')
                                 and o.classname == 'connector'
                                 and o.type == 'mem-bus')])
                slot = mem_slots[i]
            else:
                if slot_name == None:
                    slot_name = 'connector_ddr_slot'
                slot = slot_name + '%d' % i

            cli.run_command("connect %s.%s $dimms[%d].mem_bus"
                            % (system, slot, i))

def ddr_expander(string):
    return cli.get_completions(string, ('DDR', 'DDR2', 'DDR3'))
cli.new_command('create-and-connect-ddr-memory-comp',
                create_and_connect_ddr,
                [cli.arg(cli.str_t, "system"),
                 cli.arg(cli.int_t, "memory_megs"),
                 cli.arg(cli.str_t, "organization"),
                 cli.arg(cli.str_t, "slot_name", "?", None),
                 cli.arg(cli.int_t, "ranks_per_module", "?", 1),
                 cli.arg(cli.int_t, "min_module_size", "?", 4),
                 cli.arg(cli.int_t, "max_module_size", "?", 4096),
                 cli.arg(cli.int_t, "ecc", "?", 0),
                 cli.arg(cli.str_t, "ddr_type", "?", "DDR", expander=ddr_expander),
                 cli.arg(cli.str_t, "module_type", "?", "UDIMM"),
                 cli.arg(cli.flag_t,"-h"),
                 cli.arg(cli.int_t, "columns", "?", -1),
                 cli.arg(cli.int_t, "rows", "?", -1)],
                type = ["Components"],
                short = 'create and connect memory modules to the system',
                doc = """
Create and connect DDR memory modules to the <arg>system</arg>.
The <arg>memory_megs</arg> attribute defines the total module
memory size in MB.

It is possible to create different kind of
module combinations with the <arg>organization</arg> parameter.
The <arg>organization</arg> is a string. Each character in the
string represents a module. The first character is module 0,
second character is module 1, etc. Supported characters are
a-d and A-D. Two modules can have the same character. An equal
upper case character means that the modules must be of identical
size. An equal lower case character means that the modules must
be identical or unpopulated. The character '-' indicates that
the slot should not contain any modules. A maximum of 8 characters
are supported, i.e. maximum number of DIMMs is 8.

Example 1: AB
Create one or two modules with any size (all slots need not be populated).

Example 2: AA
Create two modules with identical size.

Example 3: aa
Create one module or two modules with identical size.

Setting <arg>ecc</arg> argument to 1 enables ECC in the SPD data, which means
<tt>ecc_width</tt> will be set to 8 and <tt>module_data_with</tt> to 72 for the
underlying ddrN-memory-module component.

<arg>ddr_type</arg> may be set to one of 'DDR' (default), 'DDR2' or 'DDR3'.
Default <arg>module_type</arg> is 'UDIMM' but may be set to a valid type for
the given <arg>ddr_type</arg>.

The <tt>-h</tt> flag (hierarchical) will put the created memory component in
the slot named <em>memoryX</em> in <arg>system</arg>, where <em>X</em> is the
DIMM number.

Optional arguments are <arg>slot_name</arg>, <arg>ranks_per_module</arg>,
<arg>min_module_size</arg>, <arg>max_module_size</arg>, <arg>columns</arg> and
<arg>rows</arg>.  """)
