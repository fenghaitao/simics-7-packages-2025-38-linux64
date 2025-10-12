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


# simple test for bug 18494.
# old hpe-timer don't update pseudo register main_cnt_cur when counting
# is stopped and then restarted
from hpe_timer_common import *
import stest

timer = ICH9R_HPE_TIMER()

timer.start_timer()
SIM_continue(10000)
stest.expect_equal(timer.timer.regs_running_main_cnt, 10000)
timer.stop_timer()
stest.expect_equal(timer.timer.regs_main_cnt, 10000)
SIM_continue(10000)
timer.start_timer()
SIM_continue(10000)
stest.expect_equal(timer.timer.regs_running_main_cnt, 20000)
timer.stop_timer()
stest.expect_equal(timer.timer.regs_main_cnt, 20000)
timer.start_timer()
SIM_continue(10000)
stest.expect_equal(timer.timer.regs_running_main_cnt, 30000)
SIM_continue(10000)
stest.expect_equal(timer.timer.regs_running_main_cnt, 40000)
