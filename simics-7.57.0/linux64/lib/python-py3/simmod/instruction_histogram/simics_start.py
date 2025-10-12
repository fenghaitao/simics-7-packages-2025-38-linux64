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

def create_histogram_tool(cls, name, view):
    return simics.SIM_create_object(cls, name, view=view)

def pre_connect(obj, provider, *tool_args):
    return ([["cpu", provider],
             ["parent", obj]], "")

connect_extra_args = ([], pre_connect, "")

new_doc = """Creates a new instruction_histogram object which
can be connected to processors which support instrumentation.
This tool can be used to get an instruction histogram based of the frequency
of the instructions that have been executed.

The <arg>view</arg> argument decides which
instruction "perspective" that should be collected.
Currently there are eight choices:
<br/>1. <b>mnemonic</b> - Groups all instructions with
the same first word in the instruction disassembly.
<br/>2. <b>size</b> - Groups the instructions by the length of the
instruction.
<br/>3. <b>xed-iform</b> - Uses Intel® X86 Encoder Decoder (Intel® XED)
module and groups the x86 instruction by their instruction form definition, e.g.,
ADD_GPRv_GPRv_01.
<br/>4. <b>xed-extension</b> - Uses Intel® X86 Encoder Decoder (Intel® XED)
module and groups the x86 instruction by their extension, e.g., SSE.
<br/>5. <b>xed-isa-set</b> - Uses Intel® X86 Encoder Decoder (Intel® XED)
module and groups the x86 instruction by their isa-set, e.g., I386.
<br/>6. <b>xed-iclass</b> - Uses Intel® X86 Encoder Decoder (Intel® XED)
module and groups the x86 instruction by their iclass, e.g., ADD.
<br/>7. <b>xed-category</b> - Uses Intel® X86 Encoder Decoder (Intel® XED)
module and groups the x86 instruction by their category, e.g., LOGICAL.
<br/>8. <b>x86-normalized</b> - The instruction disassembly, but
replaces register names and immediates with normalized names.
<br/>Default, the <i>mnemonic</i> view is used.
The <i>xed-iform</i>, <i>xed-extension</i>, <i>xed-isa-set</i>,
<i>xed-iclass</i>, <i>xed-contegory</i>, and
<i>x86-normalized</i> views are only applicable when connected to x86 target
processors."""

instrumentation.make_tool_commands(
    "instruction_histogram",
    object_prefix = "ihist",
    provider_requirements = \
        "cpu_instrumentation_subscribe",
    provider_names = ("processor", "processors"),
    new_cmd_doc = new_doc,
    new_cmd_extra_args = (
        [cli.arg(cli.string_set_t(
            ["mnemonic", "size", "xed-iform", "x86-normalized", "xed-extension",
             "xed-isa-set", "xed-iclass", "xed-category"]),
                 "view", "?", "mnemonic")],
        create_histogram_tool),
    connect_extra_args = connect_extra_args)
