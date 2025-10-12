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

import comp
import simics


class sample_i3c_target_comp(comp.StandardConnectorComponent):
    """The component for sample I3C target."""

    _class_desc = "I3C target component"
    _help_categories = ()

    class static_address(comp.SimpleConfigAttribute(0xff, "i",
                                                    simics.Sim_Attr_Optional)):
        """Static address, set if initial communication use static address"""

    class pid(comp.SimpleConfigAttribute(0xFFFF_0000_0000, "i",
                                         simics.Sim_Attr_Optional)):
        """Provisional ID"""

    class dcr(comp.SimpleConfigAttribute(0x00, "i", simics.Sim_Attr_Optional)):
        """Device Characteristics Register"""

    class read_value(comp.SimpleConfigAttribute(0x00, "i",
                                                simics.Sim_Attr_Optional)):
        """Read response value"""

    def setup(self):
        comp.StandardConnectorComponent.setup(self)
        if not self.instantiated.val:
            self.add_objects()

        self.add_connector("bus_slot",
                           comp.I3CLinkUpConnector("target", "bus"))

    def add_objects(self):
        tgt = self.add_pre_obj("target", "sample-i3c-target")
        tgt.provisional_id = self.pid.val
        tgt.static_address = self.static_address.val
        tgt.dcr = self.dcr.val
