# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

from comp import (StandardConnectorComponent, PciBusUpConnector,
                  PciBusDownConnector)


class legacy_upstream_pcie_adapter_comp(StandardConnectorComponent):
    """An adapter component that allows connecting a PCIe endpoint implemented
    with the new PCIe library to an upstream that is implemented with the
    legacy PCIe library. Note that the upstream must be PCIe compatible (a
    pcie-bus, not a pci-bus)."""
    _class_desc = "PCIe Compatibility Adapter"
    _help_categories = ()

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_connectors(self):
        self.add_connector('pci_bus', PciBusUpConnector(0, 'bridge'))
        self.add_connector('pcie', PciBusDownConnector(0, 'bridge'))

    def add_objects(self):
        self.add_pre_obj('bridge', 'legacy-upstream-pcie-adapter')
