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
import simics

device_name = "signal_to_interrupt"

def pretty_print_port(port):
    if isinstance(port, simics.conf_object_t):
        return port.name
    elif isinstance(port, list):
        return "%s:%s" % (port[0].name, port[1])

def get_info(obj):
    return [(None,
             [("IRQ device", pretty_print_port(obj.irq_dev)),
              ("IRQ level", obj.irq_level)])]

def get_status(obj):
    return []

cli.new_info_command(device_name, get_info)
cli.new_status_command(device_name, get_status)
