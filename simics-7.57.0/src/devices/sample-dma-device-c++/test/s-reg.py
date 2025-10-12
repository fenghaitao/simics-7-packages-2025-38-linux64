# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import dev_util as du
import stest

import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

stest.untrap_log("spec-viol")

# Create fake Memory and Interrupt objects, these are required
mem = du.Memory()
intr_dev = du.Dev([du.Signal])

# Create DMA device and connect with clock, memory and interrupt
dma = simics.pre_conf_object('mydma', 'sample_dma_device_cpp')
dma.target_mem = mem.obj
dma.intr_target = intr_dev.obj

# Create the configuration
simics.SIM_add_configuration([dma], None)
mydma = conf.mydma

dma_src_reg = du.Register_BE(mydma.bank.regs, 4, 4)
dma_dst_reg = du.Register_BE(mydma.bank.regs, 8, 4)
dma_ctrl_reg = du.Register_BE(mydma.bank.regs, 0, 4,
                              du.Bitfield({'en': 31,
                                           'swt': 30,
                                           'eci': 29,
                                           'tc': 28,
                                           'sg': 27,
                                           'err': 26,
                                           'ts': (15,0)}))
cli.run_command("log-level 4")

# Test read/write register without fields
stest.expect_equal(dma_src_reg.read(), 0)
dma_src_reg.write(0x12345678)
stest.expect_equal(dma_src_reg.read(), 0x12345678)

# Test read/write register with fields
stest.expect_equal(dma_ctrl_reg.read(), 0)
dma_ctrl_reg.write(0x00c0ffee)
# bits unmapped read back 0
stest.expect_equal(dma_ctrl_reg.read(), 0xffee)

# Test read partial register
dma_src_first_2bytes = du.Register(mydma.bank.regs, 4, 2)
stest.expect_equal(dma_src_first_2bytes.read(), 0x7856)
dma_src_last_byte = du.Register(mydma.bank.regs, 7, 1)
stest.expect_equal(dma_src_last_byte.read(), 0x12)

# Test write partial register
dma_src_first_2bytes.write(0x1111)
stest.expect_equal(dma_src_first_2bytes.read(), 0x1111)
dma_src_last_byte.write(0x22)
stest.expect_equal(dma_src_last_byte.read(), 0x22)

# Test read/write unmapped bytes
dma_unmapped = du.Register(mydma.bank.regs, 12, 4)
with stest.expect_exception_mgr(du.MemoryError):
    dma_unmapped.read()
with stest.expect_exception_mgr(du.MemoryError):
    dma_unmapped.write(0)

# Test read/write partial unmapped bytes
dma_partial_unmapped = du.Register(mydma.bank.regs, 10, 4)
with stest.expect_exception_mgr(du.MemoryError):
    dma_partial_unmapped.read()
with stest.expect_exception_mgr(du.MemoryError):
    dma_partial_unmapped.write(0)

# Test read/write overlapped registers
dma_src_dst_reg = du.Register(mydma.bank.regs, 4, 8)
dma_src_dst_reg.write(0x0102030405060708)
stest.expect_equal(dma_src_dst_reg.read(), 0x0102030405060708)

# Test read/write unaligned & overlapped registers
dma_unaligned_src_dst = du.Register(mydma.bank.regs, 6, 6)
dma_unaligned_src_dst.write(0x060504030201)
stest.expect_equal(dma_unaligned_src_dst.read(), 0x060504030201)

# Test larger than 8 bytes access
dma_big = du.Register_BE(mydma.bank.regs, 0, 12)
stest.expect_equal(dma_big.read(),
                   dma_ctrl_reg.read() << 64 | dma_src_reg.read() << 32
                   | dma_dst_reg.read())

# Test access from memory space
ms = SIM_create_object('memory-space', 'ms', [])
ms.map = [
    [0x1000, mydma.bank.regs, 0, 0, 0x1000, None, 0, 16, 0],
]

t = transaction_t(size = 12, read = True)
ms.iface.transaction.issue(t, 0x1000)
stest.expect_equal(t.data, dma_big.read().to_bytes(12, "big"))
