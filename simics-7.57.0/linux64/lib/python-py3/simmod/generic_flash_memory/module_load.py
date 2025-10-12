# commands.py

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
    arg,
    flag_t,
    new_command,
    new_info_command,
    new_status_command,
    )

def accept_inquiries_cmd(object, flags):
    raise CliError("Use <memory_space>.read or <memory_space>.write to " +
                   "simulate non-inquiry accesses.")

new_command("accept-inquiries", accept_inquiries_cmd,
            [arg((flag_t, flag_t), ("-on", "-off"), "?")],
            cls = "generic-flash-memory",
            short = "set whether or not to handle inquiry accesses",
            deprecated = "<memory_space>.write")

def command_set(cmd_set):
    all = ["None", "Intel", "AMD", "Intel (extended)", "AMD (extended)"]
    if cmd_set < len(all):
        return all[cmd_set]
    else:
        return "Unknown (%s)" % cmd_set

def get_info(obj):
    timing_info = [[state, "%g s"%secs] for state, secs in
                   list(dict(obj.timing_model).items()) if secs != 0.0 ]

    return [(None,
             [("Command set", command_set(obj.command_set)),
              ("Device", obj.device_id),
              ("Manufacturer", obj.manufacturer_id),
              ("Interleave", "%d" % obj.interleave),
              ("Bus width", "%d bits" % obj.bus_width)]),
            ("Timing model",
             timing_info)]

def get_status(obj):
    return [(None,
             [("Mode", obj.chip_mode)])]

new_info_command('generic-flash-memory', get_info)
new_status_command('generic-flash-memory', get_status)
