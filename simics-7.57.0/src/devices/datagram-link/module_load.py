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

class_name = 'datagram_link_impl'

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
cli.new_info_command('datagram_link_endpoint', endpoint_info)
cli.new_status_command('datagram_link_endpoint', endpoint_status)

#
# component for datagram-link
#

# <add id="dl_comp"><insert-until text="# dl_comp_end"/></add>
from link_components import create_simple

class datagram_link(
    create_simple(link_class = 'datagram_link_impl',
                  endpoint_class = 'datagram_link_endpoint',
                  connector_type = 'datagram-link',
                  class_desc = "datagram link",
                  basename = 'datagram_link')):
    """The datagram link component creates a datagram-link, which is a simple
    broadcast bus forwarding messages (as sequences of bytes) from a sender
    device to all other devices present of the link. The datagram-link is both
    an example of how to build a link with the Simics Link Library, and a
    simple broadcast link that can be reused when multi-cell communication
    between devices is necessary. Refer to the <cite>Link Library Programming
    Guide</cite> for more information."""
# dl_comp_end
