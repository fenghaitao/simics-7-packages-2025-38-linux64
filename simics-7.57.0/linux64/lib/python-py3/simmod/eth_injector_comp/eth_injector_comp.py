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


import simics
from comp import *

class eth_injector_comp(StandardComponent):
    """The Ethernet frame injector is a pseudo-device that reads a pcap
    formatted file and inject the packets it found into another device, or an
    Ethernet link."""
    _class_desc = 'ethernet frame injector'
    _help_categories = ('Networking',)

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_pre_obj('injector', 'eth_injector')
            self.add_connector(
                'link', 'ethernet-link', True, False, False,
                simics.Sim_Connector_Direction_Up)

    class basename(StandardComponent.basename):
        val = "injector"

    class component_connector(Interface):
        def get_check_data(self, cnt):
            return self._up.get_connect_data(cnt)
        def get_connect_data(self, cnt):
            return self._up.get_connect_data(cnt)
        def check(self, cnt, attr):
            return True
        def connect(self, cnt, attr):
            self._up.connect(cnt, attr)
        def disconnect(self, cnt):
            self._up.disconnect(cnt)

    def get_connect_data(self, cnt):
        if cnt.type == 'ethernet-link':
            return [self.get_slot('injector')]

    def connect(self, cnt, attr):
        if cnt == self.get_slot('link'):
            self.get_slot('injector').connection = attr[0]

    def disconnect(self, cnt):
        if cnt == self.get_slot('link'):
            self.get_slot('injector').connection = None
