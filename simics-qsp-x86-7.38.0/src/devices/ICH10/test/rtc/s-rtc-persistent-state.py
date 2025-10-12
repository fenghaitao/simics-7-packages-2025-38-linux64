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


# test RTC deterministic for bug 16860

from rtc_tb import *
import stest
import shutil

start = "2008-06-05 23:50:00"

vectors = [
           "08-06-06 00:55:00",
           "08-06-06 02:00:00",
           "08-06-06 03:05:00",
           "08-06-06 04:10:00",
           "08-06-06 05:15:00",
           "08-06-06 06:20:00",
           ]

def do_test():
    for i in range(len(vectors)):
        tb.enable_rtc(0)
        tb.rtc.time = start
        tb.enable_rtc(1)
        if i > 0:
            SIM_run_command('load-persistent-state %s'
                            % stest.scratch_file('state%d' % (i - 1)))
        # run 1 hour and 5 minutes
        SIM_continue(int(len_hour + 5 * len_min))
        expect_string(tb.rtc.time, vectors[i], 'failed load persistent state')
        state = stest.scratch_file('state%d' % i)
        shutil.rmtree(state, ignore_errors = True)
        SIM_run_command('save-persistent-state %s' % state)

do_test()
