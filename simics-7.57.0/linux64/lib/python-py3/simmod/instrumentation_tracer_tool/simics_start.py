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


import simics
import instrumentation
import cli

# Called by <obj>.add-instrumentation framework prior to doing the
# actual connect to the provider.
def pre_connect(obj, provider, *tool_args):

    if not provider:
        if not any(tool_args):
            return (None, None)

        raise cli.CliError(
            "Error: tracer argument specified with nothing connected")

    # Must be kept in sync with connect_args
    (trace_data,
     trace_instructions,
     trace_exceptions,
     print_virtual_address,
     print_physical_address,
     print_linear_address,
     print_opcode,
     print_access_type,
     print_memory_type,
     print_register_changes,
     print_old_value,
     print_execution_mode,
     use_cpu_number,
     remove_duplicates) = tool_args

    if not any(tool_args[:-5]):
        # Without any specified flags, we enable everything by default,
        # except remove_duplicates, use_cpu_number, print_register_changes,
        # print_old_value and print_execution_mode.
        trace_data = True
        trace_instructions = True
        trace_exceptions = True
        print_virtual_address = True
        print_physical_address = True
        print_linear_address = True
        print_opcode = True
        print_access_type = True
        print_memory_type = True
    elif not (trace_data or trace_instructions or trace_exceptions):
        # Be user-friendly: ensure that commands like "new-tracer-tool
        # -print-opcode -connect-all" produce output.
        trace_data = trace_instructions = trace_exceptions = True

    print_register_changes = (print_register_changes and
                              (trace_instructions or trace_exceptions))
    print_old_value = print_old_value and print_register_changes

    if hasattr(cli, "get_shortest_unique_object_names"):
        get_short = cli.get_shortest_unique_object_names
    else:
        get_short = lambda l: [l[0].name]

    args = [["trace_data", trace_data],
            ["trace_instructions", trace_instructions],
            ["trace_exceptions", trace_exceptions],
            ["print_virtual_address", print_virtual_address],
            ["print_physical_address", print_physical_address],
            ["print_linear_address", print_linear_address],
            ["print_opcode", print_opcode],
            ["print_access_type", print_access_type],
            ["print_register_changes", print_register_changes],
            ["print_old_value", print_old_value],
            ["print_memory_type", print_memory_type],
            ["print_execution_mode", print_execution_mode],
            ["use_cpu_number", use_cpu_number],
            ["remove_duplicates", remove_duplicates],
            ["short_name", get_short([provider])[0]]]

    # Format a description based on the settings used.
    desc = ""
    desc += "Types:"
    desc += "D" if trace_data else ""
    desc += "I" if trace_instructions else ""
    desc += "E" if trace_exceptions else ""
    desc += " remove-duplicates" if remove_duplicates else ""
    desc += " Address:"
    desc += "V" if print_virtual_address else ""
    desc += "P" if print_physical_address else ""
    desc += "L" if print_linear_address else ""
    desc += " Misc:"
    desc += "access-types " if print_access_type else ""
    desc += "mem-types " if print_memory_type else ""
    desc += "execution-mode " if print_execution_mode else ""
    desc += "opcode " if print_opcode else ""
    desc += "reg-changes" if print_register_changes else ""
    desc += "-with-old-value" if print_old_value else ""
    return (args, desc)

# Must be kept in sync with parsing of tool_args in pre_connect
connect_args = [
    cli.arg(cli.flag_t, "-trace-data"),
    cli.arg(cli.flag_t, "-trace-instructions"),
    cli.arg(cli.flag_t, "-trace-exceptions"),
    cli.arg(cli.flag_t, "-print-virtual-address"),
    cli.arg(cli.flag_t, "-print-physical-address"),
    cli.arg(cli.flag_t, "-print-linear-address"),
    cli.arg(cli.flag_t, "-print-opcode"),
    cli.arg(cli.flag_t, "-print-access-type"),
    cli.arg(cli.flag_t, "-print-memory-type"),
    cli.arg(cli.flag_t, "-print-register-changes"),
    cli.arg(cli.flag_t, "-print-old-value"),
    cli.arg(cli.flag_t, "-print-execution-mode"),
    cli.arg(cli.flag_t, "-use-cpu-number"),
    cli.arg(cli.flag_t, "-remove-duplicates")]

connect_doc = \
    """Each new connection to the tracer tool can be configured with flags.
    The flags are described below.

    The following three flags control what type of tracing is done:

    <tt>-trace-data</tt> : Enabling tracing of data operations.
    <br/><tt>-trace-instructions</tt> : Enabling tracing of instruction.
    <br/><tt>-trace-exceptions</tt> : Enabling tracing of exceptions.

    The following flags allow controlling the output:

    <br/><tt>-print-register-changes</tt> : Print register changes after
    traced instruction and/or traced exception.
    Registers that normally change with every instruction, like program counter
    or cycles counter, are not listed.
    <br/><tt>-print-old-value</tt> : Print the previous register value together
    with register changes.
    <br/><tt>-print-virtual-address</tt> : Print the virtual address of an
    entry.
    <br/><tt>-print-physical-address</tt> : Print the physical address of an
    entry.
    <br/><tt>-print-linear-address</tt> : Print the linear address of an entry
    (only x86).
    <br/><tt>-print-opcode</tt> : Print the opcode of an instruction entry.
    <br/><tt>-print-access-type</tt> : Print the access type (only x86).
    <br/><tt>-print-memory-type</tt> : Print the memory type (only x86).
    <br/><tt>-print-execution-mode</tt> :
        Print the execution mode (only x86). See description of recognized modes
        below.
    <br/><tt>-use-cpu-number</tt> : Print the CPU number instead of its name.
    <br/><tt>-remove-duplicates</tt> : Remove duplicated lines from
    the output.

    If none of the <tt>-print...</tt> or <tt>-trace..</tt> flags are
    given all of those will be enabled by default except
    <tt>-print-register-changes</tt>, i.e., trace and print everything
    except register changes.

    If only <tt>-print-register-changes</tt> are given everything including
    register changes will be enabled.

    The <tt>-print-execution-mode</tt> recognizes the following modes of
    execution. Note that several modes can be recognized simultaneously.
    <br/><tt>AC</tt> :
        The processor is executing inside an Authenticated Code Module (ACM).
    <br/><tt>SEAM</tt> :
        The processor is executing inside Secure Arbitration Mode (SEAM) mode.
    <br/><tt>SGX</tt> :
        The processor is executing inside an Intel&reg; Software Guard Extensions
        (Intel&reg; SGX) enclave.
    <br/><tt>SMM</tt> :
        The processor is executing inside System Management Mode (SMM) mode.
    <br/><tt>VMX root</tt> :
        The processor is executing inside Virtual Machine Extensions (VMX) root
        mode.
    <br/><tt>VMX non-root</tt> :
        The processor is executing inside Virtual Machine Extensions (VMX)
        non-root mode.
    """

def new_command_fn(tool_class, name, filename, trace_history_size):
    if filename and trace_history_size:
        raise cli.CliError("You cannot set both file and trace-history-size")
    return simics.SIM_create_object(tool_class, name, file=filename,
                                    trace_history_size=trace_history_size)

connect_extra_args = (connect_args, pre_connect, connect_doc)
new_cmd_extra_args = ([cli.arg(cli.filename_t(), "file", "?"),
                       cli.arg(cli.uint_t, "trace-history-size", "?", 0)], new_command_fn)


instrumentation.make_tool_commands(
    "tracer_tool",
    object_prefix = "trace",
    provider_requirements = "cpu_instrumentation_subscribe",
    provider_names = ("processor", "processors"),
    connect_extra_args = connect_extra_args,
    new_cmd_extra_args = new_cmd_extra_args,
    new_cmd_doc = """Creates a new instruction tracer tool object which
    can be connected to processors which supports instrumentation.

    The <arg>file</arg> argument specifies a file
    to write the trace to, without any file, the trace will be printed
    to standard out.

    If the <arg>trace-history-size</arg> is set to a size, the tool will instead
    of constantly writing the output to standard out or a file, keep the output
    in a cyclic buffer in memory with this number of lines. The buffer can be
    written to file later with the
    &lt;instrumentation_tracer_tool>.save-trace-buffer> command.
    """)
