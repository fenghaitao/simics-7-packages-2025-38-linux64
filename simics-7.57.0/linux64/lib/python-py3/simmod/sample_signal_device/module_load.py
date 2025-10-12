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


from cli import new_info_command, new_status_command

class_name = "sample_signal_device_impl"

def info(obj):
    return []

def status(obj):
    return [ ("Input",
              [ ("Number of positive flanks", obj.attr.incount )]),
             ("Output",
              [ ("Toggle cycles left flanks", obj.attr.count )])]

new_info_command(class_name, info)
new_status_command(class_name, status)


# test component with one sample-signal-device

from comp import StandardComponent, ConfigAttribute, Interface
import simics

class sample_signal_device(StandardComponent):
    """A sample-signal-device with in/out connectors"""
    _class_desc = 'sample signal link component'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()

    class basename(StandardComponent.basename):
        val = 'sample_signal_device'

    class period(ConfigAttribute):
        """Period of this component, connected to sub objects."""
        attrtype = 'f'
        def _initialize(self):
            self.val = 0.1
        def setter(self, val):
            if self._up.obj.configured:
                self._up.get_slot("dev").attr.period = val
            self.val = val
        def getter(self):
            return self.val

    class count(ConfigAttribute):
        """Count of this component, connected to sub objects."""
        attrtype = 'i'
        def _initialize(self):
            self.val = 10
        def setter(self, val):
            if self._up.obj.configured:
                self._up.get_slot("dev").attr.count = val
            self.val = val
        def getter(self):
            return self.val

    def add_objects(self):
        dev = self.add_pre_obj('dev', 'sample_signal_device_impl')
        dev.attr.period = self.period.val
        dev.attr.count = self.count.val
        self.add_connector('in','signal-link-receiver', True, False,
                           False, simics.Sim_Connector_Direction_Down)
        self.add_connector('out', 'signal-link-sender', True, False,
                           False, simics.Sim_Connector_Direction_Down)
        self.add_connector('clock', 'clock', True, False, False,
                           simics.Sim_Connector_Direction_Up)

    class component_connector(Interface):
        def get_check_data(self, cnt):
            # same as connect_data
            return self._up.get_connect_data(cnt)
        def get_connect_data(self, cnt):
            return self._up.get_connect_data(cnt)
        def check(self, cnt, attr):
            return True
        def connect(self, cnt, attr):
            self._up.connect(cnt, attr)
        def disconnect(self, cnt):
            self._up.disconnect(cnt)

    def get_connect_data(self, cnt):
        if cnt == self.get_slot('out'):
            return [[self.get_slot('dev'), 'outgoing']]
        elif cnt == self.get_slot('in'):
            return [[self.get_slot('dev'), 'incoming']]
        else:
            return []

    def connect(self, cnt, attr):
        if cnt == self.get_slot('out'):
            self.get_slot('dev').attr.outgoing_receiver = attr[0]
        elif cnt == self.get_slot('clock'):
            self.get_slot('dev').attr.queue = attr[0]

    def disconnect(self, cnt):
        if cnt == self.get_slot('out'):
            self.get_slot('dev').attr.outgoing_receiver = None
        elif cnt == self.get_slot('clock'):
            self.get_slot('dev').attr.queue = None

sample_signal_device.register()
