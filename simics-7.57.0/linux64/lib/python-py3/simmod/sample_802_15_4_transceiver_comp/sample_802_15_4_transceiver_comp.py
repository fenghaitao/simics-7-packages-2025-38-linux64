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


from comp import *
import systempanel
import systempanel.widgets as w

class IEEE_802_15_4_Down_Connector(StandardConnector):
    '''The IEEE_802_15_4_Down_Connector class handles
    ieee-802-15-4-link down connections. The first
    argument to the init method is the device to
    be connected to a link.'''

    type = 'ieee-802-15-4-link'
    direction = simics.Sim_Connector_Direction_Down
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, dev):
        self.dev = dev

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.dev)]

    def connect(self, cmp, cnt, attr):
        (ep,) = attr
        cmp.get_slot(self.dev).ep = ep

    def disconnect(self, cmp, cnt):
        cmp.get_slot(self.dev).ep = None

class sample_802_15_4_transceiver_comp(StandardConnectorComponent):
    """a sample 802.15.4 transceiver component."""
    _class_desc = "sample transceiver"
    _help_categories = ()

    class id(SimpleConfigAttribute(0, 'i', simics.Sim_Attr_Optional)):
        """node ID"""

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_objects(self):
        transceiver = self.add_pre_obj('transceiver',
                                       'sample_802_15_4_transceiver')
        transceiver.id = self.id.val
        self.add_component('system_panel', 'sample_802_15_4_panel', [])
        transceiver.id_target = self.get_slot('system_panel.id')
        transceiver.pkt_sent_target = self.get_slot('system_panel.pkt_sent')
        transceiver.pkt_recv_target = self.get_slot('system_panel.pkt_recv')
        transceiver.pkt_lost_target = self.get_slot('system_panel.pkt_lost')
        transceiver.contention_target = self.get_slot('system_panel.contention')
        self.get_slot('system_panel.reset').target = [transceiver, "reset"]

    def add_connectors(self):
        self.add_connector('phy', IEEE_802_15_4_Down_Connector('transceiver'))

class sample_802_15_4_panel(systempanel.SystemPanel):
    """a sample 802.15.4 panel."""
    _class_desc = "sample 802.15.4 panel"
    default_layout = w.Row([w.Label('id'),
                            w.NumberOutput('id'),
                            w.Label("received"),
                            w.NumberOutput('pkt_recv'),
                            w.Label("lost"),
                            w.NumberOutput('pkt_lost'),
                            w.Label("sent"),
                            w.NumberOutput('pkt_sent'),
                            w.Label("contention"),
                            w.NumberOutput('contention'),
                            w.Button('reset', 'Reset')])
    objects = default_layout.objects()
