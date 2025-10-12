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


from . import tcf_common as tcfc
from . import stepper_statistics
from . import target_identification
from . import proxy_commands
from . import tcf_object_commands
import os
import debugger_commands
from prompt_information import register_prompt_callback


def prompt_callback(frontend_id, output_function):
    dbg_obj = tcfc.get_debug_object()
    if dbg_obj is None:
        return

    p = tcfc.collect_prompt(tcfc.Debug_state.debug_state(dbg_obj))
    tcfc.print_prompt_to_frontend(frontend_id, p, output_function)

register_prompt_callback(prompt_callback)
debugger_commands.register_debug_object_updater(tcfc.update_debug_object)
stepper_statistics.register()

proxy_commands.register_proxy_cmds()
tcf_object_commands.register_cmds()
target_identification.register()
