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


# s-smbus-byte.py
# tests the byte transfer command of ICH9 SMBus controller module

from smbus_tb import *

tb.enable_smbus_host(1)

def do_test():
    tb.map_smbus_func(smbus_mapped_addr)
    cmd_data = 0x88
    # Set the slave address and the write
    tb.configure_transfer_paras(byte_slave_addr, SmbusConst.smb_write, 0, cmd_data, 0)
    # Set and start the smb command
    slave = tb.slaves[byte_slave_addr]
    slave.caps_lock = 1
    tb.start_smb_cmd(SmbusConst.cmd["byte"])
    # Check the slave has toggled its capital lock state
    simics.SIM_continue(100)
    expect(slave.caps_lock, 0,
            "the capital lock state toggled in the byte SMBus slave device")
    expect(slave.cmd_data, 0,
            "the command data written into the byte SMBus slave device")
    expect(slave.stop_called, 1,
           "the count of stop called by the i2c link")
    expect(slave.stop_condition, [0],
            "the conditions of stops called by the i2c link")

    cmd_data = 98
    slave.cmd_data = cmd_data
    # Set the slave address and the read
    tb.configure_transfer_paras(byte_slave_addr, SmbusConst.smb_read, 0, 0, 0)
    # Set and start the smb command
    slave.num_lock = 1
    tb.start_smb_cmd(SmbusConst.cmd["byte"])
    # Check the slave has toggled its number lock state
    simics.SIM_continue(100)
    expect(slave.num_lock, 0,
            "the number lock state toggled in the byte SMBus slave device")
    reg_val = tb.read_io_le(tb.smbus_func_mapped_addr + 0x5, 8)
    expect(reg_val, cmd_data,
            "the command data read from the byte SMBus slave device")
    expect(slave.stop_called, 2,
            "the count of stop called by the i2c link")
    expect(slave.stop_condition, [0, 0],
            "the conditions of stops called by the i2c link")

do_test()
