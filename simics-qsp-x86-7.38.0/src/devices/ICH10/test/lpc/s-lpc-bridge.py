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


# s-lpc-bridge.py
# test the bridge function between PCI and LPC bus
# of the LPC module in the ICH10 chip

from lpc_tb import *

# IO cycles decoding test
def do_test(dev_idx):
    # Connect the device to the LPC bridge
    tb.lpc_io.map += [[lpc_dev_io_base[dev_idx],
                      [tb.lpc_dev[dev_idx], 'io_func'], 0, 0, 0x100]]

    # Configure the IO range base and mask
    tb.write_conf_le(lpc_reg_addr + 0x84 + dev_idx * 4, 32,
                     lpc_dev_io_base[dev_idx] + 1)
    # Read/write the IO regs in the LPC device
    reg_val = 0xFFFFFFFF
    tb.write_io_le(lpc_dev_io_base[dev_idx], 32, reg_val)
    real_val = tb.read_io_le(lpc_dev_io_base[dev_idx], 32)
    expect_hex(real_val, reg_val,
        "value written to the LPC device %d control register" % dev_idx)

# Memory cycles decoding test
def ich10_corporate_test():
    lpc_mem_addr = 0x87560000
    tb.write_conf_le(lpc_reg_addr + 0x98, 32, lpc_mem_addr | 1)
    for offset in (0, 0x1000, 0x5678, 0xfffc):
        addr = lpc_mem_addr | offset
        tb.write_value_le(addr, 32, addr)
        expect_hex(
            tb.read_value_le(addr, 32), addr, 'LPC memory cycles read/write')
    tb.write_conf_le(lpc_reg_addr + 0x98, 32, lpc_mem_addr)

# Be careful to modify following codes,
# for it's fixed in LPC bridge that every LPC device uses the GEN_DEC register
# of its device id, that means the No 0 test device must be allocated to the
# device id of 0, 1 to 1, 2 to 2, etc.
do_test(0)
do_test(1)
do_test(2)
do_test(3)

ich10_corporate_test()
