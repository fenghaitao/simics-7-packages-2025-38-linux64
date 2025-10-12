# © 2016 Intel Corporation
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
import conf

cls = conf.classes.tracer_tool

conns = {}

def get_str_mask(subset, total_order):
    m = 0
    for t in subset:
        m = m | (1 << total_order.index(t))
    return m

def add_log_message_cmd(obj, log_objs, level, types, groups):
    if level < 0 or level > 4:
        raise cli.CliError("level must be from 1 to 4")

    for o in log_objs:
        group_set = set(o.log_groups)
        for g in groups:
            if not g in group_set:
                raise cli.CliError(f"undefined log group '{g}' given for object '{o.name}'")

        obj.logging = obj.logging + [[o, level,
                                      get_str_mask(types, conf.sim.log_types),
                                      get_str_mask(groups, o.log_groups)]]

def group_expander(prefix, obj, args):
    log_objects = args[0]
    if not log_objects:
        return []

    # use first object for expansion, all object need to have common groups to add
    return cli.get_completions(prefix, log_objects[0].log_groups)

cli.new_command("add-log-message", add_log_message_cmd,
                args = [cli.arg(cli.obj_t("log-objects", "log_object"),
                                "log-objects", "+"),
                        cli.arg(cli.int_t, "level", '?', 4),
                        cli.arg(cli.string_set_t(list(conf.sim.log_types)),
                                "types", "*"),
                        cli.arg(cli.str_t, "groups", "*",
                                expander = group_expander),
                        ],
                cls = "tracer_tool",
                short = "add log messages to trace",
                doc =
"""Add log entries to the log output for specific
objects. <arg>log-objects</arg> is one or several object to add log outputs
from. The <arg>level</arg> specifies the log level to consider. Log messages
with less than or equal level will be included. The current log level for each
object is ignored, i.e., specifying 4 here will include all messages for an
object regardless of its log level setting. The <arg>types</arg> argument
specifies what log types to include. All log types are included if not set. The
<arg>groups</arg> argument specifies the log group for the object to
consider. All objects given must define the groups specified. If this is not
the case, this command can be executed several times, adding different objects
with different log groups. All log groups are included if not set.""")

def del_obj_expander(prefix, obj):
    return cli.get_completions(prefix, map(lambda li: li[0].name, obj.logging))

def del_log_message_cmd(obj, log_objs):
    new_val = []
    for a in obj.logging:
        if a[0] not in log_objs:
            new_val.append(a)
    obj.logging = new_val

cli.new_command("del-log-message", del_log_message_cmd,
                args = [cli.arg(cli.obj_t("log-objects", "log_object"),
                                "log-objects", "+",
                                expander = del_obj_expander)],
                cls = "tracer_tool",
                short = "delete log objects from tracer",
                doc = """Delete all log entries from the log output for objects
                in <arg>log-objects</arg>.""")

def save_trace_buffer_cmd(obj, file):
    if obj.trace_history_size == 0:
        raise cli.CliError("No trace buffer configured")
    obj.trace_buffer_to_file = file

cli.new_command("save-trace-buffer", save_trace_buffer_cmd,
                args=[cli.arg(cli.filename_t(), "file")],
                cls="tracer_tool",
                short="save the current trace buffer to a file",
                doc=
"""Save the current trace buffer to the specified <arg>file</arg>.""")

def print_trace_buffer_cmd(obj):
    if obj.trace_history_size == 0:
        raise cli.CliError("No trace buffer configured")

    buffer = obj.trace_buffer
    if buffer == []:
        print("Trace buffer is empty.")
        return

    for entry in buffer:
        print(entry, end="")

cli.new_command("print-trace-buffer", print_trace_buffer_cmd,
                args=[],
                cls="tracer_tool",
                short="print trace buffer",
                doc="""Print the current trace buffer.""")
