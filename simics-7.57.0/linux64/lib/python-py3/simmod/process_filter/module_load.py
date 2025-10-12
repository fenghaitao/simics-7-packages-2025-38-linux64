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


import cli
import instrumentation
import simics

def get_info(obj):
    return []

def get_status(obj):
    return [("Processes tracked",
             [(str(i), obj.tracked_processes[i])
              for i in range(len(obj.tracked_processes))])]

cli.new_info_command("process_filter", get_info)
cli.new_status_command("process_filter", get_status)

def add_process_cmd(obj, process_name):
    try:
        obj.tracked_processes.append(process_name)
    except simics.SimExc_IllegalValue as e:
        raise cli.CliError("Failed adding pattern:" + str(e))

def remove_process_cmd(obj, poly):
    (type, value, _) = poly
    if type == cli.flag_t:
        # -all used, remove all processes associated to the tool
        obj.tracked_processes = []
    else:
        # Dedicated process-name specified
        process_name = value
        if not process_name in obj.tracked_processes:
            raise cli.CliError("Error: process %s not tracked" % (process_name))

        p = obj.tracked_processes
        p.remove(process_name)
        obj.tracked_processes = p

def process_expander(comp, obj):
    processes = obj.tracked_processes
    return cli.get_completions(comp, processes)

cli.new_command("add-pattern", add_process_cmd,
            args = [cli.arg(cli.str_t, "pattern")],
            cls = "process_filter",
            type = ["Instrumentation"],
            short = "filter on a specific node path pattern",
            see_also = ["<process_filter>.remove-pattern"],
            doc = """Restrict instrumentation to only a specific node
            path pattern as given by the <arg>pattern</arg>
            argument. The pattern can be a simple string just naming a
            process, e.g., "grep", or it can be more precise, like
            "pid=103,tid=103". For more information about node path
            patterns see the Analyzer User Guide. The filter uses
            os-awareness to automatically enable measurements for the
            tool when the given pattern matches the currently running
            process/thread on a processor.  Similarly, disable
            measurement for the tool on the processor when the
            process/thread stops executing. Note that one single
            pattern can match several processes or threads. More than
            one pattern can be given by using this command several
            times, then the union of all patterns will be used.""")

cli.new_command("remove-pattern", remove_process_cmd,
            args = [cli.arg((cli.str_t, cli.flag_t), ("pattern", "-all"),
                        expander = (process_expander,None))],
            cls = "process_filter",
            type = ["Instrumentation"],
            short = "stop filtering on a process",
            see_also = ["<process_filter>.add-pattern"],
            doc = ("Remove a <arg>pattern</arg> from being tracked." +
                   " If <tt>-all</tt> is given all patterns will be removed."))

def delete_cmd(obj):
    instrumentation.delete_filter(obj)
    simics.SIM_delete_object(obj)

cli.new_command("delete", delete_cmd,
            args = [],
            cls = "process_filter",
            type = ["Instrumentation"],
            short = "remove the filter",
            doc = """
            Removes the filter.
            """)
