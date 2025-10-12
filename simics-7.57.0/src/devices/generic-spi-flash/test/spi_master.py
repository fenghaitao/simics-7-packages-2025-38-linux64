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


import pyobj
import simics
from functools import reduce

class SPIMaster(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()

        self.slave_obj = None
        self.slave_iface = None
        self.payload = None
        self.bit_order_reverse = True #default true for testing M25Pxx

    def reverse_bit_order(self, payload):
        return reduce(
                lambda x, y: x + bytes((
                    sum(((y >> (7 - i)) & 1) << i for i in range(8)),)),
                payload, b'')

    class serial_peripheral_interface_master(pyobj.Interface):
        def spi_response(self, bits, payload):
            if self._up.bit_order_reverse:
                payload = self._up.reverse_bit_order(payload)
            self._up.payload = list(payload)

    class serial_peripheral_interface_slave(pyobj.Interface):
        def connect_master(self, master, port, flag):
            if not self._up.slave_obj:
                raise Exception('slave object hasn\'t been configured')
            self._up.slave_iface.connect_master(master, port, flag)

        def disconnect_master(self, master):
            if not self._up.slave_obj:
                raise Exception('slave object hasn\'t been configured')
            self._up.slave_iface.disconnect_master(master)

        def spi_request(self, first, last, bits, payload):
            if not self._up.slave_obj:
                raise Exception('slave object hasn\'t been configured')
            if self._up.bit_order_reverse:
                payload = self._up.reverse_bit_order(payload)
            self._up.slave_iface.spi_request(first, last, bits, payload)

    class slave(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional#Required
        attrtype = 'o'
        def getter(self):
            return self._up.slave_obj
        def setter(self, val):
            self._up.slave_obj = val
            self._up.finalize_slave()

    class bit_reverse(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'

        def setter(self, val):
            if val == 0:
                self._up.bit_order_reverse = False
            else:
                self._up.bit_order_reverse = True
        def getter(self):
            return (0, 1)[self._up.bit_order_reverse]

    class payload(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'd|n'
        def getter(self):
            return (None if self._up.payload == None
                    else tuple(self._up.payload))

        def setter(self, val):
            self._up.payload = val

    def _finalize(self):
        super()._finalize()
        if not self.slave_obj:
            return
        simics.SIM_require_object(self.slave_obj)
        self.finalize_slave()

    def finalize_slave(self):
        if not self.slave_obj:
            return
        self.slave_iface \
            = self.slave_obj.iface.serial_peripheral_interface_slave
