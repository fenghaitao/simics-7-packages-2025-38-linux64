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


from comp import PciBusDownConnector, PciBusUpConnector, StandardConnectorComponent


class sample_pcie_device_comp(StandardConnectorComponent):
    """A sample PCIe endpoint"""

    _class_desc = "A PCIe Endpoint"
    _help_categories = ()
    nvme = None

    def setup(self):
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_connectors(self):
        self.add_connector("upstream_target", PciBusUpConnector(0, "ep"))

    def add_objects(self):
        self.add_pre_obj("ep", "sample-pcie-device")
