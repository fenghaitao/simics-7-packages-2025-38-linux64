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


import simics
from comp import *

class GMLDownConnector(StandardConnector):
    def __init__(self, device):
        if not isinstance(device, str):
            raise CompException('device must be a string')
        self.device = device
        self.type = 'gml-link'
        self.hotpluggable = True
        self.required = False
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Down

    def get_check_data(self, cmp, cnt):
        return []
    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.device)]
    def check(self, cmp, cnt, attr):
        return True
    def connect(self, cmp, cnt, attr):
        (link,) = attr
        cmp.get_slot(self.device).link = link
    def disconnect(self, cmp, cnt):
        cmp.get_slot(self.device).link = None

class gml_dev_comp(StandardConnectorComponent):
    """The component encapsulating generic message devices for testing."""

    class top_level(StandardConnectorComponent.top_level):
        def _initialize(self):
            self.val = True

    class address(SimpleConfigAttribute(1, 'i')):
        """The address."""

    class dest_address(SimpleConfigAttribute(2, 'i')):
        """The destination address."""

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_gml_objects()
        self.add_gml_connectors()

    def add_gml_connectors(self):
        self.add_connector('connector_link', GMLDownConnector('dev'))
        self.add_connector('connector_link2', GMLDownConnector('dev2'))

    def add_gml_objects(self):
        self.add_pre_obj('clock', 'clock', freq_mhz = 0.000001)
        self.add_pre_obj('dev', 'test_generic_message_device',
                         address = self.address.val,
                         dest_address = [self.dest_address.val,
                                         self.dest_address.val])
        self.add_pre_obj('dev2', 'test_generic_message_device',
                         address = self.dest_address.val,
                         dest_address = [self.address.val,
                                         self.address.val])
