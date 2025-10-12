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


import instrumentation

new_doc = """Creates a new x86_branch_profiler tool object. The tool
is used to get statistic of normal branches executed on connected
processors. """

instrumentation.make_tool_commands(
    "x86_branch_profiler",
    object_prefix = "bprof",
    provider_requirements = "x86_instrumentation_subscribe",
    provider_names = ("processor", "processors"),
    new_cmd_doc = new_doc)
