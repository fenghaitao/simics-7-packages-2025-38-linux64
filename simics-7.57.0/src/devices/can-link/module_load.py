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


import cli, simics

link_class_name     = 'can_link_impl'
endpoint_class_name = 'can_endpoint'

def objport(op):
    try:
        obj, port = op
    except (TypeError, ValueError):
        obj, port = (op, None)
    return obj, port

def fmt(op):
    if op == None:
        return 'None'
    obj, port = objport(op)
    cellname = getattr(simics.VT_object_cell(obj),
                       'name', 'no cell')
    if port == None:
        return (obj.name, cellname)
    else:
        return ('%s:%s' % (obj.name, port), cellname)

def link_info(obj):
    return [('Latency configuration',
             [('Goal latency', cli.format_seconds(obj.goal_latency)),
              ('Effective latency',
               cli.format_seconds(obj.effective_latency))]),
            ('Connected endpoints/devices',
             [(ep.name,
               fmt(ep.device)) for ep in obj.endpoints])]

def link_status(obj):
    return []

cli.new_info_command(link_class_name, link_info)
cli.new_status_command(link_class_name, link_status)

def ep_info(obj):
    return [('Endpoint info',[('Link', '%s (%s)' % (obj.link.name, obj.link.classname)),
            ('Connected device', fmt(obj.device))])]

def ep_status(obj):
    return []
cli.new_info_command(endpoint_class_name, ep_info)
cli.new_status_command(endpoint_class_name, ep_status)

#
# CAN link components
#

import link_components

class can_link(
    link_components.create_simple(link_class = link_class_name,
                                  endpoint_class = endpoint_class_name,
                                  connector_type = 'can_link',
                                  class_desc =
                                  'distributed CAN link component',
                                  basename = 'can_link',
                                  help_categories = ['distributed CAN link'])):
    """This component represents a simple CAN link allowing any number
    of devices to connect."""
