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

import os
import cli
import cli_impl
import simics
import conf
import json
import table
from . import tcf_common as tcfc

log_help = """
With the option <tt>-log</tt> you can specify the agent to log TCF traces in
the file specified with option <arg>log-file</arg>. Option <arg>log-file</arg>
defaults to 'tcf.log'. The flag <tt>-log</tt> is automatically set if
<arg>log-file</arg> is specified. If "-" is set as log file, logs will be sent
to stderr.

With the option <arg>log-mode</arg> you can specify what TCF traces will be
logged. The command is a comma separated list of modes. The list of modes is
available through auto-completion. By default, all modes are selected.
"""

def is_writable_log_file(path):
    """Returns true if path is an existing file that can be written to or if
    the file can be created."""
    path = os.path.realpath(os.path.abspath(path))  # get unlinked path
    if os.path.exists(path):
        if os.path.isfile(path):
            return os.access(path, os.W_OK)
        else:
            return False
    return os.access(os.path.dirname(path), os.W_OK)

def is_valid_log_file(log_file):
    return log_file == '-' or is_writable_log_file(log_file)

def all_valid_log_modes():
    return sorted(simics.SIM_get_class('tcf-agent').log_modes)

def is_valid_log_mode(log_mode):
    return set(log_mode.split(',')) <= set(all_valid_log_modes())

def is_existing_tcf():
    try:
        simics.SIM_get_object('tcf')
    except simics.SimExc_General:
        return False
    return True

def default_log_settings(log, log_file, log_mode):
    if not log and (log_file or log_mode):
        log = True
    if log and not log_file:
        log_file = 'tcf.log'
    if log and not log_mode:
        log_mode = ','.join(simics.SIM_get_class('tcf-agent').log_modes)
    return (log, log_file, log_mode)

def check_log_arguments(log, log_file, log_mode):
    """Check validity of log arguments and raise exception on error."""
    if log_file and not is_valid_log_file(log_file):
        raise cli.CliError(
            f"The log file '{log_file}' cannot be written to")

    if log_mode and not is_valid_log_mode(log_mode):
        valid_modes = ','.join(all_valid_log_modes())
        raise cli.CliError(
            f"The log_mode '{log_mode}' is invalid. The log_mode should be"
            f" '{valid_modes}' or a subset thereof.")

def apply_log_settings(tcf, log, log_file, log_mode):
    tcf.log = bool(log)
    tcf.log_file = log_file
    tcf.log_mode = log_mode

def new_tcf_agent(parameters = None, log = False, log_file = None,
                  log_mode = None):
    if is_existing_tcf():
        raise cli.CliError("The TCF object ('tcf') already exists.")
    (log, log_file, log_mode) = default_log_settings(log, log_file, log_mode)
    check_log_arguments(log, log_file, log_mode)
    tcf = simics.SIM_get_debugger()
    [ok, msg] = tcf.iface.tcf_channel.start_channel(parameters)
    if not ok:
        raise cli.CliError(
            "Created agent, but failed to listen for connections: %s" % msg)
    apply_log_settings(tcf, log, log_file, log_mode)
    return tcf

def log_modes_expander(comp, nmsp, args):
    log_modes = simics.SIM_get_class('tcf-agent').log_modes
    l = comp.split(',')
    c = str(l[-1])
    l[-1] = ''
    lst = [mode for mode in log_modes if mode.startswith(c)]
    return lst

def add_new_tcf_agent_command():
    cli.new_command("new-tcf-agent", new_tcf_agent,
                    args = [cli.arg(cli.str_t, "parameters", "?", "TCP:"),
                            cli.arg(cli.flag_t, "-log", "?", False),
                            cli.arg(cli.str_t, "log-file", "?", None),
                            cli.arg(cli.str_t, "log-mode", "?", None,
                                    expander=log_modes_expander)],
                    type = ["Debugging"],
                    short = "create a tcf agent",
                    see_also = ['debug-context', 'start-eclipse-backend'],
                    doc = """
Command for creating a TCF agent in Simics.

The <arg>parameters</arg> is used to specify Simics capabilities.

""" + log_help)

def backend_info(tcf, msg_prefix):
    properties = dict(tcf.properties)
    protocol = properties['TransportName']
    if 'Host' in properties:
        hosts = [properties['Host']]
    else:
        hosts = ['localhost']
        if hasattr(conf.sim, 'host_ipv4'):
            hosts += [conf.sim.host_ipv4]
    port = properties['Port']
    msg = msg_prefix
    for host in hosts:
        msg += f'\n  {protocol}:{host}:{port}'
    return (msg, protocol, hosts, port)

def start_eclipse_backend(url, name, log, log_file, log_mode):
    tcf = simics.SIM_get_debugger()
    if tcf.properties:
        prefix = 'TCF already started'
    else:
        (log, log_file, log_mode) = default_log_settings(
            log, log_file, log_mode)
        check_log_arguments(log, log_file, log_mode)
        prefix = 'Starting TCF'
        [ok, msg] = tcf.iface.tcf_channel.start_channel(url + ';Name=' + name)
        if not ok:
            raise cli.CliError(msg)
        apply_log_settings(tcf, log, log_file, log_mode)

    (msg, protocol, hosts, port) = backend_info(tcf, f'{prefix} on:')
    return cli.command_return(message=msg, value=[protocol, hosts, port])

def add_start_eclipse_backend_cmd():
    cli.new_command("start-eclipse-backend", start_eclipse_backend,
                    args = [cli.arg(cli.str_t, "url", "?", "TCP:"),
                            cli.arg(cli.str_t, "name", "?", "Simics"),
                            cli.arg(cli.flag_t, "-log", "?", False),
                            cli.arg(cli.str_t, "log-file", "?", None),
                            cli.arg(cli.str_t, "log-mode", "?", None,
                                    expander=log_modes_expander)],
                    type = ["Debugging"],
                    short = "start accepting connections from Eclipse",
                    see_also = ['debug-context', 'new-tcf-agent'],
                    doc = """
Start accepting connections from Eclipse on the given <arg>url</arg> and
participate in autodiscovery.

The <arg>url</arg> argument specifies the protocol and optionally address where
TCF will open a TCP server socket on an available port, typically <tt>1534</tt>.

The <arg>name</arg> is the <tt>Locator</tt> service peer name and it defaults to
'Simics'.

""" + log_help +
"""

On success, the command returns a list on the format [protocol, [host*], port].
Once this command has been executed and successfully configured a network
service, this cannot be changed in the same Simics session, which means
that Simics needs to be restarted in order to provide different network
properties (<arg>url</arg> and <arg>name</arg>).
""")

def print_debug_object_changed_information(cmdline_id, dbg_obj):
    if dbg_obj and dbg_obj.classname == 'tcf-context-proxy':
        msg = ['%s (%s)\n' % (dbg_obj.name,
                              tcfc.describe_debug_object(dbg_obj))]

        all_output = tcfc.collect_prompt(tcfc.Debug_state.debug_state(dbg_obj))
        tcfc.print_prompt_to_frontend(cmdline_id, all_output, msg.append)
    else:
        msg = ['<no debug object>']

    # Stripping the last newline since debug-context and <cpu>.debug both will
    # end up printing their output using the built-in print function which will
    # add a newline itself. Compare to terminal_write.
    return ''.join(msg).rstrip('\n')

def hw_debug_cmd(obj, name):
    try:
        proxy = tcfc.proxy_for_object(obj, name)
    except simics.SimExc_General as m:
        raise cli.CliError(m)
    if proxy:
        tcfc.set_debug_object(proxy)
        cmdline_id = cli.get_current_cmdline()
        dobj = tcfc.get_debug_object()
        message = print_debug_object_changed_information(cmdline_id, dobj)
        return cli.command_return(message, proxy)
    else:
        raise cli.CliError('No TCF context for %s' % obj.name)

def add_debug_cmds():
    for iface in ['memory_space', 'processor_info']:
        cli.new_command('debug', hw_debug_cmd, iface = iface,
                        args = [cli.arg(cli.str_t, 'name', '?')],
                        type = ['Debugging'],
                        short = 'get debug object',
                        doc = """
Get a debug context for the memory space or processor with the given
<arg>name</arg>.

Also enables the debugger.
""")

def is_proxy(obj):
    return (isinstance(obj, simics.conf_object_t)
            and obj.classname == 'tcf-context-proxy')

class Debugger:
    def what(self):
        return "Debugger"
    def is_enabled(self):
        return bool(tcfc.get_debug_object())
    def set_enabled(self, enable):
        if enable:
            dbg = tcfc.calculate_current_debug_object()
            if dbg:
                tcfc.set_debug_object(dbg)
            else:
                raise cli.CliError('No valid debug context found')
        else:
            tcfc.set_debug_object(None, False)

def add_enable_disable_debugger_cmds():
    cli.new_command("enable-debugger", cli.enable_cmd(Debugger),
                    type = ['Debugging'],
                    short = 'enable command line debugger',
                    see_also = ["disable-debugger", "<memory_space>.debug",
                                "<processor_info>.debug", "debug-context"],
                    doc = """
Enables the command line debugger and sets the current debug context
to the software running on the current processor.
""")

    cli.new_command("disable-debugger", cli.disable_cmd(Debugger),
                    type = ['Debugging'],
                    short = 'get debug object',
                    see_also = ["enable-debugger"],
                    doc = "Disables the command line debugger.")

pathmap_common = """
The pathmap is the name for the translations from paths in target
binaries to paths on the Simics host. This pathmap is specific to the
command line interface to the debugger, it is not shared with the
Eclipse frontend to the debugger.
"""

def add_pathmap_entry_cmd(source, destination, context_query):
    e = { 'Source': json.dumps(source), 'Destination': json.dumps(destination) }
    if not context_query is None:
        e['ContextQuery'] = json.dumps(tcfc.simics_query_reformat(context_query))
    (ok, r) = simics.SIM_get_debugger().iface.tcf_pathmap.add_entry(e)
    if not ok:
        raise cli.CliError(r)

def add_add_pathmap_entry_cmd():
    cli.new_command('add-pathmap-entry', add_pathmap_entry_cmd,
                    args = [cli.arg(cli.str_t, 'source'),
                            cli.arg(cli.filename_t(dirs=True), 'destination'),
                            cli.arg(cli.str_t, 'context-query', '?', None)],
                    type = ['Debugging'],
                    see_also = ["show-pathmap"],
                    short = 'add a path map entry',
                    doc = """
Add an entry mapping from <arg>source</arg> path in binaries known by the
debugger to a <arg>destination</arg> path on the Simics host.

The mapping can be limitied to debug contexts matching a particular context
query with <arg>context-query</arg>. It defaults to <em>*</em>, which matches
all debug contexts.

""" + pathmap_common)

def clear_pathmap_cmd():
    simics.SIM_get_debugger().iface.tcf_pathmap.clear_entries()

def add_clear_pathmap_cmd():
    cli.new_command('clear-pathmap', clear_pathmap_cmd,
                    type = ['Debugging'],
                    short = 'clear all path map entries',
                    doc = """
Remove all entries used to translate from paths in binaries to paths
on the Simics host.

""" + pathmap_common)

def show_pathmap_cmd():
    required_keys = set(['Source', 'Destination'])
    (ok, r) = simics.SIM_get_debugger().iface.tcf_pathmap.get_entries()
    if not ok:
        raise cli.CliError(r)
    translated = [list(map(json.loads, [e['Source'], e['Destination'],
                                   e.get('ContextQuery', 'null')]))
                  for e in r if set(e.keys()) >= required_keys]
    msg = []
    for (s, d, cq) in translated:
        msg.append(("%s -> %s (%s)" % (s, d, cq))
                   if cq else ("%s -> %s" % (s, d)))
    if msg == [] :
        return cli.command_return(message = "No Path Map entries are currently set.", value = [])
    message = '\n'.join(msg)
    return cli.command_return(value = translated,
                              message = message)

def add_show_pathmap_cmd():
    cli.new_command('show-pathmap', show_pathmap_cmd,
                    type = ['Debugging'],
                    see_also = ["add-pathmap-entry"],
                    short = 'show the current path map',
                    doc = """
Show all entries in the pathmap.

""" + pathmap_common)

def generate_multi_lines(lst, width):
    res = []
    while len(lst) > 0:
        count = 0
        tmp_lst = []
        while len(lst) > 0:
            count += len(lst[0]) + 2
            if count >= width:
                break
            tmp_lst.append(lst.pop(0))
        line = ', '.join(tmp_lst)
        if len(lst) > 0:
            line += ','
        res.append(line)
    return res

def segments_list_cmd(filename):
    tcf_elf = simics.SIM_get_debugger().iface.tcf_elf
    (ok, elf_id) = tcf_elf.open_symbol_file(filename, 0)
    if not ok:
        raise cli.CliError(elf_id)
    (ok, r) = tcf_elf.get_segments_info(elf_id)
    width = cli.terminal_width() - len('Segments') - 4
    lst = []
    ret = []
    for i, seg in enumerate(r):
        sections = seg['section_list']
        idx = str(i)
        ret.append([str(i), ', '.join(sections)])
        lines = generate_multi_lines(sections, width)
        if lines == []:
            lines.append('<segment is empty>')
        for line in lines:
            lst.append([idx, line])
            idx=''
    cli.print_columns ('rl', [['Segments', 'Sections']] + lst)
    tcf_elf.close_symbol_file(elf_id)
    return cli.command_quiet_return(value = ret)


def add_list_segments_cmd():
    cli.new_command('list-segments', segments_list_cmd,
                    args = [cli.arg(cli.filename_t(dirs=False, simpath=1), 'symbol-file')],
                    type = ['Debugging'],
                    short = "lists the segments of a symbol file",
                    doc = """
Lists the segments of the symbol file <arg>symbol-file</arg>.

<arg>symbol-file</arg> uses Simics's Search Path and path markers (%simics%,
%script%) to find the symbol file. Refer to <cite>The Command Line
Interface</cite> chapter of the <cite>Simics User's Guide</cite> manual for
more information on how Simics's Search Path is used to locate files.
                      """)

def sections_list_cmd(filename):
    tcf_elf = simics.SIM_get_debugger().iface.tcf_elf
    (ok, elf_id) = tcf_elf.open_symbol_file(filename, 0)
    if not ok:
        raise cli.CliError(elf_id)
    (ok, r) = tcf_elf.get_sections_info(elf_id)
    lst = [section['name'] for section in r if 'name' in section]
    m = ', '.join(lst)
    tcf_elf.close_symbol_file(elf_id)
    return cli.command_verbose_return(message = m, value = lst)

def add_list_sections_cmd():
    cli.new_command('list-sections', sections_list_cmd,
                    args = [cli.arg(cli.filename_t(dirs=False, simpath=1),
                                    'symbol-file')],
                    type = ['Debugging'],
                    short = "lists the relocatable sections of a symbol file",
                    doc = """
Lists the sections of the symbol file <arg>symbol-file</arg>.

<arg>symbol-file</arg> uses Simics's Search Path and path markers (%simics%,
%script%) to find the symbol file. Refer to <cite>The Command Line
Interface</cite> chapter of the <cite>Simics User's Guide</cite> manual for
more information on how Simics's Search Path is used to locate files.
                      """)

def find_section_by_name(name, section_list):
    for s in section_list:
        if 'name' in s and s['name'] == name:
            return s
    return None


def symbol_file_cmd(filename, query, relocation, relative, section, segment):
    if section is not None and segment is not None:
        raise cli.CliError("Can't relocate a segment and a section at the"
                           " same time.")
    if relocation is None:
        if section is not None or segment is not None:
            raise cli.CliError("Missing relocation address.")
        if relative:
            raise cli.CliError("relocation-address must be provided when"
                               " -relative flag is used")
        relocation = 0
        relative = True

    query = tcfc.simics_query_reformat(query)
    setup_iface = simics.SIM_get_debugger().iface.debug_setup

    if section is not None:
        (err, file_id) = setup_iface.add_symbol_section(
            query, filename, section, relocation, not relative)
        if err == simics.Debugger_Section_Not_Found:
            # Override error message to suggest list-sections command.
            file_id = ('Section cannot be found in the file.\n'
                       'Use the list-sections command to list all sections.')
    elif segment is not None:
        (err, file_id) = setup_iface.add_symbol_segment(
            query, filename, segment, relocation, not relative)
        if err == simics.Debugger_Segment_Not_Found:
            # Override error message to suggest list-segments command.
            file_id = ('Segment cannot be found in the file.\n'
                       'Use the list-segments command to list all segments.')
    else:
        (err, file_id) = setup_iface.add_symbol_file(
            query, filename, relocation, not relative)
    if err != simics.Debugger_No_Error:
        raise cli.CliError(file_id)

    query_iface = simics.SIM_get_debugger().iface.debug_query
    (err, matching) = query_iface.matching_contexts(query)
    if err == simics.Debugger_No_Error:
        nr_matching = len(matching)
    else:
        nr_matching = 0
    return cli.command_return(
        message = ("Context query %s currently matches %d context%s.\n"
                   "Symbol file added with id '%s'." % (
                       query, nr_matching,  "" if nr_matching == 1 else "s",
                       file_id)),
        value = file_id)

def remove_symbol_file_cmd(filename, query, relocation, relative, section,
                           file_id):
    def msg(r):
        return ("Removed %d Memory Map entr%s." % (r, "y" if r <= 1 else "ies"))

    setup_iface = simics.SIM_get_debugger().iface.debug_setup
    if file_id is not None:
        if (filename is not None or query is not None or relocation is not None
            or section is not None):
            raise cli.CliError("'id' argument should be given alone")

        (err, err_msg) = setup_iface.remove_symbol_file(file_id)
        if err == simics.Debugger_No_Error:
            return
        raise cli.CliError(err_msg)

    if filename is None:
        raise cli.CliError("Missing symbol file")

    (err, entries) = setup_iface.symbol_files()
    if err != simics.Debugger_No_Error:
        raise cli.CliError(entries)

    if len(entries) == 0:
        return cli.command_return(
            message = "No Memory Map entries are currently set.")

    nr_removed = 0
    for (file_id, entry) in entries.items():
        # skip entry if symbol file does not match
        if entry.get('symbol-file') != filename:
            continue

        # skip if query does not match specified query
        if query is not None and entry.get('query') != query:
            continue

        if (relative and relocation is not None
            and entry.get('relocation') != relocation):
            continue

        match = False
        mem_maps = entry.get('memory-maps', [])
        any_skipped = False
        for m in mem_maps:
            # skip entry if relocation address does not match
            if (not relative and relocation is not None
                and m.get('address') != relocation):
                any_skipped = True
                continue

            # skip entry if section does not match specified section name
            if section is not None and m.get('section') != section:
                any_skipped = True
                continue

            match = True

        if not match:
            continue

        if any_skipped:
            raise cli.CliError("The arguments given only partly matches memory"
                               " maps added for a symbol file with id %s, no"
                               " memory maps removed. Use id or other"
                               " arguments instead." % file_id)

        (err, err_msg) = setup_iface.remove_symbol_file(file_id)
        if err != simics.Debugger_No_Error:
            raise cli.CliError(err_msg)
        nr_removed += len(mem_maps)

    return cli.command_return(message = msg(nr_removed), value = nr_removed)

def sec_expander(comp, nmsp, args):
    if args[0] == None:
        return []
    tcf_elf = simics.SIM_get_debugger().iface.tcf_elf
    (ok, elf_id) = tcf_elf.open_symbol_file(args[0], 0)
    if not ok:
        raise cli.CliError(elf_id)
    (ok, sect_list) = tcf_elf.get_sections_info(elf_id)
    tcf_elf.close_symbol_file(elf_id)
    return [sec['name'] for sec in sect_list if (sec['flags'] & 2) and sec['name'].startswith(comp)]

def seg_expander(comp, nmsp, args):
    if args[0] == None:
        return []
    tcf_elf = simics.SIM_get_debugger().iface.tcf_elf
    (ok, elf_id) = tcf_elf.open_symbol_file(args[0], 0)
    if not ok:
        raise cli.CliError(elf_id)
    (ok, seg_list) = tcf_elf.get_segments_info(elf_id)
    tcf_elf.close_symbol_file(elf_id)
    if comp != "" or len(seg_list) < 2:
        return [str(i) for i in range(len(seg_list))
                if str(i).startswith(comp)]
    width = cli.terminal_width()
    res = []
    for (i, seg) in enumerate(seg_list):
        sections = seg['section_list']
        lines = generate_multi_lines(sections, width)
        if lines:
            res.append(str(i) + '  (' + '\n    '.join(lines) + ')')
        else:
            res.append(str(i) + '  <segment is empty>')
    return res

def add_add_symbol_file_cmd():
    cli.new_command('add-symbol-file', symbol_file_cmd,
                    args = [cli.arg(cli.filename_t(dirs=False, simpath=1),
                                    'symbolfile'),
                            cli.arg(cli.str_t, 'context-query', '?', '*'),
                            cli.arg(cli.uint64_t, 'relocation-address',
                                    '?', None),
                            cli.arg(cli.flag_t, '-relative'),
                            cli.arg(cli.str_t, 'section', '?',
                                    None, expander = sec_expander),
                            cli.arg(cli.uint32_t, 'segment', '?',
                                    None, expander = seg_expander)],
                    type = ['Debugging'],
                    short = 'add symbol file to debugging contexts',
                    see_also = ["list-sections", "list-segments",
                                "show-memorymap", "clear-memorymap",
                                "remove-symbol-file"],
                    doc = """
Add the symbol file <arg>symbolfile</arg> to debugging contexts matching the
context query <arg>context-query</arg>.

<arg>symbolfile</arg> uses Simics's Search Path and path markers (%simics%,
%script%) to find the symbol file. Refer to <cite>The Command Line
Interface</cite> chapter of the <cite>Simics User's Guide</cite> manual for
more information on how Simics's Search Path is used to locate files.

<arg>context-query</arg> defaults to <em>*</em> which matches all contexts.

<arg>relocation-address</arg> is the address, the file/segment/section should be
mapped to. The <tt>-relative</tt> flag specifies if the relocation address will
be relative to the load address in the binary. When not set the address will be
the absolule address specified.

<arg>section</arg> is the name of the section to relocate. See the
<cmd>list-sections</cmd> command.

<arg>segment</arg> is the number of the segment to relocate. See the
<cmd>list-segments</cmd> command.

The command will return an ID that can be used with
<cmd>remove-symbol-file</cmd> to remove that mappings that were added.
""")

def sym_file_id_expander(prefix):
    setup_iface = simics.SIM_get_debugger().iface.debug_setup
    (err, sym_files) = setup_iface.symbol_files()
    if err != simics.Debugger_No_Error:
        return []
    file_ids = [str(file_id) for file_id in sym_files]
    return cli.get_completions(prefix, file_ids)

def add_remove_symbol_file_cmd():
    cli.new_command('remove-symbol-file', remove_symbol_file_cmd,
                    args = [cli.arg(cli.filename_t(dirs=False, simpath=1),
                                    'symbolfile', '?', None),
                            cli.arg(cli.str_t, 'context-query', '?', None),
                            cli.arg(cli.uint64_t, 'relocation-address',
                                    '?', None),
                            cli.arg(cli.flag_t, '-relative'),
                            cli.arg(cli.str_t, 'section', '?', None,
                                    expander = sec_expander),
                            cli.arg(cli.uint64_t, 'id', '?', None,
                                    expander = sym_file_id_expander)],
                    type = ['Debugging'],
                    short = 'remove symbol file from debugging contexts',
                    see_also = ["list-sections", "list-segments",
                                "show-memorymap", "clear-memorymap",
                                "add-symbol-file"],
                    doc = """
Remove Memory Map entries matching and <arg>id</arg> or the symbol file
<arg>symbolfile</arg> and optional criteria context query
<arg>context-query</arg>, relocation address <arg>relocation-address</arg>
and/or section name <arg>section</arg>.

The <arg>id</arg> argument is the value returned from <cmd>add-symbol-file</cmd>
and can be used to remove all memory maps that were added from a call to that
command. No other arguments should be given when this argument is given.

<arg>symbolfile</arg> uses Simics's Search Path and path markers (%simics%,
%script%) to find the symbol file. Refer to <cite>The Command Line
Interface</cite> chapter of the <cite>Simics User's Guide</cite> manual for
more information on how Simics's Search Path is used to locate files.

<arg>context-query</arg> causes the removal of Memory Map entries matching
this context query.

<arg>relocation-address</arg> is the address, the file/segment/section is mapped
to. If <tt>-relative</tt> is given this matches the relocation address as
relative to the binary load address, otherwise it matches the absolute addres.
See the <cmd>show-memorymap</cmd> command.

<arg>section</arg> is the name of the relocated section. See the
<cmd>show-memorymap</cmd> command.

The arguments provided are required to match all mappings added at once for a
symbol file, i.e. all mappings that have the same <arg>id</arg> must be removed
at once.
""")

def clear_memory_map_cmd():
    simics.SIM_get_debugger().iface.debug_setup.clear_symbol_files()

def add_clear_memory_map_cmd():
    cli.new_command('clear-memorymap', clear_memory_map_cmd,
                    type = ['Debugging'],
                    short = 'clear all memory map entries',
                    see_also = ["add-symbol-file", "remove-symbol-file",
                                "show-memorymap"],
                    doc = """
Remove all files in the current memory map used by the debugger.

The memory map is built with the add-symbol-file command. The memory
map is used in addition to the memory map configured in Eclipse.
""")

def memory_map_tabulator(all_entries):
    def fmt(f):
        def ff(e):
            return f.format(**e)
        return ff
    def addr(field):
        def f(e):
            s = e[field]
            return '0x%x' % s
        return f
    def val(field):
        def f(e):
            s = e[field]
            return '0x%x' % s if s else ''
        return f
    def flags(e):
        f = e['flags']
        return '%s%s%s' % ('r' if f & 1 else '', 'w' if f & 2 else '',
                           'x' if f & 4 else '')
    def ofs(e):
        # The offset is relative the start of the section or the start
        # of the file for segments
        s, o = e['section'], e['offset']
        return '%s%s%s' % (('%s' % s) if s else '',
                           (' + ' if s and o else ''),
                           ('0x%x' % o if (o or not s) else ''))

    def ids(e):
        return str(e['id'])

    heads = ['ID', 'Address', 'Size', 'Flags', 'Offset', 'File']
    align = ['>', '>', '>', '>', '>', '<']
    fs = [ids, addr('address'), val('size'), flags, ofs, fmt('{file}')]

    all_rows = [heads] + [[f(e) for f in fs] for e in all_entries]
    widths = [max(len(r) for r in c) for c in zip(*all_rows)]

    def tabulate(es):
        es.sort(key = lambda e: e['address'])
        rows = ([heads] + [[f(e) for f in fs] for e in es])
        return '\n'.join(' '.join('{0: {1}{2}}'.format(c, a, w)
                                  for (c, a, w) in zip(r, align, widths))
                         for r in rows)
    return tabulate

def group_by(key, dicts):
    res = {}
    for d in dicts:
        res.setdefault(d[key], []).append(d)
    return res

def show_memory_map_cmd():
    (err, entries) = simics.SIM_get_debugger().iface.debug_setup.symbol_files()
    if err != simics.Debugger_No_Error:
        raise cli.CliError(entries)

    if len(entries) == 0:
        return cli.command_return(
            message = "No Memory Map entries are currently set.")

    formatted_entries = [{'id': file_id,
                          'query': e['query'],
                          'file': e['symbol-file'],
                          'address': m['address'],
                          'size': m['size'],
                          'flags': m['flags'],
                          'section': m['section'],
                          'offset': m['file-offset']}
                         for (file_id, e) in entries.items()
                         for m in e['memory-maps']]
    tabulate = memory_map_tabulator(formatted_entries)

    def show_group(query, formatted_entries):
        title = 'Contexts matching %s' % (query,)
        title = title + '\n' + '=' * len(title) + '\n\n'
        return title + tabulate(formatted_entries)

    def group_sort_key(data):
        (k, v) = data
        return k

    tables = '\n\n'.join(show_group(q, g)
                         for (q, g) in sorted(
                                 list(group_by('query',
                                               formatted_entries).items()),
                                 key=group_sort_key))
    return cli.command_return(message = tables)

def add_show_memory_map_cmd():
    cli.new_command('show-memorymap', show_memory_map_cmd,
                    type = ['Debugging'],
                    short = 'show the current memory map',
                    see_also = ['add-symbol-file', 'clear-memorymap'],
                    doc = """
Show the current memory map used by the debugger. This is what is
built with the add-symbol-file command. The memory map is used in
addition to the memory map configured in Eclipse.
""")


def debug_context_cmd(ctx, name):
    (kind, ctx, _) = ctx
    if ctx is not None:
        if kind == cli.str_t:
            proxy_finder = simics.SIM_get_debugger().iface.agent_proxy_finder
            ctxs = proxy_finder.list_contexts(tcfc.simics_query_reformat(ctx))
            if ctxs is None:
                raise cli.CliError("Invalid query %s" % ctx)
            ctx_ids = [i for (i, n) in ctxs]
            ctx_ids = [i for i in ctx_ids if proxy_finder.get_context_info(i)['HasState']]
            if ctx_ids == []:
                raise cli.CliError("No thread context matching %s" % ctx)
            if len(ctx_ids) > 1:
                raise cli.CliError("Multiple debug contexts matching %s" % ctx)
            obj = tcfc.proxy_for_id(ctx_ids[0], name)
        elif ctx.classname == 'tcf-context-proxy':
            obj = ctx
        else:
            try:
                obj = tcfc.proxy_for_object(ctx, name)
            except simics.SimExc_General as m:
                try:
                    obj = tcfc.proxy_for_id(ctx, name)
                except:
                    raise cli.CliError(m)
        tcfc.set_debug_object(obj)

    cmdline_id = cli.get_current_cmdline()
    dobj = tcfc.get_debug_object()
    message = print_debug_object_changed_information(cmdline_id, dobj)

    return cli.command_return(message, value = dobj)


def add_debug_context_cmd():
    cli.new_command('debug-context', debug_context_cmd,
                    args = ([cli.arg((cli.obj_t('Debug context',
                                                ('tcf-context-proxy',
                                                 'memory_space',
                                                 'processor_info')),
                                      cli.str_t),
                                     ('object', 'context-query'), '?',
                                     (cli.obj_t, None, 'object')),
                             cli.arg(cli.str_t, 'name', '?')]),
                    type = ['Debugging'],
                    short = 'return the current debug object',
                    doc = """
Optionally change the current debug context and return it, naming the debug
object <arg>name</arg> unless a object for the debug context already exists.

The current debug context can be specified either using the <arg>object</arg>
argument to select a <em>processor</em> object, or the <arg>context-query</arg>
argument to match any kind of <em>debug context</em> with state. The context
query should match one unique processor or OS awareness leaf node.

The current debug context is the debug context global stepping and
debugger inspection commands will affect.

Setting the current debug context also enables the debugger.
""")

def list_debug_contexts_cmd(query):
    proxy_finder = simics.SIM_get_debugger().iface.agent_proxy_finder
    res = proxy_finder.list_contexts(tcfc.simics_query_reformat(query))
    if res is None:
        raise cli.CliError("Invalid context query: %s" % query)
    qname = [proxy_finder.context_full_name(elem[0]) for elem in res]
    for i in range(len(qname)):
        res[i][1] = qname[i]
    res.sort(key=lambda x: (x[1], x[0]))
    cli.print_columns('l', ['Fully Qualified Name'] + [x[1] for x in res])
    return cli.command_quiet_return(value = res)

def add_list_debug_contexts_cmd():
    cli.new_command('list-debug-contexts', list_debug_contexts_cmd,
                    args = [cli.arg(cli.str_t, 'context-query', '?', None)],
                    short = 'list debug contexts',
                    type = ['Debugging'],
                    doc = """
List debug contexts matching the context query <arg>context-query</arg>.
The displayed value is the list of all the fully qualified names of the
context matching the context query. The return value is a list of contexts.
Each element of the list is a list of two elements: the context id and the
fully qualified context name.

<arg>context-query</arg> defaults to <em>*</em> which matches all contexts.
                      """)

def objects_with_contexts():
    object_names = []
    debugger = simics.SIM_get_debugger()
    for obj in simics.SIM_object_iterator(None):
        if obj.classname == "tcf-context-proxy":
            object_names.append(obj.name)
            continue

        (err, _) = debugger.iface.debug_query.context_id_for_object(obj)
        if err == simics.Debugger_No_Error:
            object_names.append(obj.name)
    return object_names

def obj_with_ctx_expander(ctx_obj):
    return cli.get_completions(ctx_obj, objects_with_contexts())

def ctx_id_for_object(ctx_obj):
    debugger = simics.SIM_get_debugger()
    if ctx_obj.classname == "tcf-context-proxy":
        assert hasattr(ctx_obj, "cid"), f"{ctx_obj.name} lacks cid attribute"
        ctx_id = ctx_obj.cid
        if not ctx_id:
            raise cli.CliError(f'No context id for {ctx_obj}')
    else:
        (err, ctx_id) = debugger.iface.debug_query.context_id_for_object(
            ctx_obj)
        if err != simics.Debugger_No_Error:
            raise cli.CliError(f'{ctx_obj.name} has no debug context')
    return ctx_id

def ctx_query_for_object_cmd(ctx_obj):
    ctx_id = ctx_id_for_object(ctx_obj)

    debugger = simics.SIM_get_debugger()
    (err, query) = debugger.iface.debug_query.query_for_context_id(ctx_id)
    if err != simics.Debugger_No_Error:
        raise cli.CliError(f'Failed to construct a context query for {ctx_obj}:'
                           f' {query}')
    return cli.command_return(message=cli_impl.repr_cli_string(query),
                              value=query)

def add_context_query_for_object_cmd():
    cli.new_command('context-query-for-object', ctx_query_for_object_cmd,
                    args = [cli.arg(cli.obj_t('object'), 'object',
                                    expander=obj_with_ctx_expander)],
                    short = 'create a context query for a Simics object',
                    type = ['Debugging'],
                    see_also = ['context-query-for-object-list'],
                    doc = """
Returns a context query that matches a Simics <arg>object</arg>.

This returned context query can then be used with other commands that take
a context query as argument to match only the specified Simics object.

The printed output is formatted for use with CLI commands.

An error will be raised if the <arg>object</arg> doesn't have a backing debug
context or isn't a debug context object.
""")

def ctx_query_for_object_list_cmd(objects):
    ctx_list = set([])
    for obj in objects:
        if isinstance(obj, str):
            try:
                obj = simics.SIM_get_object(obj)
            except simics.SimExc_General:
                raise cli.CliError(f'Could not get object {obj}')
        ctx_id = ctx_id_for_object(obj)
        ctx_list.add(ctx_id)

    query = f'IDList="[{",".join(sorted(ctx_list))}]"'
    return cli.command_return(message=cli_impl.repr_cli_string(query),
                              value=query)

cli.new_command('context-query-for-object-list',
                ctx_query_for_object_list_cmd,
                args = [cli.arg(cli.list_t, 'objects')],
                short = 'create a context query for a list of objects',
                type = ['Debugging'],
                see_also = ['context-query-for-object'],
                doc = """
Returns a context query that matches a list of <arg>objects</arg>.

This returned context query can then be used with other commands that take
a context query as argument to match only the specified Simics object.

The printed output is formatted for use with CLI commands.

An error will be raised if the list contains any object that doesn't have a
backing debug context or isn't a debug context object.
""")

def parse_sw_domains(sw_domains_arg):
    assert sw_domains_arg is not None
    from .debug_config_interface import (
        Config_Sw_Domain_Full,
        Config_Sw_Domain_Main)

    (arg_type, val, arg_name) = sw_domains_arg
    sw_config = 0
    sw_domains = None
    if arg_name == '-full-system':
        sw_config = Config_Sw_Domain_Full
    elif arg_name == '-main-software-domain':
        sw_config = Config_Sw_Domain_Main
    elif arg_type == cli.list_t:
        if not val:
            raise cli.CliError('Empty list not allowed')
        sw_domains = []
        for sw in val:
            if isinstance(sw, str):
                try:
                    sw = simics.SIM_get_object(sw)
                except simics.SimExc_General:
                    pass
            sw_domains.append(sw)
    else:
        assert isinstance(val, simics.conf_object_t)
        sw_domains = [val]

    if isinstance(sw_domains, list):
        for sw in sw_domains:
            if not isinstance(sw, simics.conf_object_t):
                raise cli.CliError(f'Not a Simics object: {sw}')
            if not simics.SIM_c_get_interface(sw, 'osa_component'):
                raise cli.CliError(f'Not a software domain: {sw}')

    return (sw_config, sw_domains)

def write_debug_context_config(config, sw_domains):
    debugger = simics.SIM_get_debugger()
    (err, err_msg) = debugger.iface.debug_config.configure(config, sw_domains)
    if err != simics.Debugger_No_Error:
        raise cli.CliError(err_msg)

phys_mem_options = ("shared", "per-cpu", "unchanged")

def phys_mem_expander(prefix):
    return cli.get_completions(prefix, phys_mem_options)

osa_options = ("included", "excluded", "tracker", "unchanged")

def osa_expander(prefix):
    return cli.get_completions(prefix, osa_options)

def ctx_id_to_object(query_iface, ctx_id):
    (err, obj) = query_iface.object_for_context(ctx_id)
    if err == simics.Debugger_No_Error:
        return obj
    return None

def debug_context_objs():
    debugger = simics.SIM_get_debugger()
    query_iface = debugger.iface.debug_query
    (err, ctx_ids) = query_iface.matching_contexts(None)
    assert err == simics.Debugger_No_Error
    return [ctx_id_to_object(query_iface, ctx_id) for ctx_id in ctx_ids
            if ctx_id_to_object(query_iface, ctx_id)]

def set_debug_contexts(sw_domains, osa, phys_mem, verbose):
    debugger = simics.SIM_get_debugger()
    from .debug_config_interface import (
        Config_Os_Awareness,
        Config_Os_Awareness_Hide_Cpu_Mapped,
        Config_Shared_Phys_Mem,
        Config_Sw_Domain_Full,
        Config_Sw_Domain_Main)
    old_objs = debug_context_objs()
    old_config = debugger.iface.debug_config.get_configuration()
    new_config = old_config
    any_set = False
    if osa and osa != 'unchanged':
        if osa not in osa_options:
            raise cli.CliError(f'Incorrect type "{osa}" for os-awareness')
        new_config &= ~(Config_Os_Awareness
                        | Config_Os_Awareness_Hide_Cpu_Mapped)
        if osa == "tracker":
            new_config |= (Config_Os_Awareness
                           | Config_Os_Awareness_Hide_Cpu_Mapped)
        elif osa == "included":
            new_config |= Config_Os_Awareness
        any_set = True

    if phys_mem and phys_mem != "unchanged":
        if phys_mem == "shared":
            new_config |= Config_Shared_Phys_Mem
        elif phys_mem == "per-cpu":
            new_config &= ~Config_Shared_Phys_Mem
        else:
            raise cli.CliError(
                f'Incorrect type "{phys_mem}" for physical-memory')
        any_set = True

    if sw_domains is not None:
        (sw_config, sw_domains) = parse_sw_domains(sw_domains)
        new_config &= ~(Config_Sw_Domain_Main | Config_Sw_Domain_Full)
        new_config |= sw_config
        any_set = True

    if any_set:
        write_debug_context_config(new_config, sw_domains)

    def format_configuration_output(config, sw_domains):
        def phys_mem_str(config):
            if config & Config_Shared_Phys_Mem:
                return "shared"
            else:
                return "per cpu"

        def osa_str(config):
            if not config & Config_Os_Awareness:
                return 'excluded'
            if not config & Config_Os_Awareness_Hide_Cpu_Mapped:
                return 'included'
            return 'depends on tracker'

        def sw_str(config, sw_domains):
            if config & Config_Sw_Domain_Full:
                return "full system"
            if config & Config_Sw_Domain_Main:
                return "main"
            if not isinstance(sw_domains, list):
                return "<bad format>"
            return ', '.join([sw.name for sw in sw_domains])

        return [['OS Awareness:', osa_str(new_config)],
                ['Software domains:', sw_str(new_config, sw_domains)],
                ['Physical mem:', phys_mem_str(new_config)]]

    def format_objects(objects):
        return '\n' + '\n'.join(sorted([f'{x.name}' for x in objects]))

    def format_object_output():
        new_objs = debug_context_objs()
        data = [['Objects:', format_objects(new_objs)]]
        added = list(set(new_objs) - set(old_objs))
        removed = list(set(old_objs) - set(new_objs))
        if added:
            data.append(['Added:', format_objects(added)])
        if removed:
            data.append(['Removed:', format_objects(removed)])
        return data

    new_sw_domains = debugger.iface.debug_config.get_enabled_sw_domains()
    data = format_configuration_output(new_config, new_sw_domains)
    if verbose:
        data += format_object_output()
    tbl = table.Table([], data)
    return cli.command_return(
        message=tbl.to_string(no_row_column=True, no_footers=True,
                              border_style='borderless', rows_printed=0))

def add_set_debug_contexts_cmd():
    cli.new_tech_preview_command(
        'set-debug-contexts', 'set-debug-contexts', set_debug_contexts,
        args = [cli.arg((cli.flag_t, cli.flag_t,
                         cli.obj_t('software domain', ('osa_component')),
                         cli.list_t),
                        ('-full-system', '-main-software-domain',
                         'software-domain', 'software-domain-list'), '?'),
                cli.arg(cli.str_t, 'os-awareness', '?', None,
                        expander=osa_expander),
                cli.arg(cli.str_t, 'physical-memory', '?', None,
                        expander=phys_mem_expander),
                cli.arg(cli.flag_t, '-verbose')],
        short = 'list and update Simics debugger context configuration',
        type = ['Debugging'],
        doc = """
This command is used to configure what debugger contexts are created for the
Simics TCF debugger.

The <arg>software-domain</arg> and <arg>software-domain-list</arg> arguments are
used to specify that debug contexts for the selected software domain(s) should
be included. The <tt>-main-software-domain</tt> flag can be used instead to
specify the main software domain(s). Use the <tt>-full-system</tt> flag to
include all processors, regardless of software domain.

Set <arg>os-awareness</arg> to <tt>included</tt>, <tt>excluded</tt> to update
configuration to include or exclude OS Awareness contexts, respectively. The
argument can also be set to <tt>tracker</tt> which means that it is defined by
tracker whether the contexts are shown or not, this is the default behavior.

Set <arg>physical-memory</arg> to <tt>shared</tt> to update configuration to try
to find a shared physical memory for the general purpoose compute
processors. Setting it to <tt>per-cpu</tt> will use the actual physical memory
of each processor which is often a memory space that is local to the processor.

If either argument is left out then that part of the configuration is left
unchanged. If no argument is given the command will just show the current
configuration.

The <tt>-verbose</tt> flag can be used for a more verbose output that will show
which objects are included in the configuration.
""")

def register_global_cmds():
    add_new_tcf_agent_command()
    add_start_eclipse_backend_cmd()
    add_debug_cmds()
    add_enable_disable_debugger_cmds()
    add_add_pathmap_entry_cmd()
    add_clear_pathmap_cmd()
    add_show_pathmap_cmd()
    add_list_segments_cmd()
    add_list_sections_cmd()
    add_add_symbol_file_cmd()
    add_remove_symbol_file_cmd()
    add_clear_memory_map_cmd()
    add_show_memory_map_cmd()
    add_debug_context_cmd()
    add_list_debug_contexts_cmd()
    add_context_query_for_object_cmd()
    add_set_debug_contexts_cmd()
