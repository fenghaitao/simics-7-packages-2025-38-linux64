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

device_name = "signal-bus"

def get_status(obj):
    return [(None,
             [("Current output level", "%d" % obj.level)])]

def get_info(obj):
    target_list = []
    for tgt in obj.targets if obj.targets else []:
        if isinstance(tgt, list):
            target_list += [[tgt[0].name, "Port '%s'" % tgt[1]]]
        else:
            target_list += [[tgt.name, ""]]

    return [("Connected devices",
             [(("%s" % tgt[0], "%s" % tgt[1])) for tgt in target_list])]

cli.new_info_command(device_name, get_info)
cli.new_status_command(device_name, get_status)
