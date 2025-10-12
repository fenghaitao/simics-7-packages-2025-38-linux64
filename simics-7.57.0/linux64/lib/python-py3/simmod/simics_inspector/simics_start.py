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
import instrumentation

def pre_connect(obj, provider, with_vmp_flag):
    if hasattr(provider, "vmp_use_instrumentation"):
        provider.vmp_use_instrumentation = with_vmp_flag
    return ([["cpu", provider],
             ["parent", obj]], "")

connect_extra_arg = (
    [cli.arg(cli.flag_t, "-with-vmp")],
    pre_connect,
    "VMP on x86 targets is disabled by this instrumentation."
    " The <tt>-with-vmp</tt> will enable VMP and the tool will only"
    " measure execution of the instructions outside of VMP.")

instrumentation.make_tool_commands(
    "sr_histogram",
    object_prefix = "sr_hist",
    provider_requirements = "cpu_instrumentation_subscribe",
    provider_names = ("processor", "processors"),
    connect_extra_args = connect_extra_arg,
    new_cmd_doc = """
    Internal command.

    Creates a new sr_histogram object which can be connected to a processor
    which supports instrumentation.

    This tool presents a service-routine histogram of the most commonly
    executed service-routine in both the generated JIT code and in the
    interpreter. This can be used to find instructions that should be
    turbofied to improve performance."""
)

instrumentation.make_tool_commands(
    "sr_ticks",
    object_prefix = "sr_ticks",
    provider_requirements = "cpu_instrumentation_subscribe",
    provider_names = ("processor", "processors"),
    connect_extra_args = connect_extra_arg,
    new_cmd_doc = """
    Internal command.

    Creates a new sr_ticks object which can be connected to a processor which
    supports instrumentation.

    This tool measures how long time each service-routine takes to commit
    (both in the generated JIT code and the interpreter). This can be used to
    find instructions which executes slowly and possibly should be
    optimized."""
)
