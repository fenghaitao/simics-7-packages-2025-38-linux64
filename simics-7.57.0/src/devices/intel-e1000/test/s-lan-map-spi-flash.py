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


# s-lan-map-spi-flash.py
# tests ICH LAN to map GbE SPI flash program register bank in the SPI interface

from tb_lan import *
stest.untrap_log("unimpl")
stest.untrap_log("spec-viol")

def do_test():
    tb.lan.ports.HRESET.signal.signal_raise()
    tb.write_value_le(ICH9_PCI_CONF_BASE + 0x14, 32, SPI_FLASH_BASE)
    tb.write_value_le(ICH9_PCI_CONF_BASE + 0x04, 16, 0x3)
    for i in range(SPI_FLASH_LEN):
        tb.write_value_le(SPI_FLASH_BASE + i, 8, i & 0xFF)
        val = tb.read_value_le(SPI_FLASH_BASE + i, 8)
        expect(val, i & 0xFF,
               "value in the GbE SPI flash program register bank")

do_test()
