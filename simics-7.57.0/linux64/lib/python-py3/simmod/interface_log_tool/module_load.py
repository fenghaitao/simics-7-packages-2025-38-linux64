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
from . import simics_start

def control_logged_interfaces_cmd(conn, ifaces_or_regexps, remove):
    if ifaces_or_regexps == [] and not remove:
        used = conn.enabled_wrapped_interfaces
        if used:
            return cli.command_return(
                message="The following interfaces are logged:\n" +
                "\n".join(used) + "\n",
                value=used)

    ifaces = simics_start.collect_ifaces_from_regexps(ifaces_or_regexps)
    current = set(conn.enabled_wrapped_interfaces)
    if remove:
        current.difference_update(set(ifaces))
    else:
        current.update(set(ifaces))
        current.difference_update(set(simics_start.blocked_ifaces))

    conn.enabled_wrapped_interfaces = list(current)

cli.new_command("control-logged-interfaces",
                control_logged_interfaces_cmd,
            [cli.arg(cli.str_t, "ifaces", "*", expander = simics_start.iface_expander),
             cli.arg(cli.flag_t, "-remove")],
                cls = "interface_log_tool",
                short = "control logged interfaces",
                doc = """This command can be used to control the logging of the
                interfaces when the tool has been created. <arg>ifaces</arg>
                sets the interfaces to log. Each string can be a name of an
                individual interface to consider, or one Python regular
                expressions that can match several interfaces. All interfaces
                mentioned are added to the currently logged interfaces. If
                <tt>-remove</tt> is given already enabled interfaces that match
                the ifaces list will be removed from the logging. If no
                flag is used, the current setting is printed.

                The command can be given several times, enabling (or disabling)
                more interfaces each time.
                """)

def control_blocked_interfaces_cmd(conn, ifaces_or_regexps, remove):
    if ifaces_or_regexps == [] and not remove:
        used = conn.blocked_interfaces
        if used:
            return cli.command_return(
                message="The following interfaces are blocked:\n" +
                "\n".join(used) + "\n",
                value=used)

    ifaces = simics_start.collect_ifaces_from_regexps(ifaces_or_regexps)
    current = set(conn.blocked_interfaces)
    if remove:
        current.difference_update(set(ifaces))
    else:
        current.update(set(ifaces))

    conn.blocked_interfaces = list(current)

cli.new_command("control-blocked-interfaces",
                control_blocked_interfaces_cmd,
            [cli.arg(cli.str_t, "ifaces", "*", expander = simics_start.iface_expander),
             cli.arg(cli.flag_t, "-remove")],
                cls = "interface_log_tool",
                short = "control blocked interfaces",
                doc = """This command can be used to control the logging of the
                interfaces when the tool has been created. <arg>ifaces</arg>
                sets the list of blocked interfaces not to log. Each string can
                be a name of an individual interface to consider, or one Python
                regular expressions that can match several interfaces. All
                interfaces mentioned are blocked from logging.  If
                <tt>-remove</tt> is given already blocked interfaces that match
                the ifaces list will be removed from the blocking list. If no
                flag is used, the current setting is printed.

                The command can be given several times, adding or removing
                interfaces from the blocked list.
                """)
