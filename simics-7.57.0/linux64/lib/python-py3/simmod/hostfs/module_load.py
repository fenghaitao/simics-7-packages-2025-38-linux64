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
    command_quiet_return,
    filename_t,
    new_command,
    new_info_command,
    new_status_command,
    )

def root_cmd(obj, root):
    if root:
        if obj.mounted:
            raise CliError("Cannot change hostfs root while simicsfs "
                           "is mounted")
        obj.host_root = root
        return command_quiet_return(obj.host_root)

    return obj.host_root

new_command("root", root_cmd,
            [arg(filename_t(dirs=1, exist=1), "dir", "?", "")],
            cls = "hostfs",
            type = ["Matic"],
            short = "get or set the hostfs root directory",
            doc = """
If <arg>dir</arg> is specified, set the host directory that is visible
to the simulated machine accordingly. This is only allowed when the
file system is not mounted by the simulated machine.

Returns the current root directory.""")

def get_info(obj):
    return [(None,
             [("Host Root", obj.host_root)])]

new_info_command('hostfs', get_info)

def get_status(obj):
    if obj.version == (1 << 64) - 1:
        mount_stat = "no"
    else:
        mount_stat = "yes"
    return [(None,
             [("Mounted", mount_stat)])]

new_status_command('hostfs', get_status)
