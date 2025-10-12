# © 2017 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import pyobj
from comp import *

# define sample i3c slave/master device
class foo(pyobj.ConfObject):
    '''i3c slave device'''
    def _initialize(self):
        super()._initialize()
        self.reqs = []

    class bus(pyobj.SimpleAttribute(None, 'n|o')):
        '''i3c bus'''

    class i3c_slave(pyobj.Interface):
        def start(self, addr):
            self._up.reqs.append(['start', addr])

        # slave write() called when it receives daa address
        def write(self, addr):
            self._up.reqs.append(['daa_address', addr])

        def sdr_write(self, data):
            self._up.reqs.append(['write', data])

        def read(self):
            self._up.reqs.append(['read'])

        def daa_read(self):
            self._up.reqs.append(['daa_read'])

        def stop(self):
            self._up.reqs.append(['stop'])

        def ibi_start(self):
            self._up.reqs.append(['ibi_start'])

        def ibi_acknowledge(self, ack):
            self._up.reqs.append(['ibi_acknowledge', ack])

    class i3c_hdr_slave(pyobj.Interface):
        def hdr_write(self, data):
            self._up.reqs.append(['hdr_write', data])

        def hdr_read(self, max_len):
            self._up.reqs.append(['hdr_read', max_len])

        def hdr_restart(self):
            self._up.reqs.append(['hdr_restart'])

        def hdr_exit(self):
            self._up.reqs.append(['hdr_exit'])


class bar(pyobj.ConfObject):
    '''i3c master device'''
    def _initialize(self):
        super()._initialize()
        self.reqs = []

    class bus(pyobj.SimpleAttribute(None, 'n|o')):
        '''i3c bus'''

    class i3c_master(pyobj.Interface):
        def acknowledge(self, ack):
            self._up.reqs.append(['ack', ack])

        def read_response(self, data, more):
            self._up.reqs.append(['r_resp', data, more])

        def daa_response(self, id, bcr, dcr):
            self._up.reqs.append(['daa_response', id, bcr, dcr])

        def ibi_request(self):
            self._up.reqs.append(['ibi_request'])

        def ibi_address(self, addr):
            self._up.reqs.append(['ibi_address', addr])

    class i3c_hdr_master(pyobj.Interface):
        def hdr_read_response(self, data, more):
            self._up.reqs.append(['hdr_r_resp', data, more])

        def hdr_acknowledge(self, ack):
            self._up.reqs.append(['hdr_ack', ack])

# define i3c components containing master and slave device
class i3c_master_dev_comp(StandardComponent):
    '''A component containing i3c master device and link device.'''

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()

    def add_objects(self):
        master = self.add_pre_obj('master', 'bar')
        link = self.add_pre_obj('link', 'i3c_link_impl')
        ep1  = self.add_pre_obj('ep1', 'i3c_link_endpoint')
        ep2  = self.add_pre_obj('ep2', 'i3c_link_endpoint')

        link.goal_latency = 0.0
        ep1.id = 1
        ep1.link = link
        ep1.device = master
        ep2.id = 2
        ep2.link = link
        ep2.device = None
        master.bus = ep1

        self.add_connector('link_conn', 'i3c-link', True, False, False,
                           simics.Sim_Connector_Direction_Down)

    class component_connector(Interface):
        def get_check_data(self, cnt):
            return []
        def get_connect_data(self, cnt):
            return [self._up.get_slot('ep2')]
        def check(self, cnt, attr):
            return True
        def connect(self, cnt, attr):
            self._up.get_slot('ep2').device = attr[0]
        def disconnect(self, cnt):
            self._up.get_slot('ep2').device = None

class i3c_slave_dev_comp(StandardComponent):
    """A component containing i3c slave device."""

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()

    def add_objects(self):
        self.add_pre_obj('slave', 'foo')
        self.add_connector('link_conn', 'i3c-link', True, False, False,
                           simics.Sim_Connector_Direction_Up)

    class component_connector(Interface):
        def get_check_data(self, cnt):
            return []
        def get_connect_data(self, cnt):
            return [self._up.get_slot('slave')]
        def check(self, cnt, attr):
            return True
        def connect(self, cnt, attr):
            self._up.get_slot('slave').bus = attr[0]
        def disconnect(self, cnt):
            self._up.get_slot('slave').bus = None

# The difference between i3c_master_dev_comp and i3c_simple_master_dev_comp
# is that i3c_master_dev_comp contains link device while the other is not.
class i3c_simple_master_dev_comp(StandardComponent):
    """A component containing i3c master device."""

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()

    def add_objects(self):
        self.add_pre_obj('master', 'bar')
        self.add_connector('link_conn', 'i3c-link', True, False, False,
                           simics.Sim_Connector_Direction_Down)

    class component_connector(Interface):
        def get_check_data(self, cnt):
            return []
        def get_connect_data(self, cnt):
            return [self._up.get_slot('master')]
        def check(self, cnt, attr):
            return True
        def connect(self, cnt, attr):
            self._up.get_slot('master').bus = attr[0]
        def disconnect(self, cnt):
            self._up.get_slot('master').bus = None
