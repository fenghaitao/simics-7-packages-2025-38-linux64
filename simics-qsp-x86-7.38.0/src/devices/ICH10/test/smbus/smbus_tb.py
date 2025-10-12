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


# smbus_tb.py
# instantiated testbench of SMBus controller module in ICH9

import builtins
from smbus_tb_decl import *

if hasattr(builtins, "ich10_smbus_use_i2c_v2"):
    use_i2c_v2 = builtins.ich10_smbus_use_i2c_v2
else:
    use_i2c_v2 = False

if use_i2c_v2:
    print('Running test for i2c v2')
else:
    print('Running test for i2c v1')

tb = TestBench(smbus_reg_addr, use_i2c_v2)
tb.construct_slave("Smbus_Slave_Quick", quick_slave_addr, quick_slave_addr_mask, use_i2c_v2)
tb.construct_slave("Smbus_Slave_Byte", byte_slave_addr, byte_slave_addr_mask, use_i2c_v2)
tb.construct_slave("Smbus_Slave_Byte_Data", byte_data_slave_addr, byte_data_slave_addr_mask, use_i2c_v2)
tb.construct_slave("Smbus_Slave_Word_Data", word_data_slave_addr, word_data_slave_addr_mask, use_i2c_v2)
tb.construct_slave("Smbus_Slave_Process_Call", process_call_slave_addr, process_call_slave_addr_mask, use_i2c_v2)
tb.construct_slave("Smbus_Slave_Block", block_slave_addr, block_slave_addr_mask, use_i2c_v2)
tb.construct_slave("Smbus_Slave_Block_Process", block_process_slave_addr, block_process_slave_addr_mask, use_i2c_v2)
