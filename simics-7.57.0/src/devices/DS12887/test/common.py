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


# Definitions used by several subtests

import simics
import conf
import dev_util
import stest

# SIMICS-21543
conf.sim.deprecation_level = 0

class Struct:
    def __init__(self, **kws):
        for (k, v) in list(kws.items()):
            setattr(self, k, v)

# The default simple-interrupt interface class does track interrupt raise/lower
# calls, but we want to override it to get more details (e.g. timestamps)
class Pic(dev_util.SimpleInterrupt):
    def __init__(self):
        self.seq = []
        self.break_on_raise = False

    def interrupt(self, sim_obj, line):
        self.seq.append((1, line, simics.SIM_cycle_count(conf.clk)))
        if self.break_on_raise:
            simics.SIM_break_simulation(None)

    def interrupt_clear(self, sim_obj, line):
        self.seq.append((0, line, simics.SIM_cycle_count(conf.clk)))

# Clock frequency; should provide enough resolution for our test purposes
cpufreq = 1000000

def create_config():
    # Create a fake PIC that implements the simple-interrupt interface. The
    # handlers for the interface callbacks are defined in our own Pic class
    fake = dev_util.Dev([Pic])
    pic_state = fake.simple_interrupt

    # Need a clock to make time progress (any processor would do, but
    # since we are not interested in instruction execution, the clock
    # is the simplest class available
    clock = simics.pre_conf_object('clk', 'clock')
    clock.freq_mhz = cpufreq / 1000000

    ds = simics.pre_conf_object('ds', 'DS12887')
    ds.queue = clock
    ds.irq_dev = fake.obj
    ds.irq_level = 17

    simics.SIM_add_configuration([clock, ds], None)
    return (conf.ds, conf.clk, pic_state)

def ds_regs(ds):
    # DS12887 registers
    return Struct(
        sec        = dev_util.Register_LE(conf.ds.bank.registers,  0, 1),
        sec_alarm  = dev_util.Register_LE(conf.ds.bank.registers,  1, 1),
        min        = dev_util.Register_LE(conf.ds.bank.registers,  2, 1),
        min_alarm  = dev_util.Register_LE(conf.ds.bank.registers,  3, 1),
        hour       = dev_util.Register_LE(conf.ds.bank.registers,  4, 1),
        hour_alarm = dev_util.Register_LE(conf.ds.bank.registers,  5, 1),
        weekday    = dev_util.Register_LE(conf.ds.bank.registers,  6, 1),
        day        = dev_util.Register_LE(conf.ds.bank.registers,  7, 1),
        month      = dev_util.Register_LE(conf.ds.bank.registers,  8, 1),
        year       = dev_util.Register_LE(conf.ds.bank.registers,  9, 1),
        a          = dev_util.Register_LE(conf.ds.bank.registers, 10, 1),
        b          = dev_util.Register_LE(conf.ds.bank.registers, 11, 1),
        c          = dev_util.Register_LE(conf.ds.bank.registers, 12, 1),
        d          = dev_util.Register_LE(conf.ds.bank.registers, 13, 1),
        )

# Check that two values are equal, but with a tolerance allowing small
# deviations
def approx_equal(got, expected, tolerance):
    if abs(got - expected) > tolerance:
        raise stest.fail("got %r, expected %r" % (got, expected))
