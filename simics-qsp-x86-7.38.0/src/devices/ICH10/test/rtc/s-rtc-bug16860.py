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

def do_test():
    init_time = [0, 0, 0, 5, 1, 1, 0] # 2000-1-1, Saturday

    tb.enable_rtc(0)
    # Set the initial time of RTC
    tb.set_rtc(init_time)
    # Enable the RTC
    tb.enable_rtc(1)

    delta = 0
    for sec in [10.5, 0.5, 12.5, 21.5, 14, 100, 3650.5, 6400.5]:
        delta += sec
        SIM_continue(int(len_sec * sec))
        expect_string(tb.rtc.time,
                      '00-01-01 %02d:%02d:%02d' % (delta/3600,
                                                   (delta/60) % 60,
                                                   int(delta) % 60),
                      'real time after run %f seconds' % delta)

do_test()
