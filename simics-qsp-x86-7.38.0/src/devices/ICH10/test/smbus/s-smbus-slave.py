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


# s-smbus-slave.py
# tests the slave mode of ICH9 SMBus controller module

from smbus_tb import *

tb.enable_smbus_host(1)

def do_test():
    tb.map_smbus_func(smbus_mapped_addr)

    # Write two bytes to the slave mode
    data0 = 0x88
    data1 = 0x99
    tb.configure_transfer_paras(smbus_slave_addr << 1, SmbusConst.smb_write,
                                data0, data1, 0)
    tb.start_smb_cmd(SmbusConst.cmd["byte-data"])
    simics.SIM_continue(100)

    slv_data = tb.read_io_le(smbus_mapped_addr + 0xA, 16)
    expect_hex(slv_data & 0xFF, data0,
               "data message byte 0 received by the slave interface of SMBus")
    expect_hex(slv_data >> 8, data1,
               "data message byte 1 received by the slave interface of SMBus")

    # Read one byte from the slave mode
    tb.write_io_le(smbus_mapped_addr + 0x5, 8, 0xAA)
    tb.configure_transfer_paras(smbus_slave_addr << 1, SmbusConst.smb_read,
                                0, 0, 0)
    tb.start_smb_cmd(SmbusConst.cmd["byte"])
    simics.SIM_continue(100)

    read_data = tb.read_io_le(smbus_mapped_addr + 0x5, 8)
    expect_hex(read_data, 0,
               "data message byte received from the slave interface of SMBus")
do_test()
