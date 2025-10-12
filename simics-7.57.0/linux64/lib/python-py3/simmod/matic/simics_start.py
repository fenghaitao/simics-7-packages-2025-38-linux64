# © 2013 Intel Corporation
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

def get_agent_manager():
    all_objs = list(simics.SIM_object_iterator_for_class("agent_manager"))
    if not all_objs:
        return None
    return all_objs[0]  # There can be only one

def ok_msg(name, created):
    if not created:
        return "Agent manager '%s' is already started." % name
    return "'%s' is created and enabled." % name

def new_agent_manager_cmd(name):
    created = False
    agent_manager = get_agent_manager()
    if not agent_manager:
        if not name:
            name = 'agent_manager'
        try:
            agent_manager = simics.SIM_create_object("agent_manager", name, [])
        except simics.SimExc_General as e:
            raise cli.CliError(str(e))
        created = True
    elif name and agent_manager.name != name:
        raise cli.CliError("An agent manager called '%s' already exists and it"
                           " cannot be renamed." % (agent_manager.name))
    return cli.command_return(value=agent_manager,
                              message=ok_msg(agent_manager.name, created))

cli.new_command("start-agent-manager", new_agent_manager_cmd,
                [cli.arg(cli.str_t, "name", "?", "")],
                type = ["Matic"],
                short = "create and enable a Matic agent manager",
                doc = """
    Create and enable a Simics Agent Manager for <i>Matic</i>. Only <i>one</i>
    agent manager can exist in the simulation.

    The <arg>name</arg> argument is optional and defaults to
    'agent_manager'.

    <b>See also:</b> the <nref label="__rm_class_agent_manager">
    agent_manager</nref> class.""")
