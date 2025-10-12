# © 2012 Intel Corporation
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
    doc = [("FTP Server",
            [("Enabled", obj.enabled),
             ("Service Node", obj.tcp),
             ("IP addresses", obj.server_ip_list),
             ("Root directory", obj.ftp_root_directory)])]
    return doc

def get_status(obj):
    doc = []
    id = 0
    for (sip, cip, cport, cwd, d_id) in obj.c_sessions:
        if d_id == -1:
            data = []
        else:
            passive, _, wr, filename, _, _, dirlist, _ = obj.d_sessions[d_id]
            data = [("Client Data Port", cport),
                    ("Type", 'passive' if passive else 'active'),
                    ("Direction", ('from' if wr else 'to') + ' client')]
            if filename:
                data += [("Data", 'file ' + filename)]
            elif dirlist:
                data += [("Data", 'directory listing')]
        stat = [("Server IP", sip),
                ("Client IP", cip),
                ("Current directory", cwd)] + data
        doc += [("Session %d" % id, stat)]
        id += 1
    return doc

def get_empty_info_status(obj):
    return []

cli.new_info_command("ftp-service", get_info)
cli.new_status_command("ftp-service", get_status)

cli.new_info_command("ftp-data", get_empty_info_status)
cli.new_status_command("ftp-data", get_empty_info_status)

cli.new_info_command("ftp-control", get_empty_info_status)
cli.new_status_command("ftp-control", get_empty_info_status)
