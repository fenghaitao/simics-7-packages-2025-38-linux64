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


# s-smbus-quick.py
# tests the quick transfer command of ICH9 SMBus controller module

from smbus_tb import *

tb.enable_smbus_host(1)

def do_test():
    tb.map_smbus_func(smbus_mapped_addr)
    # Set the slave address and the write
    tb.configure_transfer_paras(quick_slave_addr, SmbusConst.smb_write, 0, 0, 0)
    # Set and start the smb command
    tb.slaves[quick_slave_addr].caps_lock = 1
    tb.start_smb_cmd(SmbusConst.cmd["quick"])
    # Check the slave has toggled its capital lock state
    simics.SIM_continue(100)
    expect(tb.slaves[quick_slave_addr].caps_lock, 0,
            "the capital lock state toggled in quick SMBus slave device")
    expect(tb.slaves[quick_slave_addr].stop_called, 1,
           "the count of stop called by the i2c link")
    expect(tb.slaves[quick_slave_addr].stop_condition, [0],
            "the conditions of stops called by the i2c link")

    # Set the slave address and the read
    tb.configure_transfer_paras(quick_slave_addr, SmbusConst.smb_read, 0, 0, 0)
    # Set and start the smb command
    tb.slaves[quick_slave_addr].num_lock = 1
    tb.start_smb_cmd(SmbusConst.cmd["quick"])
    # Check the slave has toggled its number lock state
    simics.SIM_continue(100)
    expect(tb.slaves[quick_slave_addr].num_lock, 0,
            "the number lock state toggled in quick SMBus slave device")
    expect(tb.slaves[quick_slave_addr].stop_called, 2,
            "the count of stop called by the i2c link")
    expect(tb.slaves[quick_slave_addr].stop_condition, [0, 0],
            "the conditions of stops called by the i2c link")

do_test()
