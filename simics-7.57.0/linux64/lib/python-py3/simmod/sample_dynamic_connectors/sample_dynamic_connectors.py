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


#:: pre comp-dynamic-connectors-example {{
import simics
from comp import *

class sample_dynamic_connectors(StandardComponent):
    """A sample component dynamically creating connectors."""
    _class_desc = "sample comp with dynamic connectors"

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()

    class top_level(StandardComponent.top_level):
        def _initialize(self):
            self.val = True

    class num_serials(SimpleAttribute(0, 'i')):
        """Number of serial connectors"""

    def create_uart_and_connector(self):
        num = self.num_serials.val
        self.add_connector(
            'uart%d' % num, 'serial', True, False, False,
            simics.Sim_Connector_Direction_Down)
        if self.instantiated.val:
            o = simics.SIM_create_object('NS16550', '')
        else:
            o = pre_obj('', 'NS16550')
        self.add_slot('uart_dev%d' % num, o)
        self.num_serials.val += 1

    def add_objects(self):
        self.add_pre_obj('clock', 'clock', freq_mhz = 10)
        self.create_uart_and_connector()

    class component_connector(Interface):
        def get_check_data(self, cnt):
            return []
        def get_connect_data(self, cnt):
            self._up.create_uart_and_connector()
            num = int(cnt.name.split('uart')[1])
            return [None, self._up.get_slot('uart_dev%d' % num), cnt.name]
        def check(self, cnt, attr):
            return True
        def connect(self, cnt, attr):
            num = int(cnt.name.split('uart')[1])
            udev = self._up.get_slot('uart_dev%d' % num)
            (link, console) = attr
            if link:
                udev.link = link
            else:
                udev.console = console
        def disconnect(self, cnt):
            num = int(cnt.name.split('uart')[1])
            udev = self._up.get_slot('uart_dev%d' % num)
            udev.link = None
            udev.console = None
# }}
