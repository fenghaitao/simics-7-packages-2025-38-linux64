# © 2020 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import simics, conf
import os
from cli import (
    CliError,
    arg,
    command_quiet_return,
    filename_t,
    flag_t,
    get_available_object_name,
    int_t,
    new_command,
    )
from simicsutils.host import is_windows
from deprecation import DEPRECATED
import update_checkpoint as uc

def external_connection_attributes(obj):
    if hasattr(obj, 'port'):
        obj.tcp.port = obj.port
        delattr(obj, 'port')
    if hasattr(obj, 'unix_socket'):
        obj.unix_socket.socket_name = obj.unix_socket
        delattr(obj, 'unix_socket')
    if hasattr(obj, 'use_ipv4'):
        conf.sim.force_ipv4 = obj.use_ipv4
        delattr(obj, 'use_ipv4')

uc.SIM_register_class_update(7003, "telnet_frontend",
                             external_connection_attributes)

def telnet_frontend_cmd(port_or_socket_arg, max_connections,
                        non_interactive, plain_text):
    (_, port_or_socket, _) = port_or_socket_arg
    if isinstance(port_or_socket, str):
        (port, unix_socket) = (None, port_or_socket)
    else:
        (port, unix_socket) = (port_or_socket, None)
        if not (port == 0 or 1024 <= port <= 65535):
            raise CliError("Port number should be between 1024 and 65535")

    if is_windows() and unix_socket:
        raise CliError("UNIX domain sockets are not available on Windows.")

    tcon = simics.pre_conf_object(get_available_object_name("tcon"),
                                  "telnet_frontend")
    tcon.max_connections = max_connections
    tcon.interactive = not non_interactive
    tcon.plain_text = bool(plain_text) # bool() can be removed in Simics 5
    simics.SIM_add_configuration([tcon], None)
    tcon = simics.SIM_get_object(tcon.name)
    try:
        if unix_socket:
            tcon.unix_socket.socket_name = unix_socket
        elif port:
            tcon.tcp.port = port
        else:
            tcon.tcp.port = 0
    except simics.SimExc_IllegalValue:
        pass
    if tcon.tcp.port:
        print(f"\nSECURITY WARNING: Port {tcon.tcp.port} will be open "
              "for anyone to access.\n")
    if not is_windows() and tcon.unix_socket.socket_name is not None:
        return command_quiet_return(value=tcon.unix_socket.socket_name)
    elif tcon.tcp.port:
        return command_quiet_return(value=tcon.tcp.port)
    else:
        simics.SIM_delete_object(tcon)
        raise CliError("Failed creating telnet-frontend")

new_command("telnet-frontend", telnet_frontend_cmd,
            args = [arg((int_t, filename_t()),
                         ("port", "unix_socket"), "?", (int_t, 0, "port")),
                    arg(int_t, "max-connections", "?", 0),
                    arg(flag_t, "-non-interactive"),
                    arg(flag_t, "-plain-text")],
            type = ["CLI"],
            short = "enable telnet access to the command line",
            doc = """
Creates a new Simics command-line accessible using telnet on TCP port
<arg>port</arg> or on UNIX socket <arg>unix_socket</arg>. If neither
<arg>port</arg> nor <arg>unix_socket</arg> is specified, a currently
free port will be selected. If a busy port is specified the command
will fail. The port or UNIX socket actually used is returned by the
command.

The command will fail if a privileged TCP socket is specified or if
<arg>unix_socket</arg> specifies a file that already exists. UNIX sockets
are not supported on Windows.

The <tt>-non-interactive</tt> flag can be used to prepare for scripted,
non-interactive sessions. This prevents Simics from using fancy formatting and
coloring of the output and disables the asynchronous prompt for commands
running the simulation. The <tt>-plain-text</tt> flag can be used to only
disable output formatting. These two flags affect all future connections made
to the telnet frontend. The corresponding <attr>interactive</attr> and
<attr>plain_text</attr> attributes can be used to change the settings of an
already created <class>telnet-frontend</class> object, although existing
connections will not be affected.

It is possible to limit the number of allowed connections to the frontend with
the <arg>max-connections</arg> argument. Once this number of connections has
been reached, no new connections are allowed even if previous ones disconnect.
It is possible to reset the count of connections by writing directly to the
<attr>num_connections</attr> attribute in the <class>telnet-frontend</class>
class.
""")
