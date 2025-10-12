# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import cli


def get_info(obj):
    info = [("Share", obj.share),
            ("Debug logs", obj.daemon_log_file)]
    if obj.always_cache:
        info.append(("Always cache", True))
    return [("", info)]


def get_status(obj):
    return [("",
             [("Connection status",
               "Connected" if obj.connection_established else "Not connected"),
              ("FUSE daemon PID",
              obj.daemon_pid if obj.daemon_pid > 0 else None)])]


cli.new_info_command('virtiofs_fuse', get_info)
cli.new_status_command('virtiofs_fuse', get_status)
