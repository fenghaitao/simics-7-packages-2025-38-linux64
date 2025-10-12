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


import simics
from cli import (
    CliError,
    arg,
    command_return,
    flag_t,
    get_available_object_name,
    int_t,
    new_command,
    object_exists,
    str_t,
)

def new_time_server_cmd(port, name, poll):
    name = name if name else get_available_object_name('time_server')
    if object_exists(name):
        raise CliError("Time-server '%s' already exists." % name)

    cycle_queues = list(simics.SIM_object_iterator_for_interface(["cycle"]))
    if not cycle_queues:
        raise CliError("This command requires an existing time queue"
                           " (processor)")

    try:
        obj = simics.SIM_create_object("time-server", name,
                                       [['port', port],
                                        ['queue', cycle_queues[0]],
                                        ['poll_mode_enabled',
                                         bool(poll)]])
    except Exception as ex:
        raise CliError("Failed creating time-server: %s" % ex)

    return command_return(value = obj,
                          message = "New time server '%s' created" % name)

new_command("new-time-server", new_time_server_cmd,
            args = [arg(int_t,  "port", "?", 8123),
                    arg(str_t,  "name", "?"),
                    arg(flag_t, "-poll")],
            short = "create a new time server",
            doc = """

Create a new time server that listens on <arg>port</arg> (8123 by default), or
use <arg>port</arg> 0 for any port. <arg>name</arg> is optional and the name
of the created object will be returned.

With the <tt>-poll</tt> flag the time-server will periodically poll the time
and return the polled value in queries. Otherwise, the time server will always
return the current time in queries. Polled mode offers better performance when
the time server is queried at a high frequency, but does not support events.

Connected clients can query the virtual time, install alarm events
that are triggered after a certain amount of virtual time, or install
keepalive events that trigger at a periodic rate (real time).""")
