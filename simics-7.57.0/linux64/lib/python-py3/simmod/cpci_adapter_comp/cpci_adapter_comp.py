# © 2013 Intel Corporation
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

class cpci_adapter(StandardComponent):
    """Adapter between a standard PCI up-connector and a cPCI down-connector."""
    _class_desc = 'a PCI to cPCI adapter'
    _help_categories = ('PCI',)

    class basename(StandardComponent.basename):
        val = 'cpci_adapter'

    def setup(self):
        StandardComponent.setup(self)
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_objects(self):
        self.pci_data = None
        self.cpci_data = None

    def add_connectors(self):
        # neither up nor down connectors can be hotpluggable, as the connect
        # logic relies on passing down the cPCI data to the PCI device and the
        # PCI device up to the cPCI bus without caching the data in attributes.
        # In addition, the hotplug event cannot be relayed over an adapter
        self.add_connector('pci', 'pci-bus', hotpluggable=False,
                           required=True, multi=False,
                           direction=simics.Sim_Connector_Direction_Down)
        self.add_connector('cpci', 'compact-pci-bus', hotpluggable=False,
                           required=True, multi=False,
                           direction=simics.Sim_Connector_Direction_Up)

    class component_connector(Interface):
        def get_check_data(self, cnt):
            return []
        def get_connect_data(self, cnt):
            # Convert the data before returning it. The reason this is done
            # here and not in the connect() method is because the adapter must
            # convert the pre-obj into a conf-obj before passing it on to the
            # other side, iff the other side has been instantiated already
            if cnt.type == 'pci-bus':
                # Nothing to convert for pci-bus (down)
                return self._up.pci_data
            if cnt.type == 'compact-pci-bus':
                # Transform PCI data to cPCI data (up)
                (device_list,) = self._up.cpci_data
                data = []
                for dev in device_list:
                    # If cpci has been instantiated, it expects real objects
                    # If not, Simics will handle the conversion
                    obj = get_pre_obj_object(dev[1])
                    data += [[[dev[0], obj if obj else dev[1], False]]]

                return data
            assert False
        def check(self, cnt, attr):
            return True
        def connect(self, cnt, attr):
            # Store connect data to be used at the other end of the adapter
            if cnt.type == 'pci-bus':
                self._up.cpci_data = attr
            if cnt.type == 'compact-pci-bus':
                self._up.pci_data = attr
        def disconnect(self, cnt):
            if cnt.type == 'pci-bus':
                self._up.pci_data = None
            if cnt.type == 'compact-pci-bus':
                self._up.cpci_data = None
