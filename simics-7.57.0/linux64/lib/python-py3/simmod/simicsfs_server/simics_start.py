# © 2015 Intel Corporation
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
from cli import (
    CliError,
    arg,
    command_return,
    new_command,
    quiet_run_command,
    str_t,
    )
from simics import *

def get_simicsfs_server():
    all_objs = list(SIM_object_iterator_for_class("simicsfs_server"))
    return all_objs[0] if all_objs else None

def ok_msg(name, created):
    return "SimicsFS server '%s' is %s." % (
        name, "created and connected" if created else "already started")

def _name_ok(s):
    return bool(s) and bool(re.match(r"^[a-zA-Z][0-9a-zA-Z_]*$", s))

def new_simicsfs_server_cmd(name):
    if not _name_ok(name):
        raise CliError("Illegal server name: %s" % name)
    server = get_simicsfs_server()
    mp_name = None  # This is only set if a server is created.
    if not server:
        try:
            server = SIM_create_object("simicsfs_server", name, [])
        except SimExc_General as e:
            raise CliError(str(e))
        # Connect server to magic-pipe
        (mp_name, _) = quiet_run_command('start-magic-pipe')
        server.pipe = SIM_get_object(mp_name)
    elif server.name != name:
        raise CliError(ok_msg(server.name, False))
    return command_return(value=server,
                          message=ok_msg(name, bool(mp_name)))

new_command("start-simicsfs-server", new_simicsfs_server_cmd,
            [arg(str_t, "name", "?", "simicsfs_server")],
            type = ["Files"],
            short = "create and connect the SimicsFS server",
            doc = """
    Create SimicsFS server and connect to magic-pipe. Only
    one SimicsFS server can exist in the simulation.

    The <arg>name</arg> argument is optional and defaults to
    "simicsfs_server".""")
