#  s-sampledma.py - sample Python code for a Simics test

# © 2011 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


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
dma = simics.pre_conf_object('mydma', 'sample_dma_device_cpp')
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

def write_scatter_block(start_addr, indata, extension):
    addr = start_addr
    junk = [0xba]
    for data in indata:
        write_addr = data[0]
        write_data = junk * data[1] + data[2]
        mem.write(write_addr, write_data)
        flags = du.Bitfield_BE({"ext" : 7}, bits = 8)
        blockrow = du.Layout_BE(mem, addr, {"addr" : (0, 4),
                                            "len"  : (4, 2),
                                            "offset" : (6, 1),
                                            "flags" : (7, 1, flags)})
        blockrow.clear()
        blockrow.addr = data[0]
        blockrow.len = len(data[2])
        blockrow.offset = data[1]
        addr += 8
    if extension:
        extrow = du.Layout_BE(mem, addr, {"addr" : (0, 4),
                                          "len"  : (4, 2),
                                          "offset" : (6, 1),
                                          "flags" : (7, 1, flags)})
        extrow.clear()
        extrow.addr = extension[0]
        extrow.len = extension[2]
        extrow.offset = extension[1]
        extrow.flags.ext = 1

def setup_scatter_block(start_addr, startnr, datalen, offslen):
    ret = []
    for i in range(len(datalen)):
        (addr, offs, data) = (start_addr + i * 0x100,
                              offslen[i],
                              [(startnr + i * 10) & 0xff] * datalen[i])
        ret.append([addr, offs, data])
    return ret

def write_head_block(src_addr, block_addr, block_len, total):
    header = du.Layout_BE(mem, src_addr, { "addr"    : (0, 4),
                                           "len"     : (4, 2),
                                           "tot_len" : (6, 2)})
    header.addr = block_addr
    header.len = block_len
    header.tot_len = total

# Test with no extensionblocks
def setup_scatter_list_noext(src_addr):
    datalen = (100, 10,  5,  8, 20, 15)
    offslen = (10,   5,  1, 20,  0, 11)
    totlen = sum(datalen, 0)
    data = setup_scatter_block(0x30000, 0, datalen, offslen)
    write_scatter_block(0x20000, data, 0)
    write_head_block(src_addr, 0x20000, len(datalen) * 8, totlen)
    expdata = []
    for a in range(len(datalen)):
        expdata += data[a][2]
    return expdata

# Test where dma should get stuck in loop
def setup_scatter_loop(src_addr):
    print(" == DMA SG - Loop test")
    blockaddr = 0x20000
    dataaddr = 0x40000

    datalen = (10, 20, 30, 20, 10, 15)
    offslen = (10,   5,  1, 20,  0, 11)
    totlen = sum(datalen, 0) * 2

    ext1 = (blockaddr + 0x100, 0, 7 * 8)
    ext2 = (blockaddr, 0, 7 * 8)

    data = setup_scatter_block(dataaddr, 0, datalen, offslen)
    write_scatter_block(blockaddr, data, ext1)
    write_scatter_block(blockaddr, data, ext2)

    write_head_block(src_addr, blockaddr, (len(datalen) + 1) * 8, totlen)
    expdata = []
    for a in range(len(datalen)):
        expdata += data[a][2]
    expdata = expdata * 2
    return expdata


# Test with random values
def setup_scatter_list_rand(src_addr, seed):
    blockaddr = 0x20000
    dataaddr = 0x40000

    r.seed(seed)
    expdata = []
    blocklengths = []
    datalengths = []
    offsetlengths = []
    blockoffsets = [0]
    # Randomize sizes for blocks and data
    nr_blocks = r.randrange(1, 20)
    for i in range(nr_blocks):
        blocklengths.append(r.randrange(1, 20))
        if i > 0:
            blockoffsets.append(r.randrange(1, 20))
        dlen = []
        offslen = []
        for j in range(blocklengths[i]):
            dlen.append(r.randrange(1, 100))
            offslen.append(r.randrange(0, 20))
        datalengths.append(dlen)
        offsetlengths.append(offslen)
    count = 0

    print(" == Random SG: seed %d  %d blocks" % (seed, nr_blocks))
    print(" == Blockslengths: ", blocklengths)
    print(" == Blockoffsets : ", blockoffsets)
    # Write blocks and data
    for i in range(nr_blocks):
        data = setup_scatter_block(dataaddr, count,
                                   datalengths[i],
                                   offsetlengths[i])
        for a in range(len(datalengths[i])):
            expdata += data[a][2]
        if i < nr_blocks - 1:
            next_len = blocklengths[i + 1] * 8
            if i != nr_blocks - 2:
                next_len += 8
            ext = (blockaddr + 0x100, blockoffsets[i + 1], next_len)
        else:
            ext = 0
        write_scatter_block(blockaddr + blockoffsets[i], data, ext)
        if blockoffsets[i]: # Write junkdata
            mem.write(blockaddr, [0xba] * blockoffsets[i])
        dataaddr += 0x100 * blocklengths[i]
        blockaddr += 0x100
        count += blocklengths[i] * 10
    first_len = blocklengths[0] * 8
    if(nr_blocks > 1):
        first_len += 8
    write_head_block(src_addr, 0x20000, first_len , len(expdata))
    return expdata


def test_scatter_gather(src_addr, dst_addr, expect_data, interrupt = True,
                        looptest = False):
    data_len = len(expect_data)
    test_words = (data_len + 3) // 4
    # Configure DMA for Scatter Gather
    dma_ctrl_reg.write(0, en = 1, eci = interrupt, sg = 1)

    # Set source and destination addresses
    dma_src_reg.write(src_addr)
    dma_dst_reg.write(dst_addr)

    # set length (in words) to transfer and start transmitting
    dma_ctrl_reg.ts = test_words
    dma_ctrl_reg.swt = 1

    # TC should not be set because no time passed
    if test_words > 1:
        run_seconds((test_words - 1) * mydma.throttle)
    if looptest:
        stest.expect_equal(dma_ctrl_reg.err, 1)
        return
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

    stest.expect_equal(dma_ctrl_reg.err, 0)
    # Transferred data should match written data
    out_data = mem.read(dst_addr, data_len)
    # sum(in_data, [])
    stest.expect_equal(out_data, expect_data,
                       "Outdata does not match indata")
    if interrupt:
        # Clear TC to notify that data is read, should lower interrupt
        dma_ctrl_reg.tc = 0
        stest.expect_false(intr_dev.signal.raised)

srcaddr = 0x10000
dstaddr = 0x60000
mem.clear()
expdata = setup_scatter_list_noext(srcaddr)
# Test Scatter Gather without interrupts
test_scatter_gather(srcaddr, dstaddr, expdata, False)
# Test Scatter Gather with interrupts
test_scatter_gather(srcaddr, dstaddr, expdata, True)

mem.clear()
expdata = setup_scatter_list_rand(srcaddr, 1)
test_scatter_gather(srcaddr, dstaddr, expdata, False)

mem.clear()
expdata = setup_scatter_list_rand(srcaddr, 10)
test_scatter_gather(srcaddr, dstaddr, expdata, False)

mem.clear()
expdata = setup_scatter_list_rand(srcaddr, 0xabba)
test_scatter_gather(srcaddr, dstaddr, expdata, False)

mem.clear()
expdata = setup_scatter_loop(srcaddr)
stest.expect_log(test_scatter_gather, (srcaddr, dstaddr, expdata, False, True),
                 log_type = "spec-viol")
