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


#:: pre module {{
import simics
from comp import StandardComponent, SimpleConfigAttribute, Interface

class sample_pci_card(StandardComponent):
    """A sample component containing a sample PCI device."""
    _class_desc = "sample PCI card"
    _help_categories = ('PCI',)

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_objects(self):
        sd = self.add_pre_obj('sample_dev', 'sample_pci_device')
        sd.int_attr = self.integer_attribute.val

    def add_connectors(self):
        self.add_connector(slot = 'pci_bus', type = 'pci-bus',
                           hotpluggable = True, required = False, multi = False,
                           direction = simics.Sim_Connector_Direction_Up)

    class basename(StandardComponent.basename):
        """The default name for the created component"""
        val = "sample_cmp"

    class integer_attribute(SimpleConfigAttribute(None, 'i',
                                                  simics.Sim_Attr_Required)):
        """Example integer attribute."""

    class internal_attribute(SimpleConfigAttribute(
            0,  # initial value
            'i',
            simics.Sim_Attr_Internal | simics.Sim_Attr_Optional)):
        """Example internal attribute (will not be documented)."""

    class component_connector(Interface):
        """Uses connector for handling connections between components."""
        def get_check_data(self, cnt):
            return []
        def get_connect_data(self, cnt):
            return [[[0, self._up.get_slot('sample_dev')]]]
        def check(self, cnt, attr):
            return True
        def connect(self, cnt, attr):
            self._up.get_slot('sample_dev').pci_bus = attr[1]
        def disconnect(self, cnt):
            self._up.get_slot('sample_dev').pci_bus = None

# }}
