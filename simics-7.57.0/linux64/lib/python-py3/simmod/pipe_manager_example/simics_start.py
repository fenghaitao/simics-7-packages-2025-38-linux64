# © 2014 Intel Corporation
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
import simics

def get_pipe_manager():
    all_objs = list(simics.SIM_object_iterator_for_class("pipe_manager"))
    if not all_objs:
        return None
    return all_objs[0]  # There can be only one

def ok_msg(name, created):
    if not created:
        return "Pipe Manager '%s' is already started." % name
    return "'%s' is created and enabled." % name

def new_pipe_manager_cmd(name):
    created = False
    pipeman = get_pipe_manager()
    if not pipeman:
        try:
            pipeman = simics.SIM_create_object("pipe_manager", name)
        except simics.SimExc_General as e:
            raise cli.CliError(str(e))
        created = True
    elif pipeman.name != name:
        raise cli.CliError("A pipe manager already exists as '%s'."
                       % pipeman.name)
    return cli.command_return(value=pipeman,
                          message=ok_msg(name, created))

cli.new_command("start-pipe-manager", new_pipe_manager_cmd,
            [cli.arg(cli.str_t, "name", "?", "pipe_manager")],
            type = ["Matic"],
            short = "create and enable the Magic pipe manager",
            doc = """
    Create and enable the test pipe manager. Only
    one pipe manager can exist in the simulation.

    The <arg>name</arg> argument is optional and defaults to
    "pipe_manager".""")
