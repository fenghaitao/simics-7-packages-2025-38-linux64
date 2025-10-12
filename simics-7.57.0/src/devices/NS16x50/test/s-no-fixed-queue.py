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


import common_test as c
import simics
import stest

config = c.TestConfig('NS16550')
other_clock = simics.SIM_create_object("clock", "initiator_clock",
                                       [["freq_mhz", 10]])
regs = c.UartRegs(config.uart, initiator=other_clock)

# Initial initiator is the fixed clock
stest.expect_equal(config.uart.initiator, config.clock)

# Initially no events
stest.expect_equal(config.clock.vtime.cycles.events, [])
stest.expect_equal(other_clock.vtime.cycles.events, [])

# Fixed queue used => initiator not changed
stest.expect_equal(config.uart.use_fixed_queue, True)
regs.lcr.write(0)
stest.expect_equal(config.uart.initiator, config.clock)
# Event posted on fixed clock
stest.expect_equal(config.clock.vtime.cycles.events,
                   [[config.uart, "transmit", None, None, 2]])
stest.expect_equal(other_clock.vtime.cycles.events, [])

# No fixed queue => initiator changed
config.uart.use_fixed_queue = False
regs.lcr.write(0)
stest.expect_equal(config.uart.initiator, other_clock)
stest.expect_equal(config.clock.vtime.cycles.events,
                   [[config.uart, "transmit", None, None, 2]])
# Event posted on initiator
stest.expect_equal(other_clock.vtime.cycles.events,
                   [[config.uart, "transmit", None, None, 10]])
