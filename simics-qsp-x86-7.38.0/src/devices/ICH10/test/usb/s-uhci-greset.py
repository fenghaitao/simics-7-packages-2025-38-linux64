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


# Test that an USB device connected to the UHCI controller show up as
# connected after a global reset (GRESET). Bug #23861.

from usb_tb import *
import stest

usb_dev = conf.usb_dev
uhci0 = conf.uhci0
ehci0 = conf.ehci0

ehci0.companion_hc = [uhci0, None, None, None, None, None]
usb_dev.usb_host = conf.ehci0

# map UHCI registers
io_base = ich9_uhci_io_base[0]
tb.map_hc_io("uhci", 0)

def read_usbcmd():
    return tb.read_io_le(io_base + 0x0, 16)
def write_usbcmd(val):
    tb.write_io_le(io_base + 0x0, 16, val)
def read_portsc0():
    return tb.read_io_le(io_base + 0x10, 16)

# the USB device should show up as connected to port 0
stest.expect_equal(read_portsc0(), 0x83)

# Begin GRESET cycle
GRESET = 1 << 2
write_usbcmd(GRESET)

# GRESET bit should be set until cleared by software
stest.expect_equal(read_usbcmd(), GRESET)

# port status should be reset to 0x80 (nothing connected)
stest.expect_equal(read_portsc0(), 0x80)

# clear GRESET
write_usbcmd(0)
stest.expect_equal(read_usbcmd(), 0)

# the USB device should again show up as connected to port 0
stest.expect_equal(read_portsc0(), 0x83)
