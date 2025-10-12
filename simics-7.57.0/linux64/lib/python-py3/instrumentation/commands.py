# © 2016 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import simics
from cli import (
    CliError,
    arg,
    command_return,
    command_verbose_return,
    flag_t,
    get_completions,
    int_t,
    new_command,
    obj_t,
    quiet_run_command,
    str_t,
    )
import cli_impl
import instrumentation
from instrumentation import name_expander
from table import (
    Column_Key_Hide_Homogeneous,
    Column_Key_Name,
    Table,
    Table_Key_Columns,
)
from . import groups
from conf_commands import obj_cls_name_match

def print_connection(c):
    group_name = get_group_name(c.get_group_id())
    disabled = c.get_disabled_string()
    print("%3d %s - %s%s%s" % (
        c.get_id(), c.get_name(), c.get_description(),
        (" Group:" + group_name) if group_name else "",
        " (Disabled by %s)" % disabled if disabled else ""))

def filter_connections(id, name, group):
    if id == None and not name and not group:
        raise CliError(
            "Error: must specify either id, name, or group")

    if id != None:
        if name or group:
            raise CliError(
                "Cannot combine id with name or group")

        ids = [c for c in instrumentation.get_all_connections()
                if c.get_id() == id]
        if ids:
            return ids
        raise CliError("Unknown connection: %d" % id)

    if group:
        if name:
            raise CliError("Cannot combine group with name")
        gid = get_group_id(group)
        return get_group_connections(gid)

    if name:
        return [c for c in instrumentation.get_all_connections()
                if c.get_name() == name]
    else:
        assert 0

def register_remove_instrumentation_command():

    def remove(c, verbose):
        if verbose:
            print("Removing:", end=' ')
            print_connection(c)
        instrumentation.delete_connection(c)
        c.delete()

    def remove_instrumentation_cmd(id, name, group, verbose):
        for c in filter_connections(id, name, group):
            remove(c, verbose)

    new_command("remove-instrumentation", remove_instrumentation_cmd,
                args = [arg(int_t, "id", "?"),
                        arg(str_t, "name", "?", expander = name_expander),
                        arg(str_t, "group", "?", expander = group_expander),
                        arg(flag_t, "-verbose"),
                        ],
                see_also = sorted(normal_cmds - set(["remove-instrumentation"])),
                type = ["Instrumentation"],
                short = "remove instrumentation",
                doc = """
                Remove one or multiple established instrumentation
                connections.

                Specify which connections to disable with one of
                <arg>id</arg>, <arg>name</arg> or <arg>group</arg>
                arguments. The <arg>id</arg> specifies one unique connection.
                The <arg>name</arg> specifies all connections associated with
                a specific tool. The <arg>group</arg> selects all connections
                associated with a connection group.

                The <tt>-verbose</tt> lists information on the connections
                that becomes disabled.""")


def register_list_instrumentation_command():
    def list_instrumentation_cmd(name, group):

        def con_data(c):
            group_name = get_group_name(c.get_group_id())
            disabled = c.get_disabled_string()
            args = c.get_connection_args()
            if disabled:
                dis = "by %s" % (disabled,)
            else:
                dis = ""
            filters = ", ".join(c.get_filters())
            return [
                c.get_id(),
                c.get_name(),
                c.get_provider_object(),
                group_name if group_name else "",
                args,
                filters,
                dis
            ]

        struct = [
            [Table_Key_Columns, [
                [(Column_Key_Name, "Id")],
                [(Column_Key_Name, "Tool")],
                [(Column_Key_Name, "Provider")],
                [(Column_Key_Name, "Group"),
                 (Column_Key_Hide_Homogeneous, "")],
                [(Column_Key_Name, "Connection args"),
                 (Column_Key_Hide_Homogeneous, "")],
                [(Column_Key_Name, "Filters"),
                 (Column_Key_Hide_Homogeneous, "")],
                [(Column_Key_Name, "Disabled"),
                 (Column_Key_Hide_Homogeneous, "")],
            ]]]

        data = []
        if group:
            gid = get_group_id(group)
            for c in get_group_connections(gid):
                if not name or name == c.get_name():
                    data.append(con_data(c))
        elif name:
            for c in instrumentation.get_named_connections(name):
                data.append(con_data(c))
        else:
            conns = instrumentation.get_all_connections()
            if not conns:
                return command_verbose_return(
                    "Nothing instrumented.\nSee 'help Instrumentation'"
                    " for commands related to instrumentation.", [])
            for c in sorted(conns, key = lambda c: c.get_id()):
                data.append(con_data(c))

        # Produce and print the resulting table
        return command_verbose_return(
            Table(struct, data).to_string(no_row_column=True, rows_printed=0),
            data)

    new_command('list-instrumentation',
                list_instrumentation_cmd,
                args = [
                    arg(str_t, "name", "?", expander = name_expander),
                    arg(str_t, "group", "?", expander = group_expander)
                ],
                short = 'list established instrumentation connections',
                type = ["Instrumentation"],
                see_also = sorted(normal_cmds - set(["list-instrumentation"])),
                doc = """
                List which established instrumentation connections
                that is currently setup.

                Without any arguments, all connections are listed. To narrow
                down the list the <arg>name</arg> argument can specify tool
                specific connections, or the <arg>group</arg> can be used to
                only print the connections associated with a certain named
                group.""")

    # Check if a command is "unsupported" or part of a tech-preview,
    # and then if it is currently enabled for the user
    def command_available(cmd):
        for (feature, enabled, cmd_set) in (cli_impl.unsupported_info()
                                            + cli_impl.tech_preview_info()):
            if cmd in cmd_set:
                return enabled
        return True          # Not unsupported or tech-preview command

    def list_instrumentation_tools_cmd(substr, req, verbose):
        props = [[Table_Key_Columns,
                  [[(Column_Key_Name, "Tool create command")],
                   [(Column_Key_Name, "Tool class")],
                   [(Column_Key_Name, "Available objects"),
                    (Column_Key_Hide_Homogeneous, "")],
                   [(Column_Key_Name, "Provider requirements\n(interfaces)"),
                    (Column_Key_Hide_Homogeneous, "")],
                   [(Column_Key_Name, "Description"),
                    (Column_Key_Hide_Homogeneous, "")],
                   ]]
                 ]
        data = []

        for cls in instrumentation.get_registered_tool_classes():
            pr = str(cls.provider_requirements) if req else ""
            cl = cls.tool_class
            if not obj_cls_name_match(substr, cl):
                continue
            cmd = "new-%s" % (cl.replace('_', '-'))
            if not command_available(cmd):
                continue
            objs = ", ".join([
                o.name for o in simics.SIM_object_iterator_for_class(cl)])
            if verbose:
                doc = simics.VT_get_class_info(cl)[0]
            else:
                doc = simics.SIM_get_class(cl).class_desc
            data.append([cmd, cl, objs, pr, doc])

        msg = Table(props, data).to_string(no_row_column=True, rows_printed=0)
        msg += ('\nFor more information type "help <tool create command>"'
                + ' or "help <tool class>".')
        return command_verbose_return(msg, data)

    new_command('list-instrumentation-tools',
                list_instrumentation_tools_cmd,
                args = [arg(str_t, "substr", "?", ""),
                        arg(flag_t, "-provider-requirements"),
                        arg(flag_t, "-verbose")],
                short = 'list existing instrumentation tools',
                type = ["Instrumentation"],
                see_also = sorted(normal_cmds
                                  - set(["list-instrumentation-tools"])),

                doc = """ List all instrumentation tool classes
                registered in the system. It is possible to only
                include classes whose name matches a certain sub-string,
                specified by the <arg>substr</arg> argument.
                For each tool class, the
                command to use for creating such tool is provided as
                well. If there are already created tools their
                corresponding objects will be listed in an additional
                column. Use the <tt>-provider-requirements</tt> flag
                to also show the interfaces required by a provider to
                connect to the tool. A description of the tool is also
                printed. The <tt>-verbose</tt> flag selects between a
                short and a verbose description.""")

def get_group_id(name):
    groups = instrumentation.get_groups()
    if name not in groups:
        raise CliError("Unknown group name '%s'" % name)
    return groups[name]

def get_groups():
    return [g for g in instrumentation.get_groups() if g != None]

def get_group_name(id):
    groups = instrumentation.get_groups()
    for n in groups:
        if groups[n] == id:
            return n
    return None

def group_expander(name):
    return get_completions(name, get_groups())

def get_group_connections(group_id):
    connections = instrumentation.get_all_connections()
    return [ c for c in connections if c.get_group_id() == group_id ]

def register_group_commands():

    def add_instrumentation_group_cmd(name):
        if name in instrumentation.get_groups():
            raise CliError(
                "Error: instrumentation group '%s' already exists" % name)

        instrumentation.set_group(name)

    new_command("add-instrumentation-group", add_instrumentation_group_cmd,
                args = [arg(str_t, "name")],
                short = "add new instrumentation group",
                type = ["Instrumentation"],
                see_also = sorted(normal_cmds
                                  - set(["add-instrumentation-group"])),

                doc = """
                Create a new named group that can be used in commands that
                add instrumentation to the system. This allows connections to
                be grouped together.

                The <arg>name</arg> argument specifies the name of the group.
                A connection can then be assigned a group with the
                <cmd>&lt;tool&gt;.add-instrumentation</cmd> command. The group
                can be used in the <cmd>list-instrumentation</cmd>,
                <cmd>[&lt;tool&gt;.]enable-instrumentation</cmd>,
                <cmd>[&lt;tool&gt;.]disable-instrumentation</cmd> or
                <cmd>[&lt;tool&gt;.]remove-instrumentation</cmd> commands to
                handle multiple connections with one command.""")

    def remove_instrumentation_group_cmd(name):
        gid = get_group_id(name)
        c = get_group_connections(gid)
        if c:
            raise CliError(
                "Cannot remove group, '%s' has still %d connection%s"
                " established" % (
                name, len(c), "s" if len(c) > 1 else ""))
        instrumentation.remove_group(name)

    new_command("remove-instrumentation-group",
                remove_instrumentation_group_cmd,
                args = [arg(str_t, "name",
                            expander = group_expander)],
                short = "remove an instrumentation group",
                see_also = sorted(normal_cmds
                                  - set(["remove-instrumentation-group"])),
                type = ["Instrumentation"],
                doc = """
                Remove an existing instrumentation group.

                The <arg>name</arg> is the name of a group created with the
                <cmd>add-instrumentation-group</cmd> earlier. If the group
                still has established connections, these must first be removed
                with the <cmd>remove-instrumentation</cmd> command.""")

    def list_instrumentation_groups_cmd():
        ret = []
        for g in sorted(list(instrumentation.get_groups()),
                        key = lambda x: '' if x is None else x):
            if g != None:
                ret.append(g)
        return command_verbose_return(
            value = ret,
            message = "\n".join(ret) if ret else "No groups")

    new_command("list-instrumentation-groups",
                list_instrumentation_groups_cmd,
                short = "list instrumentation groups",
                see_also = sorted(normal_cmds
                                  - set(["list-instrumentation-groups"])),
                type = ["Instrumentation"],
                doc = """List the currently available groups that was created
                with the <cmd>add-instrumentation-group</cmd> command""")

def register_enable_disable_commands():
    user_num = instrumentation.get_filter_source("user")

    def enable_disable(id, name, group, enable, verbose):

        def enable_or_disable_connection(c, enable, verbose):

            if verbose:
                print("%s:" % ('Enabling' if enable else 'Disabling'), end=' ')
                print_connection(c)
            if enable:
                c.enable(user_num)
            else:
                c.disable(user_num)

        for c in filter_connections(id, name, group):
            enable_or_disable_connection(c, enable, verbose)

    def enable_instrumentation_cmd(id, name, group, verbose):
        enable_disable(id, name, group, True, verbose)

    def disable_instrumentation_cmd(id, name, group, verbose):
        enable_disable(id, name, group, False, verbose)

    new_command("enable-instrumentation",
                enable_instrumentation_cmd,
                args = [arg(int_t, "id", "?", None),
                        arg(str_t, "name", "?", expander = name_expander),
                        arg(str_t, "group", "?", expander = group_expander),
                        arg(flag_t, "-verbose")
                ],
                short = "enable instrumentation",
                see_also = sorted(normal_cmds
                                  - set(["enable-instrumentation"])),
                type = ["Instrumentation"],
                doc = """

                Enable an instrumentation connection that has been disabled
                earlier with the <cmd>disable-instrumentation</cmd>.

                Specify which connections to enable with one of the
                <arg>id</arg>, <arg>name</arg> or <arg>group</arg> arguments.
                The <arg>id</arg> specifies one unique connection.
                <arg>name</arg> specifies all connections associated with a
                specific tool. The <arg>group</arg> selects all connections
                associated with a connection group.

                The <tt>-verbose</tt> lists information on the connections
                that becomes enabled.""")

    new_command("disable-instrumentation",
                disable_instrumentation_cmd,
                args = [arg(int_t, "id", "?", None),
                        arg(str_t, "name", "?", expander = name_expander),
                        arg(str_t, "group", "?", expander = group_expander),
                        arg(flag_t, "-verbose")
                ],
                short = "disable instrumentation",
                see_also = sorted(normal_cmds
                                  - set(["disable-instrumentation"])),
                type = ["Instrumentation"],
                doc = """
                Disable instrumentation connections. The connections
                between the provider and tool remains, but instrumentation
                gathering is stopped.

                Specify which connections to disable with one of
                <arg>id</arg>, <arg>name</arg> or <arg>group</arg>
                arguments. The <arg>id</arg> specifies one unique connection.
                The <arg>name</arg> specifies all connections associated with
                a specific tool. The <arg>group</arg> selects all connections
                associated with a connection group.

                The <tt>-verbose</tt> lists information on the connections
                that becomes disabled.""")

def register_instrumentation_order_commands():
    def instrumentation_order_cmd(obj):
        for conn in obj.iface.instrumentation_order.get_connections():
            for pyconn in instrumentation.get_all_connections():
                if pyconn.get_connection_object() == conn:
                    print("%3d : %s %s" % (
                        pyconn.get_id(),
                        pyconn.get_description(),
                        " - disabled" if not pyconn.get_enabled() else ""))

    new_command("instrumentation-order", instrumentation_order_cmd,
                args = [arg(obj_t("object", "instrumentation_order"),
                            "provider")],
                short = "list instrumentation order for object",
                see_also = sorted(all_instrumentation_cmds -
                                  set(["instrumentation-order",
                                       ("<instrumentation_order>"
                                        ".instrumentation-order")])),
                namespace_copy = ("instrumentation_order",
                                  instrumentation_order_cmd),
                type = ["Instrumentation"],
                doc = """
                List the order of all instrumentation connections for an
                instrumentation <arg>provider</arg>. The order determines the
                order in which the instrumentation connections are
                dispatched.""")

    def get_connection_id(conn):
        for c in instrumentation.get_all_connections():
            if c.get_connection_object() == conn:
                return c.get_id()
        return None

    def id_expand(s, obj):
        if not obj: # None, if global command is used
            return []
        ids = [str(get_connection_id(c))
               for c in obj.iface.instrumentation_order.get_connections()]
        return get_completions(s, ids)

    def get_connection(id):
        if id == None:
            return None
        for c in instrumentation.get_all_connections():
            if c.get_id() == id:
                obj = c.get_connection_object()
                if obj:
                    return obj
                raise CliError(
                    "Error: the connection does not support reordering")
        raise CliError("Unknown connection: %d" % id)

    def instrumentation_move_cmd(obj, id, achor_id):
        id_obj = get_connection(id)
        achor_id_obj = get_connection(achor_id)
        conns = obj.iface.instrumentation_order.get_connections()

        if id_obj not in conns:
            raise CliError("Cannot find id = %d in %s" % (id, obj.name))

        if achor_id_obj and achor_id_obj not in conns:
            raise CliError("Cannot find id = %d in %s" % (achor_id, obj.name))

        obj.iface.instrumentation_order.move_before(get_connection(id),
                                                    get_connection(achor_id))

    new_command("instrumentation-move", instrumentation_move_cmd,
                args = [arg(obj_t("object", "instrumentation_order"),
                            "provider"),
                        arg(int_t, "id", expander = id_expand),
                        arg(int_t, "anchor-id", "?", None, expander = id_expand)],
                short = "reorder instrumentation connections",
                see_also = sorted(all_instrumentation_cmds -
                                  set(["instrumentation-move",
                                       ("<instrumentation_order>"
                                        ".instrumentation-move")])),
                namespace_copy = ("instrumentation_order",
                                  instrumentation_move_cmd),
                type = ["Instrumentation"],
                doc = """
                Move the connection identified by <arg>id</arg> just
                before the connection identified by
                <arg>anchor-id</arg> in the <arg>provider</arg>. If
                the achor connection is not given the connection will
                be moved last. This command can be used to control the
                order in which instrumentation connections are
                considered.""")

def register_instrumentation_filter_commands():
    def add_instrumentation_filter(filter, group):
        id = groups.cli_get_group_id(group)

        conns = [c for c in instrumentation.get_all_connections()
                 if group == None or c.get_group_id() == id]
        tools = set()
        for c in conns:
            tools.add(c.get_tool_object())

        f = f"{filter.name}" if filter else ""
        g = f"{group}" if group else ""
        for t in tools:
            quiet_run_command(f"{t.name}.add-filter {f} {g}")

        return command_return(
            message=f"Added {len(conns)} connection to {len(tools)} tools",
            value=len(conns))

    new_command("add-instrumentation-filter", add_instrumentation_filter,
                args = [arg(obj_t("filter", "instrumentation_filter_master"),
                            "filter"),
                        arg(str_t, "group", "?", expander = group_expander)],

                short = "add filter to connections",
                see_also = sorted(all_instrumentation_cmds
                                  - { "add-instrumentation-filter" }),
                type = ["Instrumentation"],

                doc = """Apply the instrumentation <arg>filter</arg>
                to all tools with the instrumentation <arg>group</arg>,
                or to all tools if no group is given. """)

    def remove_instrumentation_filter(filter, group, all_flag):
        def match_conn(c, filter, all_flag, gid):
            if filter and filter not in c.get_filter_objects():
                return False
            return all_flag or c.get_group_id() == gid

        if group and all_flag:
            raise CliError("Cannot combine -all and group")

        if not filter and not group and not all_flag:
            raise CliError("With no filter, either group or -all must be given")

        gid = groups.cli_get_group_id(group)

        conns = [c for c in instrumentation.get_all_connections()
                 if match_conn(c, filter, all_flag, gid)]

        tools = set()
        for c in conns:
            tools.add(c.get_tool_object())

        f = f"{filter.name}" if filter else ""
        a = "-all" if all_flag else ""
        g = f"{group}" if group else ""
        for t in tools:
            quiet_run_command(f"{t.name}.remove-filter {f} {a} {g}")

        return command_return(
            message=f"Removed {len(conns)} connections from {len(tools)} tools",
            value=len(conns))


    new_command(
        "remove-instrumentation-filter", remove_instrumentation_filter,
        args = [arg(obj_t("filter", "instrumentation_filter_master"),
                    "filter", "?"),
                arg(str_t, "group", "?",
                    expander = groups.group_expander),
                arg(flag_t, "-all")],
        type = ["Instrumentation"],
        short = "remove instrumentation filter",
        see_also = sorted(all_instrumentation_cmds
                          - { "remove-instrumentation-filter" }),
        doc = """Removes the <arg>filter</arg> from all tools. If
        <tt>-all</tt> is given, all filters will be removed.
        If <arg>group</arg> is given only filters connected to the group will be
        removed.""")


def register_instrumentation_commands():
    register_remove_instrumentation_command()
    register_list_instrumentation_command()
    register_group_commands()
    register_enable_disable_commands()
    register_instrumentation_order_commands()
    register_instrumentation_filter_commands()

# Don't use 'see-also' to these commands everywhere
order_cmds = set([
    "instrumentation-order",
    "<instrumentation_order>.instrumentation-order",
    "instrumentation-move",
    "<instrumentation_order>.instrumentation-move"])

normal_cmds = set([
    "add-instrumentation-group",
    "enable-instrumentation",
    "disable-instrumentation",
    "list-instrumentation",
    "list-instrumentation-groups",
    "remove-instrumentation-group",
    "remove-instrumentation",
    "add-instrumentation-filter",
    "remove-instrumentation-filter"
])

all_instrumentation_cmds = normal_cmds.union(order_cmds)

register_instrumentation_commands()
