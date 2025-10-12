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


# s-hpe-timer-comp-same.py
# test the high-precision event timer in the ICH10 when all 8 timer comparator
# registers have the same values

from hpe_timer_common import *
import random

def get_main_cnt():
    return timer.read_register("MAIN_CNT")

def clear_intr_state(timN):
    stat = timer.read_register("GINTR_STA")
    expect(stat & (1 << timN), (1 << timN))
    # clear interrupt
    timer.write_register("GINTR_STA", (1<<timN) )
    stat = timer.read_register("GINTR_STA")
    expect(stat & (1 << timN), 0)

def verify_intr_clear():
    stat = timer.read_register("GINTR_STA")
    expect(stat, 0)

timer = ICH9R_HPE_TIMER(log_level=4)
clk = timer.get_clock()

print()
print('Testing all comparators set to same value')
timer.start_timer()
for i in range (4):
    timer.set_timer_intr_conf(i, 1, 1, 0 )
for i in range (8):
    timer.set_time_count(i, 0x100 )

SIM_continue(0x100)
print('verify interrupts at count = 0x%x' % get_main_cnt())
for i in range (4):
    clear_intr_state(i)
verify_intr_clear()

SIM_continue(MAX32+1)
print('verify interrupts at count = 0x%x' % get_main_cnt())
for i in range (1,4):
    clear_intr_state(i)
verify_intr_clear()

SIM_continue(MAX32+1)
print('verify interrupts at count = 0x%x' % get_main_cnt())
for i in range (1,4):
    clear_intr_state(i)
verify_intr_clear()

timer.stop_timer()

print()
print('Testing all comparators in default state')
timer.reset()
timer.start_timer()

for i in range (4):
    timer.set_timer_intr_conf(i, 1, 1, 0 )
SIM_continue(MAX32)
print('verify interrupts at count = 0x%x' % get_main_cnt())
for i in range (1,4):
    clear_intr_state(i)
verify_intr_clear()

SIM_continue(MAX32+1)
print('verify interrupts at count = 0x%x' % get_main_cnt())
for i in range (1,4):
    clear_intr_state(i)
verify_intr_clear()

timer.stop_timer()

print()
print('Testing 64 bit timer 0 with other comparators in default state')
timer.reset()
timer.start_timer()
for i in range (0,4):
    timer.set_timer_intr_conf(i, 1, 1, 0 )
timer.set_time_count(0, 0x100000100 )

SIM_continue(MAX32)
print('verify interrupts at count = 0x%x' % get_main_cnt())
for i in range (1,4):
    clear_intr_state(i)
verify_intr_clear()

SIM_continue(0x100+1)
print('verify interrupts at count = 0x%x' % get_main_cnt())
clear_intr_state(0)
verify_intr_clear()

SIM_continue(MAX32-0x100)
print('verify interrupts at count = 0x%x' % get_main_cnt())
for i in range (1,4):
    clear_intr_state(i)
verify_intr_clear()
