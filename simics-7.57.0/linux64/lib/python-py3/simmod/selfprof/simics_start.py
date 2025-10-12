# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

from cli import (
    CliError,
    add_unsupported,
    arg,
    command_return,
    int_t,
    new_unsupported_command,
    )
import simics
import conf

def start_selfprof_obj_cmd(obj, num_bufs):
    obj.cells = conf.sim.cell_list
    if num_bufs != -1:
        obj.init = num_bufs
    try:
        obj.run = True
    except Exception as ex:
        raise CliError("Failed starting self profiling: %s" % ex)
    return command_return(message = "Self profiling of Simics started.",
                          value = obj)

def start_selfprof_cmd(num_bufs):
    simics.SIM_load_module('selfprof')
    from simmod.selfprof import module_load
    return start_selfprof_obj_cmd(module_load.get_object(), num_bufs)

add_unsupported("selfprof")

new_unsupported_command("start-selfprof", "selfprof", start_selfprof_cmd,
                        [arg(int_t, "max-samples", "?", -1)],
                        see_also = ['<selfprof>.stop', '<selfprof>.clear',
                                    '<selfprof>.list', '<selfprof>.print-tree',
                                    '<selfprof>.save-graph'],
                        short = "start self-profiling",
                        doc = """
Start profiling of Simics itself. The <arg>max-samples</arg> argument is the
number of samples to allocate buffers for; only change it from the default
if you get a warning in a previous run. When <arg>max-samples</arg> is
supplied, any previously collected statistics will be cleared.
""")
