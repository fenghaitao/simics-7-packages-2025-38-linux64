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
import simics

def connect_extra(obj, ram, r, w, e, i, b):
    if not ram and any([r, w, e, i, b]):
        raise cli.CliError(
            "Error: tracer argument specified with nothing connected")

    if not any([r, w, e]):
        r = w = e = True

    access = ((simics.Sim_Access_Read if r else 0)
              | (simics.Sim_Access_Write if w else 0)
              | (simics.Sim_Access_Execute if e else 0))
    string = (("R" if r else "-") + ("W" if w else "-") + ("E" if e else "-"))
    string = string + "I" if i else string
    return ([["ram", ram], ["access", access], ["inquiry", i], ["block", b]], string)

connect_doc = """The <tt>-read</tt>, <tt>-write</tt>,
<tt>-execute</tt> flags can be set to only trace specific
accesses. The <tt>-inquiry</tt> flag can be used to trace inquiry
accesses as well. Every access is traced by default but with inquiry
switched off. If <tt>-block-only</tt> is given, no tracing will occur, but
the tool will still block caching of ram/rom pages which is useful for
other tools, such as the transaction-tracer."""

def new_command_fn(tool_class, name, filename):
    return simics.SIM_create_object(tool_class, name, file=filename)

new_cmd_extra_args = ([cli.arg(cli.filename_t(), "file", "?")], new_command_fn)

instrumentation.make_tool_commands(
    "ram_tracer",
    object_prefix = "rt",
    provider_requirements = "ram_access_subscribe",
    provider_names = ("ram", "ram-objects"),
    connect_extra_args = ([cli.arg(cli.flag_t, "-read"),
                           cli.arg(cli.flag_t, "-write"),
                           cli.arg(cli.flag_t, "-execute"),
                           cli.arg(cli.flag_t, "-inquiry"),
                           cli.arg(cli.flag_t, "-block-only")],
                           connect_extra, connect_doc),
    new_cmd_extra_args = new_cmd_extra_args,
    new_cmd_doc = """Creates a new ram_tracer object which can be
    connected to ram/rom objects. The tracer will print all accesses
    to the ram/rom objects that occurs in the system.

    For each access the following trace format will used: <tt>[dest
    object] &lt;- initiator object I type offset size data</tt> where
    dest object is the destination ram/rom object, initiator object is
    the object that sends the transaction, I is displayed if the
    transaction is an inquiry access, type will be Execute, Read,
    or Write. Offset is the offset in the ram/rom object where
    the access hits. Size is the size of the transaction in bytes
    and data is the raw content in bytes.

    The <arg>file</arg> argument specifies a file
    to write the trace to, without any file, the trace will be printed
    to standard out.
""")
