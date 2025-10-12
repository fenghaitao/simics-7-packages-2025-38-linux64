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


# setup: a 16-bit AMD CFI compatible flash on a 16-bit bus
#        belonging to the S29GL-P MirrorBit Flash Family that
#        can do repeated sector erases. (bug 16419)
#
# From datasheet: Software Functions and Sample Code
#                   Table 7.8 Sector Erase
#         (LLD Function = lld_SectorEraseCmd)
# Cycle      Description   Operation Byte Address   Word Address   Data
#   1           Unlock        Write  Base + AAAh    Base + 555h    00AAh
#   2           Unlock        Write  Base + 555h    Base + 2AAh    0055h
#   3      Setup Command      Write  Base + AAAh    Base + 555h    0080h
#   4           Unlock        Write  Base + AAAh    Base + 555h    00AAh
#   5           Unlock        Write  Base + 555h    Base + 2AAh    0055h
#   6  Sector Erase Command   Write  Sector Address Sector Address 0030h
# Unlimited additional sectors may be selected for erase; command(s) must
# be written within 50 µs.

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("S29GL256N", 1, 16)

# need a clock to be able to test timing
SIM_create_object("clock", "clock", freq_mhz=1)
conf.flash.queue = conf.clock
conf.flash.timing_model['AMD Erase In Progress'] = 50e-6

conf.flash_ram.queue = conf.clock

secsize = 128*1024

fill(1 * secsize - 1, 1 * secsize + 1, 0xaa)
fill(2 * secsize - 1, 2 * secsize + 1, 0xbb)
fill(3 * secsize - 1, 3 * secsize + 1, 0xcc)

expect_hex("sector erase 1", get8(1 * secsize - 1), 0xaa)
expect_hex("sector erase 2", get8(1 * secsize + 0), 0xaa)
expect_hex("sector erase 3", get8(2 * secsize - 1), 0xbb)
expect_hex("sector erase 4", get8(2 * secsize + 0), 0xbb)
expect_hex("sector erase 5", get8(3 * secsize - 1), 0xcc)
expect_hex("sector erase 6", get8(3 * secsize + 0), 0xcc)

run_command("log-level 4")

# autoselect at correct address
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0x80)
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)

set16(1 * secsize, 0x30)
SIM_continue(40) # start repeated write within 50 µs
set16(3 * secsize, 0x30)
SIM_continue(60) # let the erase finish by waiting more than 50 µs

expect_hex("sector erase 1", get8(1 * secsize - 1), 0xaa)
expect_hex("sector erase 2", get8(1 * secsize + 0), 0xff)
expect_hex("sector erase 3", get8(2 * secsize - 1), 0xff)
expect_hex("sector erase 4", get8(2 * secsize + 0), 0xbb)
expect_hex("sector erase 5", get8(3 * secsize - 1), 0xcc)
expect_hex("sector erase 6", get8(3 * secsize + 0), 0xff)
