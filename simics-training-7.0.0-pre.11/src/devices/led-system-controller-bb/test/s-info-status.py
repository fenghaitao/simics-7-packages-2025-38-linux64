# © 2018 Intel Corporation
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

import stest
import info_status
import dev_util
import pyobj

# Create test system - use from X import star in order to make
# all local variables in the module appear in the top-level 
# namespace in this test file
from led_system_controller_common import *

# Verify that info/status commands have been registered for all
# classes in this module.
info_status.check_for_info_status(['led_system_controller_bb'])

# Run info and status on the controller object created by the import.
for obj in [controller]:
    for cmd in ['info', 'status']:
        try:
            SIM_run_command(obj.name + '.' + cmd)
        except SimExc_General as e:
            stest.fail(cmd + ' command failed: ' + str(e))
