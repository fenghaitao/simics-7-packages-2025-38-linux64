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


# s-smbus-block-process-call.py
# tests the block process call command of ICH9 SMBus controller module

from smbus_tb import *

tb.enable_smbus_host(1)

def do_test():
    cmd_code = 0x66
    wr_byte_cnt = 20
    wr_block_data = [ 1, 3, 5, 7, 11,
                   13, 17, 19, 23, 29,
                   31, 37, 41, 43, 47,
                   53, 59, 61, 67, 71 ]

    rd_byte_cnt = 13
    rd_block_data = [ 2, 4, 6, 10, 16,
                      26, 42, 68, 110, 178,
                      68, 42, 26]

    slave = tb.slaves[block_process_slave_addr]
    slave.caps_lock = 1
    slave.num_lock = 1
    slave.cmd_code = ~cmd_code
    slave.byte_cnt = 0
    slave.block_data = []
    slave.rd_byte_cnt = rd_byte_cnt
    slave.rd_block_data = rd_block_data

    tb.map_smbus_func(smbus_mapped_addr)
    # Set the slave address and the write
    tb.configure_block_paras(block_process_slave_addr, SmbusConst.smb_write,
                                cmd_code, wr_byte_cnt, wr_block_data)
    # Set and start the smb command
    tb.start_smb_cmd(SmbusConst.cmd["block-process"])

    # Check the slave has toggled its capital lock state
    simics.SIM_continue(100)
    expect(slave.caps_lock, 0,
            "the capital lock state toggled in the block process call SMBus slave device")
    expect(slave.num_lock, 0,
            "the number lock state toggled in the block process call SMBus slave device")
    expect(slave.cmd_code, cmd_code,
            "the command code written into the block process call SMBus slave device")
    expect(slave.byte_cnt, wr_byte_cnt,
            "the byte count written into the block process call SMBus slave device")
    expect_list(slave.block_data, wr_block_data,
            "the block data array written into the block process call SMBus slave device")
    (real_cnt, real_data) = tb.read_block_data()
    expect_cnt = rd_byte_cnt
    expect_data = rd_block_data
    if rd_byte_cnt + wr_byte_cnt > 32:
        expect_cnt = 32 - wr_byte_cnt
        expect_data = rd_block_data[0:expect_cnt]
    expect(real_cnt, expect_cnt,
            "the byte count read from the block process call SMBus slave device")
    expect(real_data, expect_data,
            "the block data array read from the block process call SMBus slave device")
    expect(slave.stop_called, 2,
           "the count of stop called by the i2c link")
    expect(slave.stop_condition, [0, 0],
            "the conditions of stops called by the i2c link")

do_test()
