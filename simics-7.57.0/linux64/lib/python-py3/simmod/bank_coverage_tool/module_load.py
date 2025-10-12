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


import operator
import pickle
import re

import cli
import device_info
import simics
import table
import sim_commands

def qualifying_registers(bank, register_qualifier):
    rs = {}
    rv = bank.iface.register_view
    for i in range(0, rv.number_of_registers()):
        if register_qualifier(i):
            (name, _, size, offset) = rv.register_info(i)[:4]
            rs[name] = (offset, size)
    return rs

def all_registers(bank):
    return qualifying_registers(bank, lambda _ : True)

def writeable_registers(bank):
    ro = simics.SIM_c_get_interface(bank, 'register_view_read_only')
    def is_writeable(r):
        return not ro.is_read_only(r) if ro else True
    return qualifying_registers(bank, lambda r : is_writeable(r))

def read_only_registers(bank):
    ro = simics.SIM_c_get_interface(bank, 'register_view_read_only')
    return qualifying_registers(
        bank, lambda r : ro.is_read_only(r) if ro else False)

def in_range(l_offset, l_size, r_offset, r_size):
    if (l_offset <= (r_offset + r_size - 1)
        and (l_offset + l_size - 1) >= r_offset):
        return True
    return False

def overlapping(registers, ofs, size):
    return [r_name for (r_name, (r_ofs, r_size)) in registers.items()
            if in_range(r_ofs, r_size, ofs, size)]

def overlapping_access_count(accesses, registers):
    num_accesses = {}
    for (offset, size, count) in accesses:
        hits = overlapping(registers, offset, size)
        for hit in hits:
            if not hit in num_accesses:
                num_accesses[hit] = 0
            num_accesses[hit] += count
    return num_accesses

def hit_ratio(bank, bank_accesses, registers):
    num_accesses = overlapping_access_count(bank_accesses, registers)
    return (len(num_accesses), len(registers))

def percentage(num_accesses, num_regs):
    return (1.0 if num_regs == 0 else (float(num_accesses)/float(num_regs)))

per_tool = {}
def loaded_accesses(obj):
    if not obj in per_tool:
        per_tool[obj] = {}
    return per_tool[obj]

def coverage_table_properties():
    return [
        (table.Table_Key_Name, 'Device coverage'),
        (table.Table_Key_Description,
         "Devices with register banks"),
        (table.Table_Key_Default_Sort_Column, 'Coverage%'),
        (table.Table_Key_Columns, [
            [(table.Column_Key_Name, 'Device'),
             (table.Column_Key_Description, "Device name.")],
            [(table.Column_Key_Name, 'No. accessed registers'),
             (table.Column_Key_Description, "Number of accessed registers."),
             (table.Column_Key_Footer_Sum, True),
             (table.Column_Key_Int_Radix, 10),
             (table.Column_Key_Generate_Percent_Column, [])],
            [(table.Column_Key_Name, 'No. registers'),
             (table.Column_Key_Description, "Total number of registers."),
             (table.Column_Key_Footer_Sum, True),
             (table.Column_Key_Int_Radix, 10),
             (table.Column_Key_Generate_Percent_Column, [])],
            [(table.Column_Key_Name, 'Coverage%'),
             (table.Column_Key_Description, "Share of covered registers."),
             (table.Column_Key_Float_Percent, True)],
        ])]

def compile_or_throw(regexp):
    try:
        return re.compile(regexp)
    except re.error as e:
        raise cli.CliError(
            "'%s' is not a valid regular expression: %s" % (regexp, e))

def accumulated_accesses(obj):
    accesses = {
        c.bank : ([i for i in c.read_accesses],
                  [i for i in c.write_accesses]) for c in obj.connections }
    for (bank, (reads, writes)) in loaded_accesses(obj).items():
        if not bank in accesses:
            accesses[bank] = ([], [])
        accesses[bank] = [l1 + l2 for (l1, l2) in zip(
            accesses[bank], (reads, writes))]
    return accesses

def coverage_cmd(obj, read, write, device_regexp, to_file, *table_args):
    if not any((read, write)):
        read = write = True
    compiled_device_regexp = (compile_or_throw(device_regexp)
                              if device_regexp else re.compile('.*'))

    accesses = accumulated_accesses(obj)

    num_excluded_registers = 0
    access_ratios = {}
    for (bank, (reads, writes)) in accesses.items():
        (num_accesses, num_registers) = hit_ratio(
            bank, (reads if read else []) + (writes if write else []),
            all_registers(bank) if read else writeable_registers(bank))
        if not read:
            num_excluded_registers += len(read_only_registers(bank))
        device_name = sim_commands.get_device(bank).name

        if device_name not in access_ratios:
            access_ratios[device_name] = (0, 0)
        access_ratios[device_name] = map(operator.add,
                                    access_ratios[device_name],
                                    (num_accesses, num_registers))

    # table expects list of lists
    coverage = [
        [device_name, num_accesses, num_regs,
         percentage(num_accesses, num_regs)]
        for (device_name, (num_accesses, num_regs)) in access_ratios.items()
        if compiled_device_regexp.match(device_name)]

    if to_file:
        show_all = table.get_table_arg_value("-show-all-columns", table_args)
        table.Table(coverage_table_properties(), coverage, show_all).csv_export(
            to_file)
        return

    msg = "Table reduced from %d to %d rows. " % (
        len(accesses), len(coverage)) if device_regexp else ""
    if num_excluded_registers > 0:
        msg += "Excluding %d read-only register%s." % (
            num_excluded_registers, '' if num_excluded_registers == 1 else 's')
    msg += '\n'
    msg += table.get(coverage_table_properties(), coverage, *table_args)
    return cli.command_return(msg, coverage)

table.new_table_command(
    'coverage', coverage_cmd,
    args = [cli.arg(cli.flag_t, '-read'),
            cli.arg(cli.flag_t, '-write'),
            cli.arg(cli.str_t, 'device-regexp', '?', None),
            cli.arg(cli.filename_t(exist = False), 'to-file', '?', None),],
    cls = 'bank_coverage_tool',
    type = ['Instrumentation'],
    short = "print bank coverages",
    doc = ("Per device, present the coverage of instrumented banks. Provide a"
           " Python regular expression to filter on device name using"
           " <arg>device-regexp</arg>. Use the <tt>-read</tt> or"
           " <tt>-write</tt> flags to present either type of accesses. If"
           " neither is provided, all accesses are included. To export the"
           " results as CSV, provide a file name using <arg>to-file</arg>."),
    sortable_columns = ['Device', 'No. accessed registers',
                        'No. registers', 'Coverage%'])

def save_cmd(obj, filename):
    d = { c.bank.name : (
        [(ofs, size, count) for (ofs, size, count) in c.read_accesses],
        [(ofs, size, count) for (ofs, size, count) in c.write_accesses])
          for c in obj.connections }
    with open(filename, 'wb') as f:
        pickle.dump(d, f, pickle.HIGHEST_PROTOCOL)

cli.new_command(
    'save', save_cmd,
    args = [cli.arg(cli.filename_t(dirs=False, exist=False), 'filename'),],
    cls = 'bank_coverage_tool',
    type = ['Instrumentation'],
    short = "save instrumented bank coverage to file",
    doc = ("Save collected bank coverage to <arg>filename</arg>. Saved coverage"
           " from multiple sessions of the same setup may"
           " subsequently be loaded to display the total"
           " bank coverage"))

def load_cmd(obj, filename):
    accesses = loaded_accesses(obj)
    with open(filename, 'rb') as f:
        d = pickle.load(f)  # nosec
    for (bank_name, (reads, writes)) in d.items():
        accesses[simics.SIM_get_object(bank_name)] = list(map(
            operator.add,
            (accesses[simics.SIM_get_object(bank_name)]
             if simics.SIM_get_object(bank_name) in accesses else [[], []]),
            (reads, writes)))

cli.new_command(
    'load', load_cmd,
    args = [cli.arg(cli.filename_t(dirs=False, exist=False), 'filename'),],
    cls = 'bank_coverage_tool',
    type = ['Instrumentation'],
    short = "load instrumented bank coverage from file",
    doc = ("Load previously collected bank coverage from <arg>filename</arg>."
           " Loaded coverage from earlier sessions is compiled with current"
           " coverage when presenting the displayed totals."))

def access_count_table_properties(device_name, bank_name):
    return [
        (table.Table_Key_Name, 'Access count'),
        (table.Table_Key_Description,
         "Register access count for %s (%s)" % (bank_name, device_name)),
        (table.Table_Key_Default_Sort_Column, 'Offset'),
        (table.Table_Key_Columns, [
            [(table.Column_Key_Name, 'Name'),
             (table.Column_Key_Description, "Register name.")],
            [(table.Column_Key_Name, 'Offset'),
             (table.Column_Key_Description, "Register offset."),
             (table.Column_Key_Int_Radix, 16),
             (table.Column_Key_Sort_Descending, False)],
            [(table.Column_Key_Name, 'Size'),
             (table.Column_Key_Description, "Register size."),
             (table.Column_Key_Int_Radix, 10)],
            [(table.Column_Key_Name, 'Count'),
             (table.Column_Key_Description,
              "Number of times the register was accessed."),
             (table.Column_Key_Footer_Sum, True),
             (table.Column_Key_Int_Radix, 10)],
        ])]

def access_count_cmd(obj, bank, read, write, show_zeroes, *table_args):
    bank_name = bank.name
    device_name = sim_commands.get_device(bank).name
    if not any((read, write)):
        read = write = True

    all_accesses = accumulated_accesses(obj)
    if bank not in all_accesses:
        return cli.command_return(table.get(access_count_table_properties(
            device_name, bank_name), [], *table_args), [])

    regs = all_registers(bank)
    (reads, writes) = all_accesses[bank]

    num_accesses = overlapping_access_count(
        (reads if read else []) + (writes if write else []), regs)

    if show_zeroes:
        for r in regs:
            if r not in num_accesses:
                num_accesses[r] = 0

    data = [
        [register_name, regs[register_name][0], regs[register_name][1], count]
        for (register_name, count) in num_accesses.items()]

    msg = table.get(access_count_table_properties(device_name, bank_name),
                    data, *table_args)
    return cli.command_return(msg, data)

def access_count_expander(comp, obj):
    return [b.name for b in accumulated_accesses(obj)
            if b.name.startswith(comp)]

access_count_bank_reqs = 'bank_instrumentation_subscribe & register_view'
table.new_table_command(
    'access-count', access_count_cmd,
    args = [cli.arg(cli.obj_t('bank', access_count_bank_reqs), 'bank',
                    expander=access_count_expander),
            cli.arg(cli.flag_t, '-read'),
            cli.arg(cli.flag_t, '-write'),
            cli.arg(cli.flag_t, '-show-zeroes')],
    cls = 'bank_coverage_tool',
    type = ['Instrumentation'],
    short = "print bank access count",
    doc = ("Present the access count of an instrumented bank. Provide the"
           " <arg>bank</arg>, and optionally the <tt>-read</tt> and"
           " <tt>-write</tt> flags to indicate whether or not read and write"
           " accesses should be presented, respectively. If neither is"
           " provided, both are presented."
           " The <tt>-show-zeroes</tt> flag also presents the registers"
           " without any accesses."),
    sortable_columns = ['Name', 'Offset', 'Size', 'Count'])

def banks(obj):
    cls = simics.SIM_object_class(obj)
    ports = [(name, size) for (name, size, iface)
             in simics.VT_get_port_interfaces(cls) if iface == 'register_view']
    indexed = [['%s[%d]' % (name, idx) for idx in range(size)]
               if size > 1 else [name] for (name, size) in ports]
    return [bank for banks in indexed for bank in banks]

def lacks_registers(device, bank_name):
    register_view = simics.SIM_get_port_interface(
        device, 'register_view', bank_name)
    return register_view.number_of_registers() == 0

def connect_all_cmd(tool):
    tool_name = tool.name
    # TODO(enilsson): perhaps this can be done without involving CLI?
    cli.quiet_run_command('%s.add-instrumentation -connect-all' % tool_name)

cli.new_command(
    'connect-all', connect_all_cmd,
    args = [],
    cls = 'bank_coverage_tool',
    type = ['Instrumentation'],
    short = "connect to the banks of all devices",
    doc = ("Connect to every bank of all devices in the current configuration."
           " Exclude banks of devices of which there are no attached device"
           " info XML or EML files."))
