# © 2015 Intel Corporation
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

class_name = 'gml_link_impl'

def status(obj):
    return []
def info(obj):
    def fmt_dev(dev_attr):
        if isinstance(dev_attr, list):
            (o, port) = dev_attr
            s = "%s:%s" % (o.name, port)
        else:
            o = dev_attr
            s = o.name if o else "(none)"
        cellname = None
        if o and simics.VT_object_cell(o):
            cellname = simics.VT_object_cell(o).name
        return (s, cellname or "(no cell)")

    return [(None,
             [('Goal latency', '%g s' % obj.goal_latency),
              ('Effective latency', '%g s' % obj.effective_latency)]),
            ('Connected devices',
             [fmt_dev(ep.device) for ep in obj.endpoints])]
cli.new_info_command(class_name, info)
cli.new_status_command(class_name, status)

def endpoint_info(obj):
    op = obj.device
    if isinstance(op, list):
        desc = "%s:%s" % (op[0].name, op[1])
    else:
        desc = op.name if op else '<none>'
    return [(None, [('Link', obj.link),
                    ('Connected device', desc)])]
def endpoint_status(obj):
    return []
cli.new_info_command('gml_link_endpoint', endpoint_info)
cli.new_status_command('gml_link_endpoint', endpoint_status)

from link_components import create_simple

class gml_link(
    create_simple(link_class = 'gml_link_impl',
                  endpoint_class = 'gml_link_endpoint',
                  connector_type = 'gml-link',
                  class_desc = "general message link component",
                  basename = 'gml_link')):
    """The gml link component creates a gml-link, which is a simple
    bus for forwarding messages (as sequences of bytes) from a sender
    to one or more destination devices."""
