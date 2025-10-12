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

from cli import (
    new_info_command,
    new_status_command,
)
from simics import *

#
# -------------------- info, status --------------------
#

def get_info(obj):
    return [(None,
             [("Frequency",  "%s MHz" % obj.freq_mhz),
              ("Cell" , obj.cell)])]

new_info_command("clock", get_info)

def get_status(obj):
    return []

new_status_command("clock", get_status)

from comp import *

class cell_and_clocks_comp(StandardComponent):
    """The "cell_and_clock_comp" component builds a simulation cell with a
       configurable number of clocks. Each clock is exported as a connector.
       This component is meant to be used for building small test
       configurations."""
    _class_desc = "cell with one or more clocks"
    _help_categories = ()

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()

    class basename(StandardComponent.basename):
        val = 'cell_and_clocks_cmp'

    class clock_number(SimpleConfigAttribute(1, 'i')):
        """Number of clocks to run"""
        pass

    class freq_mhz(SimpleConfigAttribute(1, 'i')):
        """Frequency of Clocks"""
        pass

    class top_level(StandardComponent.top_level):
        def _initialize(self):
            self.val = True

    def add_objects(self):
        self.add_pre_obj("clock_dev[%d]" % self.clock_number.val, 'clock',
                         freq_mhz = self.freq_mhz.val)
        self.add_connector("clock[%d]" % self.clock_number.val, 'clock', True,
                           False, True, simics.Sim_Connector_Direction_Down)

    class component_connector(Interface):
        def get_check_data(self, cnt):
            return self._up.get_connect_data(cnt)
        def get_connect_data(self, cnt):
            return self._up.get_connect_data(cnt)
        def check(self, cnt, attr):
            return True
        def connect(self, cnt, attr):
            pass
        def disconnect(self, cnt):
            pass

    def get_connect_data(self, cnt):
        if cnt in self.get_slot('clock'):
            num = self.get_slot('clock').index(cnt)
            return [self.get_slot("clock_dev[%d]" % num)]

cell_and_clocks_comp.register()
