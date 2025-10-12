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
    return [("Modes tracked",
             [(str(i), obj.tracked_modes[i])
              for i in range(len(obj.tracked_modes))])]

cli.new_info_command("cpu_mode_filter", get_info)
cli.new_status_command("cpu_mode_filter", get_status)

def add_mode_cmd(obj, mode_name):
    p = obj.tracked_modes
    p.append(mode_name)
    obj.tracked_modes = p

def remove_mode_cmd(obj, mode_name):
    if mode_name not in obj.tracked_modes:
        raise cli.CliError("Error: mode %s not tracked" % (mode_name))

    p = obj.tracked_modes
    p.remove(mode_name)
    obj.tracked_modes = p

def mode_expander(comp, obj):
    modes = obj.tracked_modes
    return cli.get_completions(comp, modes)

cli.new_command("add-mode", add_mode_cmd,
            args = [cli.arg(cli.string_set_t(["user", "supervisor", "hypervisor"]),
                        "mode")],
            cls = "cpu_mode_filter",
            type = ["Instrumentation"],
            short = "filter on specific modes",
            see_also = ["new-cpu-mode-filter",
                        "<cpu_mode_filter>.remove-mode",
                        "<cpu_mode_filter>.delete"],
            doc = """Restrict instrumentation to only a specific mode.
            The <arg>mode</arg> argument can be one of: user, supervisor, or
            hypervisor.""")

cli.new_command("remove-mode", remove_mode_cmd,
            args = [cli.arg(cli.str_t, "mode", expander = mode_expander)],
            cls = "cpu_mode_filter",
            type = ["Instrumentation"],
            short = "stop filtering on a mode",
            see_also = ["new-cpu-mode-filter",
                        "<cpu_mode_filter>.add-mode",
                        "<cpu_mode_filter>.delete"],
            doc = "Remove a <arg>mode</arg> from being tracked.")

def delete_cmd(obj):
    instrumentation.delete_filter(obj)
    simics.SIM_delete_object(obj)

cli.new_command("delete", delete_cmd,
            args = [],
            cls = "cpu_mode_filter",
            type = ["Instrumentation"],
            short = "remove the filter",
            see_also = ["new-cpu-mode-filter",
                        "<cpu_mode_filter>.add-mode",
                        "<cpu_mode_filter>.remove-mode"],
            doc = """
            Removes the filter.
            """)
