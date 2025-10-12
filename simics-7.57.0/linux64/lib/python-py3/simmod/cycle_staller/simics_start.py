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


from cli import (
    arg,
    get_available_object_name,
    int_t,
    new_command,
    str_t,
    CliError,
)
from simics import *
import conf


def new_cycle_stall_cmd(name, interval):
    if not name:
        name = get_available_object_name("cs")
    if hasattr(conf, name):
        raise CliError(f"An object with name '{name}' already exists")
    else:
        return SIM_create_object("cycle_staller", name, interval=interval)


new_command("new-cycle-staller", new_cycle_stall_cmd,
            args = [arg(str_t, "name", "?"),
                    arg(int_t, "stall-interval", "?", 10000)],
            short = "create new cycle staller",
            type = ["Instrumentation"],
            see_also = ["new-simple-cache-tool"],
            doc = """
            Return a new cycle staller object that can be used to
            insert extra stall cycles to the clocks/processors in the
            model. An example usage is together with caches to model
            extra cycles due to cache misses. A cycle staller object
            will accumulate the extra stall cycles fed by other
            objects and eventually at every <arg>stall-interval</arg>
            insert those extra cycles by stalling the associated
            clock. <arg>name</arg> can be given to set a name for the
            object.""")
