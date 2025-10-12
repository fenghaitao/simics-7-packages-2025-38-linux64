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

class phy_comp(StandardConnectorComponent):
    """Component representing a generic IEEE 802.3 PHY"""
    _class_desc = 'generic IEEE 802.3 PHY'
    _help_categories = ('Networking',)

    class basename(StandardConnectorComponent.basename):
        val = 'phy_cmp'

    class phy_id(SimpleConfigAttribute(0, 'i')):
        """PHY ID (i.e., vendor)"""

    class mii_address(SimpleConfigAttribute(0, 'i')):
        """PHY address on MII bus"""

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_objects(self):
        phy = self.add_pre_obj('phy', 'generic_eth_phy')
        phy.address = self.mii_address.val
        phy.phy_id = self.phy_id.val

    def add_connectors(self):
        self.add_slot('mac', self.add_connector(
                None, PhyUpConnector('phy', self.mii_address.val, True)))
        self.add_slot('eth', self.add_connector(
                None, EthernetLinkDownConnector('phy')))
