# © 2022 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

#
# Test that we have non-crashing info and status commands
# 

import info_status
import stest
import dev_util
import pyobj
import p_control_common
import simics

classname = 'p_control'

dev =  p_control_common.create_p_control()[0]

# Verify that info/status commands have been registered for all
# classes in this module.
info_status.check_for_info_status([classname])

# Run info and status on the controller object created by the import.
for obj in [dev]:
    for cmd in ['info', 'status']:
        try:
            simics.SIM_run_command(obj.name + '.' + cmd)
        except SimExc_General as e:
            stest.fail(cmd + ' command failed: ' + str(e))

            
