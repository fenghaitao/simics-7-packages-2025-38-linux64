# © 2014 Intel Corporation
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
from component_utils import get_component
from link_components import create_simple

class_name = 'ieee_802_15_4_link_impl'

def status(obj):
    return [('Connected endpoints',
            [(d.name, d.device.name if d.device else "None")
              for d in obj.endpoints])]

def info(obj):
    return [(None,
             [('Goal latency', '%g s' % obj.goal_latency),
              ('Effective latency', '%g s' % obj.effective_latency)])]

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

cli.new_info_command('ieee_802_15_4_link_endpoint', endpoint_info)
cli.new_status_command('ieee_802_15_4_link_endpoint', endpoint_status)

#
# component for ieee-802-15-4-link
#
class ieee_802_15_4_link(
    create_simple(link_class='ieee_802_15_4_link_impl',
                  endpoint_class='ieee_802_15_4_link_endpoint',
                  connector_type='ieee-802-15-4-link',
                  class_desc="model of IEEE 802.15.4 link",
                  basename='ieee_802_15_4_link')):
    """The IEEE 802.15.4 link component creates a ieee-802-15-4-link."""

    def get_free_connector_cmd(self):
        c = self.get_unconnected_connector_object('device')
        if not c:
            raise cli.CliError('Internal error: no connectors found')
        return c.name

get_free_connector_doc = """
This command returns the name of a connector which is not
connected to anything."""

cli.new_command('get-free-connector',
                lambda x : get_component(x).get_free_connector_cmd(),
                [],
                cls='ieee_802_15_4_link',
                type = ["Links"],
                short='return the name of an unused connector',
                doc=get_free_connector_doc)
