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

modes = ["user", "supervisor", "hypervisor"]

def new_cpu_mode_filter(name, mode):
    if not name:
        name = cli.get_available_object_name("cpu_mode")

    msg = "Created filter %s" % name
    try:
        filt = simics.SIM_create_object("cpu_mode_filter", name)
    except simics.SimExc_General as msg:
        raise cli.CliError("Cannot create %s: %s" % (name, msg))

    source_id = instrumentation.get_filter_source(filt.name)
    filt.iface.instrumentation_filter_master.set_source_id(source_id)

    if mode:
        msg += " with mode %s" % (mode)
        filt.tracked_modes = [mode]

    return cli.command_return(message = msg, value = filt)

cli.new_command("new-cpu-mode-filter", new_cpu_mode_filter,
            args = [
                cli.arg(cli.str_t, "name", "?"),
                cli.arg(cli.string_set_t(modes), "mode", "?"),
            ],
            type = ["Instrumentation"],
            short = "filter on certain modes (user/supervisor/hypervisor)",
            see_also = ["<cpu_mode_filter>.add-mode",
                        "<cpu_mode_filter>.remove-mode",
                        "<cpu_mode_filter>.delete"],
            doc = """
            Creates a new filter with the name given by the <arg>name</arg>
            argument. The filter restricts instrumentation to be
            enabled only when the processor executes in a certain
            mode(s).  The <arg>mode</arg> argument can be used to
            configure the filter for a specific mode. Once created, the filter
            can be added to tool(s) with the tool specific
            <cmd>&lt;tool&gt;.add-filter</cmd> command.""")
