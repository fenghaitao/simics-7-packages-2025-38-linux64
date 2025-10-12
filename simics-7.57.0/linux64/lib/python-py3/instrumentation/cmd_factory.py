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
import types
import conf
from cli import (
    CliError,
    arg,
    command_return,
    doc,
    expand_expression_to_dnf,
    flag_t,
    get_available_object_name,
    get_completions,
    int_t,
    new_command,
    new_unsupported_command,
    new_info_command,
    new_status_command,
    obj_t,
    str_t,
    )

from . import groups
from . import connections
from . import filter

class tool_info:
    def __init__(self, cls, provider_requirements):
        self.tool_class = cls
        self.provider_requirements = provider_requirements

_tool_classes = {}

def get_registered_tool_classes():
    return list(_tool_classes.values())

def _get_objects_with_matching_ifaces(dependencies):
    '''Return all objects which have matching dependencies.
    Dependencies are expression like: "(ifaceA & ifaceB) | ifaceC"'''

    oset = set()
    for o in simics.SIM_object_iterator(None):
        for andexp in dependencies.split("|"):
            if all([hasattr(o.iface, i) for i in andexp.split("&")]):
                oset.add(o)
    return sorted(list(oset))

def _get_matching_providers(f):
    objs = [o for o in simics.SIM_object_iterator(None) if f(o)]
    return sorted(objs)

def get_all_matching_providers(provider_requirements):
    if isinstance(provider_requirements, types.FunctionType):
        return _get_matching_providers(provider_requirements)
    else:
        req_dnf = expand_expression_to_dnf(provider_requirements)
        return _get_objects_with_matching_ifaces(req_dnf)

def new_tool_connection(con_obj, tool_obj, prov_obj, group_num = 0, desc = ""):
    new = connections.tool_connection(tool_obj, group_num, prov_obj, con_obj,
                                      desc)
    connections.insert_connection(tool_obj.name, new)
    return new

def connect(tool, prov, args, desc, group_num):
    # Request the tool to do the insertion
    conn = tool.iface.instrumentation_tool.connect(prov, args)

    if conn:
        # remember the connection
        new = new_tool_connection(conn, tool, prov, group_num, desc)
    else:
        raise CliError("Failed to connect %s to %s" % (
            tool.name, prov.name))

    return new

def connect_providers(obj, providers, group,
                      connect_pre_fn, *tool_args):
    # Verify group name
    try:
        group_id = groups.cli_get_group_id(group)
    except CliError as msg:
        simics.SIM_delete_object(obj)
        raise CliError("Cannot connect: %s" % msg)

    # Do generic setup
    args = []
    desc = ""
    ids = []
    prov_list = providers if isinstance(providers, list) else [providers]
    for provider in prov_list:
        try:
            if connect_pre_fn:
                ret = connect_pre_fn(obj, provider, *tool_args)
                if isinstance(ret, tuple):
                    (args, desc) = ret
                else:
                    (args, desc) = ([], ret)

            pyconn = connect(obj, provider, args, desc, group_id)
            ids.append(pyconn.get_id())
        except CliError as msg:
            print(msg)
    return ids

def get_connection_position(provider_obj, connection):
    if not hasattr(provider_obj.iface, "instrumentation_order"):
        return -1
    conns = provider_obj.iface.instrumentation_order.get_connections()
    for (i, c) in enumerate(conns):
        if c == connection:
            return i
    return -1

# Get all connections for a tool, return a list of tuples:
# (connection, provider-position)
def get_established_connections(tool):
    return [ (c, get_connection_position(c._provider, c._conn))
             for c in connections.get_named_connections(tool.name) ]

def provider_arg(name, prov_req_dnf_or_filter, cli_type = "+", expander = None):
    return arg(obj_t(name, prov_req_dnf_or_filter), name, cli_type, expander = expander)

user_num = -1

def add_tool_commands(simics_class,
                      provider_names,
                      provider_requirements,
                      cmd_type,
                      make_add_instrumentation_cmd,
                      make_remove_instrumentation_cmd,
                      make_enable_cmd,
                      make_disable_cmd,
                      make_info_cmd,
                      make_status_cmd,
                      make_delete_cmd,
                      make_filter_cmds,

                      connect_extra_args,
                      connect_all_flag,

                      # Info/status
                      info_cmd_extend_fn,
                      status_cmd_extend_fn):
    global user_num
    user_num = filter.get_filter_source("user")

    def connected_prov_expander(s, obj, prev_args):
        provs = [c._provider
                 for c in connections.get_named_connections(obj.name)]
        return get_completions(s, [t.name for t in provs])

    def id_expander(s, obj):
        all_ids = [str(c.get_id())
                   for c in connections.get_named_connections(obj.name)]
        return get_completions(s, all_ids)

    # Return true if a connection at pos matches the required elements
    def filter_connection(connection, req_id, req_provider, req_group):
        if (req_id != None) and (req_id != connection.get_id()):
            return False

        if req_provider and req_provider != connection._provider:
            return False

        if req_group:
            if req_group != groups.get_group_name(connection.get_group_id()):
                return False

        return True

    def check_args(obj, cid, prov, group):
        if cid != None:
            if prov or group:
                raise CliError("Cannot combine connection-id with other arguments")

            all_ids = [c.get_id()
                       for c in connections.get_named_connections(obj.name)]
            if cid not in all_ids:
                raise CliError("Invalid connection id")

        if prov:
            all_provs = {c._provider
                         for c in connections.get_named_connections(obj.name)}

            provs = set(prov) if isinstance(prov, list) else {prov}
            uncon_provs = provs - all_provs
            if uncon_provs:
                names = ", ".join([p.name for p in uncon_provs])
                raise CliError("Provider%s '%s' is not connected"
                               % ('s' if len(uncon_provs) > 1 else '', names))

        if group:
            gid = groups.cli_get_group_id(group)
            grps = [c.get_group_id()
                    for c in connections.get_named_connections(obj.name)]

            if not gid in grps:
                raise CliError("Group '%s' is not connected" % group)

    def conn_str(count):
        if count == 1:
            return "1 connection"
        return "%d connections" % count

    def enable_instrumentation_cmd(obj, cid, provider, group):
        check_args(obj, cid, provider, group)
        count = 0
        for (c, pos) in get_established_connections(obj):
            if filter_connection(c, cid, provider, group):
                c.enable(user_num)
                count += 1
        return command_return(message = "Enabled %s" % conn_str(count),
                              value = count)

    def disable_instrumentation_cmd(obj, cid, provider, group):
        check_args(obj, cid, provider, group)
        count = 0
        for (c, pos) in get_established_connections(obj):
            if filter_connection(c, cid, provider, group):
                c.disable(user_num)
                count += 1
        return command_return(message = "Disabled %s" % conn_str(count),
                              value = count)

    def remove_instrumentation_cmd(obj, cid, provider, group):
        check_args(obj, cid, provider, group)
        count = 0
        providers = provider if isinstance(provider, list) else [provider]
        for (c, pos) in get_established_connections(obj):
            for p in providers if providers else [None,]:
                if filter_connection(c, cid, p, group):
                    connections.delete_connection(c)
                    c.delete()
                    count += 1
        return command_return(message = "Removed %s" % conn_str(count),
                              value = count)

    def delete_cmd(obj):
        # Remove all connections etc.
        tool_conns = connections.get_named_connections(obj.name)
        for c in tool_conns:
            connections.delete_connection(c)
            c.delete()

        simics.SIM_delete_object(obj)
        count = len(tool_conns)
        return command_return(message = "Removed %s" % conn_str(count),
                              value = count)

    def list_providers_cmd(obj):
        msg = ""
        providers = get_all_matching_providers(provider_requirements)
        for p in providers:
            msg += f"{p.name}\n"
        return command_return(message=msg, value=providers)

    def info_cmd(obj):
        cl = []
        cl.append(("Interfaces",
                   [("Required", provider_requirements)]))
        if info_cmd_extend_fn:
            return cl + info_cmd_extend_fn(obj)
        return cl

    def status_cmd(obj):

        connections = []
        for (c, pos) in get_established_connections(obj):
            provider = c.get_provider_object().name
            connection = c.get_connection_object().name
            agg = c.get_slave().name
            group = c.get_group_id()
            group_name = groups.get_group_name(group)
            if c.get_enabled():
                disabled = "no"
            else:
                disabled = "yes, by %s" % (c.get_disabled_string())

            cl = [
                ("provider", provider),
                ("connection", connection),
                ("aggregator", agg),
                ("args", c._desc),
                ("group", group_name),
                ("disabled", disabled),
                ("filters", c.get_filters())
            ]

            connections.append(["Connection %d" % (c.get_id(),),
                                cl])

        status = connections

        if status_cmd_extend_fn:
            return status + status_cmd_extend_fn(obj)
        return status

    # body of add_tool_commands
    # -------------------------
    (prov_name, prov_names) = provider_names

    if make_info_cmd:
        new_info_command(simics_class, info_cmd,
                         ctype = cmd_type,
                         doc = ("Print detailed information about the" +
                                " configuration of the tool."))

    if make_status_cmd:
        new_status_command(simics_class, status_cmd,
                           ctype = cmd_type,
                           doc = ("Print detailed information about the" +
                                  " current status of the tool."))

    if make_add_instrumentation_cmd:
        make_connect_command(simics_class,
                             provider_names,
                             provider_requirements,
                             cmd_type,
                             connect_all_flag,
                             connect_extra_args)

    args = [arg(int_t, "id", "?", None, expander = id_expander),
            provider_arg(prov_name, provider_requirements, "?",
                         connected_prov_expander),
            arg(str_t, "group", "?", expander = groups.group_expander)]

    if make_enable_cmd:
        new_command(
            "enable-instrumentation", enable_instrumentation_cmd,
            args = args,
            type = cmd_type,
            cls = simics_class,
            short = "enable instrumentation",
            doc = """Enables instrumentation for previously disabled
            connections. Without any arguments, all connections for the
            tool will be enabled.

            The <arg>id</arg> specifies a specific connection number
            to be enabled.

            The <arg>%s</arg> selects the connections towards a specific
            provider that should be enabled.
            The <arg>group</arg> will only enable the
            connections which have been associated to a specific group.
            """ % prov_name)

    if make_disable_cmd:
        new_command(
            "disable-instrumentation", disable_instrumentation_cmd,
            args = args,
            type = cmd_type,
            cls = simics_class,
            short = "disable instrumentation",

            doc = """Disables instrumentation for established
            connections. The connection(s) between the provider and host
            remains, but instrumentation is either stopped from the
            provider or filtered away in the tool.

            Without any arguments, all connections for the tool will be
            disabled.

            The <arg>id</arg> specifies a specific connection number
            to be disabled.

            The <arg>%s</arg> selects the connections towards a specific
            provider that should be disabled.

            The <arg>group</arg> will only disable the
            connections which have been associated to a specific group.
            """ % prov_name)

    if make_remove_instrumentation_cmd:
        rargs = list(args)
        rprov_name = prov_name
        if prov_names:
            rargs[1] = provider_arg(prov_names, provider_requirements, "*",
                                    connected_prov_expander)
            rprov_name = prov_names
        new_command(
            "remove-instrumentation", remove_instrumentation_cmd,
            args = rargs,
            type = cmd_type,
            cls = simics_class,
            short = "remove instrumentation",

            doc = """Removes instrumentation for established
            connections.

            Without any arguments all connection for the tool will be
            removed.

            The <arg>id</arg> specifies a specific connection number
            to be removed.

            The <arg>%s</arg> selects the connections towards one or
            several %s that should be removed.

            The <arg>group</arg> will only remove the
            connections which have been associated to a specific group.
            """ % (rprov_name, rprov_name))

    if make_delete_cmd:
        new_command(
            "delete", delete_cmd,
            args = [],
            type = cmd_type,
            cls = simics_class,
            short = "deletes instrumentation tool",
            doc = """Removes any connected instrumentation and deletes
            the tool object.""")

    if 1:
        new_command(
            "list-providers", list_providers_cmd,
            args = [],
            type = cmd_type,
            cls = simics_class,
            short = "list-provider objects",
            doc = """List all provider objects that can be connected to the
            tool.""")

    if make_filter_cmds:

        def add_filter_cmd(obj, filter_obj, group):
            gid = groups.cli_get_group_id(group)
            conns_added = filter.attach_filter(obj.name, filter_obj, gid)

            return command_return(
                message=f"Added filter to {conns_added} connections",
                value=conns_added)

        def remove_filter_cmd(obj, filter_obj, all_flag, group):
            def match_conn(c, filter, all_flag, id):
                if filter and filter not in c.get_filter_objects():
                    return False
                return all_flag or c.get_group_id() == id

            if group and all_flag:
                raise CliError("Cannot combine -all and group")

            if not filter and not group and not all_flag:
                raise CliError(
                    "With no filter, either group or -all must be given")

            gid = groups.cli_get_group_id(group)

            conns_removed = 0
            for c in connections.get_named_connections(obj.name):
                if match_conn(c, filter_obj, all_flag, gid):
                    print(c.get_filter_objects())
                    for f in c.get_filter_objects()[:]:
                        print(f)
                        if filter_obj == None or f == filter_obj:
                            print(c)
                            filter.detach_filter(obj.name, f)
                        conns_removed += 1
            return command_return(
                message=f"Removed filters from {conns_removed} connections",
                value=conns_removed)

        new_command(
            "add-filter", add_filter_cmd,
            args = [arg(obj_t("filter", "instrumentation_filter_master"),
                        "filter"),
                    arg(str_t, "group", "?", expander = groups.group_expander)],
            cls = simics_class,
            type = cmd_type,
            short = "add filter to the tool",

            doc = """Add a <arg>filter</arg> object to the tool. This
            allows the filter to control fine grained enabling and
            disabling of connections in the tool. See the
            documentation of the existing filters for more information
            of their capabilities.
            Use the <arg>group</arg> parameter to tie the filter to just a
            particular instrumentation group.""")

        new_command(
            "remove-filter", remove_filter_cmd,
            args = [arg(obj_t("filter", "instrumentation_filter_master"),
                        "filter", "?"),
                    arg(flag_t, "-all"),
                    arg(str_t, "group", "?", expander = groups.group_expander)],
            cls = simics_class,
            type = cmd_type,
            short = "remove filter from the tool",
            doc = """Removes the <arg>filter</arg> from the tool. If
            <tt>-all</tt> is given, all filters will be removed.
            If <arg>group</arg> is given only filters connected to a group
            will be removed.""")

@doc('Python function which creates commands for instrumentation tools',
     module = "instrumentation",
     doc_id = 'instrumentation_tool_python_api')
def make_tool_commands(simics_class,
                       object_prefix,
                       provider_requirements,
                       tied_to_class = None,
                       provider_names = ("provider", "providers"),
                       cmd_type = None,
                       # Which commands that should be created
                       make_new_cmd = True,
                       make_add_instrumentation_cmd = True,
                       make_remove_instrumentation_cmd = True,
                       make_enable_cmd = True,
                       make_disable_cmd = True,
                       make_info_cmd = True,
                       make_status_cmd = True,
                       make_delete_cmd = True,
                       make_filter_cmds = True,

                       new_cmd_name = None,
                       new_cmd_extra_args = ([], None),    # (args, fn)
                       new_cmd_can_connect = True,
                       new_cmd_doc = "",

                       connect_extra_args = ([], None, ""), # (args, fn, doc)
                       connect_all_flag = True,

                       info_cmd_extend_fn = None,
                       status_cmd_extend_fn = None,
                       unsupported = False):
    """This factory function creates several useful commands for an
    instrumentation tool. Using this function will assert that all
    instrumentation tools works in an uniform manner. The following
    commands are created:<ul>

    <li><cmd>new-&lt;tool&gt;</cmd></li>
    <li><cmd>&lt;tool&gt;.add-instrumentation</cmd></li>
    <li><cmd>&lt;tool&gt;.remove-instrumentation</cmd></li>
    <li><cmd>&lt;tool&gt;.enable-instrumentation</cmd></li>
    <li><cmd>&lt;tool&gt;.disable-instrumentation</cmd></li>
    <li><cmd>&lt;tool&gt;.info</cmd></li>
    <li><cmd>&lt;tool&gt;.status</cmd></li>
    <li><cmd>&lt;tool&gt;.delete</cmd></li>
    <li><cmd>&lt;tool&gt;.add-filter</cmd></li>
    <li><cmd>&lt;tool&gt;.remove-filter</cmd></li>
    </ul>

    The function should be called from the tool's <file>simics_start.py</file>
    file (read at Simics start-up time, before the module is loaded).
    The <cmd>new-&lt;tool&gt;</cmd> will be created directly while the
    other commands will appear once the tool's module has been loaded.

    For the simplest case, only the <arg>simics_class</arg>,
    <arg>object_prefix</arg> and <arg>provider_requirements</arg>
    parameters needs to be specified. The rest of the parameters can
    be used to make tool specific adaptations for the commands created.

    By default, all commands useful for an instrumentation tool are created.
    However, if certain commands should be omitted, the corresponding
    <arg>make_*</arg> parameters can be set to False.

    <b><cmd>new-&lt;tool&gt;</cmd></b>: This command creates a Simics object
    for the given class. The command will be called
    <tt>new-&lt;simics_class&gt;</tt> where any underscores are replaced with
    hyphens. The <arg>object_prefix</arg> is used to create an automatic name
    for the object, by concatenating the prefix with a serial number. This
    automatic name can be overridden by supplying the <arg>name</arg> command
    argument.

    The <arg>provider_requirements</arg> specifies what interface(s) the
    tool depends on from the provider in order to connect, two variants
    can be used.
    <ul>
    <li>A string with the interface requirement. For example,
    <tt>cpu_instrumentation_subscribe</tt> (when this interface is needed)
    or more complex such as
    <tt>cpu_instrumentation_subscribe &amp; x86_instrumentation_subscribe</tt>
    when both interfaces must be available.
    </li>
    <li>A Python function acting as a filter function, which takes an object
    as argument and returns True if it was accepted or False if it should not
    be connected.</li>
    </ul>

    By default, the <cmd>new-&lt;tool&gt;</cmd> command is created in the
    Simics global namespace. The optional <arg>tied_to_class</arg> creates
    the <cmd>new-&lt;tool&gt;</cmd> command in the class's namespace, i.e. it
    will be invoked as <cmd>&lt;class&gt;.new-&lt;tool&gt;</cmd>.

    The <arg>provider_names</arg> parameter should be a tuple of two strings,
    where the first part is the singular name of the provider and the second
    the plural. This can be used to give a more descriptive name for the
    provider objects, e.g., ('processor', 'processors') or ('mouse', 'mice').
    This is used in both the argument description and the commands associated
    help text. If the tool can only be connected to one object, <tt>None</tt>
    can be specified as the plural argument.

    By default, the <cmd>new-&lt;tool&gt;</cmd> command uses simics_class as
    the command name. Other name can be used by setting the optional
    <arg>new_cmd_name</arg>.

    If the tool needs additional arguments when created, for instance to be
    able to set required attributes, the <arg>new_cmd_extra_args</arg>
    parameter can be used. This parameter is a tuple with two elements; the
    first specifies additional CLI arguments added to the command and the
    second element specifies a function that will be called to create the
    object. The function takes the class of the tool, the name of the object,
    and then user added parameters corresponding to the CLI arguments. The
    function should return the created object. The following example
    illustrates how this can be done:

    <pre size="smaller">
    import instrumentation
    def create_logger(tool_class, name, filename):
        return SIM_create_object(tool_class, name, log_file=filename)

    instrumentation.make_tool_commands(
        'logger_tool', 'logger',
        new_cmd_extra_args = ([(filename_t(), 'log-file', '?', 'default.log')],
                              create_logger),
        new_cmd_doc = 'The log-file argument sets the log file to write to')
    </pre>

    The optional <arg>cmd_type</arg> may specify a list of help categories for
    the created commands. If not specified, all commands
    will be added to the "Instrumentation" category.

    By default, the <cmd>new-&lt;tool&gt;</cmd> command will get the same
    connection arguments as the <cmd>&lt;tool&gt;.add-instrumentation</cmd>
    command, see below. However, the <arg>new_cmd_can_connect</arg> can be set
    to False to remove the connection arguments.  The
    <arg>new_cmd_doc</arg> can be set to improve and customize the help text
    for the command.

    <b><cmd>&lt;tool&gt;.add-instrumentation</cmd></b>: This command
    connects the tool to one or several providers.

    The <arg>connect_all_flag</arg> which is set to True by default adds a
    <i>-connect-all</i> command switch to the
    <cmd>add-instrumentation</cmd> command. This is a convenient way to
    connect to all compatible providers in the system.

    When using <cmd>add-instrumentation</cmd>, each connection to a
    provider can be configured differently, allowing the tool to instrument
    different aspects of the system.
    Tools that supports this, should use the <arg>connect_extra_args</arg>
    parameter to add additional arguments to the command. This
    parameter is a tuple with three elements:
    <ul>
    <li>The additional CLI arguments as a list.</li>
    <li>A pre-connect function (called prior to connecting to the provider),
    which takes the parameters: (tool_object, provider_object,
    *additional_cli_args).
    The function should return a tuple with two elements; the argument
    list which will be passed to the tool's <fun>connect()</fun> method,
    followed by a textual description of the arguments used, this string
    is used as a short description of the connection and will for instance
    be used by the <cmd>list-instrumentation</cmd> command.
    Any errors in the additional arguments can raise a <tt>cli.CliError</tt>
    exception, causing the connection to be discarded.</li>
    <li>Additional documentation for the arguments added to the
    <cmd>add-instrumentation</cmd> command, found in the help text
    of the command.</li>
    </ul>

    The provider can be <tt>None</tt> if the tool is created without
    any connection(s).  This allows the tool to signal an error if
    arguments are given which do not have any effect.

    The following code is an example of how to use the
    <arg>connect_extra_args</arg>:

    <pre size="smaller">
    import instrumentation
    def pre_connect(obj, provider, verbose_flag, reg_num):
        if provider == None and (verbose_flag or reg_num != None):
            raise cli.CliError("Connect arguments given without a provider")

        args = [["verbose", verbose_flag],
                ["reg_num", reg_num]]
        desc = 'Traces reg-%d %s' % (
            reg_num, '-verbose' if verbose_flag else '')
        return (args, desc)

    instrumentation.make_tool_commands(
        'reg-trazer', 'traze',
        connect_extra_args = (
            [cli.arg(cli.flag_t, '-v'),
             cli.arg(cli.int_t, 'reg-num', "?", None)],
            pre_connect,
            '-v for verbose mode. The reg-num sets which register to trace.'))
    </pre>

    The <cmd>add-instrumentation</cmd> command also gets a <arg>group</arg>
    argument that can be set to add the connection to an instrumentation
    group. See the <cmd>add-instrumentation-group</cmd> command for more
    information.

    <b><cmd>&lt;tool&gt;.remove-instrumentation</cmd></b>: This command
    removes connections previously established.

    <b><cmd>&lt;tool&gt;.info</cmd></b> and
    <b><cmd>&lt;tool&gt;.status</cmd></b>: These commands displays some
    simple generic instrumentation information.
    It is also possible to extend the output of the info/status
    commands by passing a Python function in the
    <arg>info_cmd_extend_fn</arg> and <arg>status_cmd_extend_fn</arg>
    parameters. These functions takes the tool objects as parameter
    and should return a list of the following format:

    <tt>[(heading, [(tag, value), ...]), ...]</tt>

    This gives the following output to the info/status command: <pre>
    heading:
       tag1 : value1
       tag2 : value2
       ...
    ...
    </pre>

    <b><cmd>&lt;tool&gt;.disable-instrumentation</cmd></b> and
    <b><cmd>&lt;tool&gt;.enable-instrumentation</cmd></b>: These commands
    allows the user to disable and enable the tools connections.

    <b><cmd>&lt;tool&gt;.add-filter</cmd></b> and
    <b><cmd>&lt;tool&gt;.remove-filter</cmd></b>: These commands add
    or remove a filter associated with the tool. A filter can disable and
    enable the tools connection during execution.

    """

    # Adds the object specific commands, called directly if the class
    # exists, or lazily when the module becomes loaded.
    def add_object_commands():

        add_tool_commands(simics_class,
                          provider_names,
                          provider_requirements,
                          cmd_type,
                          make_add_instrumentation_cmd,
                          make_remove_instrumentation_cmd,
                          make_enable_cmd,
                          make_disable_cmd,
                          make_info_cmd,
                          make_status_cmd,
                          make_delete_cmd,
                          make_filter_cmds,
                          connect_extra_args,
                          connect_all_flag,

                          info_cmd_extend_fn,
                          status_cmd_extend_fn)


    def add_new_command():
        make_new_command(simics_class,
                         tied_to_class,
                         object_prefix,
                         provider_names,
                         provider_requirements,
                         cmd_type,
                         new_cmd_name,
                         new_cmd_extra_args,
                         new_cmd_can_connect,
                         connect_all_flag,
                         connect_extra_args,
                         new_cmd_doc,
                         unsupported)

    # Wait until the class is registered and add the commands then
    def add_command_when_class_registered(add_cmd_fn, class_name):
        # This function is unique for each run of make_tool_commands
        # so the delete hap would not delete all occurrences
        def _delayed_tool_cmd_registration(data, trigger, name):
            if class_name == name:
                add_cmd_fn()
                simics.SIM_hap_delete_callback("Core_Conf_Class_Register",
                                               _delayed_tool_cmd_registration,
                                               None)
        simics.SIM_hap_add_callback("Core_Conf_Class_Register",
                                    _delayed_tool_cmd_registration, None)

    # body of make_tool_commands
    if cmd_type == None:
        # Add instrumentation category default
        cmd_type = ['Instrumentation',]

    if make_new_cmd:
        if not new_cmd_name:
            new_cmd_name = 'new-' + simics_class.replace('_', '-')
        if not tied_to_class or hasattr(conf.classes,
                                        tied_to_class.replace('-', '_')):
            add_new_command()
        else:
            add_command_when_class_registered(add_new_command, tied_to_class)

    if not simics_class in _tool_classes:
        _tool_classes[simics_class] = tool_info(simics_class,
                                                provider_requirements)
        if hasattr(conf.classes, simics_class):
            # Class already loaded, create object commands directly
            add_object_commands()
        else:
            add_command_when_class_registered(add_object_commands, simics_class)

def make_new_command(simics_class,
                     tied_to_class,
                     object_prefix,
                     provider_names,
                     provider_requirements,
                     cmd_type,
                     new_cmd_name,
                     new_cmd_extra_args,
                     can_connect, # True/False or the string "automatic"
                     connect_all_flag,
                     connect_extra_args,
                     doc,
                     unsupported):

    (prov_name, prov_names) = provider_names
    (obj_args, obj_args_fn) = new_cmd_extra_args
    (connect_args, connect_pre_fn, connect_doc) = connect_extra_args

    automatic_connect = False
    if isinstance(can_connect, str):
        if can_connect != "automatic":
            raise CliError('Illegal setting for can_connect option: '
                           f'"{can_connect}",'
                           ' only "automatic" is supported.')
        automatic_connect =True
        can_connect = False

    if not can_connect:
        connect_all_flag = False

    # Callback for new-<class> command
    # Creates a tool and optionally connects the tool to providers
    def new_tool_cmd(*args):
        # If tied_to_class, the first argument specifies the object
        # which is not used in this function. In Python 3, one can
        # do: (object, name, *args) = args.
        name_idx = 1 if tied_to_class else 0
        name, args = args[name_idx], args[name_idx+1:]

        if name == None:
            name = get_available_object_name(object_prefix)

        # Only the name argument has a given position, all other arguments
        # have dynamic positions depending on the config given by the user.
        alist = list(args)

        # User selected additional arguments when creating the object
        user_obj_args = alist[:len(obj_args)]
        alist = alist[len(obj_args):]

        providers   = alist.pop(0) if can_connect           else []
        parent      = alist.pop(0) if connect_all_flag      else False
        connect_all = alist.pop(0) if connect_all_flag      else False
        group       = alist.pop(0)

        # User selected additional arguments for the connection (last)
        user_conn_args = alist

        if [bool(providers), bool(parent), connect_all].count(True) > 1:
            raise CliError("Cannot mix -connect-all, parent and %s." % (
                prov_names if prov_names else prov_name))

        if automatic_connect:
            providers = get_all_matching_providers(provider_requirements)
            if len(providers) != 1:
                CliError(f"Number of matching providers are {len(providers)}"
                         ", cannot auto connect")
        elif connect_all or parent:
            providers = get_all_matching_providers(provider_requirements)
            if parent:
                providers = [p for p in providers
                             if p.name.startswith(parent.name + ".")]

            if providers == []:
                raise CliError("No matching %s." % (
                    prov_names if prov_names else prov_name))

        try:
            if obj_args:
                tool = obj_args_fn(simics_class, name, *user_obj_args)
            else:
                tool = simics.SIM_create_object(simics_class, name)
        except simics.SimExc_General as msg:
            raise CliError("Cannot create %s: %s" % (name, msg))

        if providers:
            _ = connect_providers(tool, providers, group, connect_pre_fn,
                                  *user_conn_args)
        elif can_connect and connect_pre_fn:
            # Inform the pre_connect function that nothing is connected
            try:
                connect_pre_fn(tool, None, *user_conn_args)
            except CliError as msg:
                simics.SIM_delete_object(tool)
                raise CliError(msg)

        msg = "Created %s" % (tool.name)
        connected = len(connections.get_named_connections(tool.name))
        if connected:
            msg += " (connected to %d %s)" % (
                connected, prov_name if connected == 1 else prov_names)
        else:
            msg += " (unconnected)"

        return command_return(message = msg, value = tool)

    # Body of make_new_command
    if not doc:
        doc = ("Create a new object of the <class>%s</class> class. "
               % simics_class)

    doc += """<br/><br/>The optional <arg>name</arg> argument can be
    used to set a name of the created object. If no name is given,
    a default name <i>%s</i> followed by a sequence number is generated
    (<i>%s0</i>, <i>%s1</i>,...).""" % (object_prefix, object_prefix,
                                        object_prefix)

    # The name argument
    args = [arg(str_t, "name", "?", None)]

    # Additional arguments for instantiation
    if obj_args:
        args.extend(obj_args)

    if can_connect:
        if prov_names: # we have the plural name
            cli_type = "*" if connect_all_flag else "+"
            prov_arg_name = prov_names
        else:
            cli_type = "?"
            prov_arg_name = prov_name
            connect_all_flag = False  # Useless for only one provider

        if isinstance(provider_requirements, types.FunctionType):
            args.append(provider_arg(prov_arg_name,
                                     provider_requirements, cli_type))
        else:
            req_dnf = expand_expression_to_dnf(provider_requirements)
            args.append(provider_arg(prov_arg_name,
                                     req_dnf, cli_type))

        if prov_names:
            doc += """<br/><br/> The optional <arg>%s</arg> argument,
            supports connecting one or several %s directly. """ % (
                prov_names, prov_names)

    if connect_all_flag:
        args.append(arg(obj_t("parent", "component"), "parent", "?"))

        doc += """With the optional <arg>parent</arg> argument a hierarchical
                  object can be specified and all %s below this object
                  matching the provider requirements will be connected to
                  the tool.""" % prov_names

        args.append(arg(flag_t, "-connect-all"))
        doc += """
        The <tt>-connect-all</tt> flag can be given to add a connection to all
        supported %s in the configuration.""" % prov_names

    args.append(arg(str_t, "group", "?", expander = groups.group_expander))
    doc += """<br/><br/>The optional argument <arg>group</arg> lets a
    user specify a named instrumentation group to use for the connection.
    (See <cmd>add-instrumentation-group</cmd> for details on named
    groups.)"""

    # Additional arguments for connecting
    if can_connect and connect_args:
        args.extend(connect_args)
        doc += "<br/><br/>" + connect_doc

    args = dict(args = args,
                type = cmd_type,
                cls = tied_to_class,
                short = "create a new %s object" % simics_class,
                doc = doc)

    if unsupported:
        new_unsupported_command(new_cmd_name, "internals", new_tool_cmd, **args)
    else:
        new_command(new_cmd_name, new_tool_cmd, **args)

def make_connect_command(simics_class,
                         provider_names,
                         provider_requirements,
                         cmd_type,
                         connect_all_flag,
                         connect_extra_args):
    (prov_name, prov_names) = provider_names
    (connect_args, connect_pre_fn, connect_doc) = connect_extra_args

    def add_instrumentation_cmd(obj, providers, *args):
        # Only the obj, providers and group arguments are used by default, the
        # rest of the arguments depend on the user selection. Consequently, we
        # need to extract the other each argument dynamically.
        alist = list(args)
        parent      = alist.pop(0) if connect_all_flag      else False
        connect_all = alist.pop(0) if connect_all_flag      else False
        group       = alist.pop(0)

        # Remaining should be the user selected arguments for the connection
        tool_args = alist

        if [bool(providers), bool(parent), connect_all].count(True) > 1:
            raise CliError("Cannot mix -connect-all, parent and %s." % (
                prov_names if prov_names else prov_name))

        if connect_all or parent:
            providers = get_all_matching_providers(provider_requirements)
            if parent:
                providers = [p for p in providers
                             if p.name.startswith(parent.name + ".")]

        if not providers:
            raise CliError("Nothing to connect.")

        ids = connect_providers(obj, providers, group, connect_pre_fn,
                                *tool_args)

        n_ids = len(ids)
        msg = "Connected to %d %s" % (n_ids, prov_name
                                      if n_ids <= 1 else prov_names)

        return command_return(message = msg, value = ids)

    # Connect command
    if prov_names: # we have the plural name
        cli_type = "*" if connect_all_flag else "+"
        prov_arg_name = prov_names
    else:
        cli_type = "1"
        prov_arg_name = prov_name
        connect_all_flag = False  # Useless for only one provider

    if isinstance(provider_requirements, types.FunctionType):
        args = [provider_arg(prov_arg_name,
                             provider_requirements, cli_type)]
    else:
        req_dnf = expand_expression_to_dnf(provider_requirements)
        args = [provider_arg(prov_arg_name, req_dnf, cli_type)]

    doc = ("""Connects the tool to one """
           + (("or several " + prov_names)
              if prov_names else prov_name)
           + (" as given by the <arg>%s</arg> argument." % prov_arg_name))

    if connect_all_flag:
        args.append(arg(obj_t("parent", "component"), "parent", "?"))

        doc += """The <arg>parent</arg> argument specifies an hierarchical
                  object and all %s below this object matching the provider
                  requirements will be added to the tool.""" % prov_names

        args.append(arg(flag_t, "-connect-all"))
        doc += """The <tt>-connect-all</tt> flag can be given to
        add a connection to all supported %s in the configuration.
        """ % prov_names

    args.append(arg(str_t, "group", "?", expander = groups.group_expander))
    doc += """<br/><br/>The optional argument <arg>group</arg> lets a
    user specify a named instrumentation group to use for the connection.
    (See <cmd>add-instrumentation-group</cmd> for details on named
    groups.)"""

    # Tool specific arguments last
    if connect_args:
        args += connect_args
        doc += "<br/><br/>" + connect_doc

    new_command(
        "add-instrumentation", add_instrumentation_cmd,
        args = args,
        type = cmd_type,
        cls = simics_class,
        short = "add instrumentation",
        doc = doc)
