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

# List of prompt callbacks, should be functions on the following format:
# f(frontend_id, writer)
prompt_callbacks = []

# Registered by the debugger once it's created. For updating current debug
# object. Should be a function on the format: f(cpu)
debug_object_updater = None

def register_prompt_callback(f):
    prompt_callbacks.append(f)

def trigger_prompt_callbacks(frontend_id, writer):
    for f in prompt_callbacks:
        f(frontend_id, writer)

def update_debug_object(cpu=None):
    if not debug_object_updater:
        return
    debug_object_updater(cpu)

def register_debug_object_updater(f):
    global debug_object_updater
    debug_object_updater = f
