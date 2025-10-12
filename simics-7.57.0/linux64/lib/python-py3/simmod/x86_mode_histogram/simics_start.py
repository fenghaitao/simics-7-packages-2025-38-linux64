# © 2022 Intel Corporation
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

def pre_connect(obj, provider, *tool_args):
    return ([["cpu", provider],
             ["tool", obj]], "")

connect_extra_args = ([], pre_connect, "")

instrumentation.make_tool_commands(
    "x86_mode_histogram",
    object_prefix = "xhist",
    provider_requirements = ("x86_instrumentation_subscribe_v2"
                             " & vmx_instrumentation_subscribe"
                             " & smm_instrumentation_subscribe"),
    provider_names = ("processor", "processors"),
    connect_extra_args = connect_extra_args,
    new_cmd_doc = """Creates a new x86_mode_histogram object which can be connected to
    X86 processors. The tool collects information about x86 mode switches
    and how many steps has been executed in each mode.

    The modes collected are: Real 16, Real32, V86, Protected 16,
    Protected 32, Protected 64, Compatibility 16, Compatibility 32,
    VMX Off, VMX Root, VMX Non-Root, System Management and combinations
    of them. When the processor is running in more then one mode, for
    instance, Protected 64 and in VMX Non-Root mode at the same time,
    the tool displays this as the concatenation of the two modes.""")
