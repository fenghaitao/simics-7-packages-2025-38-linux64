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

def pre_connect(obj, provider, *tool_args):
    return ([["cpu", provider],
             ["tool", obj]], "")

connect_extra_args = ([], pre_connect, "")

instrumentation.make_tool_commands(
    "exception_histogram",
    object_prefix = "ehist",
    provider_requirements = "cpu_instrumentation_subscribe",
    provider_names = ("processor", "processors"),
    connect_extra_args = connect_extra_args,
    new_cmd_doc = """Creates a new exception_histogram object which
    can be connected to processors which support instrumentation.
    This tool can be used to get a histogram of the taken exceptions.
    """)
