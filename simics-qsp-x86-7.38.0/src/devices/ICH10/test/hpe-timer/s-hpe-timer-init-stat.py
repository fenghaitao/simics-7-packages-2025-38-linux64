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


# s-hpe-timer-init-stat.py
# test initial status of the high-precision event timer in the ICH9

from hpe_timer_common import *

def test32BitMode():
    for i in [0, 1, 2, 3]:
        timer.set_32bit_mode(i, 1)

    for i in [0, 1, 2, 3]:
        regname = ("TIM%d_COMP" % i)
        cmp = timer.read_register(regname)
        expect(cmp, MAX32)

def test64BitMode():
    regname = ("TIM%d_COMP" % 0)
    cmp = timer.read_register(regname)
    expect(cmp, MAX64)
    for i in [1, 2, 3]:
        regname = ("TIM%d_COMP" % i)
        cmp = timer.read_register(regname)
        expect(cmp, MAX32)

timer = ICH9R_HPE_TIMER()

test32BitMode()

for i in [0, 1, 2, 3]:
    regname = ("TIM%d_COMP" % i)
    timer.write_register(regname, 0x100 * i)

timer.reset("SRESET")
test64BitMode()
