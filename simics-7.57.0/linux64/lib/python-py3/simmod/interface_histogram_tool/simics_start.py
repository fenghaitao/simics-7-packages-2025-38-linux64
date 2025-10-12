# © 2024 Intel Corporation
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
import conf
import simics
import instrumentation

def new_command_fn(tool_class, name):
    if not conf.sim.wrap_iface:
        print("WARNING: the interface-histogram-tool only works if Simics is started"
              " with the --wrap-iface flag.")

    return simics.SIM_create_object(tool_class, name)

new_cmd_extra_args = ([], new_command_fn)

instrumentation.make_tool_commands(
    "interface_histogram_tool",
    object_prefix = "ifhist",
    new_cmd_extra_args = new_cmd_extra_args,
    provider_requirements = "iface_wrap_instrumentation",
    make_add_instrumentation_cmd = False,
    connect_all_flag = False,
    new_cmd_can_connect = "automatic",
    new_cmd_doc = """Creates a new interface histogram tool that provides
    information on the frequency of all called interfaces and methods in Simics.

    NOTE: this tool only works if you start Simics with the
    <tt>--wrap-iface</tt> flag.""",
    unsupported=True)
