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


# s-lan-eeprom.py
# tests the EEPROM reading by bit banging the EEC register

from tb_lan import *

tb.lan.log_level = 1

# Verify that the EEC.Auto_RD bit is set by default.
expect(tb.read_reg('EEC') & 0x200, 0x200, "EEC.Auto_RD not set")

def request_eeprom():
    tb.write_reg('EEC', 0x40)
    expect(tb.read_reg('EEC') & 0x80, 0x80, "EEPROM access not granted")

def release_eeprom():
    tb.write_reg('EEC', 0x00)
    expect(tb.read_reg('EEC') & 0x80, 0x00, "EEPROM access not granted")

def xfer_byte(byte):
    eecd = tb.read_reg('EEC')

    dataout = 0
    for mask in [128,64,32,16,8,4,2,1]:
        if (byte & mask) != 0:
            eecd |= (1 << 2)
        else:
            eecd &= ~(1 << 2)

        # Write data
        tb.write_reg('EEC', eecd)
        # Raise clock
        tb.write_reg('EEC', eecd | (1 << 0))

        x = tb.read_reg('EEC')
        if x & (1 << 3):
            dataout |= mask
        else:
            dataout &= ~mask

        # Lower clock
        tb.write_reg('EEC', eecd)

    return dataout

def xfer_bytes(bytes):
    outbytes = []

    for b in bytes:
        outbytes.append(xfer_byte(b))
    return outbytes

def read_bytes(addr, num_bytes):
    request_eeprom()
    _ = xfer_bytes([0x03, addr])
    bytes = xfer_bytes([0]*num_bytes)
    release_eeprom()
    return bytes


def do_test():
    lan_drv.reset_mac()

    mac_address = [0x01, 0x23, 0x45, 0x67, 0x89, 0xab]

    # Set the mac address. It will also be written to the EEPROM.
    tb.lan.mac_address = ":".join(["%02x" % (i) for i in mac_address])

    # Read MAC address from EEPROM
    eeprom_mac_address = read_bytes(0, 6)
    expect_list(eeprom_mac_address, mac_address, "MAC address mismatch")

    # Read it again
    eeprom_mac_address = read_bytes(0, 6)
    expect_list(eeprom_mac_address, mac_address, "MAC address mismatch")

do_test()
