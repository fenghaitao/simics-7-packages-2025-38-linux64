# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import sys
from blueprints.impl import BlueprintBuilder, last_built, _sorted_state
from blueprints.top import expand
from blueprints.types import State
from blueprints.data import bp_expander, lookup_bp
from blueprints.debug import _print_state
import cli

def iface_expander(base):
    comp = last_built()
    if not comp:
        return []
    ifaces = {type(x).__name__ for x in comp._state.values()}
    return sorted(x for x in ifaces if x.startswith(base))

def field_expander(prefix, _, vals):
    comp = last_built()
    if not comp:
        return []
    iface_name = vals[0]
    fields = set()
    for iface in comp._state.values():
        if not iface_name or type(iface).__name__ == iface_name:
            fields.update(k for k in iface._keys if k.startswith(prefix))
    return list(fields)

def _list_binds(bp: BlueprintBuilder, iface_name: str, pat: str):
    def mysort(v):
        ((k, iface), _) = v
        return (k, type(iface).__name__, type(iface).__module__)
    for (b, i) in sorted(bp._binds.items(), key=mysort):
        t = type(i).__name__
        if iface_name and iface_name != t:
            continue
        s = f"{b[0]:40} {t:30} {i._name()}"
        if not pat or pat in s:
            print(s)

def _list_iface_usage(bp: BlueprintBuilder, iface_name: str, pat: str):
    def key(v):
        (ns, iface, _) = v
        return (ns, iface.__name__, iface.__module__)
    for (b, i, resolved) in sorted(bp._state_subs, key=key):
        iname = i.__name__
        if iface_name and iface_name != iname:
            continue
        bound_path = f"-> {resolved._key[0]}" if resolved else ""
        s = f"{str(b):40} {iname:30} {bound_path}"
        if not pat or pat in s:
            print(s)

def comp_state_cmd(iface_name, field_pat, pat, list_binds, list_ifaces, show_unbound):
    comp = last_built()
    if not comp:
        return
    if list_binds:
        _list_binds(comp, iface_name, pat)
        return
    if list_ifaces:
        _list_iface_usage(comp, iface_name, pat)
        return
    states = comp._state if show_unbound else comp._bound_state()
    _print_state(_sorted_state(states), sys.stdout, field_pat,
                 iface_name, pat)

def list_state_cmd(bp_name: str, expected: bool, show_used: bool):
    builder = expand("", lookup_bp(bp_name), ignore_errors=True)
    if expected:
        # Accessed state not published in the blueprint
        data = [[str(ns), ic.__name__] for (ns, ic, found) in builder._state_subs
                if not found]
    else:
        published = dict(builder._binds)

        def remove_subscribed(ic: State):
            if ic._key in published:
                del published[ic._key]
                # Remove contained state
                for (k, v) in ic._defaults.items():
                    if isinstance(v, State):
                        remove_subscribed(v)

        # Remove all state that are used within the blueprint
        if not show_used:
            for (_, _, ic) in builder._state_subs:
                if ic:
                    remove_subscribed(ic)

        data = [[str(ns), ic.__name__] for (ns, ic) in published]

    import table
    headers = ["Namespace", "State"]
    props = [(table.Table_Key_Columns, [[(table.Column_Key_Name, n)]
             for n in headers])]
    rows = [[f"<top>.{ns}" if ns else "<top>", ic] for (ns, ic) in data]
    tbl = table.Table(props, rows)
    msg = tbl.to_string(rows_printed=0, no_row_column=True) if rows else ""
    return cli.command_return(msg, rows)

def list_blueprints_cmd(substr):
    data = [name for name in bp_expander("") if substr in name]
    import table
    headers = ["Name"]
    props = [(table.Table_Key_Columns, [[(table.Column_Key_Name, n)]
             for n in headers])]
    rows = [[name] for name in data]
    tbl = table.Table(props, rows)
    msg = tbl.to_string(rows_printed=0, no_row_column=True) if rows else ""
    return cli.command_return(msg, data)

def register_cli_commands():
    cli.new_command("print-blueprint-state", comp_state_cmd, [
        cli.arg(cli.str_t, "iface", "?", "", expander=iface_expander),
        cli.arg(cli.str_t, "field", "?", "", expander=field_expander),
        cli.arg(cli.str_t, "pat", "?", ""),
        cli.arg(cli.flag_t, "-b", "?", ""),
        cli.arg(cli.flag_t, "-i", "?", ""),
        cli.arg(cli.flag_t, "-show-unbound", "?", ""),
    ], type=["Configuration"], short="print blueprint state", alias="pbs", doc="""
        Inspect blueprint state. If <arg>iface</arg> is specified, limit output
        to blueprint state of the specified type. The <arg>field</arg>
        argument can be used to restrict the output to just include
        the specified field.

        As an alternative/complement to <arg>iface</arg>, it is possible to
        specify <arg>pat</arg> which selects all state that match the
        specified substring. This is for instance useful to select state
        defined in a specific node.

        If the <tt>-b</tt> flag is specified, then all state
        bound to a specific namespace node are listed. Conversely,
        the <tt>-i</tt> flag lists all state subscription points.

        If the <tt>-show-unbound</tt> flag is specified, then unbound states
        are shown (hidden by default).
    """, see_also = ["list-blueprint-params"])

    cli.new_command("list-blueprint-state", list_state_cmd,
                    [cli.arg(cli.str_t, "blueprint", "1", doc="blueprint",
                             expander=bp_expander),
                    cli.arg(cli.flag_t, "-expected", "?", ""),
                    cli.arg(cli.flag_t, "-show-used", "?", "")],
                    type=["Configuration"], short="list blueprint state",
                    doc="""
        List state structures used by <arg>blueprint</arg>.

        If <tt>-expected</tt> is TRUE, list state accessed by
        the blueprint but not published, i.e. the expected input
        state. Otherwise display the published state,
        by default only those which are not used by the blueprint,
        i.e. the "connection points". If <tt>-show-used</tt> is set,
        also list state used by the blueprint.
    """)

    cli.new_command("list-blueprints", list_blueprints_cmd,
                    [cli.arg(cli.str_t, "substr", "?", "")],
                    type=["Configuration"], short="list blueprints",
                    doc="""
        List blueprints registered wih Simics.

        The <arg>substr</arg> can be used to only list blueprints with
        names containing that sub-string.
    """)
