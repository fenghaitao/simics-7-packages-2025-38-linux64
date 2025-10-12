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


# s-lan-checkpoint.py
# tests the checkpointing of Gigabit LAN Controller in ICH9

import os.path
import shutil
from tb_lan import *
import cli
import simics
import stest

stest.untrap_log("unimpl")
stest.untrap_log("spec-viol")

def remove_check(check_name):
    if os.path.isdir(check_name):
        shutil.rmtree(check_name)

check_name = stest.scratch_file("lan_checkpoint_check1")
# Remove the checkpointing files
remove_check(check_name)
# Run a test file
cli.run_command('run-script s-lan-tx-legacy-td.py')
# Remember an meaningful attribute
tx_desc_addr = tb.lan.csr_tx_queue_tdbal[0]
if tx_desc_addr == 0:
    raise Exception('tx queue desc addr: got %d, expected a non-zero value' % seg_idx)
# Do the checkpointing
cli.run_command('write-configuration %s' % check_name)
# Reset the testbench
tb.lan.ports.HRESET.signal.signal_raise()

if tb.lan.csr_tx_queue_tdbal[0] != 0:
    raise Exception('reset tx queue desc addr: got %d, expected a zero'
                    % val)
# Restore the checkpoint
cli.run_command('read-configuration %s %s' % (check_name, 'machine_0_'))
expect_hex(conf.machine_0_lan.csr_tx_queue_tdbal[0], tx_desc_addr,
           'same tx queue desc addr between the original and restored checkpoint')

# Cleanup: delete the checkpoint to save disk space. NB: on Windows we cannot
# delete image files from the checkpoint while they are referenced
# by the objects. So we delete all objects first.
simics.SIM_delete_objects(list(simics.SIM_object_iterator(None)))
remove_check(check_name)
