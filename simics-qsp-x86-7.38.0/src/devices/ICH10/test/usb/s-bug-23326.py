# © 2016 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Test that changing ownership of an usb device back and forth between
# the EHCI controller and its companion (UHCI) controller works properly.
# In particular, the device should not become disconnected. Bug #23326.

from usb_tb import *
import stest

usb_dev = conf.usb_dev
ehci0 = conf.ehci0
uhci0 = conf.uhci0

# map EHCI io region
io_base = ich9_ehci_io_base[0]
tb.map_hc_mem("ehci", 0)

def read_port0sc():
    return tb.read_value_le(io_base + 0x64, 32)
def write_port0sc(val):
    tb.write_value_le(io_base + 0x64, 32, val)

ehci0.companion_hc = [uhci0, None, None, None, None, None]
usb_dev.usb_host = conf.ehci0

# ehci0 should still have a reference to the usb device
stest.expect_equal(ehci0.usb_devices[0], usb_dev)

# uhci0 should also have a reference to the usb device
stest.expect_equal(uhci0.usb_devices[0], usb_dev)

# mark EHCI controller as configured
tb.write_value_le(io_base + 0x60, 32, 0x1)

# ehci0 should have a reference to the usb device
stest.expect_equal(ehci0.usb_devices[0], usb_dev)

# the uhci0 should have lost its reference to the device
# (it is now owned by the EHCI controller)
stest.expect_equal(uhci0.usb_devices[0], None)

# PORTSC register should indicate that the EHCI controller owns the port
stest.expect_equal(read_port0sc(), 0x100f)

# move usb device back to the UHCI controller
write_port0sc(read_port0sc() | 0x2000)

# check that the device is now owned by the UHCI controller
stest.expect_equal(read_port0sc(), 0x3006)

# check that both controllers have references to the device
stest.expect_equal(uhci0.usb_devices[0], usb_dev)
stest.expect_equal(ehci0.usb_devices[0], usb_dev)

# move the usb device back to the EHCI controller
write_port0sc(read_port0sc() & ~0x2000)

# check that the EHCI controllers has a references to the device
stest.expect_equal(uhci0.usb_devices[0], None)
stest.expect_equal(ehci0.usb_devices[0], usb_dev)
