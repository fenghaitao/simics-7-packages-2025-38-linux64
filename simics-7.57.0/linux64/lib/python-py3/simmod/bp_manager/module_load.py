# © 2012 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import re
import simics
import conf
import cli
import table
from . import bp

bp_manager_cls = "bp-manager"
bpm_iface = 'bp_manager'

simics.SIM_register_class(bp_manager_cls, simics.class_data_t(
    description='The set of breakpoints in Simics',
    class_desc='manages the set of breakpoints in Simics',
    kind=simics.Sim_Class_Kind_Pseudo))

def all_bpids(ns):
    return ns.iface.bp_manager.list_breakpoints()

def bpid_expander(s, ns):
    return cli.get_completions(s, [str(bm_id) for bm_id in all_bpids(ns)])

def check_valid(ns, bm_id):
    if bm_id not in all_bpids(ns):
        raise cli.CliError('Invalid breakpoint number')

def delete_cmd(ns, poly_id):
    (_, bm_id, name) = poly_id
    if name == '-all':
        for bm_id in all_bpids(ns):
            ns.iface.bp_manager.delete_breakpoint(bm_id)
    else:
        check_valid(ns, bm_id)
        ns.iface.bp_manager.delete_breakpoint(bm_id)

cli.new_command('delete', delete_cmd,
                [cli.arg((cli.int_t, cli.flag_t), ('id', '-all'),
                         expander = (bpid_expander, None))],
                iface = bpm_iface,
                type = ['Debugging'],
                short = 'delete a breakpoint',
                doc = """
Delete the breakpoint with the given <arg>id</arg>, or all of
them with the <tt>-all</tt> flag.""")

def list_cmd(ns):
    ids = list(all_bpids(ns))
    data = []
    for bp_id in ids:
        d = ns.iface.bp_manager.get_properties(bp_id)
        hits = d.get('hit count', False)
        if hits:
            assert(isinstance(hits, int) or isinstance(hits, dict))
            if isinstance(hits, int):
                hit_count = hits
            elif len(hits) > 1:
                hit_count = "\n".join([f'{k}:{v}'
                                       for (k, v) in sorted(hits.items())])
            else:
                hit_count = list(hits.values())[0]
        else:
            hit_count = ""
        data.append([bp_id, d.get('description', 'unknown breakpoint'),
                     d.get('enabled', False),
                     d.get('temporary', False),
                     d.get('ignore count', 0),
                     hit_count])

    props = [(table.Table_Key_Columns,
              [[(table.Column_Key_Name, h)] for h in
               ["ID", "Description", "Enabled", "Oneshot", "Ignore count",
                "Hit count"]])]
    tbl = table.Table(props, data)
    msg = tbl.to_string(rows_printed=0, no_row_column=True)
    return cli.command_return(value=ids, message=msg)

cli.new_command('list', list_cmd, [],
                iface = bpm_iface,
                type = ['Debugging'],
                short = 'list breakpoints',
                see_also = ['bp.show'],
                doc = """
Lists all breakpoints known by the breakpoint manager. For each
breakpoint you get its id, and a short summary.

To get more details about a breakpoint use the <cmd>bp.show</cmd> command.""")

def show_cmd(ns, id):
    check_valid(ns, id)
    d = ns.iface.bp_manager.get_properties(id)

    header = ('Breakpoint %d%s'
              % (id, ' (%s)' % d['description'] if 'description' in d else ''))
    print(header)
    print('=' * max([len(x) for x in header.split('\n')]))

    props = [(k, v) for (k, v) in list(d.items())
             if k not in ['hit count', 'description']]
    # Detect when case switches
    upper_pos = re.compile(r'(?<!^)(?=[A-Z])')
    if props:
        print()
        kw = max(len(k) for (k, v) in props)

        def prop_header(k):
            # CamelCase -> Camel Case
            return upper_pos.sub(' ', k).title()

        def prop_sort_key(data):
            (k, v) = data
            return prop_header(k)

        for (k, v) in sorted(props, key=prop_sort_key):
            if isinstance(v, list):
                print('    %*s : %s' % (kw, prop_header(k), v[0]))
                if len(v) > 1:
                    for vv in v[1:]:
                        print('    %*s   %s' % (kw, '', vv))
            else:
                print('    %*s : %s' % (kw, "Oneshot" if k == "temporary"
                                        else k.title(), v))

    hits = d.get('hit count', False)
    if hits:
        assert(isinstance(hits, int) or isinstance(hits, dict))
        print()
        if isinstance(hits, int):
            print(f"Hit Counts: {hits}")
        else:
            print("Hit Counts:")
            kw = max(len(k) for k in hits)
            for (k, v) in sorted(hits.items()):
                print('    %*s : %u' % (kw, k, v))

    if not props and not hits:
        print()
        print('No breakpoint properties')

cli.new_command('show', show_cmd,
                [cli.arg(cli.int_t, 'id', expander = bpid_expander)],
                iface = bpm_iface,
                type = ['Debugging'],
                short = 'show details about a breakpoint',
                see_also = ['bp.enabled', 'bp.ignore-count', 'bp.test-trigger'],
                doc = """
Show all properties and hit count for the breakpoint with the given
<arg>id</arg>. Some of the properties can be modified through accessor
commands on the <obj>breakpoints</obj> object, but others are specific
to the breakpoint type and can not be edited here.
""")

def enabled_cmd(ns, id, e):
    check_valid(ns, id)
    if e is None:
        props = ns.iface.bp_manager.get_properties(id)
        if 'enabled' in props:
            return props['enabled']
        else:
            raise cli.CliError(f"No such breakpoint: {id}")
    if not ns.iface.bp_manager.set_enabled(id, e):
        raise cli.CliError("Setting enabled state is not supported for"
                           " breakpoint %d" % id)

cli.new_command('enabled', enabled_cmd,
                [cli.arg(cli.int_t, "id", expander = bpid_expander),
                 cli.arg(cli.bool_t("yes", "no"), 'value', '?', None)],
                iface = bpm_iface,
                type = ["Breakpoints", "Debugging"],
                short = "enable or disable breakpoint",
                doc = """
Set and get if the breakpoint with id <arg>id</arg> is enabled or not.
If <arg>value</arg> is provided the breakpoint will be enabled value
is set to <em>yes</em> and disabled if value is set to <em>no</em>.

The command returns what the, possible new, enabled state of the
breakpoint is.
""")

def enable_cmd(ns, bp_id):
    enabled_cmd(ns, bp_id, True)

cli.new_command('enable', enable_cmd,
                [cli.arg(cli.int_t, "id", expander = bpid_expander)],
                iface = bpm_iface,
                type = ["Breakpoints", "Debugging"],
                short = "enable breakpoint",
                see_also = ['bp.enabled', 'bp.disable'],
                doc = """
Set the breakpoint with id <arg>id</arg> to be enabled.
""")

def disable_cmd(ns, bp_id):
    enabled_cmd(ns, bp_id, False)

cli.new_command('disable', disable_cmd,
                [cli.arg(cli.int_t, "id", expander = bpid_expander)],
                iface = bpm_iface,
                type = ["Breakpoints", "Debugging"],
                see_also = ['bp.enabled', 'bp.enable'],
                short = "disable breakpoint",
                doc = """
Set the breakpoint with id <arg>id</arg> to be disabled.
""")

def ignore_count_cmd(ns, id, num):
    check_valid(ns, id)
    bm = ns.iface.bp_manager
    if num is None:
        props = bm.get_properties(id)
        if 'ignore count' in props:
            return props['ignore count']
        else:
            raise cli.CliError(f"No such breakpoint: {id}")
    if not bm.set_ignore_count(id, num):
        raise cli.CliError("Setting ignore count is not supported for"
                           " breakpoint %d" % id)

cli.new_command('ignore-count', ignore_count_cmd,
                [cli.arg(cli.int_t, "id", expander = bpid_expander),
                 cli.arg(cli.uint32_t, "num", '?', None)],
                iface = bpm_iface,
                type = ["Breakpoints", "Debugging"],
                short = "set number of hits of breakpoint to ignore",
                see_also = ['bp.enabled', 'bp.list'],
                doc = """
Sets the skip count for a breakpoint <arg>id</arg>. This means that the first
<arg>num</arg> times an instance of the breakpoint is reached it will not
trigger. To always break, set <arg>num</arg> to 0.

The command returns what the, possibly new, ignore count of the
breakpoint is.
""")

def list_types_cmd(ns):
    types = ns.iface.bp_manager.list_breakpoint_types()
    data = sorted([[t[0].name, t[1]] for t in types])
    props = [(table.Table_Key_Columns,
              [[(table.Column_Key_Name, h)] for h in
               ["Provider", "Breakpoint type"]])]
    tbl = table.Table(props, data)
    msg = tbl.to_string(rows_printed=0, no_row_column=True)
    return cli.command_return(value=data, message=msg)

cli.new_command('list-types', list_types_cmd,
                [],
                iface=bpm_iface,
                type=["Breakpoints", "Debugging"],
                short="list breakpoint type providers",
                doc = """
Print a list of registered breakpoint type providers. The list is
returned when used in an expression.
""")

def test_trigger_cmd(ns, bm_id):
    check_valid(ns, bm_id)
    provider = ns.iface.bp_manager.get_provider(bm_id)
    if provider:
        bp_id = ns.iface.breakpoint_type.get_break_id(bm_id)
        ns.iface.breakpoint_type.trigger(provider, bp_id, ns, "Test trigger")
    else:
        raise cli.CliError("Breakpoint without provider")

cli.new_command('test-trigger', test_trigger_cmd,
                [cli.arg(cli.int_t, "id", expander = bpid_expander)],
                iface = bpm_iface,
                type = ["Breakpoints", "Debugging"],
                see_also = ['bp.show'],
                short = "test trigger breakpoint",
                doc = """
The specified breakpoint <arg>id</arg> will be triggered, even if the specified
break condition has not been met.
""")

from . import bp_type
bp_type.setup_breakpoint_types(bp_manager_cls)

def wait_for_breakpoint_cmd(ns, bm_id, timeout, real_timeout):
    check_valid(ns, bm_id)
    name = 'breakpoint'
    cmd_name = bp_type.command_name('wait-for', None, name)
    data = bp_type.wait_for_breakpoint(
        bm_id, name, cmd_name, timeout, real_timeout)
    return cli.command_return(value=data)

cli.new_command('wait-for-breakpoint', wait_for_breakpoint_cmd,
                [cli.arg(cli.int_t, "id", expander=bpid_expander),
                 cli.arg(cli.float_t, "timeout", '?', 0.0),
                 cli.arg(cli.float_t, "timeout-rt", '?', 0.0)],
                iface=bpm_iface,
                type= ["Breakpoints", "Debugging"],
                see_also=['bp.test-trigger'],
                short = "wait for breakpoint",
                doc = """
Postpones execution of a script branch until the specified
breakpoint <arg>id</arg> triggers. The return value is the same as the
<tt>wait-for</tt> for the corresponding breakpoint type.
""" + bp_type.timeout_doc)

# Interface used by breakpoint type providers to communicate with manager
simics.SIM_register_interface(
    bp_manager_cls, 'breakpoint_registration',
    simics.breakpoint_registration_interface_t(
        register_breakpoint = bp.register_breakpoint,
        deleted = bp.deleted))

# Interface mainly used by the bp-manager CLI commands
# Also used by some breakpoint type providers
simics.SIM_register_interface(
    bp_manager_cls, bpm_iface,
    simics.bp_manager_interface_t(
        list_breakpoints = bp.list_breakpoints,
        delete_breakpoint = bp.delete,
        get_properties = bp.get_properties,
        set_enabled = bp.set_enabled,
        set_temporary = bp.set_temporary,
        set_ignore_count = bp.set_ignore_count,
        get_provider = bp.bp_get_provider,
        list_breakpoint_types = bp.list_breakpoint_types))

obj = simics.SIM_create_object(bp_manager_cls, 'bp', [])
simics.VT_add_permanent_object(obj)

def get_info(ns):
    types = ns.iface.bp_manager.list_breakpoint_types()
    return [("Available types",
             list(sorted((t[0].name, t[1]) for t in types)))]

def get_status(ns):
    bp_list = list(ns.iface.bp_manager.list_breakpoints())
    return [(None, [("Breakpoints", len(bp_list))])]

cli.new_info_command(bp_manager_cls, get_info)
cli.new_status_command(bp_manager_cls, get_status)
