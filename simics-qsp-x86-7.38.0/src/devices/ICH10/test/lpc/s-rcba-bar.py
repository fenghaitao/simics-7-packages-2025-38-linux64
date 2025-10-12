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


# Test that the RCBA register maps both the chipset config bank
# (lpc function 10) and the spi flash bank (bug #22182).


import dev_util
import simics
from lpc_tb import *
import stest

CONFIG_RCBA                     = 0xf0

RCBA_BASE                       = 0xfd730000
SPI_FLASH_BASE                  = RCBA_BASE + 0x3800

CHIPSET_CONFIG_FUNCTION         = 10
# map RCRB (root complex register block) by setting RCBA
rcba = dev_util.Register_LE(tb.lpc.bank.pci_config, CONFIG_RCBA, 4)
rcba.write(RCBA_BASE)

lpc_map = [m for m in conf.mem.map if m[0] == RCBA_BASE]
spi_map = [m for m in conf.mem.map if m[0] == SPI_FLASH_BASE]

stest.expect_equal(
    lpc_map,
    [[RCBA_BASE, conf.lpc.bank.cs_conf, 0, 0, 0x3800, None, 0, 8, 0]])

stest.expect_equal(
    spi_map,
    [[SPI_FLASH_BASE, conf.spi.bank.spi_regs, 0, 0, 0x800, None, 0, 8, 0]])

# unmap
rcba.write(0)

lpc_map = [m for m in conf.mem.map if m[0] == RCBA_BASE]
spi_map = [m for m in conf.mem.map if m[0] == SPI_FLASH_BASE]

stest.expect_equal(lpc_map, [])
stest.expect_equal(spi_map, [])
