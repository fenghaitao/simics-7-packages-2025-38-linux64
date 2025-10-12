# © 2024 Intel Corporation
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
import conf
import simics
import instrumentation

import re

# Blocked interfaces by default,
# Some of these are called during the Simics prompt, which make them
# inconvenient to log them.
# And we skip the module_iface_wrapping since it is used by the wrapping itself.
blocked_ifaces = ["terminal_client", "terminal_server", "cmd_line_frontend",
                  "module_iface_wrapping"]

def all_known_interfaces():
    return set.union(*(set(simics.VT_get_interfaces(c))
                       for c in simics.SIM_get_all_classes()))

def collect_ifaces_from_regexps(regexps):
    all = set()
    for r in regexps:
        size = len(all)

        if r != "*": # skip special wildcard
            try:
                regexp = re.compile(r)
            except re.error as e:
                raise cli.CliError(f"Illegal regular expression, {e}: {r}")

            for k in all_known_interfaces():
                if re.match(regexp, k):
                    all.add(k)

        if len(all) == size:
            # did not match any
            if r == "*" or len(re.escape(r)) == len(r):
                all.add(r) # probably not a known interface at this point
            else:
                raise cli.CliError(f"Illegal interface name: {r}")
    return all

def new_command_fn(tool_class, name, filename, ifaces, blocked):
    if not conf.sim.wrap_iface:
        print("WARNING: the interface-log-tool only works if Simics is started"
              " with the --wrap-iface flag.")

    all = collect_ifaces_from_regexps(ifaces)
    blocked = collect_ifaces_from_regexps(blocked) if blocked else blocked_ifaces

    return simics.SIM_create_object(tool_class, name,
                                    file=filename,
                                    enabled_wrapped_interfaces=list(all),
                                    blocked_interfaces=list(blocked))

def iface_expander(prefix):
    return cli.get_completions(prefix, sorted(all_known_interfaces()))

new_cmd_extra_args = ([cli.arg(cli.filename_t(), "file", "?"),
                       cli.arg(cli.str_t, "ifaces", "*", expander = iface_expander),
                       cli.arg(cli.str_t, "blocked", "*", expander = iface_expander)],
                      new_command_fn)

instrumentation.make_tool_commands(
    "interface_log_tool",
    object_prefix = "iface",
    new_cmd_extra_args = new_cmd_extra_args,
    provider_requirements = "iface_wrap_instrumentation",
    make_add_instrumentation_cmd = False,
    connect_all_flag = False,
    new_cmd_can_connect = "automatic",
    unsupported = True,
    new_cmd_doc = f"""Creates a new interface log tool that provides interface
    logging for all interfaces implemented in Simics, including interfaces added
    by loadable modules.

    NOTE: this tool only works if you start Simics with the
    <tt>--wrap-iface</tt> flag. To control which interfaces you log you should
    use the <cmd>&lt;interface-log-tool>.control-wrapped-interfaces</cmd>
    command.

    The <arg>file</arg> argument specifies a file
    to write the log to. Without any file, the log output will be printed
    to standard out.

    The interface-log-tool can be configured with the interfaces to log. The
    <arg>ifaces</arg> sets the interfaces to enable logging for. Each
    string can be a name of an individual interface, or one Python
    regular expression, that can match several interfaces. All interfaces
    mentioned are added.

    For individual interfaces, those are added even though no such interfaces
    exists at the moment. If regular expressions are used, only existing
    interfaces are matched. If a module is later loaded into Simics, that
    registers new interfaces, those can be missed even if they match the any
    regular expression. However, there is a special expression, "*", that will
    match all interfaces, even if they are added later.

    The <arg>blocked</arg> argument can be used to block the logging of certain
    interfaces, even though they are mentioned in the ifaces list. This is also a
    list of individual interfaces or regular expressions.  The default value for
    the blocked argument is the following interfaces:
    {', '.join(blocked_ifaces)}. The blocked list does not support the "*"
    expression.

    Each line in the log starts with the thread name followed by the thread id,
    e.g., <tt>[simics 4184559]</tt>. This makes it clear which thread is doing
    the interface call. The thread name is set by Simics to identify the
    thread. The main thread in Simics is called simics.  The thread id is the id
    given by the operating system.

    For every call the log is indented three spaces, so it easy follow the call
    chains. When a call returns the indentation is decreased by three spaces
    again. Every thread has its own indentation depth.

    The tool is trying to print data types and values for all the method calls,
    including the argument name, and also the return value. For some data types,
    like the conf_object_t, some pretty printing is performed, showing the
    object name as well. For unknown pointers its type and value are printed,
    e.g., (pb_page_t *)0x555e06963dc8. If a value is unknown its argument name
    is printed followed by a question mark, ?, e.g., (map_info=?).""")
