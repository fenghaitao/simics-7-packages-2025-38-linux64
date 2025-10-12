# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import stest
import info_status
import m_compute_common

# Verify that info/status commands have been registered for all
# classes in this module.
info_status.check_for_info_status(['m-compute'])

# Create an instance of a compute object
for cls in ['m_compute', 'm_compute_threaded', 'm_compute_dummy', 'm_compute_threaded_dummy',]:
    dev=m_compute_common.create_m_compute(cls+'_uut', cls)[0]

    # Run info and status on each object. It is difficult to test whether
    # the output is informative, so we just check that the commands
    # complete nicely.
    for obj in [dev]:
        for cmd in ['info', 'status']:
            try:
                SIM_run_command(obj.name + '.' + cmd)
            except SimExc_General as e:
                stest.fail(cmd + ' command failed: ' + str(e))
