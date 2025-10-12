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


from cli import (new_info_command, new_status_command,
                 new_command, arg, filename_t)

def get_sbd_info(obj):
    return []

new_info_command('simple-byte-dump', get_sbd_info)

def get_sbd_status(obj):
    filename = obj.filename if obj.filename else "(not set)"
    return [(None,
             [("Output file", filename)])]

new_status_command('simple-byte-dump', get_sbd_status)

def set_output_file_cmd(obj, filename):
    try:
        obj.filename = filename
    except Exception as msg:
        print("Could not set output filename: %s" % msg)

new_command("set-output-file", set_output_file_cmd,
            [arg(filename_t(), "filename", "?", None)],
            short = "sets file to output to",
            cls = "simple-byte-dump",
            doc = """
Set the <arg>filename</arg> of the file to which bytes will be written.
""")
