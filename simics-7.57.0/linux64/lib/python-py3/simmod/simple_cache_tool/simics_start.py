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
from simics import *
from cli import (
    arg,
    obj_t,
)

def create_obj(cls, name, cycle_staller):
    return SIM_create_object(cls, name,
                                    [['cycle_staller', cycle_staller]])

instrumentation.make_tool_commands(
    "simple_cache_tool",
    object_prefix = "cache",
    provider_requirements = "cpu_instrumentation_subscribe & x86_memory_query",
    new_cmd_extra_args = ([arg(obj_t('cycle-staller', 'stall_cycles_collector'),
                               "cycle-staller", "?")], create_obj),

    new_cmd_doc = """Creates a new cache tool object which can be
    connected to processors to set up cache hierarchies.  The
    <arg>cycle-staller</arg> can be set to a cycle staller object to
    get additional cycle penalties due to cache misses.""")
