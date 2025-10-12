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

instrumentation.make_tool_commands(
    "process_histogram",
    object_prefix = "phist",
    provider_requirements = "os_awareness",
    provider_names = ("software", None),
    make_enable_cmd = False,
    make_disable_cmd = False,
    make_status_cmd = False,
    make_info_cmd = False,
    new_cmd_doc ="""
    Creates a new process_histogram object which can be connected to a
    software component.  This tool can be used to get a histogram of
    all the processes that are run under the supervision of the
    software component. The <arg>software</arg> argument tells which
    software component to use.""")
