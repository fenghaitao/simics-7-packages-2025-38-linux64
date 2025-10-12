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


# s-smbus-checkpoint.py
# tests the checkpointing of Gigabit LAN Controller in ICH9

import os.path
import shutil
import stest
from smbus_tb_decl import *


def remove_check(check_name):
    if os.path.isdir(check_name):
        shutil.rmtree(check_name)

check_name = stest.scratch_file("smbus_checkpoint_check1")
remove_check(check_name)
tb = TestBench(smbus_reg_addr)
# Remove the checkpointing files
simics.SIM_continue(1)
# Remember an meaningful attribute
slave_addr = 1
tb.smbus.smbus_func_xmit_slva = slave_addr
simics.SIM_run_command('write-configuration %s' % check_name)
# Reset the testbench
tb.smbus.ports.HRESET.signal.signal_raise()
expect_hex(tb.smbus.smbus_func_xmit_slva, 0,
           'reset value of transmit slave address')
# Restore the checkpoint
simics.SIM_run_command('read-configuration %s %s' % (check_name, 'machine_0_'))
expect_hex(conf.machine_0_smbus.smbus_func_xmit_slva, slave_addr,
           "same transmit slave address between the original"
           "and restored checkpoint")
remove_check(check_name)
