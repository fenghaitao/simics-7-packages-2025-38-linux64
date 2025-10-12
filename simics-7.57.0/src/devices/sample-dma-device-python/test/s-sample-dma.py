# © 2012 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

# This test is a copy of src/devices/sample-dma-device/test/s-sampledma.py but
# without the scatter-gather part

import random as r
import dev_util as du
import stest
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

def run_seconds(s):
    steps = s * clock.freq_mhz * 1e6
    SIM_continue(int(steps))

class PidSignal(du.Signal):
    def __init__(self):
        self.raised = False
    def signal_raise(self, sim_obj):
        self.raised = True
    def signal_lower(self, sim_obj):
        self.raised = False

# Create fake Memory and Interrupt objects, these are required
mem = du.Memory()
intr_dev = du.Dev([PidSignal])

# Create clock object for timing
clock = simics.pre_conf_object('clock', 'clock')
clock.freq_mhz = 1000

# Create DMA device and connect with clock, memory and interrupt
dma = simics.pre_conf_object('mydma', 'sample_dma_device_python')
dma.target_mem = mem.obj
dma.intr_target = intr_dev.obj
dma.queue = clock

# Create the configuration
simics.SIM_add_configuration([clock, dma], None)
mydma = conf.mydma

dma_src_reg = du.Register_BE(mydma.bank.regs, 4, 4)
dma_dst_reg = du.Register_BE(mydma.bank.regs, 8, 4)
dma_ctrl_reg = du.Register_BE(mydma.bank.regs, 0, 4, du.Bitfield({'en': 31,
                                                                  'swt': 30,
                                                                  'eci': 29,
                                                                  'tc': 28,
                                                                  'sg': 27,
                                                                  'err': 26,
                                                                  'ts': (15,0)}))

def dma_transfer_test(in_data, interrupt = False):
    pad = (4 - len(in_data) % 4) % 4
    # mem.write wants data as a tuple. (always a multiple of 4)
    test_data = tuple(list(ord(c) for c in in_data) + [0]*pad)
    test_words = len(test_data) // 4
    mem.write(0x20000, test_data)

    # Set control register to enable dma and enable/disable interrupts
    dma_ctrl_reg.write(0, en = 1, eci = interrupt)

    # Load source and target addresses and transfer size
    dma_src_reg.write(0x20000)
    dma_dst_reg.write(0x30000)
    dma_ctrl_reg.ts = test_words

    # Initiate transfer and check result
    dma_ctrl_reg.swt = 1
    # TC should not be set because no time passed
    stest.expect_equal(dma_ctrl_reg.tc, 0)

    # Nothing should happen because not enough time has passed
    if test_words > 1:
        run_seconds((test_words - 1) * mydma.throttle)
    stest.expect_equal(dma_ctrl_reg.tc, 0)
    stest.expect_equal(intr_dev.signal.raised, False)
    # Run forward until transfer should complete
    run_seconds(1.01 * mydma.throttle)
    if interrupt:
        stest.expect_equal(intr_dev.signal.raised, True)
    else:
        stest.expect_equal(intr_dev.signal.raised, False)

    # TC should be set if transfer is complete
    stest.expect_equal(dma_ctrl_reg.tc, 1)

    # Transferred data should match written data
    out_data = tuple(mem.read(0x30000, test_words * 4))
    stest.expect_equal(out_data, test_data, "Outdata does not match indata")

    if interrupt:
        # Clear TC to notify that data is read, should lower interrupt
        dma_ctrl_reg.tc = 0
        stest.expect_false(intr_dev.signal.raised)

for length in (0, 1, 4, 10, 30, 50, 121):
    in_data = ""
    for i in range(length):
        in_data += chr(ord('a') + (i % (ord('z') - ord('a') + 1) ))
        # Test without interrupts
        dma_transfer_test(in_data, False)
        # Test with interrupts
        dma_transfer_test(in_data, True)
