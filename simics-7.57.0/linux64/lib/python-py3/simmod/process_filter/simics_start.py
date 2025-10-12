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

def new_process_filter(name, sw_comp, process):
    if not name:
        name = cli.get_available_object_name("process_filter")

    msg = "Created filter %s" % name
    try:
        filt = simics.SIM_create_object("process_filter", name,
                                        [["software_comp", sw_comp]])
    except simics.SimExc_General as msg:
        raise cli.CliError("Cannot create %s: %s" % (name, msg))

    source_id = instrumentation.get_filter_source(filt.name)
    filt.iface.instrumentation_filter_master.set_source_id(source_id)

    if process:
        msg += " tracking %s" % (process)
        try:
            filt.tracked_processes = [process]
        except simics.SimExc_IllegalValue as e:
            raise cli.CliError("Failed tracking process '%s' : %s" % (
                process, str(e)))
    return cli.command_return(message = msg, value = filt)

cli.new_command("new-process-filter", new_process_filter,
            args = [
                cli.arg(cli.str_t, "name", "?"),
                cli.arg(cli.obj_t('software-component', 'os_awareness'),
                    "software-component"),
                cli.arg(cli.str_t, "pattern", "?"),
            ],
            type = ["Instrumentation"],
            short = "filter on certain processes",
            see_also = ["<process_filter>.add-pattern",
                        "<process_filter>.remove-pattern"],

            doc = """Create a process filter with the name given by the
            <arg>name</arg> argument. This object uses OS Awareness to
            restricts instrumentation tools to be enabled only when certain
            processes or threads are being executed. A node path pattern is
            used to specify the process nodes to follow. A pattern can just be
            a simple string naming a process to track, e.g., "grep" or it can
            be a more complicated one. For more information about node path
            patterns see the Analyzer User Guide.

            To add a pattern either use the <arg>pattern</arg> argument or use
            the <cmd>&lt;process_pattern&gt;.add-pattern</cmd> command once a
            process_filter has been created. If no patterns are given nothing
            will be instrumented if the filter is added to a tool.

            The <arg>software-component</arg> argument specifies which
            os-awareness object to use.""")
