# © 2015 Intel Corporation
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

# Load testing modules
SIM_load_module('sample-signal-device')
# signal-link need a clock for instantiation
SIM_create_object("clock", "clock0", freq_mhz=1)
SIM_load_module('signal-link')

# Create and instantiate components
run_command('create-sample-signal-device signal_sender_dev')
run_command('create-sample-signal-device signal_receiver_dev')
run_command('create-signal-link link0')
run_command('create-cell-and-clocks-comp cc0')
run_command('instantiate-components')

# Connection testing
run_command('connect signal_sender_dev.clock cc0.clock[0]')
run_command('connect signal_sender_dev.out link0.sender0')
run_command('connect signal_receiver_dev.in link0.receiver0')

run_command('disconnect signal_sender_dev.clock cc0.clock[0]')
run_command('disconnect signal_sender_dev.out link0.sender0')
run_command('disconnect signal_receiver_dev.in link0.receiver0')

# Attributes testing
signal_sender_comp = conf.signal_sender_dev
signal_sender_dev = conf.signal_sender_dev.dev

stest.expect_equal(signal_sender_comp.attr.period, 0.1)
stest.expect_equal(signal_sender_dev.attr.period, 0.1)
signal_sender_comp.attr.period = 1.9
stest.expect_equal(signal_sender_comp.attr.period, 1.9)
stest.expect_equal(signal_sender_dev.attr.period, 1.9)

stest.expect_equal(signal_sender_comp.attr.count, 10)
stest.expect_equal(signal_sender_dev.attr.count, 10)
signal_sender_comp.attr.count = 37
stest.expect_equal(signal_sender_comp.attr.count, 37)
stest.expect_equal(signal_sender_dev.attr.count, 37)
