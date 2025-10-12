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


import instrumentation
import cli
import math
import simics

# Called by <obj>.connect framework prior to doing the
# actual connect to the provider.
def pre_connect(obj, provider, *flags):
    if not provider and any(flags):
        raise cli.CliError(
            "Error: profiler flags specified with nothing connected")

    if provider and not any(flags):
        raise cli.CliError(
            "Refused to connect to %s, no profile flags given." % (
            provider.name))

    (read_physical, read_logical,
     write_physical, write_logical,
     execute_physical, execute_logical) = flags

    args = [["read_physical", read_physical],
            ["read_logical", read_logical],
            ["write_physical", write_physical],
            ["write_logical", write_logical],
            ["execute_physical", execute_physical],
            ["execute_logical", execute_logical]]

    p = ""
    p += "r" if read_physical else ""
    p += "w" if write_physical else ""
    p += "x" if execute_physical else ""

    l = ""
    l += "r" if read_logical else ""
    l += "w" if write_logical else ""
    l += "x" if execute_logical else ""

    desc = ""
    if l:
        desc += "logical:" + l
    if p:
        desc += (" " if l else "") + "physical:" + p

    return (args, desc)

def is_pow2(v):
    return ((v - 1) & v) == 0

def new_command_fn(tool_class, name, granularity):
    if not is_pow2(granularity) or granularity <= 0:
        raise cli.CliError('Granularity need to be a power of 2')
    gran = int(math.log2(granularity))
    return simics.SIM_create_object(tool_class, name, granularity_log2=gran)

connect_doc = """Each new connection to the memory profiler can be
configured by supplying the following flags:
<br/><tt>-read-physical</tt> : Enabling profiling of reads to physical
addresses
<br/><tt>-read-logical</tt> : Enabling profiling of read to logical addresses
<br/><tt>-write-physical</tt> : Enabling profiling of writes to physical
addresses
<br/><tt>-write-logical</tt> : Enabling profiling of writes to logical
addresses
<br/><tt>-execute-physical</tt> : Enabling profiling of instruction execution
of physical addresses.
<br/><tt>-execute-logical</tt> : Enabling profiling of instruction execution
of logical addresses.

At least one flag must be specified when connecting."""

new_cmd_extra_args = ([cli.arg(cli.int_t, "granularity", "?", 1)], new_command_fn)

connect_args = [cli.arg(cli.flag_t, "-read-physical"),
                cli.arg(cli.flag_t, "-read-logical"),
                cli.arg(cli.flag_t, "-write-physical"),
                cli.arg(cli.flag_t, "-write-logical"),
                cli.arg(cli.flag_t, "-execute-physical"),
                cli.arg(cli.flag_t, "-execute-logical")]

instrumentation.make_tool_commands(
    "memory_profiler",
    object_prefix = "mprof",
    provider_requirements = \
        "cpu_instrumentation_subscribe",
    provider_names = ("processor", "processors"),
    connect_extra_args = (connect_args, pre_connect, connect_doc),
    new_cmd_extra_args = new_cmd_extra_args,
    new_cmd_doc = """Creates a new memory profiler tool object which
    can be connected to processors which support instrumentation.

    The <arg>granularity</arg> arguments sets the minimum granularity in bytes
    for how accesses are monitored, so for example, if set to 16, the tool will
    aggregate all accesses within each 16 bytes naturally aligned memory
    chunk. Larger the granularity settings will consume less memory when
    collecting the data.""")
