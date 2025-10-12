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

class_name = 'signal_link_impl'
ep_class_name = 'signal_link_endpoint'
sender_connector = 'sender'
receiver_connector = 'receiver'

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
        cellname = getattr(simics.VT_object_cell(obj),
                           'name', 'no cell')
        if port == None:
            return (obj.name, cellname)
        else:
            return ('%s:%s' % (obj.name, port), cellname)
    return [(None,
             [('Goal latency', '%g s' % obj.goal_latency),
              ('Effective latency', '%g s' % obj.effective_latency),
              ('Connected endpoints',
               [fmt(d.device) for d in obj.endpoints])])]
cli.new_info_command(class_name, link_info)
cli.new_status_command(class_name, link_status)

def ep_info(obj):
    return [(None, [
                ("Type", obj.type)])]

def ep_status(obj):
    def fmt(op):
        obj, port = objport(op)
        if port == None:
            return obj.name if obj else '<none>'
        else:
            return '%s:%s' % (obj.name, port)
    return [(None,
             [('Link', obj.link),
              ('Connected device', fmt(obj.device))])]
cli.new_info_command(ep_class_name, ep_info)
cli.new_status_command(ep_class_name, ep_status)

# signal_link component

from component_utils import get_component
from link_components import link_component, create_generic_endpoint

# create a ready-to-instantiate signal-link endpoint pre-conf-object
def create_endpoint(link, dev, is_sender):
    ep_obj = create_generic_endpoint('signal_link_endpoint', link, dev)
    ep_obj.type = ("%s" % sender_connector if is_sender
                   else "%s" % receiver_connector)
    return ep_obj

class signal_link(link_component):
    """The "signal_link" component represents a unidirectional signal
    that can be either high or low. It can be used to model electrical
    wires or more abstract binary signals."""
    _class_desc = 'signal link component'

    class basename(link_component.basename):
        val = 'signal_link'

    def create_sender_endpoint(self, cnt):
        return create_endpoint(self.get_slot('link'), None, True)

    def create_receiver_endpoint(self, cnt):
        return create_endpoint(self.get_slot('link'), None, False)

    def register_connector_templates(self):
        self.sender_tmpl = self.add_link_connector_template(
            name = 'signal-link-sender-connector',
            type = 'signal-link-sender',
            growing = True,
            create_unconnected_endpoint = self.create_sender_endpoint)
        self.receiver_tmpl = self.add_link_connector_template(
            name = 'signal-link-receiver-connector',
            type = 'signal-link-receiver',
            growing = True,
            create_unconnected_endpoint = self.create_receiver_endpoint)

    def add_objects(self):
        self.add_pre_obj_with_name('link', 'signal_link_impl',
                                   self.get_link_object_name(),
                                   global_id = self.global_id.val,
                                   goal_latency = self.goal_latency.val)
        self.add_link_connector('%s' % sender_connector, self.sender_tmpl)
        self.add_link_connector('%s' % receiver_connector, self.receiver_tmpl)

    def get_free_sender_connector_cmd(self):
        return self.get_unconnected_connector_object('%s' % sender_connector)

    def get_free_receiver_connector_cmd(self):
        return self.get_unconnected_connector_object('%s' % receiver_connector)

cli.new_command('get-free-sender-connector',
                lambda x : get_component(x).get_free_sender_connector_cmd(),
                [],
                cls = 'signal_link',
                type = ['Networking'],
                short = 'return the name of an unused sender connector',
                doc = """This command returns the name of a sender connector
                         which is not connected to anything.""")

cli.new_command('get-free-receiver-connector',
                lambda x : get_component(x).get_free_receiver_connector_cmd(),
                [],
                cls = 'signal_link',
                type = ['Networking'],
                short = 'return the name of an unused receiver connector',
                doc = """This command returns the name of a receiver connector
                         which is not connected to anything.""")
