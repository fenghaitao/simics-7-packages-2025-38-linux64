# © 2017 Intel Corporation
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

def get_info(obj):
    return []

def get_status(obj):
    return []

for cls in ['i3c_link_endpoint', 'i3c_link_impl',
            'i3c_cable_impl', 'i3c_cable_endpoint', 'i3c_wire']:
    cli.new_info_command(cls, get_info)
    cli.new_status_command(cls, get_status)

def bus_info(obj):
    devices = [('Port %d' % i, obj.i3c_devices[i])
               for i in range(12) if obj.i3c_devices[i]]
    return [("Devices", devices)]

def bus_status(obj):
    def port_object(p):
        if p == 0xFF or not obj.i3c_devices[p]:
            return None
        return obj.i3c_devices[p]
    slaves = [port_object(i) for i in range(12)
              if obj.i3c_active_slaves & (1 << i)]
    return [(None, [('Bus status', obj.status),
                    ('Current master', port_object(obj.i3c_main_master)),
                    ('Active slaves', slaves),
                   ])]
cli.new_info_command('i3c_bus', bus_info)
cli.new_status_command('i3c_bus', bus_status)

def adapter_info(obj):
    return[(None, [('I3C link/bus', obj.i3c_link),
                   ('I2C device', obj.i2c_link_v2)])]
cli.new_info_command('i2c_to_i3c_adapter', adapter_info)
cli.new_status_command('i2c_to_i3c_adapter', lambda obj: [])

import pyobj
import link_components

class i3c_link(
    link_components.create_simple(link_class = "i3c_link_impl",
                                  endpoint_class = "i3c_link_endpoint",
                                  connector_type = 'i3c-link',
                                  class_desc = 'an I3C link component',
                                  basename = 'i3c_link')):
    """This component represents a simple i3c link allowing any number
    of devices to connect."""

def create_cable_endpoint(link, dev):
    return link_components.create_generic_endpoint('i3c_cable_endpoint',
                                                   link, dev)
class i3c_cable(link_components.link_component):
    '''I3C cable: this component represents a two-points i3c cable,
allowing two devices to connect to each other or connects an I3C device to
I3C bus.'''
    _class_desc = 'an I3C cable component'

    class basename(link_components.link_component.basename):
        val = 'i3c_cable'

    class connector_count(pyobj.SimpleAttribute(0, 'i')):
        '''Number of connectors'''

    def allow_new_connector(self):
        if self.connector_count.val == 2:
            return False
        elif self.connector_count.val == 1:
            self.connector_count.val += 1
            return False
        else:
            self.connector_count.val += 1
            return True

    def allow_destroy_connector(self):
        if self.connector_count.val == 2:
            self.connector_count.val -= 1
            return False
        else:
            self.connector_count.val -= 1
            return True

    def create_unconnected_endpoint(self, cnt):
        return create_cable_endpoint(self.get_slot('link'), None)

    def register_connector_templates(self):
        self.i3c_tmpl = self.add_link_connector_template(
                'i3c_tmpl', 'i3c-link', True,
                create_unconnected_endpoint = self.create_unconnected_endpoint,
                allow_new_cnt = self.allow_new_connector,
                allow_destroy_cnt = self.allow_destroy_connector)

    def add_objects(self):
        self.add_pre_obj_with_name('link', 'i3c_cable_impl',
                                   self.get_link_object_name(),
                                   goal_latency = self.goal_latency.val,
                                   global_id = self.global_id.val)
        self.add_link_connector('device', self.i3c_tmpl)

i3c_cable.register()
