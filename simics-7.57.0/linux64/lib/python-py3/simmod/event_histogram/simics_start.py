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
    "event_histogram",
    object_prefix = "evh",
    provider_requirements =
            "step_event_instrumentation | cycle_event_instrumentation",
    provider_names = ("queue", "queues"),
    make_enable_cmd = False,
    make_disable_cmd = False,
    make_status_cmd = False,
    make_info_cmd = False,
    new_cmd_doc ="""
    Creates a new event_histogram object which can be connected to
    a clock or a processor. This tool can be used to get a histogram
    of all the events that are run in the system during simulation.""")
