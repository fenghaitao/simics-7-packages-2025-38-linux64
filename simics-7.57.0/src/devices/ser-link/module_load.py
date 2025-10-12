# commands.py

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

class_name = 'ser-link-impl'
ep_class_name = 'ser-link-endpoint'

def objport(op):
    try:
        obj, port = op
    except (TypeError, ValueError):
        obj, port = (op, None)
    return obj, port

def link_info(obj):
    return []
def link_status(obj):
    def fmt(op):
        obj, port = objport(op)
        cellname = getattr(simics.VT_object_cell(obj), 'name', 'no cell')
        if port == None:
            return (obj.name, cellname)
        else:
            return ('%s:%s' % (obj.name, port), cellname)
    return [(None,
             [('Goal latency', '%g s' % obj.goal_latency),
              ('Effective latency', '%g s' % obj.effective_latency)]),
            ('Connected devices',
             [fmt(ep.device) for ep in obj.endpoints])]
cli.new_info_command(class_name, link_info)
cli.new_status_command(class_name, link_status)

def ep_info(obj):
    return []
def ep_status(obj):
    def fmt(op):
        obj, port = objport(op)
        if port == None:
            return obj.name if obj else '<none>'
        else:
            return '%s:%s' % (obj.name, port)
    return [(None,
             [('Link', obj.link.name),
              ('Connected device', fmt(obj.device))])]
cli.new_info_command(ep_class_name, ep_info)
cli.new_status_command(ep_class_name, ep_status)

#
# component for datagram-link
#

from comp import SimpleConfigAttribute
from link_components import link_component, create_generic_endpoint

def create_endpoint(link, dev):
    return create_generic_endpoint(ep_class_name, link, dev)

class ser_link(link_component):
    """Serial link connecting two serial devices"""
    _class_desc = 'serial link component'
    _help_categories = ['Links',]

    class basename(link_component.basename):
        val = 'serial_link'

    class buffer_size(SimpleConfigAttribute(10, 'i')):
        """The number of characters the link may buffer. Must be at least 1."""

    # the connector takes link, console as parameters, so return a None console
    def get_serial_check_data(self, cnt):
        return [None]

    def get_serial_connect_data(self, cnt):
        return [None]

    def connect_serial(self, cnt, attr):
        # the obj parameter is hidden as the second argument, for compatibility
        # reasons
        # Depending on the direction of the other component's connector,
        # we get different contents of the attr argument.
        try:
            ignore, obj, title = attr
        except ValueError:
            ignore, obj = attr
        return obj

    def create_unconnected_endpoint(self, cnt):
        return create_endpoint(self.get_slot('link'), None)

    def register_connector_templates(self):
        self.serial_tmpl = self.add_link_connector_template(
            name = 'serial-link-connector',
            type = 'serial',
            growing = False,
            create_unconnected_endpoint = self.create_unconnected_endpoint,
            get_check_data = self.get_serial_check_data,
            get_connect_data = self.get_serial_connect_data,
            connect = self.connect_serial)

    def add_objects(self):
        self.add_pre_obj_with_name('link', 'ser-link-impl',
                                   self.get_link_object_name(),
                                   goal_latency = self.goal_latency.val,
                                   global_id = self.global_id.val,
                                   buffer_size = self.buffer_size.val)
        self.add_link_connector('device', self.serial_tmpl)
        self.add_link_connector('device', self.serial_tmpl)
