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


# Test the DS12887 periodic interrupt functions.

from common import *
from stest import expect_equal

(ds, clk, pic_state) = create_config()
regs = ds_regs(ds)

def test_periodic():
    print("Testing periodic interrupts")

    # Instead of letting the pic record when interrupts occur, we let it
    # stop the simulation instead
    pic_state.break_on_raise = True

    # Test all legal combinations of the rate bits
    for rs in range(3, 16):
        freq = 1 << (16 - rs)           # frequency in Hz
        print("Testing rs=%d (%d Hz)" % (rs, freq))

        regs.a.write(0)             # turn off oscillator
        regs.b.write(0x40)          # enable periodic interrupts
        regs.a.write(rs | 0x20)     # set rate and turn on oscillator
        regs.c.read()               # reset interrupts by reading reg C

        # Run until the first interrupt edge
        SIM_continue(cpufreq * 2 // freq)

        c0 = SIM_cycle_count(clk)
        # Let one cycle pass so we don't confuse the device by resetting the
        # interrupt when it has just been raised
        SIM_continue(1)
        rc = regs.c.read()
        expect_equal(rc & 0xc0, 0xc0)     # we expect IRQF | PF

        # run until the next edge
        SIM_continue(cpufreq * 2 // freq)

        c1 = SIM_cycle_count(clk)
        SIM_continue(1)
        rc = regs.c.read()
        expect_equal(rc & 0xc0, 0xc0)     # we expect IRQF | PF

        # The exact period may vary a cycle because of round-off errors
        period = c1 - c0
        expected_period = cpufreq / freq
        approx_equal(period, expected_period, 1)

test_periodic()
