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


from comp import *
import simics
import sys, os
import dev_util
from device import can_controller

class can_link_comp(StandardComponent):
    """test new style component for can-link test device"""
    _class_desc = 'tests the CAN link component'

    class basename(StandardComponent.basename):
        val = 'can_link_comp'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()

    def add_objects(self):
        self.add_pre_obj('can_dev', 'can_controller')
        self.add_connector('link', 'can_link', True, False, False,
                           simics.Sim_Connector_Direction_Down)

    class component_connector(Interface):
        def get_check_data(self, cnt):
            return []
        def get_connect_data(self, cnt):
            if cnt == self._up.get_slot('link'):
                return [self._up.get_slot('can_dev'), None, "Test"]
            else:
                return []
        def check(self, cnt, attr):
            return True
        def connect(self, cnt, attr):
            if cnt == self._up.get_slot('link'):
                self._up.get_slot('can_dev').link = attr[0]
        def disconnect(self, cnt):
            if cnt == self._up.get_slot('link'):
                self._up.get_slot('can_dev').link = None
