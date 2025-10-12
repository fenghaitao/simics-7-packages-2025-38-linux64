# © 2020 Intel Corporation
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
    new_info_command,
    new_status_command,
)

from simicsutils.host import is_windows

def get_info(obj):
    return []

def get_status(obj):
    data = [("Incoming port", obj.tcp.port)]
    if not is_windows():
        data.append(("UNIX socket", obj.unix_socket.socket_name))
    return [("Telnet", data),
            ("Connections",
             [("So far", obj.num_connections),
              ("Maximum", obj.max_connections)])]

new_info_command("telnet_frontend", get_info)
new_status_command("telnet_frontend", get_status)
