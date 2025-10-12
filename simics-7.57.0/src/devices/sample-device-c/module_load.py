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


import cli

#
# ------------------------ info -----------------------
#

def get_sample_info(obj):
    return []

cli.new_info_command('sample-device-c', get_sample_info)

#
# ------------------------ status -----------------------
#

def get_sample_status(obj):
    return [(None,
             [("Attribute 'value'", obj.attr.value)])]

cli.new_status_command('sample-device-c', get_sample_status)

#
# ---------------- simple method ------------------------
#

def simple_method_cmd(obj, arg):
    obj.iface.sample.simple_method(arg)

cli.new_command("simple-method", simple_method_cmd,
                [cli.arg(cli.int_t, "arg")],
                short = "simple example method",
                cls = "sample-device-c",
                doc = """
Simple method used as a sample. Prints the <arg>arg</arg> argument.
""")
