# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

# Check that info and status commands work 

import stest
import info_status
import simics
import i_sync_common

# Verify that info/status commands have been registered for all
# classes in this module.
#  MODULE name, not class name! 
info_status.check_for_info_status(['i-synchronizer'])

# Create an instance of each object defined in this module
t = i_sync_common.create_test_subsystem(name="t",with_e2l=True)

# Run info and status on each object. It is difficult to test whether
# the output is informative, so we just check that the commands
# complete nicely.  
#   Note that this tests ALL the e2l objects, just to be sure
for obj in [t.dev] + list(t.e2l):
    for cmd in ['info', 'status']:
        try:
            simics.SIM_run_command(obj.name + '.' + cmd)
        except simics.SimExc_General as e:
            stest.fail(cmd + ' command failed: ' + str(e))
