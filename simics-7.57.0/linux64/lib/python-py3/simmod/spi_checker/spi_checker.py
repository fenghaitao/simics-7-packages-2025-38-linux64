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


import cli
import simics
import pyobj

# This is a Simics module, so we don't want to import stest because of its
# side-effects.
def expect_true(cond, msg=""):
    if not cond:
        raise Exception("Expectation failed: " + msg)

def expect_equal(got, expected, msg=""):
    if got != expected:
        raise Exception("got %r, expected %r: %s" % (got, expected, msg))

class spi_checker(pyobj.ConfObject):
    '''This object checks the communication between a SPI master and
    slave, and reports test failures if any of the objects breaches
    the SPI protocol.  The spi_checker implements both the SPI master
    and slave interfaces, and should be used as a proxy between these.
    You should initially set the 'slave' attribute of the spi_checker
    to the slave object you wish to check, and then connect the
    spi_checker object as a slave to the spi_master object.'''
    _class_desc = "checks the communication between master and slave"

    def _initialize(self):
        super()._initialize()
        self.slave_obj = None
        self.master_obj = None

    class slave_expected_size(pyobj.SimpleAttribute(None, "i|n")):
        '''If this is a number, we expect the next operation to be a
        response of this size from the slave.'''

    class serial_peripheral_interface_slave(pyobj.Interface):
        class active(pyobj.SimpleAttribute(False, "b")):
            '''True while an SPI transaction is active, lowered to
            False after a transaction's last SPI request from the
            master device.'''

        def connect_master(self, master, port, flags):
            expect_true(not self._up.master_obj,
                        "Calls to connect_master() should be"
                        " separated by disconnect_master() calls")
            self._up.master_obj = master
            if (port == ""):
                self._up.master_iface = simics.SIM_get_interface(
                    master, "serial_peripheral_interface_master")
            else:
                self._up.master_iface = simics.SIM_get_port_interface(
                    master, "serial_peripheral_interface_master", port)
            self._up.slave_iface.connect_master(self._up.obj, None, flags)

        def disconnect_master(self, master):
            expect_true(self._up.master_obj,
                        "disconnect_master(): not connected to a master")
            expect_equal(master, self._up.master_obj,
                         "disconnect_master() call from unexpected device")
            self._up.master_obj = None
            self._up.slave_iface.disconnect_master(self._up.obj)

        def spi_request(self, first, last, bits, payload):
            expect_equal(self._up.slave_expected_size.val, None,
                         "Got second spi_request without an intervening"
                         " response")
            expect_equal(len(payload), int((bits + 7) // 8),
                         f"Payload length={len(payload)} doesn't correspond to the length in bits={bits}")

            if first:
                expect_true(not self.active.val,
                            "spi_request: Request marked as 'first'"
                            " while a transaction is in progress")
                self.active.val = True
            else:
                expect_true(self.active.val,
                            "spi_request: Request for new transaction"
                            " not marked as 'first'")

            if last:
                self.active.val = False

            self._up.slave_expected_size.val = bits
            self._up.slave_iface.spi_request(first, last, bits, payload)

    class serial_peripheral_interface_master(pyobj.Interface):
        def spi_response(self, bits, payload):
            expect_equal(bits, self._up.slave_expected_size.val,
                         "Length of slave's response doesn't match"
                         " previous request from master")
            expect_equal(len(payload), int((bits + 7) // 8),
                         "Payload length doesn't correspond to"
                         " the length in bits")
            expect_true(self._up.master_obj,
                        "Got response from slave after disconnect")
            self._up.slave_expected_size.val = None
            self._up.master_iface.spi_response(bits, payload)

    class slave(pyobj.Attribute):
        '''The connected slave device'''
        attrattr = simics.Sim_Attr_Required
        attrtype = 'o'
        def getter(self):
            return self._up.slave_obj
        def setter(self, val):
            # the attribute is immutable to make things easier.
            reconfig = False
            if self._up.slave_obj:
                reconfig = True
                if self._up.master_obj:
                    self._up.slave_iface.disconnect_master(self._up.obj)
            self._up.slave_obj = val
            if reconfig:
                self._up.slave_iface = (
                    self._up.slave_obj.iface.serial_peripheral_interface_slave)
                if self._up.master_obj:
                    self._up.slave_iface.connect_master(self._up.obj, None, 0)

    class master(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = 'o'
        def getter(self):
            return self._up.master_obj

    def _finalize(self):
        super()._finalize()
        simics.SIM_require_object(self.slave_obj)
        self.slave_iface = (
            self.slave_obj.iface.serial_peripheral_interface_slave)

    def _info(self):
        ongoing = bool(self.serial_peripheral_interface_slave.active.val
                       or self.slave_expected_size.val)
        return [(None,
                 [("Ongoing transfer", ["no", "yes"][ongoing])])]

    def _status(self):
        return [(None,
                 [("slave", self.slave_obj),
                  ("master", self.master_obj)])]
