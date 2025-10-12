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


class standard_pcie_switch_comp(StandardConnectorComponent):
    """A generic PCIe switch with 4 slots implemented using the new Simics PCIe
    library"""

    _class_desc = "A PCIe Switch"
    _help_categories = ()
    nvme = None

    def setup(self):
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_connectors(self):
        self.add_connector("upstream_target", PciBusUpConnector(0, "sw.usp"))
        self.add_slot(
            "slot",
            [
                self.add_connector(
                    None, PciBusDownConnector(0, f"sw.dsp[{i}].downstream_port")
                )
                for i in range(4)
            ],
        )

    def add_objects(self):
        self.add_pre_obj("sw", "standard-pcie-switch")
