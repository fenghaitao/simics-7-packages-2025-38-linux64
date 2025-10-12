# © 2017 Intel Corporation
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
import instrumentation
import cli
from . import modes

# Get the modes from the shared dict
x86_modes = list(modes.x86_modes.values())

def new_x86_mode_filter(name, mode):
    if not name:
        name = cli.get_available_object_name("x86mf")

    msg = "Created filter %s" % name
    try:
        filt = simics.SIM_create_object("x86_mode_filter", name)
    except simics.SimExc_General as msg:
        raise cli.CliError("Cannot create %s: %s" % (name, msg))

    source_id = instrumentation.get_filter_source(filt.name)
    filt.iface.instrumentation_filter_master.set_source_id(source_id)

    if mode:
        msg += " with mode %s" % (mode)
        filt.modes = [mode]

    return cli.command_return(message = msg, value = filt)

cli.new_command("new-x86-mode-filter", new_x86_mode_filter,
            args = [cli.arg(cli.str_t, "name", "?"),
                    cli.arg(cli.string_set_t(x86_modes), "mode", "?")],
            type = ["Instrumentation"],
            short = "filter on different execution modes",
            see_also = ["<x86_mode_filter>.add-mode",
                        "<x86_mode_filter>.remove-mode",
                        "<x86_mode_filter>.delete"],
            doc = """Creates an x86 mode filter object with the name
            <arg>name</arg>. The filter restricts instrumentation to
            only a specific execution mode on processors tracked by a
            tool. The <arg>mode</arg> argument can be used to
            configure the filter for a specific mode. Once create, the filter
            can be added to tool(s) with the tool specific
            <cmd>&lt;tool&gt;.add-filter</cmd> command.""")
